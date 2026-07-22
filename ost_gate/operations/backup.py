"""Commande ``uv run backup-v1`` bornée à une installation explicite."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
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
    parser.add_argument("--inside-compose", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if not arguments.inside_compose:
        return execute_compose_storage_command(
            operation="backup",
            config_path=arguments.config,
            manifest_path=arguments.manifest,
            target_path=None,
        )
    manifest = read_backup_manifest(arguments.manifest, "backup")
    configuration = load_application_configuration(
        config_path=arguments.config,
        environment_snapshot=dict(os.environ),
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


def execute_compose_storage_command(
    *,
    operation: str,
    config_path: Path,
    manifest_path: Path,
    target_path: Path | None,
) -> int:
    """Exécute l'opération dans orchestrator-api, sur les DNS et volumes du profil."""

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
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("DOCKER_UNAVAILABLE")
    base = repository_root / "deploy/environments/compose.base.yaml"
    overlay = repository_root / f"deploy/environments/{environment}.compose.yaml"
    manifest_document = manifest_path.resolve(strict=True).read_bytes()
    temporary_manifest = f"/tmp/ostrading-{operation}-{uuid.uuid4().hex}.json"
    module = f"ost_gate.operations.{operation}"
    inner_arguments = [
        "--manifest",
        temporary_manifest,
        "--config",
        "/workspace/config/application.yaml",
        "--inside-compose",
    ]
    if operation == "restore":
        if target_path is None:
            raise ValueError("RESTORE_TARGET_REQUIRED")
        selected_target = require_profile_scoped_path(
            target=target_path,
            profile_root=(
                repository_root
                / configuration.paths.reports_root
                / "restore-drills"
            ),
        )
        inner_arguments.extend(
            ("--target", _container_workspace_path(selected_target, repository_root))
        )
    elif target_path is not None:
        raise ValueError("BACKUP_TARGET_FORBIDDEN")
    bootstrap = "\n".join(
        (
            "from pathlib import Path",
            "import importlib, sys",
            f"manifest_path = Path({temporary_manifest!r})",
            "manifest_path.write_bytes(sys.stdin.buffer.read())",
            "try:",
            f"    result = importlib.import_module({module!r}).main({inner_arguments!r})",
            "finally:",
            "    manifest_path.unlink()",
            "raise SystemExit(result)",
        )
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
        "exec",
        "--no-TTY",
        "orchestrator-api",
        "python",
        "-c",
        bootstrap,
    ]
    completed = subprocess.run(
        command,
        cwd=repository_root,
        input=manifest_document,
        check=False,
    )
    if completed.returncode != 0:
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
