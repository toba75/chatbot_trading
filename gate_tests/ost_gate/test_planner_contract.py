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
    assert [node.identifier for node in full_plan.nodes] == ["governance", "m008.case"]
    assert full_plan.offline is True
    activated_full_plan = build_plan(manifest, None, False, include_live=True)
    assert [node.identifier for node in activated_full_plan.nodes] == [
        "governance",
        "m008.case",
        "m013.live",
    ]
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

    acceptance = GateNode(
        "m013.acceptance",
        root / "acceptance.py",
        "test",
        "m013_environments",
        "tests",
        30,
        "parallel",
        (),
        False,
    )
    live = GateNode(
        "m013.live",
        root / "live.py",
        "test",
        "m013_environments",
        "live",
        30,
        "process",
        ("m013.acceptance",),
        True,
    )
    manifest = GateManifest(root, root / "gate.toml", (acceptance, live))

    standard_scope = build_plan(manifest, "m013_environments", False)
    assert [node.identifier for node in standard_scope.nodes] == ["m013.acceptance"]
    assert standard_scope.offline is True

    live_scope = build_plan(
        manifest,
        "m013_environments",
        False,
        include_live=True,
    )
    assert [node.identifier for node in live_scope.nodes] == [
        "m013.acceptance",
        "m013.live",
    ]
    assert live_scope.offline is False
