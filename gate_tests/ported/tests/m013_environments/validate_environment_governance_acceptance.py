"""Gate statique de traçabilité et d'étanchéité M13-environments."""

from __future__ import annotations

from pathlib import Path


def test_environment_governance_acceptance() -> None:
    from ost_gate.environment_governance import validate_repository_environment_governance

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )

    # Given les rapports réels ont été consolidés sans secret et les trois
    # configurations décrivent toutes leurs ressources mutables.
    # When la gate statique relie ADR, spécification, code, tests et runbook.
    evidence = validate_repository_environment_governance(
        repository_root=repository_root,
        require_live_sources=False,
    )

    # Then la matrice 3 x 3 et les six workers sont couverts, sans prétendre
    # clore le milestone M-013 global.
    assert evidence.environments == ("development", "test", "production")
    assert evidence.worker_names == (
        "worker-backtest",
        "worker-documents",
        "worker-projection",
        "worker-research",
    )
    assert evidence.worker_replica_count == 6
    assert evidence.matrix_cell_count == 9
    assert evidence.mutable_resource_count >= 30
    assert evidence.execution_count == 4
    assert evidence.closure_status == "SUBMILESTONE_GREEN_M013_OPEN"
    assert evidence.source == "versioned-live-evidence"

