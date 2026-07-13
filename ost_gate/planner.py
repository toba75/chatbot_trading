"""Planificateur déterministe de dépendances de la gate."""

from __future__ import annotations

from collections import defaultdict

from ost_gate.errors import PlanError
from ost_gate.models import GateManifest, GateNode, GatePlan


def build_plan(manifest: GateManifest, scope: str | None, offline: bool) -> GatePlan:
    """Construit un plan DAG complet ou explicitement partiel."""

    nodes_by_id = {node.identifier: node for node in manifest.nodes}
    _assert_acyclic(nodes_by_id)
    selected = _select_nodes(nodes_by_id, scope, offline)
    selected_ids = frozenset(selected)
    for node in selected.values():
        missing = [dependency for dependency in node.depends_on if dependency not in selected_ids]
        if missing:
            raise PlanError(f"GATE_NODE_DEPENDENCY_EXCLUDED:{node.identifier}:{','.join(sorted(missing))}")
    levels = _topological_levels(selected)
    ordered = tuple(node for level in levels for node in level)
    return GatePlan(
        repository_root=manifest.repository_root,
        nodes=ordered,
        levels=tuple(tuple(level) for level in levels),
        partial=scope is not None or offline,
        scope=scope,
        offline=offline,
    )


def _assert_acyclic(nodes_by_id: dict[str, GateNode]) -> None:
    permanent: set[str] = set()
    visiting: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in permanent:
            return
        if identifier in visiting:
            raise PlanError(f"GATE_DEPENDENCY_CYCLE:{identifier}")
        visiting.add(identifier)
        for dependency in nodes_by_id[identifier].depends_on:
            visit(dependency)
        visiting.remove(identifier)
        permanent.add(identifier)

    for identifier in sorted(nodes_by_id):
        visit(identifier)


def _select_nodes(
    nodes_by_id: dict[str, GateNode], scope: str | None, offline: bool
) -> dict[str, GateNode]:
    if scope is None:
        requested = set(nodes_by_id)
    else:
        requested = {node.identifier for node in nodes_by_id.values() if node.scope == scope}
        if not requested:
            raise PlanError(f"GATE_SCOPE_UNKNOWN:{scope}")
    if offline:
        requested = {identifier for identifier in requested if not nodes_by_id[identifier].live}
    selected: set[str] = set()

    def include(identifier: str) -> None:
        if identifier in selected:
            return
        node = nodes_by_id[identifier]
        if offline and node.live:
            return
        selected.add(identifier)
        for dependency in node.depends_on:
            include(dependency)

    for identifier in sorted(requested):
        include(identifier)
    if not selected:
        raise PlanError("GATE_PLAN_EMPTY")
    return {identifier: nodes_by_id[identifier] for identifier in selected}


def _topological_levels(nodes_by_id: dict[str, GateNode]) -> list[tuple[GateNode, ...]]:
    indegree = {identifier: 0 for identifier in nodes_by_id}
    children: dict[str, list[str]] = defaultdict(list)
    for node in nodes_by_id.values():
        for dependency in node.depends_on:
            indegree[node.identifier] += 1
            children[dependency].append(node.identifier)
    ready = sorted(identifier for identifier, count in indegree.items() if count == 0)
    levels: list[tuple[GateNode, ...]] = []
    seen = 0
    while ready:
        current_ids = ready
        ready = []
        current = tuple(nodes_by_id[identifier] for identifier in current_ids)
        levels.append(current)
        seen += len(current)
        for identifier in current_ids:
            for child in sorted(children[identifier]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        ready.sort()
    if seen != len(nodes_by_id):
        raise PlanError("GATE_DEPENDENCY_CYCLE")
    return levels
