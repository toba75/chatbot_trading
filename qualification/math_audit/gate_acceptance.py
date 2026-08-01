from __future__ import annotations

from typing import Any


def build_gate_report(
    manifest: dict[str, Any],
    corpus_results: list[dict[str, Any]],
    mutation_results: list[dict[str, Any]],
) -> dict[str, Any]:
    false_conformant = sum(
        mutation["expected"] != "conformant_within_scope"
        and mutation["observed"] == "conformant_within_scope"
        for mutation in mutation_results
    )
    reasons = []
    for metric in ("detection_recall", "detection_precision"):
        if _representative_below_threshold(
            corpus_results, metric, manifest["thresholds"][metric]
        ):
            reasons.append(f"{metric}_below_threshold")
    if false_conformant > manifest["thresholds"]["false_conformant_mutations"]:
        reasons.append("false_conformant_mutation")
    proof_metrics = ("traceability_coverage", "semantic_expectation_accuracy")
    if any(manifest["thresholds"][metric] is None for metric in proof_metrics):
        reasons.append("proof_coverage_thresholds_missing")
    else:
        for metric in proof_metrics:
            if _representative_below_threshold(
                corpus_results, metric, manifest["thresholds"][metric]
            ):
                reasons.append(f"{metric}_below_threshold")
    if not any(_is_representative(corpus) for corpus in corpus_results):
        reasons.append("representative_exhaustive_oracle_missing")
    return {
        "schema_version": 1,
        "accepted": not reasons,
        "blocking_reasons": reasons,
        "corpora": corpus_results,
        "mutations": {
            "total": len(mutation_results),
            "false_conformant": false_conformant,
            "results": mutation_results,
        },
    }


def _representative_below_threshold(
    corpora: list[dict[str, Any]], metric: str, threshold: float
) -> bool:
    return any(
        _is_representative(corpus) and corpus["metrics"][metric] < threshold
        for corpus in corpora
    )


def _is_representative(corpus: dict[str, Any]) -> bool:
    return corpus["exhaustive_oracle"] and corpus["representative"]
