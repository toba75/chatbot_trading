"""Commande ``uv run backup-v1`` : vérification d'une archive chiffrée existante."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

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
from app.platform.datastore_identity import DatastoreIdentity
from app.platform.environment_compose import (
    _compose_process_environment,
    _technical_environment_from_repository,
)
from ost_gate.operations.backup_manifest import (
    BACKUP_MANIFEST_CONTRACT_VERSION,
    read_backup_manifest,
    read_backup_manifest_bytes,
)
from ost_gate.operations.compose_transport import (
    COMPOSE_ERROR_EXIT_CODES,
    encode_compose_payload,
)
from ost_gate.operations.encrypted_archive import (
    load_archive_material,
    verify_encrypted_archive,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backup-v1")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inside-compose", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if not arguments.inside_compose:
        return execute_compose_storage_command(
            operation="backup",
            config_path=arguments.config,
            manifest_path=arguments.manifest,
            archive_path=arguments.archive,
            key_path=arguments.key_file,
            target_path=None,
        )
    manifest = read_backup_manifest(arguments.manifest, "backup")
    material = load_archive_material(
        archive_path=arguments.archive,
        key_path=arguments.key_file,
    )
    configuration = load_application_configuration(
        config_path=arguments.config,
        environment_snapshot=dict(os.environ),
    )
    identity = configured_datastore_identity(configuration)
    preflight = build_configured_datastore_preflight(
        configuration,
        include_postgres=True,
        include_qdrant=True,
        file_root_names=APPLICATION_FILE_ROOT_NAMES,
    )
    verified = execute_administrative_operation(
        request=AdministrativeOperationRequest(
            operation="backup",
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
        mutate=lambda: verify_encrypted_archive(manifest=manifest, material=material),
        record_audit=_print_audit,
    )
    print(
        f"Archive chiffrée V1 vérifiée: {manifest.path} "
        f"({len(verified.entries)} entrée(s) extraite(s) et vérifiée(s))"
    )
    return 0


def execute_compose_storage_command(
    *,
    operation: str,
    config_path: Path,
    manifest_path: Path,
    archive_path: Path,
    key_path: Path,
    target_path: Path | None,
) -> int:
    """Exécute l'opération dans un conteneur Compose du profil via stdin borné."""

    if operation not in {"backup", "restore"}:
        raise ValueError("ADMINISTRATIVE_OPERATION_UNKNOWN")
    selected_config = config_path.resolve(strict=True)
    repository_root = selected_config.parents[2]
    configuration = load_application_configuration(
        config_path=selected_config,
        environment_snapshot=dict(os.environ),
    )
    environment = configuration.application.environment
    expected_config = repository_root / "config" / "environments" / f"{environment}.yaml"
    if selected_config != expected_config.resolve(strict=True):
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH")
    selected_key = key_path.resolve(strict=True)
    try:
        selected_key.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ValueError("ARCHIVE_KEY_INSIDE_REPOSITORY")
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("DOCKER_UNAVAILABLE")
    base = repository_root / "deploy/environments/compose.base.yaml"
    overlay = repository_root / f"deploy/environments/{environment}.compose.yaml"
    material = load_archive_material(
        archive_path=archive_path.resolve(strict=True),
        key_path=selected_key,
    )
    manifest_document = read_backup_manifest_bytes(
        manifest_path.resolve(strict=True),
        label=operation,
    )
    payload = encode_compose_payload(
        manifest=manifest_document,
        archive=material.ciphertext,
        key=material.encryption_key,
    )
    if operation == "restore":
        if target_path is None:
            raise ValueError("RESTORE_TARGET_REQUIRED")
        selected_target = require_profile_scoped_path(
            target=target_path,
            profile_root=repository_root / configuration.paths.reports_root / "restore-drills",
        )
        container_target = _container_workspace_path(selected_target, repository_root)
    else:
        if target_path is not None:
            raise ValueError("BACKUP_TARGET_FORBIDDEN")
        container_target = None
    bootstrap = (
        "from ost_gate.operations.compose_transport import run_streamed_compose_operation; "
        f"raise SystemExit(run_streamed_compose_operation(operation={operation!r}, "
        "config_path='/workspace/config/application.yaml', "
        f"target_path={container_target!r}))"
    )
    command = [
        docker,
        "compose",
        "--project-name",
        f"ostrading-{environment}",
        "--file",
        str(base),
        "--file",
        str(overlay),
        "run",
        "--rm",
        "--build",
        "--no-deps",
        "--no-TTY",
        "--entrypoint",
        "python",
        "orchestrator-api",
        "-c",
        bootstrap,
    ]
    technical_environment = _technical_environment_from_repository(repository_root)
    completed = subprocess.run(
        command,
        cwd=repository_root,
        input=payload,
        check=False,
        env=_compose_process_environment(technical_environment),
    )
    if completed.returncode != 0:
        for error_code, exit_code in COMPOSE_ERROR_EXIT_CODES.items():
            if completed.returncode == exit_code:
                raise RuntimeError(error_code)
        raise RuntimeError(f"{operation.upper()}_COMPOSE_FAILED:{completed.returncode}")
    return 0


def _container_workspace_path(path: Path, repository_root: Path) -> str:
    selected = path.resolve(strict=False)
    try:
        relative = selected.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError("ADMINISTRATIVE_PATH_OUTSIDE_PROFILE") from exc
    return f"/workspace/{relative.as_posix()}"


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
