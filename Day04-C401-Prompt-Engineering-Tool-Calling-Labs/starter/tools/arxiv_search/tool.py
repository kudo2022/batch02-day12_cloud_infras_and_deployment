from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

import requests

from tools._shared import TIMEOUT, err, fold_text, terms


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_RSS_URL = "https://rss.arxiv.org/rss/{category}"
ARXIV_MIN_INTERVAL_SECONDS = 3.0
RSS_DEFAULT_CATEGORIES: tuple[str, ...] = ("cs.AI", "cs.LG", "cs.CL")
QUERY_NOISE_TERMS = {"arxiv", "latest", "new", "newest", "paper", "papers", "preprint", "preprints", "recent"}
BROAD_QUERY_PHRASES = {
    "ai",
    "artificial intelligence",
    "quantum",
    "quantum physics",
    "ml",
    "machine learning",
    "deep learning",
    "llm",
    "llms",
    "language model",
    "language models",
    "nlp",
    "natural language processing",
    "computer vision",
    "robotics",
}
BROAD_CATEGORY_QUERIES = {
    "ai": "cat:cs.AI",
    "artificial intelligence": "cat:cs.AI",
    "quantum": "cat:quant-ph",
    "quantum physics": "cat:quant-ph",
    "ml": "cat:cs.LG OR cat:stat.ML",
    "machine learning": "cat:cs.LG OR cat:stat.ML",
    "deep learning": "cat:cs.LG OR cat:stat.ML",
    "llm": "cat:cs.CL OR cat:cs.AI",
    "llms": "cat:cs.CL OR cat:cs.AI",
    "language model": "cat:cs.CL OR cat:cs.AI",
    "language models": "cat:cs.CL OR cat:cs.AI",
    "nlp": "cat:cs.CL",
    "natural language processing": "cat:cs.CL",
    "computer vision": "cat:cs.CV",
    "robotics": "cat:cs.RO",
}
RSS_HINTS: tuple[tuple[set[str], tuple[str, ...]], ...] = (
    ({"ai", "artificial", "intelligence", "agent", "agents", "reasoning", "planning"}, ("cs.AI", "cs.LG", "cs.CL")),
    ({"quantum", "qubit", "qubits"}, ("quant-ph",)),
    ({"ml", "machine", "learning", "deep", "neural", "transformer"}, ("cs.LG", "stat.ML", "cs.AI")),
    ({"llm", "llms", "language", "languages", "nlp", "prompt", "prompts", "dialogue", "summarization"}, ("cs.CL", "cs.AI", "cs.LG")),
    ({"retrieval", "rag", "search", "ranking", "recommender", "recommendation", "information"}, ("cs.IR", "cs.CL", "cs.AI")),
    ({"vision", "image", "images", "video", "multimodal"}, ("cs.CV", "cs.AI")),
    ({"robot", "robots", "robotic", "robotics", "embodied"}, ("cs.RO", "cs.AI")),
    ({"speech", "audio", "asr", "tts"}, ("eess.AS", "cs.SD", "cs.CL")),
)
_last_arxiv_request_at = 0.0


def _arxiv_user_agent() -> str:
    return os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (educational lab; contact: local)")


def _rate_limit_arxiv() -> None:
    global _last_arxiv_request_at
    elapsed = time.monotonic() - _last_arxiv_request_at
    if elapsed < ARXIV_MIN_INTERVAL_SECONDS:
        time.sleep(ARXIV_MIN_INTERVAL_SECONDS - elapsed)
    _last_arxiv_request_at = time.monotonic()


def _arxiv_get(url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    last_response: requests.Response | None = None
    for attempt in range(3):
        _rate_limit_arxiv()
        response = requests.get(url, params=params, headers={"User-Agent": _arxiv_user_agent()}, timeout=TIMEOUT)
        last_response = response
        if response.status_code != 429:
            return response
        time.sleep(3 * (attempt + 1))
    assert last_response is not None
    return last_response


def _arxiv_search_query(query: str) -> str:
    cleaned = " ".join((query or "").split())
    normalized = fold_text(cleaned)
    if normalized in BROAD_CATEGORY_QUERIES:
        return BROAD_CATEGORY_QUERIES[normalized]
    if ":" in cleaned:
        return cleaned
    query_terms = [term for term in re.findall(r"[A-Za-z0-9_\\-]+", cleaned) if len(term) > 1]
    return " AND ".join(f"all:{term}" for term in query_terms[:8]) or cleaned


def _arxiv_id(value: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", value or "")
    return match.group(1) if match else ""


def _strip_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id or "")


def _entry_text(entry: ET.Element, path: str, namespaces: dict[str, str]) -> str:
    node = entry.find(path, namespaces)
    return (node.text or "").strip() if node is not None and node.text else ""


def _query_terms(query: str) -> set[str]:
    return {term for term in terms(query) if term not in QUERY_NOISE_TERMS}


def _is_broad_topic_query(query: str, query_terms: set[str]) -> bool:
    normalized_query = fold_text(" ".join((query or "").split()))
    if normalized_query in BROAD_QUERY_PHRASES:
        return True

    broad_term_sets = (
        {"ai"},
        {"artificial", "intelligence"},
        {"quantum"},
        {"ml"},
        {"machine", "learning"},
        {"deep", "learning"},
        {"llm"},
        {"llms"},
        {"nlp"},
        {"computer", "vision"},
        {"robotics"},
    )
    return any(query_terms == broad_terms for broad_terms in broad_term_sets)


def _rss_categories_for_query(query: str) -> tuple[list[str], bool]:
    query_terms = _query_terms(query)
    normalized_query = fold_text(" ".join((query or "").split()))
    categories: list[str] = []
    matched = False

    for keywords, hinted_categories in RSS_HINTS:
        if query_terms.intersection(keywords) or any(keyword in normalized_query for keyword in keywords if " " in keyword):
            matched = True
            for category in hinted_categories:
                if category not in categories:
                    categories.append(category)

    if not categories:
        categories = list(RSS_DEFAULT_CATEGORIES)

    return categories, matched


def _rss_text(node: ET.Element | None) -> str:
    return unescape((node.text or "").strip()) if node is not None and node.text else ""


def _rss_iso_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _rss_summary(description: str) -> tuple[str, str]:
    match = re.search(r"arXiv:(\S+)\s+Announce Type:\s+\S+\s+Abstract:\s*(.*)", description or "", flags=re.S)
    if not match:
        return "", " ".join((description or "").split())
    return _strip_version(match.group(1)), " ".join(match.group(2).split())


def _rss_pdf_url(arxiv_id: str, abs_url: str) -> str:
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    if "/abs/" in abs_url:
        return abs_url.replace("/abs/", "/pdf/") + ".pdf"
    return ""


def _rss_item_score(item: dict[str, Any], query: str, query_terms: set[str]) -> int:
    if not query_terms:
        return 0

    normalized_query = fold_text(" ".join((query or "").split()))
    title_text = fold_text(item.get("title", ""))
    body_text = fold_text(" ".join([item.get("title", ""), item.get("summary", ""), " ".join(item.get("categories") or [])]))

    exact_phrase_bonus = 40 if normalized_query and len(normalized_query) >= 4 and normalized_query in body_text else 0
    title_hits = sum(1 for term in query_terms if term in title_text)
    body_hits = sum(1 for term in query_terms if term in body_text)
    return exact_phrase_bonus + (title_hits * 8) + (body_hits * 3)


def _rss_entry_to_item(entry: ET.Element, fallback_category: str) -> dict[str, Any]:
    namespaces = {"dc": "http://purl.org/dc/elements/1.1/"}
    title = _rss_text(entry.find("./title"))
    url = _rss_text(entry.find("./link"))
    description = _rss_text(entry.find("./description"))
    arxiv_id, summary = _rss_summary(description)
    authors_text = _rss_text(entry.find("./dc:creator", namespaces))
    authors = [author.strip() for author in authors_text.split(",") if author.strip()]
    categories = [_rss_text(node) for node in entry.findall("./category") if _rss_text(node)]
    published = _rss_iso_datetime(_rss_text(entry.find("./pubDate")))
    primary_category = categories[0] if categories else fallback_category

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "summary": summary,
        "authors": authors,
        "published": published,
        "updated": published,
        "url": url,
        "pdf_url": _rss_pdf_url(arxiv_id, url),
        "source": "arxiv.org",
        "primary_category": primary_category,
        "categories": categories or [fallback_category],
    }


def _rss_feed_items(category: str) -> list[dict[str, Any]]:
    response = requests.get(
        ARXIV_RSS_URL.format(category=category),
        headers={"User-Agent": _arxiv_user_agent()},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    return [_rss_entry_to_item(entry, category) for entry in root.findall("./channel/item")]


def _sort_rss_items(items: list[dict[str, Any]], *, query: str, sort_by: str, had_topic_match: bool) -> list[dict[str, Any]]:
    query_terms = _query_terms(query)
    broad_query = _is_broad_topic_query(query, query_terms)
    scored = [(item, _rss_item_score(item, query, query_terms)) for item in items]
    any_score = any(score > 0 for _, score in scored)

    if broad_query:
        return sorted(items, key=lambda item: item.get("published", ""), reverse=True)

    if sort_by == "relevance" and any_score:
        scored.sort(key=lambda entry: (entry[1], entry[0].get("published", "")), reverse=True)
        return [item for item, _ in scored]

    if any_score:
        scored.sort(key=lambda entry: (entry[0].get("published", ""), entry[1]), reverse=True)
        return [item for item, _ in scored]

    if had_topic_match:
        return sorted(items, key=lambda item: item.get("published", ""), reverse=True)

    return []


def _rss_fallback_search(query: str, max_results: int, sort_by: str, *, reason: str) -> dict[str, Any] | None:
    categories, had_topic_match = _rss_categories_for_query(query)
    collected: dict[str, dict[str, Any]] = {}

    for category in categories[:3]:
        try:
            for item in _rss_feed_items(category):
                item_id = item.get("arxiv_id") or item.get("url") or f"{category}:{len(collected)}"
                if item_id not in collected:
                    collected[item_id] = item
        except Exception:
            continue

    ordered_items = _sort_rss_items(list(collected.values()), query=query, sort_by=sort_by, had_topic_match=had_topic_match)
    if not ordered_items:
        return None

    return {
        "tool": "arxiv_search",
        "query": query,
        "api_query": _arxiv_search_query(query),
        "total_results": None,
        "items": ordered_items[:max_results],
        "rate_limit_note": "The arXiv API can rate-limit heavily. This result came from arXiv RSS category feeds as a fallback.",
        "fallback_used": True,
        "fallback_source": "arxiv_rss",
        "fallback_categories": categories[:3],
        "fallback_reason": reason,
    }


def _api_search(query: str, max_results: int, sort_by: str) -> dict[str, Any]:
    params = {
        "search_query": _arxiv_search_query(query),
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    response = _arxiv_get(ARXIV_API_URL, params=params)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    total_node = root.find(".//opensearch:totalResults", namespaces)
    entries: list[dict[str, Any]] = []

    for entry in root.findall(".//atom:entry", namespaces):
        abs_url = _entry_text(entry, "./atom:id", namespaces)
        arxiv_id = _arxiv_id(abs_url)
        links = [{"rel": link.get("rel"), "href": link.get("href"), "title": link.get("title")} for link in entry.findall("./atom:link", namespaces)]
        pdf_url = next((link["href"] for link in links if link.get("title") == "pdf"), f"https://arxiv.org/pdf/{arxiv_id}.pdf")
        primary = entry.find("./arxiv:primary_category", namespaces)
        summary = _entry_text(entry, "./atom:summary", namespaces).replace("\n", " ")
        entries.append(
            {
                "arxiv_id": arxiv_id,
                "title": _entry_text(entry, "./atom:title", namespaces).replace("\n", " "),
                "summary": " ".join(summary.split()),
                "authors": [_entry_text(author, "./atom:name", namespaces) for author in entry.findall("./atom:author", namespaces)],
                "published": _entry_text(entry, "./atom:published", namespaces),
                "updated": _entry_text(entry, "./atom:updated", namespaces),
                "url": abs_url,
                "pdf_url": pdf_url,
                "source": "arxiv.org",
                "primary_category": primary.get("term") if primary is not None else None,
                "categories": [cat.get("term") for cat in entry.findall("./atom:category", namespaces)],
            }
        )

    return {
        "tool": "arxiv_search",
        "query": query,
        "api_query": params["search_query"],
        "total_results": int(total_node.text) if total_node is not None and total_node.text else None,
        "items": entries,
        "rate_limit_note": "arXiv may return 429 if called too frequently; this tool waits at least 3 seconds between requests in-process.",
    }


def arxiv_search(query: str = "", max_results: int = 5, sort_by: str = "relevance") -> dict[str, Any]:
    try:
        max_results = max(1, min(int(max_results or 5), 10))
        sort_by = sort_by if sort_by in {"relevance", "lastUpdatedDate", "submittedDate"} else "relevance"
        return _api_search(query, max_results, sort_by)
    except Exception as exc:
        fallback = _rss_fallback_search(query, max_results, sort_by, reason=str(exc))
        if fallback is not None:
            return fallback
        return err("arxiv_search", exc)
