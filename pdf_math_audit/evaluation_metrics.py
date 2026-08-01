from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


_SEMANTIC_STATUSES = ("established", "conflicting", "ambiguous", "not_established")
_CANDIDATE_STATUSES = ("matching", "missing", "contradicting", "not_evaluated")
_VERDICTS = ("conformant_within_scope", "contradicted", "non_verifiable")


def _metrics(regions: list[dict[str, Any]]) -> dict[str, Any]:
    semantic = Counter(region["semantic_status"] for region in regions)
    candidates = Counter(region["candidate_status"] for region in regions)
    verdicts = Counter(region["verdict"] for region in regions)
    return {
        "regions": len(regions),
        "semantic_statuses": {
            status: semantic[status] for status in _SEMANTIC_STATUSES
        },
        "candidate_statuses": {
            status: candidates[status] for status in _CANDIDATE_STATUSES
        },
        "verdicts": {verdict: verdicts[verdict] for verdict in _VERDICTS},
    }


def evaluation_metrics(regions: list[dict[str, Any]], profile: str) -> dict[str, Any]:
    by_page: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for region in regions:
        by_page[region["page"]].append(region)
    pages = [
        {"page": page, **_metrics(page_regions)}
        for page, page_regions in sorted(
            by_page.items(), key=lambda item: (item[0] is None, item[0] or 0)
        )
    ]
    return {"semantic_profile": profile, "overall": _metrics(regions), "pages": pages}
