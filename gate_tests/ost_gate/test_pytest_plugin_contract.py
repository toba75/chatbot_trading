from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ost_gate.pytest_plugin as gate_plugin


def test_xdist_worker_never_publishes_the_aggregated_gate_report(monkeypatch, tmp_path: Path) -> None:
    """Given-When-Then : seul le maître publie le résultat agrégé de la gate."""

    report_path = tmp_path / "pytest-results.json"
    monkeypatch.setattr(gate_plugin, "_report_path", report_path)
    monkeypatch.setattr(
        gate_plugin,
        "_expected",
        {tmp_path / "case.py": "case"},
    )
    worker_session = SimpleNamespace(
        config=SimpleNamespace(workerinput={"workerid": "gw0"})
    )

    gate_plugin.pytest_sessionfinish(worker_session, exitstatus=0)

    assert report_path.exists() is False
