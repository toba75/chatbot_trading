from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


def test_administrative_operations_unit() -> None:
    from app.platform.administrative_operations import (
        AdministrativeBackupManifest,
        AdministrativeOperationRequest,
    )
    from app.platform.datastore_identity import DatastoreIdentity

    identity = DatastoreIdentity(
        environment="development",
        deployment_id="ostrading-development-local",
    )
    manifest = AdministrativeBackupManifest.from_mapping(
        {
            "contract_version": "M013-BackupManifest-1.0",
            "manifest_id": "M013-BACKUP-DEVELOPMENT-UNIT",
            "environment": "development",
            "deployment_id": "ostrading-development-local",
        }
    )
    assert manifest.identity == identity
    assert manifest.to_mapping() == {
        "contract_version": "M013-BackupManifest-1.0",
        "manifest_id": "M013-BACKUP-DEVELOPMENT-UNIT",
        "environment": "development",
        "deployment_id": "ostrading-development-local",
    }
    with pytest.raises(FrozenInstanceError):
        manifest.environment = "test"  # type: ignore[misc]

    for invalid in (
        {},
        {
            "contract_version": "M013-BackupManifest-1.0",
            "manifest_id": "M013-BACKUP-DEVELOPMENT-UNIT",
            "environment": "development",
        },
        {
            "contract_version": "M013-BackupManifest-1.0",
            "manifest_id": "M013-BACKUP-DEVELOPMENT-UNIT",
            "environment": "development",
            "deployment_id": "ostrading-development-local",
            "profile": "development",
        },
    ):
        with pytest.raises(ValueError, match="ADMINISTRATIVE_BACKUP_MANIFEST_INVALID"):
            AdministrativeBackupManifest.from_mapping(invalid)

    for operation in ("migration", "backup", "purge"):
        request = AdministrativeOperationRequest(
            operation=operation,
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=None,
        )
        assert request.operation == operation

    with pytest.raises(ValueError, match="ADMINISTRATIVE_OPERATION_UNKNOWN"):
        AdministrativeOperationRequest(
            operation="reset",  # type: ignore[arg-type]
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=None,
        )
    with pytest.raises(ValueError, match="ADMINISTRATIVE_RESTORE_MANIFEST_REQUIRED"):
        AdministrativeOperationRequest(
            operation="restore",
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=None,
        )
    with pytest.raises(ValueError, match="ADMINISTRATIVE_BACKUP_MANIFEST_FORBIDDEN"):
        AdministrativeOperationRequest(
            operation="migration",
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=manifest,
        )
    with pytest.raises(ValueError, match="TEST_LIFECYCLE_ID_REQUIRED"):
        AdministrativeOperationRequest(
            operation="test_cleanup",
            target_identity=DatastoreIdentity(
                environment="test",
                deployment_id="ostrading-test-ci",
            ),
            automatic=True,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=None,
        )

