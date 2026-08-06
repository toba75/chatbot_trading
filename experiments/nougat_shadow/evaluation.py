from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.nougat_shadow.artifacts import load_json, sha256
from pdf_math_audit.correction_application import apply_target
from pdf_math_audit.mathml_candidate import candidate_analysis


_MATH = re.compile(
    r"\\\[(?P<display>.*?)\\\]"
    r"|\\\((?P<inline>.*?)\\\)"
    r"|\$\$(?P<display_dollar>.*?)\$\$"
    r"|(?<!\\)\$(?!\$)(?P<inline_dollar>.*?)(?<!\\)\$",
    re.DOTALL,
)


def extract_math(markdown: str) -> list[str]:
    expressions = []
    for match in _MATH.finditer(markdown):
        latex = next(value for value in match.groupdict().values() if value is not None)
        if latex.strip():
            expressions.append(latex.strip())
    return expressions


def _analyze_page(markdown: str) -> list[dict[str, Any]]:
    analyzed = []
    for index, latex in enumerate(extract_math(markdown)):
        tokens, signature, reason = candidate_analysis(latex)
        analyzed.append(
            {
                "index": index,
                "latex": latex,
                "tokens": tokens,
                "signature": signature,
                "parse_rejection": reason,
            }
        )
    return analyzed


def _application_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_id": target["target_id"],
        "kind": target["kind"],
        "candidate_text": target["before"],
        "candidate_format": target.get("candidate_format"),
        "regions": [
            {
                "candidate_charspan": proof["candidate_charspan"],
                "candidate_text": proof["candidate_text"],
                "source_canonical_tokens": proof["tokens"],
                "source_relation_signature": proof["signature"],
            }
            for proof in target["proofs"]
        ],
    }


def _assess_target(
    target: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    proofs = []
    for proof in target["proofs"]:
        matches = [
            candidate["index"]
            for candidate in candidates
            if candidate["parse_rejection"] is None
            and candidate["tokens"] == proof["tokens"]
            and candidate["signature"] == proof["signature"]
        ]
        status = (
            "exact_unique"
            if len(matches) == 1
            else "exact_ambiguous"
            if matches
            else "no_exact_match"
        )
        proofs.append(proof | {"status": status, "candidate_indices": matches})
    assessed = target | {"proofs": proofs}
    statuses = {proof["status"] for proof in proofs}
    if statuses == {"no_exact_match"}:
        return assessed | {"shadow_status": "no_exact_match"}
    if statuses != {"exact_unique"}:
        return assessed | {"shadow_status": "partial_or_ambiguous"}
    selected_indices = [proof["candidate_indices"][0] for proof in proofs]
    if selected_indices != sorted(set(selected_indices)):
        return assessed | {
            "shadow_status": "partial_or_ambiguous",
            "application_reason": "candidate_mapping_not_unique_or_monotonic",
        }
    proposals = [candidates[index]["latex"] for index in selected_indices]
    try:
        after, mathml = apply_target(_application_target(assessed), proposals)
    except ValueError as error:
        return assessed | {
            "shadow_status": "exact_not_applicable",
            "application_reason": str(error),
        }
    return assessed | {
        "shadow_status": "applicable_exact",
        "after": after,
        "mathml": mathml,
    }


def _reject_cross_target_reuse(targets: list[dict[str, Any]]) -> None:
    uses: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for target in targets:
        for proof in target["proofs"]:
            if proof["status"] != "exact_unique":
                continue
            key = (target["page"], proof["candidate_indices"][0])
            uses.setdefault(key, []).append(target)
    for reused in uses.values():
        if len({target["target_id"] for target in reused}) < 2:
            continue
        for target in reused:
            target["shadow_status"] = "partial_or_ambiguous"
            target["application_reason"] = "candidate_reused_across_targets"
            target.pop("after", None)
            target.pop("mathml", None)


def evaluate(
    manifest_path: Path, predictions_path: Path, output_path: Path
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    predictions = load_json(predictions_path)
    if sha256(manifest_path.read_bytes()) != predictions["manifest_sha256"]:
        raise ValueError("l'empreinte du manifeste ne correspond pas aux prédictions")
    predictions_by_page = {page["page"]: page for page in predictions["pages"]}
    candidates_by_page = {}
    for page in manifest["pages"]:
        prediction = predictions_by_page[page["page"]]
        markdown_path = predictions_path.parent / prediction["mmd"]
        markdown = markdown_path.read_text(encoding="utf-8")
        if sha256(markdown.encode("utf-8")) != prediction["mmd_sha256"]:
            raise ValueError(f"empreinte MMD invalide pour la page {page['page']}")
        candidates_by_page[page["page"]] = _analyze_page(markdown)
    targets = [
        _assess_target(target, candidates_by_page[target["page"]])
        for target in manifest["targets"]
    ]
    _reject_cross_target_reuse(targets)
    counts = Counter(target["shadow_status"] for target in targets)
    result = {
        "summary": {
            "mode": "shadow",
            "model": predictions["model"],
            "revision": predictions["revision"],
            "pages": len(manifest["pages"]),
            "targets": len(targets),
            "statuses": dict(sorted(counts.items())),
            "model_load_seconds": predictions["model_load_seconds"],
            "inference_seconds": predictions["inference_seconds"],
        },
        "page_candidates": candidates_by_page,
        "targets": targets,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
