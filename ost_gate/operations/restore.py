"""Commande ``uv run restore-v1`` bornée à une archive vérifiée."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import uuid

from app.platform.administrative_operations import (
    AdministrativeBackupManifest,
    AdministrativeOperationEvidence,
    AdministrativeOperationRequest,
    execute_administrative_operation,
    require_profile_scoped_path,
)
from app.platform.configuration import load_application_configuration
from app.platform.configured_datastore_identity import (
    APPLICATION_FILE_ROOT_NAMES,
    build_configured_datastore_preflight,
    configured_datastore_identity,
)
from ost_gate.operations.backup import (
    _single_observed_identity,
    execute_compose_storage_command,
)
from ost_gate.operations.backup_manifest import (
    BACKUP_MANIFEST_CONTRACT_VERSION,
    BackupManifest,
    read_backup_manifest,
)
from ost_gate.operations.encrypted_archive import (
    VerifiedArchive,
    load_archive_material,
    verify_encrypted_archive,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restore-v1")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inside-compose", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if not arguments.inside_compose:
        return execute_compose_storage_command(
            operation="restore",
            config_path=arguments.config,
            manifest_path=arguments.manifest,
            archive_path=arguments.archive,
            key_path=arguments.key_file,
            target_path=arguments.target,
        )
    target = arguments.target.resolve(strict=False)
    if target.is_file() or (target.is_dir() and any(target.iterdir())):
        raise ValueError(f"RESTORE_TARGET_INVALID:{target}")
    manifest = read_backup_manifest(arguments.manifest, "restore")
    material = load_archive_material(
        archive_path=arguments.archive,
        key_path=arguments.key_file,
    )
    configuration = load_application_configuration(
        config_path=arguments.config,
        environment_snapshot=dict(os.environ),
    )
    target = require_profile_scoped_path(
        target=target,
        profile_root=Path(configuration.paths.reports_root) / "restore-drills",
    )
    identity = configured_datastore_identity(configuration)
    preflight = build_configured_datastore_preflight(
        configuration,
        include_postgres=True,
        include_qdrant=True,
        file_root_names=APPLICATION_FILE_ROOT_NAMES,
    )
    execute_administrative_operation(
        request=AdministrativeOperationRequest(
            operation="restore",
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=AdministrativeBackupManifest(
                contract_version=BACKUP_MANIFEST_CONTRACT_VERSION,
                manifest_id=manifest.manifest_id,
                environment=manifest.environment,
                deployment_id=manifest.deployment_id,
            ),
        ),
        observe_identity=lambda: _single_observed_identity(
            preflight.run(initialize_if_empty=False)
        ),
        mutate=lambda: restore_verified_archive(
            manifest=manifest,
            verified_archive=verify_encrypted_archive(
                manifest=manifest,
                material=material,
            ),
            target=target,
        ),
        record_audit=_print_audit,
    )
    print(
        f"Restauration V1 vérifiée: {manifest.path} -> {target} "
        f"({len(manifest.entries)} entrée(s))"
    )
    return 0


def restore_verified_archive(
    *,
    manifest: BackupManifest,
    verified_archive: VerifiedArchive,
    target: Path,
) -> None:
    """Matérialise les seuls octets authentifiés puis relit tous leurs hashes."""

    if not isinstance(manifest, BackupManifest) or not isinstance(verified_archive, VerifiedArchive):
        raise TypeError("RESTORE_VERIFIED_ARCHIVE_REQUIRED")
    if verified_archive.ciphertext_sha256 != manifest.ciphertext_sha256:
        raise ValueError("ARCHIVE_CIPHERTEXT_HASH_MISMATCH")
    staging = target.with_name(f"{target.name}.staging-{uuid.uuid4().hex}")
    try:
        entries_path = staging / "entries"
        entries_path.mkdir(parents=True)
        restored_hashes: dict[str, str] = {}
        for entry in verified_archive.entries:
            destination = entries_path / f"{entry.entry_id}.json"
            destination.write_bytes(entry.serialized_entry)
            restored_hash = sha256(destination.read_bytes()).hexdigest()
            if restored_hash != entry.sha256:
                raise ValueError("RESTORE_ENTRY_HASH_MISMATCH")
            restored_hashes[entry.entry_id] = restored_hash
        expected_ids = {entry["entry_id"] for entry in manifest.entries}
        if set(restored_hashes) != expected_ids:
            raise ValueError("RESTORE_ENTRY_SET_MISMATCH")
        proof = {
            "restore_test_result": "GREEN",
            "manifest_id": manifest.manifest_id,
            "environment": manifest.environment,
            "deployment_id": manifest.deployment_id,
            "ciphertext_sha256": verified_archive.ciphertext_sha256,
            "restored_entry_count": len(verified_archive.entries),
            "restored_hashes": restored_hashes,
            "stable_identifiers": [
                entry.stable_identifier for entry in verified_archive.entries
            ],
            "verified_hashes": True,
            "stable_identifiers_preserved": True,
            "immutable_artifacts_preserved": all(
                not item["immutable"]
                or restored_hashes[item["entry_id"]] == item["backup_sha256"]
                for item in manifest.entries
            ),
            "negative_and_superseded_available": all(
                any(
                    item["context"] == context
                    and item["retained_negative_or_superseded"]
                    for item in manifest.entries
                )
                for context in ("EG", "RA", "SD", "EX", "EV")
            ),
            "projections_regenerable_non_authority": all(
                not item["regenerable_projection"] or not item["authority"]
                for item in manifest.entries
            ),
            "destructive_restore_performed": False,
        }
        if not proof["immutable_artifacts_preserved"]:
            raise ValueError("RESTORE_IMMUTABLE_ARTIFACT_DIVERGENT")
        if not proof["negative_and_superseded_available"]:
            raise ValueError("RESTORE_RETENTION_INCOMPLETE")
        (staging / "restore-proof.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if target.exists():
            target.rmdir()
        staging.replace(target)
    except BaseException:
        try:
            if staging.exists():
                shutil.rmtree(staging)
        except OSError as compensation_error:
            raise RuntimeError("RESTORE_COMPENSATION_FAILED") from compensation_error
        raise


def _print_audit(evidence: AdministrativeOperationEvidence) -> None:
    print(json.dumps(evidence.to_mapping(), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "restore_verified_archive"]
