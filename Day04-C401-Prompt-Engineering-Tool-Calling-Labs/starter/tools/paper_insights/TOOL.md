---
name: paper_insights
track: bonus
kind: live_api
provider: Semantic Scholar Graph API + Crossref REST API
requires_env: [SEMANTIC_SCHOLAR_API_KEY]
inputs: [paper_ref]
outputs: [paper, summary, credibility, items]
side_effect: false
---

Accepts a DOI, arXiv ID, supported URL, or paper title query. Returns:

- metadata and publication signals
- abstract-based executive summary
- credibility heuristics using venue, citation counts, influential citations, and DOI/peer-review signals

This tool should be used for paper-level inspection, not broad literature search.
