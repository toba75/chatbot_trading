from __future__ import annotations

from collections import Counter
from typing import Any


def _iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _assertions_covered(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    if observed.get("verdict") not in {"conformant_within_scope", "contradicted"}:
        return False
    source = "".join(observed.get("source_tokens", [])).rstrip(",.;")
    return all(
        assertion["relation"] == "sequence"
        and assertion["expected"] == source
        for assertion in expected["semantic_assertions"]
    )


def _expectation_met(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_verdict = expected.get("expected_verdict", "conformant_within_scope")
    if expected_verdict == "conformant_within_scope":
        return _assertions_covered(expected, observed)
    reasons = {reason.get("code") for reason in observed.get("semantic_reasons", [])}
    return (
        observed.get("verdict") == expected_verdict
        and expected.get("expected_reason") in reasons
    )


def _localization_method(candidate: dict[str, Any]) -> str:
    if method := candidate.get("localization_method"):
        return method
    return "docling_provenance_bbox" if candidate.get("bbox") is not None else "not_localized"


def measure(
    oracle: list[dict[str, Any]], audit: dict[str, Any], threshold: float
) -> dict[str, Any]:
    alignment = audit["alignment"]
    candidates = alignment["pdf_source_math_regions"]
    edges = [
        (oracle_index, candidate_index)
        for oracle_index, expected in enumerate(oracle)
        for candidate_index, observed in enumerate(candidates)
        if observed.get("page") is not None
        and observed.get("bbox") is not None
        and expected["page"] == observed["page"]
        and _iou(expected["bbox"], observed["bbox"]) >= threshold
    ]
    neighbours = {
        index: [right for left, right in edges if left == index]
        for index in range(len(oracle))
    }
    candidate_owner: dict[int, int] = {}

    def assign(oracle_index: int, visited: set[int]) -> bool:
        for candidate_index in neighbours[oracle_index]:
            if candidate_index in visited:
                continue
            visited.add(candidate_index)
            owner = candidate_owner.get(candidate_index)
            if owner is None or assign(owner, visited):
                candidate_owner[candidate_index] = oracle_index
                return True
        return False

    for oracle_index in range(len(oracle)):
        assign(oracle_index, set())
    matches = sorted((left, right) for right, left in candidate_owner.items())
    matched_oracle = {left for left, _right in matches}
    matched_candidates = {right for _left, right in matches}
    below_threshold = [
        {
            "oracle_region": expected["id"],
            "candidate_region": observed["region_id"],
            "iou": round(score, 6),
        }
        for oracle_index, expected in enumerate(oracle)
        for candidate_index, observed in enumerate(candidates)
        if oracle_index not in matched_oracle
        and candidate_index not in matched_candidates
        and observed.get("page") == expected["page"]
        and observed.get("bbox") is not None
        and 0 < (score := _iou(expected["bbox"], observed["bbox"])) < threshold
    ]
    traced = sum(candidates[right]["status"] == "traced" for _left, right in matches)
    evaluated = sum(
        candidates[right].get("verdict")
        in {"conformant_within_scope", "contradicted"}
        for _left, right in matches
    )
    assertion_covered = sum(
        _assertions_covered(oracle[left], candidates[right])
        for left, right in matches
    )
    expectations_met = sum(
        _expectation_met(oracle[left], candidates[right])
        for left, right in matches
    )
    oracle_count, candidate_count = len(oracle), len(candidates)
    candidate_methods = Counter(map(_localization_method, candidates))
    matched_methods = Counter(
        _localization_method(candidates[right]) for _left, right in matches
    )
    return {
        "metrics": {
            "oracle_regions": oracle_count,
            "candidate_regions": candidate_count,
            "matched_regions": len(matches),
            "candidate_regions_by_localization_method": dict(
                sorted(candidate_methods.items())
            ),
            "matched_regions_by_localization_method": dict(
                sorted(matched_methods.items())
            ),
            "detection_recall": len(matches) / oracle_count if oracle_count else 0.0,
            "detection_precision": len(matches) / candidate_count if candidate_count else 0.0,
            "traceability_coverage": traced / oracle_count if oracle_count else 0.0,
            "semantic_coverage": evaluated / oracle_count if oracle_count else 0.0,
            "semantic_assertion_coverage": (
                assertion_covered / oracle_count if oracle_count else 0.0
            ),
            "semantic_expectation_accuracy": (
                expectations_met / oracle_count if oracle_count else 0.0
            ),
            "false_alignments": candidate_count - len(matches),
        },
        "matches": [
            {
                "oracle_region": oracle[left]["id"],
                "candidate_region": candidates[right]["region_id"],
                "localization_method": _localization_method(candidates[right]),
                "iou": round(_iou(oracle[left]["bbox"], candidates[right]["bbox"]), 6),
            }
            for left, right in matches
        ],
        "missed_oracle_regions": [
            region["id"] for index, region in enumerate(oracle) if index not in matched_oracle
        ],
        "false_alignment_regions": [
            region["region_id"]
            for index, region in enumerate(candidates)
            if index not in matched_candidates
        ],
        "same_page_overlaps_below_threshold": below_threshold,
    }
