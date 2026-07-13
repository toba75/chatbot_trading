"""Rapport JSON déterministe de la gate."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ost_gate.models import GatePlan, NodeResult


def write_report(path: Path, plan: GatePlan, results: list[NodeResult]) -> None:
    """Écrit une preuve atomique sans masquer un doublon d’exécution."""

    counts = Counter(result.identifier for result in results)
    duplicate_identifiers = sorted(identifier for identifier, count in counts.items() if count != 1)
    expected = {node.identifier for node in plan.nodes}
    observed = set(counts)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    document = {
        "scope": plan.scope,
        "partial": plan.partial,
        "offline": plan.offline,
        "node_count": len(plan.nodes),
        "results": [
            {
                "id": result.identifier,
                "scope": result.scope,
                "phase": result.phase,
                "status": result.status,
                "duration_seconds": round(result.duration_seconds, 6),
                "executions": result.executions,
                "detail": result.detail,
            }
            for result in sorted(results, key=lambda item: item.identifier)
        ],
        "uniqueness": {
            "missing": missing,
            "unexpected": unexpected,
            "non_unique": duplicate_identifiers,
        },
        "phase_durations_seconds": _phase_durations(results),
        "slowest": _slowest(results),
    }
    if missing or unexpected or duplicate_identifiers:
        raise RuntimeError("GATE_REPORT_EXECUTION_UNIQUENESS_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _phase_durations(results: list[NodeResult]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for result in results:
        totals[result.phase] = totals.get(result.phase, 0.0) + result.duration_seconds
    return {phase: round(duration, 6) for phase, duration in sorted(totals.items())}


def _slowest(results: list[NodeResult]) -> list[dict[str, object]]:
    return [
        {
            "id": result.identifier,
            "duration_seconds": round(result.duration_seconds, 6),
            "phase": result.phase,
        }
        for result in sorted(results, key=lambda item: (-item.duration_seconds, item.identifier))[:10]
    ]
