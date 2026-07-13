from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ost_gate.executor import execute_plan
from ost_gate.models import GateNode, GatePlan, NodeResult


def test_executor_never_overlaps_a_serial_group_or_reexecutes_a_node(tmp_path: Path) -> None:
    parallel = GateNode("parallel", tmp_path / "parallel.py", "test", "m001", "tests", 10, "parallel", (), False)
    git_one = GateNode("git.one", tmp_path / "git_one.py", "test", "m001", "git", 10, "git", (), False)
    git_two = GateNode("git.two", tmp_path / "git_two.py", "test", "m001", "git", 10, "git", (), False)
    plan = GatePlan(tmp_path, (parallel, git_one, git_two), ((parallel, git_one, git_two),), False, None, False)
    batches: list[tuple[list[str], int]] = []

    def fake_run_batch(_plan: GatePlan, nodes: list[GateNode], workers: int) -> tuple[list[NodeResult], int]:
        batches.append(([node.identifier for node in nodes], workers))
        return [
            NodeResult(node.identifier, node.scope, node.phase, "GREEN", 0.1, 1, None)
            for node in nodes
        ], 0

    with patch("ost_gate.executor._run_batch", side_effect=fake_run_batch):
        results, exit_code = execute_plan(plan, parallel_workers=3)
    assert exit_code == 0
    assert batches == [(["parallel"], 3), (["git.one", "git.two"], 1)]
    assert [result.identifier for result in results] == ["parallel", "git.one", "git.two"]
    assert all(result.executions == 1 for result in results)
