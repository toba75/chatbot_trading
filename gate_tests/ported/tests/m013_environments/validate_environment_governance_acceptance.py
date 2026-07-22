"""Gate statique de traçabilité et d'étanchéité M13-environments."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest


def test_environment_governance_acceptance() -> None:
    from ost_gate.environment_governance import (
        EnvironmentGovernanceError,
        assert_no_sensitive_data,
        validate_execution_evidence,
        validate_repository_environment_governance,
    )

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

    # Then la matrice 3 x 3 et les quatre workers réels sont couverts, sans prétendre
    # clore le milestone M-013 global.
    assert evidence.environments == ("development", "test", "production")
    assert evidence.worker_names == (
        "worker-documents",
        "worker-projection",
    )
    assert evidence.worker_replica_count == 4
    assert evidence.matrix_cell_count == 9
    assert evidence.mutable_resource_count >= 30
    assert evidence.execution_count == 4
    assert evidence.closure_status == "SUBMILESTONE_GREEN_M013_OPEN"
    assert evidence.source == "versioned-live-evidence"

    versioned = json.loads(
        (
            repository_root
            / "docs"
            / "governance"
            / "m013_environments_execution_evidence.json"
        ).read_text(encoding="utf-8")
    )["reports"]
    missing = deepcopy(versioned)
    del missing["production"]
    with pytest.raises(EnvironmentGovernanceError, match="LIVE_EVIDENCE_MISSING:production"):
        validate_execution_evidence(missing, expected_worker_identity_count=6)
    collision = deepcopy(versioned)
    collision["production"]["answer_id"] = versioned["development"]["answer_id"]
    with pytest.raises(EnvironmentGovernanceError, match="EVIDENCE_ID_COLLISION"):
        validate_execution_evidence(collision, expected_worker_identity_count=6)
    sensitive = deepcopy(versioned)
    sensitive["test"]["password"] = "interdit"
    with pytest.raises(EnvironmentGovernanceError, match="SENSITIVE_EVIDENCE_REJECTED"):
        assert_no_sensitive_data(sensitive)
