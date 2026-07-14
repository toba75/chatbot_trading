"""Plugin pytest strictement limité aux nœuds d’une invocation de gate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

_expected: dict[Path, str] = {}
_timeouts: dict[str, int] = {}
_results: dict[str, dict[str, Any]] = {}
_report_path: Path | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Charge le contrat transmis par l’exécuteur sans valeur implicite."""

    expected_raw = os.environ.get("OST_GATE_EXPECTED_NODES")
    report_raw = os.environ.get("OST_GATE_PYTEST_REPORT")
    timeouts_raw = os.environ.get("OST_GATE_TIMEOUTS")
    if expected_raw is None or report_raw is None or timeouts_raw is None:
        raise pytest.UsageError("OST_GATE_PYTEST_CONTRACT_REQUIRED")
    try:
        expected = json.loads(expected_raw)
        timeouts = json.loads(timeouts_raw)
    except json.JSONDecodeError as error:
        raise pytest.UsageError(f"OST_GATE_PYTEST_CONTRACT_INVALID:{error}") from error
    if not isinstance(expected, dict) or not expected:
        raise pytest.UsageError("OST_GATE_PYTEST_EXPECTED_NODES_INVALID")
    if not isinstance(timeouts, dict):
        raise pytest.UsageError("OST_GATE_PYTEST_TIMEOUTS_INVALID")
    global _expected, _timeouts, _results, _report_path
    _expected = {Path(path).resolve(): identifier for path, identifier in expected.items()}
    _timeouts = {str(identifier): int(timeout) for identifier, timeout in timeouts.items()}
    _results = {}
    _report_path = Path(report_raw)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Refuse toute collecte ambiguë, ignorée ou non prévue."""

    collected: dict[Path, int] = {}
    for item in session.items:
        marker_names = {marker.name for marker in item.iter_markers()}
        forbidden = sorted(marker_names & {"skip", "skipif", "xfail"})
        if forbidden:
            raise pytest.UsageError(f"GATE_TEST_MARKER_FORBIDDEN:{item.nodeid}:{','.join(forbidden)}")
        item_path = Path(str(item.path)).resolve()
        if item_path not in _expected:
            raise pytest.UsageError(f"GATE_TEST_UNEXPECTED_COLLECTION:{item.nodeid}")
        collected[item_path] = collected.get(item_path, 0) + 1
        identifier = _expected[item_path]
        if identifier not in _timeouts:
            raise pytest.UsageError(f"GATE_TEST_TIMEOUT_REQUIRED:{identifier}")
        item.add_marker(pytest.mark.timeout(_timeouts[identifier]))
    missing = sorted(str(path) for path in set(_expected) - set(collected))
    repeated = sorted(str(path) for path, count in collected.items() if count != 1)
    if missing:
        raise pytest.UsageError(f"GATE_TEST_NOT_COLLECTED:{','.join(missing)}")
    if repeated:
        raise pytest.UsageError(f"GATE_TEST_COLLECTION_NON_UNIQUE:{','.join(repeated)}")


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Collecte le seul résultat autorisé de chaque test atomique."""

    item_path = Path(str(report.fspath)).resolve()
    identifier = _expected.get(item_path)
    if identifier is None:
        return
    existing = _results.setdefault(
        identifier,
        {"status": "GREEN", "duration_seconds": 0.0, "detail": None},
    )
    existing["duration_seconds"] += report.duration
    if report.failed:
        existing["status"] = "RED"
        existing["detail"] = str(report.longrepr)
    elif report.skipped:
        existing["status"] = "RED"
        existing["detail"] = f"GATE_TEST_SKIPPED:{report.nodeid}"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Écrit le résultat même quand pytest retourne RED."""

    if hasattr(session.config, "workerinput"):
        session.config.workeroutput["ost_gate_results"] = _results
        return
    if _report_path is None:
        raise pytest.UsageError("OST_GATE_PYTEST_REPORT_REQUIRED")
    for identifier in _expected.values():
        _results.setdefault(
            identifier,
            {
                "status": "RED",
                "duration_seconds": 0.0,
                "detail": "GATE_TEST_RESULT_REQUIRED",
            },
        )
    payload = {"exit_code": exitstatus, "results": _results}
    _report_path.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def pytest_testnodedown(node: object, error: object | None) -> None:
    """Rapatrie les résultats d'un worker xdist avant le rapport maître."""

    del error
    worker_output = getattr(node, "workeroutput")
    raw_results = worker_output.get("ost_gate_results")
    if raw_results is None:
        return
    if not isinstance(raw_results, dict):
        raise pytest.UsageError("OST_GATE_XDIST_RESULTS_INVALID")
    expected_identifiers = set(_expected.values())
    for identifier, result in raw_results.items():
        if identifier not in expected_identifiers or not isinstance(result, dict):
            raise pytest.UsageError("OST_GATE_XDIST_RESULTS_INVALID")
        _results[identifier] = result
