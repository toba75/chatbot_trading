from __future__ import annotations

from pathlib import Path

from ost_gate.errors import PlanError
from ost_gate.models import GateManifest, GateNode
from ost_gate.planner import build_plan


def test_planner_orders_dependencies_once_and_serializes_selection() -> None:
    root = Path.cwd()
    governance = GateNode("governance", root / "a.py", "validator", "governance", "validation", 10, "parallel", (), False)
    m008 = GateNode("m008.case", root / "b.py", "test", "m008", "tests", 10, "git", ("governance",), False)
    m013_live = GateNode("m013.live", root / "c.py", "test", "m013", "live", 30, "m013-live", ("m008.case",), True)
    manifest = GateManifest(root, root / "gate.toml", (governance, m008, m013_live))
    scoped_plan = build_plan(manifest, "m008", False)
    assert [node.identifier for node in scoped_plan.nodes] == ["governance", "m008.case"]
    assert scoped_plan.partial is True
    full_plan = build_plan(manifest, None, False)
    assert [node.identifier for node in full_plan.nodes] == ["governance", "m008.case", "m013.live"]
    assert len({node.identifier for node in full_plan.nodes}) == len(full_plan.nodes)
    cyclic = GateManifest(
        root,
        root / "gate.toml",
        (
            GateNode("a", root / "a.py", "test", "m001", "tests", 10, "parallel", ("b",), False),
            GateNode("b", root / "b.py", "test", "m001", "tests", 10, "parallel", ("a",), False),
        ),
    )
    try:
        build_plan(cyclic, None, False)
    except PlanError as error:
        assert str(error).startswith("GATE_DEPENDENCY_CYCLE:")
    else:
        raise AssertionError("Un cycle doit être refusé.")
