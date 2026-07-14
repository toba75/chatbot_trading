from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ost_gate.executor import _run_batch
from ost_gate.models import GateNode, GatePlan, NodeResult


def test_given_isolated_parallel_nodes_when_the_executor_runs_a_batch_then_each_node_uses_its_own_pytest_process() -> None:
    """Given-When-Then : le parallélisme ne partage ni processus ni rapport pytest."""

    repository_root = Path.cwd()
    first = GateNode(
        "first",
        repository_root / "first.py",
        "test",
        "m001",
        "tests",
        10,
        "parallel",
        (),
        False,
    )
    second = GateNode(
        "second",
        repository_root / "second.py",
        "test",
        "m001",
        "tests",
        10,
        "parallel",
        (),
        False,
    )
    plan = GatePlan(repository_root, (first, second), ((first, second),), False, None, False)

    def run_node(_plan: GatePlan, node: GateNode) -> tuple[NodeResult, int]:
        return (
            NodeResult(node.identifier, node.scope, node.phase, "GREEN", 0.1, 1, None),
            0,
        )

    with patch("ost_gate.executor._run_node", side_effect=run_node) as mocked:
        results, exit_code = _run_batch(plan, [first, second], workers=2)

    assert exit_code == 0
    assert [result.identifier for result in results] == ["first", "second"]
    assert [call.args[1].identifier for call in mocked.call_args_list] == ["first", "second"]
