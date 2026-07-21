"""Commande ``uv run backup-v1`` bornée à une installation explicite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.platform.administrative_operations import (
    AdministrativeBackupManifest,
    AdministrativeOperationEvidence,
    AdministrativeOperationRequest,
    execute_administrative_operation,
)
from app.platform.configuration import load_application_configuration
from app.platform.configured_datastore_identity import (
    build_configured_datastore_preflight,
    configured_datastore_identity,
)
from app.platform.datastore_identity import DatastoreIdentity
from ost_gate.operations.backup_manifest import read_backup_manifest


_FILE_ROOTS = (
    "data_root",
    "corpus_root",
    "canonical_sources_root",
    "qdrant_storage_root",
    "postgres_data_root",
    "reports_root",
    "logs_root",
    "experiments_root",
    "cache_root",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backup-v1")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args(argv)
    manifest = read_backup_manifest(arguments.manifest, "backup")
    configuration = load_application_configuration(
        config_path=arguments.config,
        environment_snapshot={},
    )
    identity = configured_datastore_identity(configuration)
    preflight = build_configured_datastore_preflight(
        configuration,
        include_postgres=True,
        include_qdrant=True,
        file_root_names=_FILE_ROOTS,
    )
    execute_administrative_operation(
        request=AdministrativeOperationRequest(
            operation="backup",
            target_identity=identity,
            automatic=False,
            lifecycle_id=None,
            lifecycle_owner_id=None,
            backup_manifest=AdministrativeBackupManifest(
                contract_version="M013-BackupManifest-1.0",
                manifest_id=manifest.manifest_id,
                environment=manifest.environment,
                deployment_id=manifest.deployment_id,
            ),
        ),
        observe_identity=lambda: _single_observed_identity(
            preflight.run(initialize_if_empty=False)
        ),
        mutate=lambda: manifest,
        record_audit=_print_audit,
    )
    print(
        f"Manifeste de sauvegarde V1 vérifié: {manifest.path} "
        f"({len(manifest.entries)} entrée(s) restaurable(s))"
    )
    return 0


def _single_observed_identity(
    observed: tuple[DatastoreIdentity, ...],
) -> DatastoreIdentity:
    if len(observed) == 0 or any(identity != observed[0] for identity in observed):
        raise ValueError("ADMINISTRATIVE_PREFLIGHT_INCOMPLETE")
    return observed[0]


def _print_audit(evidence: AdministrativeOperationEvidence) -> None:
    print(json.dumps(evidence.to_mapping(), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
