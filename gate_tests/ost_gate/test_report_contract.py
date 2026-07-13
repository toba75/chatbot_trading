from __future__ import annotations

import json
from pathlib import Path

from ost_gate.models import GateNode, GatePlan, NodeResult
from ost_gate.report import write_report


def test_report_keeps_exactly_one_result_per_node_and_phase_durations(tmp_path: Path) -> None:
    node = GateNode("m013.config", tmp_path / "test.py", "test", "m013", "configuration", 10, "parallel", (), False)
    plan = GatePlan(tmp_path, (node,), ((node,),), False, None, False)
    result = NodeResult("m013.config", "m013", "configuration", "GREEN", 1.25, 1, None)
    report_path = tmp_path / "report.json"
    write_report(report_path, plan, [result])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["uniqueness"] == {"missing": [], "unexpected": [], "non_unique": []}
    assert report["phase_durations_seconds"] == {"configuration": 1.25}
    assert report["results"][0]["executions"] == 1
