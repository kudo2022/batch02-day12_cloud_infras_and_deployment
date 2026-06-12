from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests

from tools._shared import TIMEOUT, err


SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1"
CROSSREF_URL = "https://api.crossref.org/works"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
ARXIV_PATTERN = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)


def _user_agent() -> str:
    return os.getenv("PAPER_METADATA_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (paper insights)")


def _headers() -> dict[str, str]:
    headers = {"User-Agent": _user_agent()}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _semantic_fields() -> str:
    return ",".join(
        [
            "title",
            "abstract",
            "year",
            "authors",
            "citationCount",
            "influentialCitationCount",
            "referenceCount",
            "venue",
            "publicationVenue",
            "publicationTypes",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "isOpenAccess",
            "openAccessPdf",
            "externalIds",
            "url",
        ]
    )


def _get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=_headers(), timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _normalize_ref(paper_ref: str) -> str:
    return " ".join((paper_ref or "").strip().split())


def _extract_doi(paper_ref: str) -> str:
    match = DOI_PATTERN.search(paper_ref or "")
    return match.group(0).rstrip(").,;]") if match else ""


def _extract_arxiv_id(paper_ref: str) -> str:
    match = ARXIV_PATTERN.search(paper_ref or "")
    return match.group(1) if match else ""


def _resolve_semantic_id(paper_ref: str) -> tuple[str | None, str]:
    paper_ref = _normalize_ref(paper_ref)
    lowered = paper_ref.lower()
    doi = _extract_doi(paper_ref)
    if doi:
        return f"DOI:{doi}", "doi"

    arxiv_id = _extract_arxiv_id(paper_ref)
    if "arxiv.org" in lowered and arxiv_id:
        return f"ARXIV:{arxiv_id}", "arxiv"

    if re.fullmatch(ARXIV_PATTERN, paper_ref):
        return f"ARXIV:{paper_ref}", "arxiv"

    if lowered.startswith(("http://", "https://")):
        supported_domains = ("semanticscholar.org", "arxiv.org", "aclweb.org", "acm.org", "biorxiv.org")
        if any(domain in lowered for domain in supported_domains):
            return f"URL:{paper_ref}", "url"

    return None, "query"


def _fetch_semantic_by_id(paper_id: str) -> dict[str, Any]:
    encoded = quote(paper_id, safe=":")
    return _get_json(f"{SEMANTIC_SCHOLAR_URL}/paper/{encoded}", params={"fields": _semantic_fields()})


def _search_semantic(paper_ref: str) -> dict[str, Any]:
    data = _get_json(
        f"{SEMANTIC_SCHOLAR_URL}/paper/search",
        params={"query": paper_ref, "limit": 1, "fields": _semantic_fields()},
    )
    matches = data.get("data") or []
    if not matches:
        raise ValueError("No paper match found in Semantic Scholar")
    return matches[0]


def _fetch_crossref(doi: str) -> dict[str, Any] | None:
    try:
        data = _get_json(f"{CROSSREF_URL}/{quote(doi, safe='')}")
    except Exception:
        return None
    return data.get("message") or None


def _sentence_split(text: str) -> list[str]:
    cleaned = " ".join((text or "").replace("\n", " ").split())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _build_summary(abstract: str) -> dict[str, Any]:
    sentences = _sentence_split(abstract)
    if not sentences:
        return {
            "executive_summary": "No abstract was available from the metadata source. Use the PDF-reading tool for a deeper summary.",
            "key_points": [],
        }
    executive = " ".join(sentences[: min(3, len(sentences))])
    key_points = sentences[: min(4, len(sentences))]
    return {"executive_summary": executive, "key_points": key_points}


def _paper_age(year: int | None) -> int:
    if not year:
        return 1
    return max(datetime.now().year - int(year) + 1, 1)


def _peer_review_signal(publication_types: list[str], publication_venue: dict[str, Any] | None, resolved_by: str) -> str:
    venue_type = (publication_venue or {}).get("type", "")
    normalized_types = {item.lower() for item in publication_types or []}
    if "journalarticle" in normalized_types or venue_type == "journal":
        return "likely_peer_reviewed"
    if "conference" in normalized_types or venue_type == "conference":
        return "likely_peer_reviewed"
    if resolved_by == "arxiv":
        return "preprint_signal"
    return "unclear"


def _credibility_score(
    *,
    year: int | None,
    citation_count: int,
    influential_citation_count: int,
    reference_count: int,
    publication_types: list[str],
    publication_venue: dict[str, Any] | None,
    external_ids: dict[str, Any],
    is_open_access: bool,
    resolved_by: str,
) -> dict[str, Any]:
    age = _paper_age(year)
    citations_per_year = round(citation_count / age, 2)
    score = 25
    reasons: list[str] = []
    caveats: list[str] = []

    peer_review_signal = _peer_review_signal(publication_types, publication_venue, resolved_by)
    if peer_review_signal == "likely_peer_reviewed":
        score += 20
        reasons.append("Publication metadata suggests a journal or conference venue.")
    elif peer_review_signal == "preprint_signal":
        score -= 12
        caveats.append("This looks like a preprint signal, so peer review may not have happened yet.")
    else:
        caveats.append("Peer-review status is not clear from the available metadata.")

    if external_ids.get("DOI"):
        score += 6
        reasons.append("A DOI is available, which is a good publication traceability signal.")

    if citation_count >= 200:
        score += 20
        reasons.append("The paper has a strong citation footprint.")
    elif citation_count >= 50:
        score += 15
        reasons.append("The paper has a solid citation footprint.")
    elif citation_count >= 10:
        score += 10
        reasons.append("The paper has early citation uptake.")
    elif citation_count > 0:
        score += 4

    if influential_citation_count >= 20:
        score += 12
        reasons.append("It has many influential citations, not just raw citation volume.")
    elif influential_citation_count >= 5:
        score += 8
        reasons.append("It has several influential citations.")
    elif influential_citation_count > 0:
        score += 3

    if citations_per_year >= 20:
        score += 10
        reasons.append("Citation velocity is high for its age.")
    elif citations_per_year >= 5:
        score += 7
        reasons.append("Citation velocity is healthy for its age.")
    elif citations_per_year >= 1:
        score += 3

    if reference_count >= 30:
        score += 4
    elif reference_count >= 10:
        score += 2

    if is_open_access:
        score += 2

    if year and datetime.now().year - year <= 1:
        caveats.append("This is a recent paper, so citation-based credibility signals may still be immature.")

    score = max(0, min(score, 100))
    if score >= 80:
        level = "strong"
    elif score >= 60:
        level = "promising"
    elif score >= 40:
        level = "mixed"
    else:
        level = "preliminary"

    if not reasons:
        reasons.append("Only limited metadata signals were available.")

    return {
        "score": score,
        "level": level,
        "peer_review_signal": peer_review_signal,
        "citations_per_year": citations_per_year,
        "reasons": reasons,
        "caveats": caveats,
    }


def _paper_url(paper: dict[str, Any], external_ids: dict[str, Any]) -> str:
    if paper.get("url"):
        return paper["url"]
    doi = external_ids.get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    arxiv_id = external_ids.get("ArXiv") or external_ids.get("ARXIV")
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    return ""


def _source_label(paper: dict[str, Any], external_ids: dict[str, Any], publication_venue: dict[str, Any] | None) -> str:
    venue_name = (publication_venue or {}).get("name") or paper.get("venue")
    if venue_name:
        return venue_name
    if external_ids.get("DOI"):
        return "doi.org"
    if external_ids.get("ArXiv") or external_ids.get("ARXIV"):
        return "arxiv.org"
    return "semanticscholar.org"


def paper_insights(paper_ref: str = "") -> dict[str, Any]:
    try:
        paper_ref = _normalize_ref(paper_ref)
        if not paper_ref:
            raise ValueError("paper_ref is required")

        paper_id, resolved_by = _resolve_semantic_id(paper_ref)
        paper = _fetch_semantic_by_id(paper_id) if paper_id else _search_semantic(paper_ref)
        if not paper:
            raise ValueError("No paper metadata returned")

        external_ids = dict(paper.get("externalIds") or {})
        publication_venue = paper.get("publicationVenue") or {}
        publication_types = list(paper.get("publicationTypes") or [])
        doi = external_ids.get("DOI") or _extract_doi(paper_ref)
        crossref = _fetch_crossref(doi) if doi else None

        title = paper.get("title") or paper_ref
        abstract = (paper.get("abstract") or "").strip()
        year = paper.get("year")
        citation_count = int(paper.get("citationCount") or 0)
        influential_citation_count = int(paper.get("influentialCitationCount") or 0)
        reference_count = int(paper.get("referenceCount") or 0)
        is_open_access = bool(paper.get("isOpenAccess"))
        summary = _build_summary(abstract)
        credibility = _credibility_score(
            year=year,
            citation_count=citation_count,
            influential_citation_count=influential_citation_count,
            reference_count=reference_count,
            publication_types=publication_types,
            publication_venue=publication_venue,
            external_ids=external_ids,
            is_open_access=is_open_access,
            resolved_by=resolved_by,
        )

        paper_url = _paper_url(paper, external_ids)
        source = _source_label(paper, external_ids, publication_venue)
        venue = publication_venue.get("name") or paper.get("venue")
        crossref_summary = None
        if crossref:
            crossref_summary = {
                "publisher": crossref.get("publisher"),
                "type": crossref.get("type"),
                "journal": (crossref.get("container-title") or [None])[0],
            }

        item_summary = (
            f"Summary: {summary['executive_summary']} "
            f"Credibility: level={credibility['level']}, score={credibility['score']}, "
            f"citations={citation_count}, influential_citations={influential_citation_count}, venue={venue or 'unknown'}."
        )

        return {
            "tool": "paper_insights",
            "paper_ref": paper_ref,
            "resolved_by": resolved_by,
            "paper": {
                "title": title,
                "authors": [author.get("name") for author in paper.get("authors") or [] if author.get("name")],
                "year": year,
                "venue": venue,
                "publication_types": publication_types,
                "fields_of_study": paper.get("fieldsOfStudy") or [
                    field.get("category")
                    for field in paper.get("s2FieldsOfStudy") or []
                    if field.get("category")
                ],
                "citation_count": citation_count,
                "influential_citation_count": influential_citation_count,
                "reference_count": reference_count,
                "is_open_access": is_open_access,
                "open_access_pdf": (paper.get("openAccessPdf") or {}).get("url"),
                "external_ids": external_ids,
                "url": paper_url,
            },
            "summary": summary,
            "credibility": credibility,
            "crossref": crossref_summary,
            "items": [
                {
                    "title": title,
                    "url": paper_url,
                    "source": source,
                    "summary": item_summary,
                    "section": "Paper insight",
                }
            ],
            "notes": [
                "Citation-based credibility is field-dependent and should not be treated as a perfect quality measure.",
                "Preprints can be valuable, but arXiv by itself is not a peer-review guarantee.",
            ],
        }
    except Exception as exc:
        return err("paper_insights", exc)
