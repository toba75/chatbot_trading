"""Bornage strict des migrations, sauvegardes, restaurations et nettoyages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Final, Literal

from app.platform.datastore_identity import (
    DATASTORE_ENVIRONMENT_MISMATCH,
    DatastoreEnvironmentMismatchError,
    DatastoreIdentity,
)


AdministrativeOperation = Literal[
    "migration",
    "backup",
    "restore",
    "purge",
    "test_cleanup",
]
AdministrativeDecision = Literal["authorized", "refused"]

ADMINISTRATIVE_OPERATION_FORBIDDEN: Final = "ADMINISTRATIVE_OPERATION_FORBIDDEN"
TEST_LIFECYCLE_OWNERSHIP_MISMATCH: Final = "TEST_LIFECYCLE_OWNERSHIP_MISMATCH"
_BACKUP_CONTRACT_VERSION: Final = "M013-BackupManifest-1.0"
_OPERATIONS: Final = frozenset(
    ("migration", "backup", "restore", "purge", "test_cleanup")
)
_MANIFEST_KEYS: Final = frozenset(
    ("contract_version", "manifest_id", "environment", "deployment_id")
)
_MANIFEST_ID: Final = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


class AdministrativeOperationError(RuntimeError):
    """Refus stable d'une opération avant son premier effet."""

    def __init__(self, code: str) -> None:
        if code not in {
            ADMINISTRATIVE_OPERATION_FORBIDDEN,
            TEST_LIFECYCLE_OWNERSHIP_MISMATCH,
        }:
            raise ValueError("ADMINISTRATIVE_ERROR_CODE_INVALID")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AdministrativeBackupManifest:
    """Identité obligatoire d'un manifeste utilisable par une opération."""

    contract_version: str
    manifest_id: str
    environment: str
    deployment_id: str

    def __post_init__(self) -> None:
        if self.contract_version != _BACKUP_CONTRACT_VERSION:
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_INVALID")
        if (
            not isinstance(self.manifest_id, str)
            or _MANIFEST_ID.fullmatch(self.manifest_id) is None
        ):
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_INVALID")
        try:
            DatastoreIdentity(
                environment=self.environment,
                deployment_id=self.deployment_id,
            )
        except DatastoreEnvironmentMismatchError as exc:
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_INVALID") from exc

    @classmethod
    def from_mapping(cls, payload: object) -> AdministrativeBackupManifest:
        if not isinstance(payload, Mapping) or frozenset(payload) != _MANIFEST_KEYS:
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_INVALID")
        try:
            return cls(
                contract_version=payload["contract_version"],
                manifest_id=payload["manifest_id"],
                environment=payload["environment"],
                deployment_id=payload["deployment_id"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_INVALID") from exc

    @property
    def identity(self) -> DatastoreIdentity:
        return DatastoreIdentity(
            environment=self.environment,
            deployment_id=self.deployment_id,
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "contract_version": self.contract_version,
            "manifest_id": self.manifest_id,
            "environment": self.environment,
            "deployment_id": self.deployment_id,
        }


@dataclass(frozen=True, slots=True)
class AdministrativeOperationRequest:
    """Commande complète, sans cible ni propriété implicite."""

    operation: AdministrativeOperation
    target_identity: DatastoreIdentity
    automatic: bool
    lifecycle_id: str | None
    lifecycle_owner_id: str | None
    backup_manifest: AdministrativeBackupManifest | None

    def __post_init__(self) -> None:
        if self.operation not in _OPERATIONS:
            raise ValueError("ADMINISTRATIVE_OPERATION_UNKNOWN")
        if not isinstance(self.target_identity, DatastoreIdentity):
            raise ValueError("ADMINISTRATIVE_TARGET_IDENTITY_INVALID")
        if not isinstance(self.automatic, bool):
            raise ValueError("ADMINISTRATIVE_AUTOMATIC_FLAG_INVALID")
        if self.operation in {"backup", "restore"}:
            if not isinstance(self.backup_manifest, AdministrativeBackupManifest):
                code = (
                    "ADMINISTRATIVE_BACKUP_MANIFEST_REQUIRED"
                    if self.operation == "backup"
                    else "ADMINISTRATIVE_RESTORE_MANIFEST_REQUIRED"
                )
                raise ValueError(code)
        elif self.backup_manifest is not None:
            raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_FORBIDDEN")
        if self.operation == "test_cleanup":
            for value in (self.lifecycle_id, self.lifecycle_owner_id):
                if not isinstance(value, str) or value.strip() == "" or value != value.strip():
                    raise ValueError("TEST_LIFECYCLE_ID_REQUIRED")
        elif self.lifecycle_id is not None or self.lifecycle_owner_id is not None:
            raise ValueError("TEST_LIFECYCLE_ID_FORBIDDEN")


@dataclass(frozen=True, slots=True)
class AdministrativeOperationEvidence:
    """Preuve enregistrée avant mutation ou lors d'un refus."""

    operation: AdministrativeOperation
    identity: DatastoreIdentity
    decision: AdministrativeDecision
    error_code: str | None

    def __post_init__(self) -> None:
        if self.operation not in _OPERATIONS:
            raise ValueError("ADMINISTRATIVE_OPERATION_UNKNOWN")
        if not isinstance(self.identity, DatastoreIdentity):
            raise ValueError("ADMINISTRATIVE_TARGET_IDENTITY_INVALID")
        if self.decision == "authorized":
            if self.error_code is not None:
                raise ValueError("ADMINISTRATIVE_EVIDENCE_INVALID")
        elif self.decision == "refused":
            if not isinstance(self.error_code, str) or self.error_code.strip() == "":
                raise ValueError("ADMINISTRATIVE_EVIDENCE_INVALID")
        else:
            raise ValueError("ADMINISTRATIVE_EVIDENCE_INVALID")

    def to_mapping(self) -> dict[str, str | None]:
        return {
            "operation": self.operation,
            "environment": self.identity.environment,
            "deployment_id": self.identity.deployment_id,
            "decision": self.decision,
            "error_code": self.error_code,
        }


def execute_administrative_operation(
    *,
    request: AdministrativeOperationRequest,
    observe_identity: Callable[[], DatastoreIdentity],
    mutate: Callable[[], Any],
    record_audit: Callable[[AdministrativeOperationEvidence], None],
) -> Any:
    """Vérifie identité et politique avant le premier appel de mutation."""

    if not isinstance(request, AdministrativeOperationRequest):
        raise ValueError("ADMINISTRATIVE_REQUEST_INVALID")
    for callback in (observe_identity, mutate, record_audit):
        if not callable(callback):
            raise ValueError("ADMINISTRATIVE_CALLBACK_INVALID")

    try:
        observed_identity = observe_identity()
        request.target_identity.require_match(observed_identity)
        if request.operation in {"backup", "restore"}:
            manifest = request.backup_manifest
            if not isinstance(manifest, AdministrativeBackupManifest):
                raise ValueError("ADMINISTRATIVE_BACKUP_MANIFEST_REQUIRED")
            request.target_identity.require_match(manifest.identity)
    except DatastoreEnvironmentMismatchError:
        _record_refusal(
            request=request,
            error_code=DATASTORE_ENVIRONMENT_MISMATCH,
            record_audit=record_audit,
        )
        raise

    try:
        _require_operation_policy(request)
    except AdministrativeOperationError as exc:
        _record_refusal(
            request=request,
            error_code=exc.code,
            record_audit=record_audit,
        )
        raise

    record_audit(
        AdministrativeOperationEvidence(
            operation=request.operation,
            identity=request.target_identity,
            decision="authorized",
            error_code=None,
        )
    )
    return mutate()


def require_profile_scoped_path(*, target: Path, profile_root: Path) -> Path:
    """Refuse la racine elle-même et tout chemin extérieur au profil."""

    if not isinstance(target, Path) or not isinstance(profile_root, Path):
        raise ValueError("ADMINISTRATIVE_TARGET_PATH_MISMATCH")
    resolved_target = target.resolve(strict=False)
    resolved_root = profile_root.resolve(strict=False)
    try:
        relative_target = resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("ADMINISTRATIVE_TARGET_PATH_MISMATCH") from exc
    if len(relative_target.parts) == 0:
        raise ValueError("ADMINISTRATIVE_TARGET_PATH_MISMATCH")
    return resolved_target


def _require_operation_policy(request: AdministrativeOperationRequest) -> None:
    if request.operation == "test_cleanup":
        if request.target_identity.environment != "test" or request.automatic is not True:
            raise AdministrativeOperationError(ADMINISTRATIVE_OPERATION_FORBIDDEN)
        if request.lifecycle_id != request.lifecycle_owner_id:
            raise AdministrativeOperationError(TEST_LIFECYCLE_OWNERSHIP_MISMATCH)
    if request.operation == "purge" and request.automatic:
        raise AdministrativeOperationError(ADMINISTRATIVE_OPERATION_FORBIDDEN)


def _record_refusal(
    *,
    request: AdministrativeOperationRequest,
    error_code: str,
    record_audit: Callable[[AdministrativeOperationEvidence], None],
) -> None:
    record_audit(
        AdministrativeOperationEvidence(
            operation=request.operation,
            identity=request.target_identity,
            decision="refused",
            error_code=error_code,
        )
    )


__all__ = [
    "ADMINISTRATIVE_OPERATION_FORBIDDEN",
    "TEST_LIFECYCLE_OWNERSHIP_MISMATCH",
    "AdministrativeBackupManifest",
    "AdministrativeOperationError",
    "AdministrativeOperationEvidence",
    "AdministrativeOperationRequest",
    "execute_administrative_operation",
    "require_profile_scoped_path",
]
