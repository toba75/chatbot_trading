from __future__ import annotations

import pytest


def test_administrative_operations_acceptance() -> None:
    from app.platform.administrative_operations import (
        ADMINISTRATIVE_OPERATION_FORBIDDEN,
        TEST_LIFECYCLE_OWNERSHIP_MISMATCH,
        AdministrativeBackupManifest,
        AdministrativeOperationError,
        AdministrativeOperationRequest,
        execute_administrative_operation,
    )
    from app.platform.datastore_identity import (
        DATASTORE_ENVIRONMENT_MISMATCH,
        DatastoreEnvironmentMismatchError,
        DatastoreIdentity,
    )

    test_identity = DatastoreIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
    )
    production_identity = DatastoreIdentity(
        environment="production",
        deployment_id="ostrading-production-primary",
    )
    audit: list[dict[str, str | None]] = []
    mutations: list[str] = []

    # Given un nettoyage test raccorde accidentellement un stockage production.
    cross_environment_cleanup = AdministrativeOperationRequest(
        operation="test_cleanup",
        target_identity=test_identity,
        automatic=True,
        lifecycle_id="test-lifecycle-acceptance",
        lifecycle_owner_id="test-lifecycle-acceptance",
        backup_manifest=None,
    )

    # When le preflight administratif compare la cible et l'identite observee.
    with pytest.raises(
        DatastoreEnvironmentMismatchError,
        match=DATASTORE_ENVIRONMENT_MISMATCH,
    ):
        execute_administrative_operation(
            request=cross_environment_cleanup,
            observe_identity=lambda: production_identity,
            mutate=lambda: mutations.append("cleanup"),
            record_audit=lambda evidence: audit.append(evidence.to_mapping()),
        )

    # Then aucune suppression n'a lieu et le refus stable reste auditable.
    assert mutations == []
    assert audit == [
        {
            "operation": "test_cleanup",
            "environment": "test",
            "deployment_id": "ostrading-test-ci",
            "decision": "refused",
            "error_code": DATASTORE_ENVIRONMENT_MISMATCH,
        }
    ]

    # Une restauration refuse un manifeste d'un autre environnement avant mutation.
    audit.clear()
    foreign_manifest = AdministrativeBackupManifest(
        contract_version="M013-BackupManifest-1.0",
        manifest_id="M013-BACKUP-PRODUCTION-ACCEPTANCE",
        environment="production",
        deployment_id="ostrading-production-primary",
    )
    with pytest.raises(
        DatastoreEnvironmentMismatchError,
        match=DATASTORE_ENVIRONMENT_MISMATCH,
    ):
        execute_administrative_operation(
            request=AdministrativeOperationRequest(
                operation="restore",
                target_identity=test_identity,
                automatic=False,
                lifecycle_id=None,
                lifecycle_owner_id=None,
                backup_manifest=foreign_manifest,
            ),
            observe_identity=lambda: test_identity,
            mutate=lambda: mutations.append("restore"),
            record_audit=lambda evidence: audit.append(evidence.to_mapping()),
        )
    assert mutations == []
    assert audit[0]["error_code"] == DATASTORE_ENVIRONMENT_MISMATCH

    # Aucun nettoyage automatique de production n'est autorise.
    audit.clear()
    with pytest.raises(AdministrativeOperationError, match=ADMINISTRATIVE_OPERATION_FORBIDDEN):
        execute_administrative_operation(
            request=AdministrativeOperationRequest(
                operation="test_cleanup",
                target_identity=production_identity,
                automatic=True,
                lifecycle_id="production-cleanup-forbidden",
                lifecycle_owner_id="production-cleanup-forbidden",
                backup_manifest=None,
            ),
            observe_identity=lambda: production_identity,
            mutate=lambda: mutations.append("production-cleanup"),
            record_audit=lambda evidence: audit.append(evidence.to_mapping()),
        )
    assert mutations == []
    assert audit[0]["error_code"] == ADMINISTRATIVE_OPERATION_FORBIDDEN

    # Seul le cycle test create/run/teardown qui possede la ressource peut la nettoyer.
    audit.clear()
    with pytest.raises(AdministrativeOperationError, match=TEST_LIFECYCLE_OWNERSHIP_MISMATCH):
        execute_administrative_operation(
            request=AdministrativeOperationRequest(
                operation="test_cleanup",
                target_identity=test_identity,
                automatic=True,
                lifecycle_id="test-lifecycle-acceptance",
                lifecycle_owner_id="other-lifecycle",
                backup_manifest=None,
            ),
            observe_identity=lambda: test_identity,
            mutate=lambda: mutations.append("foreign-cleanup"),
            record_audit=lambda evidence: audit.append(evidence.to_mapping()),
        )
    assert mutations == []

    audit.clear()
    result = execute_administrative_operation(
        request=cross_environment_cleanup,
        observe_identity=lambda: test_identity,
        mutate=lambda: mutations.append("owned-test-cleanup") or "cleanup-complete",
        record_audit=lambda evidence: audit.append(evidence.to_mapping()),
    )
    assert result == "cleanup-complete"
    assert mutations == ["owned-test-cleanup"]
    assert audit == [
        {
            "operation": "test_cleanup",
            "environment": "test",
            "deployment_id": "ostrading-test-ci",
            "decision": "authorized",
            "error_code": None,
        }
    ]

