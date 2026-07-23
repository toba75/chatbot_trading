"""Consolidation live après la qualification d’isolation du profil test."""

from __future__ import annotations

from pathlib import Path


def test_environment_governance_live() -> None:
    from ost_gate.environment_governance import validate_repository_environment_governance

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )

    # La dépendance de ce nœud exécute test-isolation. Cette étape refuse donc
    # un rapport fonctionnel à un cycle, absent, collisionné ou sensible.
    evidence = validate_repository_environment_governance(
        repository_root=repository_root,
        require_live_sources=True,
    )
    assert evidence.source == "latest-live-reports"
    assert evidence.execution_count == 2
    assert evidence.worker_replica_count == 4
    assert evidence.matrix_cell_count == 9
    assert evidence.closure_status == "SUBMILESTONE_GREEN_M013_OPEN"
