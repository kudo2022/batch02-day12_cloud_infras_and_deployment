from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any
from urllib.parse import quote_plus

import requests

from tools._shared import TIMEOUT, domain, err, fold_text


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text).replace("\xa0", " ")
    return " ".join(text.split())


def _google_news_query(query: str, timeframe: str | None) -> str:
    time_hints = {
        "day": "when:1d",
        "week": "when:7d",
        "month": "when:30d",
        "year": "when:365d",
    }
    hint = time_hints.get((timeframe or "").strip().lower())
    parts = [" ".join((query or "").split())]
    if hint:
        parts.append(hint)
    return " ".join(part for part in parts if part).strip()


def _expanded_news_query(query: str, timeframe: str | None) -> str:
    normalized = fold_text(query or "")
    tokens = re.findall(r"[a-z0-9]+", normalized)
    token_set = set(tokens)
    expanded: list[str] = []

    if {"uav", "uas"} & token_set or "drone" in token_set or "drones" in token_set:
        expanded.extend(["military", "UAV", "drone", "technology"])
    if "radar" in token_set:
        expanded.extend(["military", "radar", "technology"])
    if "ew" in token_set or "electronic" in token_set:
        expanded.extend(["military", "electronic", "warfare", "technology"])
    if "isr" in token_set:
        expanded.extend(["ISR", "military", "surveillance", "technology"])

    for word in ("latest", "new", "technology", "military", "defense", "uav", "drone"):
        if word in token_set:
            expanded.append(word)

    # Keep the user's core terms, but remove filler that hurts search quality.
    noise = {
        "cong", "nghe", "moi", "nhat", "gan", "day", "hom", "nay", "tuan", "thang", "nam",
        "cho", "toi", "dua", "ve", "thong", "tin",
    }
    expanded.extend(token for token in tokens if token not in noise)
    return _google_news_query(" ".join(dict.fromkeys(expanded)) or normalized, timeframe)


def _google_news_items(rss_query: str, max_results: int) -> list[dict[str, Any]]:
    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(rss_query)}&hl=en-US&gl=US&ceid=US:en"
    )
    response = requests.get(rss_url, timeout=TIMEOUT)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    channel = root.find("./channel")
    items: list[dict[str, Any]] = []
    if channel is None:
        return items

    for item in channel.findall("./item")[: max(1, int(max_results or 5))]:
        raw_title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        title = raw_title
        if source and raw_title.endswith(f" - {source}"):
            title = raw_title[: -len(f" - {source}")].strip()

        description = _clean_html_text(item.findtext("description") or "")
        if source and description.endswith(source):
            description = description[: -len(source)].rstrip(" -|")
        if not description:
            description = title

        url = (item.findtext("link") or "").strip()
        items.append(
            {
                "title": title,
                "url": url,
                "source": source or domain(url),
                "summary": description,
                "published_at": (item.findtext("pubDate") or "").strip(),
            }
        )
    return items


def _google_news_search(query: str, timeframe: str | None, max_results: int) -> dict[str, Any]:
    primary_query = _google_news_query(query, timeframe)
    items = _google_news_items(primary_query, max_results)
    effective_query = primary_query
    note = "Fallback mode because TAVILY_API_KEY is missing."
    expanded_query = _expanded_news_query(query, timeframe)

    if (not items or len(items) < min(3, max(1, int(max_results or 5)))) and expanded_query != primary_query:
        expanded_items = _google_news_items(expanded_query, max_results)
        if len(expanded_items) > len(items):
            effective_query = expanded_query
            items = expanded_items
            note += " Query was expanded for broader news coverage."

    return {
        "tool": "web_search",
        "query": query,
        "topic": "news",
        "timeframe": timeframe,
        "items": items,
        "provider": "google_news_rss_fallback",
        "effective_query": effective_query,
        "note": note,
    }


def _tavily_search(query: str, topic: str, timeframe: str | None, max_results: int) -> dict[str, Any]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("Missing TAVILY_API_KEY env var")

    body: dict[str, Any] = {
        "query": query,
        "topic": topic,
        "max_results": int(max_results or 5),
        "search_depth": "basic",
    }
    if timeframe:
        body["time_range"] = timeframe

    response = requests.post(
        "https://api.tavily.com/search",
        json=body,
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    items = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "source": domain(item.get("url", "")),
            "summary": item.get("content"),
            "score": item.get("score"),
        }
        for item in data.get("results", [])
    ]
    return {
        "tool": "web_search",
        "query": query,
        "topic": topic,
        "timeframe": timeframe,
        "items": items,
        "provider": "tavily",
    }


def web_search(query: str = "", topic: str = "general", timeframe: str | None = "week", max_results: int = 5) -> dict[str, Any]:
    try:
        if os.getenv("TAVILY_API_KEY"):
            return _tavily_search(query, topic, timeframe, max_results)
        return _google_news_search(query, timeframe, max_results)
    except Exception as exc:
        return err("web_search", exc)
