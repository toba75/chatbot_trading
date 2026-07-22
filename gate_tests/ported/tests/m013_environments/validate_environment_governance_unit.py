"""Décisions unitaires de la clôture M13-environments."""

from __future__ import annotations

from copy import deepcopy

import pytest


def _report(environment: str) -> dict[str, object]:
    deployment_ids = {
        "development": "ostrading-development-local",
        "test": "ostrading-test-ci",
        "production": "ostrading-production-primary",
    }
    prefix = environment.upper()
    common: dict[str, object] = {
        "completed_at": "2026-07-22T03:02:53Z",
        "configuration_hash": {
            "development": "1" * 64,
            "test": "2" * 64,
            "production": "3" * 64,
        }[environment],
        "deployment_id": deployment_ids[environment],
        "environment": environment,
        "image_revision": "a" * 40,
        "source_pdf_path": "data/corpus/the-original-turtle-trading-rules.pdf",
        "source_pdf_sha256": "0" * 64,
    }
    if environment == "test":
        return {
            **common,
            "foreign_volume_sentinels_preserved": True,
            "non_test_credentials_inaccessible": True,
            "test_resources_removed": True,
            "runs": [
                {
                    "run_number": number,
                    "proof_id": f"PROOF-{number}",
                    "document_id": f"DOC-{prefix}-{number}",
                    "canonical_version_id": f"CVER-{prefix}-{number}",
                    "projection_id": f"PROJ-{prefix}-{number}",
                    "answer_id": f"ANS-{prefix}-{number}",
                    "spark_raw_response_id": f"chatcmpl-{prefix}-{number}",
                    "pdf_sha256": str(number) * 64,
                    "progress_phases": ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"],
                    "worker_identity_count": 6,
                    "environment_job_count": 3,
                    "citation_url": "https://localhost:19443/api/v1/documents/x/original#page=1",
                    "non_test_credentials_inaccessible": True,
                }
                for number in (1, 2)
            ],
        }
    report = {
        **common,
        "document_id": f"DOC-{prefix}",
        "canonical_version_id": f"CVER-{prefix}",
        "projection_id": f"PROJ-{prefix}",
        "answer_id": f"ANS-{prefix}",
        "spark_raw_response_id": f"chatcmpl-{prefix}",
        "pdf_sha256": {"development": "4" * 64, "production": "5" * 64}[environment],
        "progress_phases": ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"],
        "worker_identity_count": 6,
        "environment_job_count": 3,
        "restart_persistence_verified": True,
    }
    if environment == "development":
        report.update(
            foreign_environment_probes=["test:ABSENT", "production:ABSENT"],
            volume_sentinels_preserved=True,
            citation_url="https://localhost:18443/api/v1/documents/x/original#page=1",
        )
    else:
        report.update(
            foreign_environment_probes=["development:ABSENT", "test:ABSENT"],
            production_resources_preserved=True,
            automatic_cleanup_performed=False,
            non_production_credentials_inaccessible=True,
            citation_url="https://localhost:20443/api/v1/documents/x/original#page=1",
        )
    return report


def test_environment_governance_unit() -> None:
    from ost_gate.environment_governance import (
        EnvironmentGovernanceError,
        assert_no_sensitive_data,
        build_isolation_access_matrix,
        validate_closure_status,
        validate_execution_evidence,
    )

    reports = {environment: _report(environment) for environment in (
        "development",
        "test",
        "production",
    )}

    # Given quatre exécutions réelles couvrent les trois profils.
    # When la gouvernance consolide les preuves et la matrice d'accès 3 x 3.
    evidence = validate_execution_evidence(reports)

    # Then toutes les identités restent distinctes et M-013 reste ouvert.
    assert evidence.environments == ("development", "test", "production")
    assert evidence.execution_count == 4
    assert evidence.worker_identity_count == 24
    assert build_isolation_access_matrix(evidence.environments) == {
        "development": {
            "development": "OWNED",
            "test": "FORBIDDEN",
            "production": "FORBIDDEN",
        },
        "test": {
            "development": "FORBIDDEN",
            "test": "OWNED",
            "production": "FORBIDDEN",
        },
        "production": {
            "development": "FORBIDDEN",
            "test": "FORBIDDEN",
            "production": "OWNED",
        },
    }
    assert validate_closure_status("SUBMILESTONE_GREEN_M013_OPEN") == (
        "SUBMILESTONE_GREEN_M013_OPEN"
    )

    collided = deepcopy(reports)
    collided["production"]["document_id"] = reports["development"]["document_id"]
    with pytest.raises(EnvironmentGovernanceError, match="EVIDENCE_ID_COLLISION"):
        validate_execution_evidence(collided)

    missing = deepcopy(reports)
    del missing["test"]
    with pytest.raises(EnvironmentGovernanceError, match="LIVE_EVIDENCE_MISSING:test"):
        validate_execution_evidence(missing)

    secret = deepcopy(reports)
    secret["development"]["api_token"] = "token-versionne-interdit"
    with pytest.raises(EnvironmentGovernanceError, match="SENSITIVE_EVIDENCE_REJECTED"):
        assert_no_sensitive_data(secret)

    with pytest.raises(EnvironmentGovernanceError, match="M013_GLOBAL_CLOSURE_FORBIDDEN"):
        validate_closure_status("M013_CLOSED")

