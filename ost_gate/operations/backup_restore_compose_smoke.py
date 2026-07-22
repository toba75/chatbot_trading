"""Smoke Compose borné du contrat d'archive chiffrée M013 1.1."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import secrets
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Final
from uuid import uuid4

from app.platform.environment_compose import (
    _compose_process_environment,
    _technical_environment_from_repository,
)
from ost_gate.operations.backup import execute_compose_storage_command
from ost_gate.operations.encrypted_archive import (
    BackupArchiveEntry,
    archive_entry_sha256,
    build_encrypted_archive,
)


_PROJECT: Final = "ostrading-test"
_ARTIFACTS: Final = (
    ("SP", "corpus_original", "SRC-SMOKE-001", True, True, False, False),
    ("SP", "canonical_versions", "CANON-SMOKE-001", True, True, False, False),
    ("KA", "qdrant_projection", "PROJ-SMOKE-001", False, False, True, False),
    ("EG", "claim_registry", "CLAIM-SMOKE-001", True, True, False, True),
    ("RA", "verified_answers", "ANSWER-SMOKE-001", True, True, False, True),
    ("CV", "conversation_turns", "TURN-SMOKE-001", True, True, False, False),
    ("SD", "strategy_snapshots", "STRATEGY-SMOKE-001", True, True, False, True),
    ("EX", "experiment_results", "EXPERIMENT-SMOKE-001", True, True, False, True),
    ("EV", "evaluation_reports", "EVALUATION-SMOKE-001", True, True, False, True),
    ("platform", "governance_artifacts", "GOVERNANCE-SMOKE-001", True, True, False, False),
)


def run_backup_restore_compose_smoke(*, repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve(strict=True)
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("DOCKER_UNAVAILABLE")
    base = root / "deploy/environments/compose.base.yaml"
    overlay = root / "deploy/environments/test.compose.yaml"
    config = root / "config/environments/test.yaml"
    _require_no_project_resources(docker=docker, repository_root=root)
    technical = _technical_environment_from_repository(root)
    process_environment = _compose_process_environment(technical)
    compose = (
        docker,
        "compose",
        "--project-name",
        _PROJECT,
        "--file",
        str(base),
        "--file",
        str(overlay),
    )
    report: dict[str, object] = {
        "valid_restore": "NOT_RUN",
        "altered_archive": "NOT_RUN",
        "wrong_key": "NOT_RUN",
        "cleanup_complete": False,
    }
    cleanup_required = True
    try:
        _run(
            (*compose, "up", "--detach", "--wait", "postgres", "qdrant"),
            cwd=root,
            environment=process_environment,
            timeout_seconds=240,
        )
        _run(
            (*compose, "build", "orchestrator-api"),
            cwd=root,
            environment=process_environment,
            timeout_seconds=600,
        )
        _initialize_profile_storage(
            compose=compose,
            repository_root=root,
            environment=process_environment,
        )
        with TemporaryDirectory(prefix="ostrading-backup-smoke-") as directory:
            material_root = Path(directory)
            key = secrets.token_bytes(32)
            entries = _smoke_entries()
            archive = build_encrypted_archive(
                entries=entries,
                encryption_key=key,
                nonce=secrets.token_bytes(12),
            )
            archive_path = material_root / "backup.m013.aesgcm"
            key_path = material_root / "backup.key"
            manifest_path = material_root / "manifest.json"
            archive_path.write_bytes(archive)
            key_path.write_bytes(key)
            _write_manifest(manifest_path, archive=archive, entries=entries)
            target = (
                root
                / "data/environments/test/reports/restore-drills"
                / f"compose-smoke-{uuid4().hex}"
            )
            execute_compose_storage_command(
                operation="backup",
                config_path=config,
                manifest_path=manifest_path,
                archive_path=archive_path,
                key_path=key_path,
                target_path=None,
            )
            execute_compose_storage_command(
                operation="restore",
                config_path=config,
                manifest_path=manifest_path,
                archive_path=archive_path,
                key_path=key_path,
                target_path=target,
            )
            _verify_restore_proof(
                compose=compose,
                target=target,
                repository_root=root,
                environment=process_environment,
            )
            report["valid_restore"] = "GREEN"

            altered = bytearray(archive)
            altered[-1] ^= 1
            altered_path = material_root / "altered.m013.aesgcm"
            altered_path.write_bytes(altered)
            _expect_compose_red(
                expected="ARCHIVE_CIPHERTEXT_HASH_MISMATCH",
                operation="backup",
                config_path=config,
                manifest_path=manifest_path,
                archive_path=altered_path,
                key_path=key_path,
                target_path=None,
            )
            report["altered_archive"] = "RED"

            wrong_key_path = material_root / "wrong.key"
            wrong_key_path.write_bytes(secrets.token_bytes(32))
            _expect_compose_red(
                expected="ARCHIVE_DECRYPTION_FAILED",
                operation="backup",
                config_path=config,
                manifest_path=manifest_path,
                archive_path=archive_path,
                key_path=wrong_key_path,
                target_path=None,
            )
            report["wrong_key"] = "RED"
    finally:
        if cleanup_required:
            _run(
                (*compose, "down", "--volumes", "--remove-orphans"),
                cwd=root,
                environment=process_environment,
                timeout_seconds=240,
            )
            _require_no_project_resources(docker=docker, repository_root=root)
            report["cleanup_complete"] = True
    return report


def _initialize_profile_storage(
    *,
    compose: tuple[str, ...],
    repository_root: Path,
    environment: dict[str, str] | object,
) -> None:
    source = (
        "from pathlib import Path; "
        "from app.platform.configuration import load_application_configuration; "
        "from app.platform.configured_datastore_identity import APPLICATION_FILE_ROOT_NAMES, build_configured_datastore_preflight; "
        "from app.platform.postgres_migrations import build_configured_postgres_migration_runner; "
        "c=load_application_configuration(config_path=Path('/workspace/config/application.yaml'), environment_snapshot={}); "
        "build_configured_datastore_preflight(c, include_postgres=True, include_qdrant=True, file_root_names=APPLICATION_FILE_ROOT_NAMES).run(initialize_if_empty=True); "
        "build_configured_postgres_migration_runner(c, initialize_identity_if_empty=False, adopt_legacy_if_unidentified=False).run()"
    )
    _run(
        (
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "--no-TTY",
            "--entrypoint",
            "python",
            "orchestrator-api",
            "-c",
            source,
        ),
        cwd=repository_root,
        environment=environment,
        timeout_seconds=240,
    )


def _verify_restore_proof(
    *,
    compose: tuple[str, ...],
    target: Path,
    repository_root: Path,
    environment: dict[str, str] | object,
) -> None:
    container_target = "/workspace/" + target.relative_to(repository_root).as_posix()
    source = (
        "from pathlib import Path; import json; "
        f"p=json.loads((Path({container_target!r})/'restore-proof.json').read_text(encoding='utf-8')); "
        "assert p['restore_test_result']=='GREEN'; assert p['verified_hashes'] is True; "
        "assert p['stable_identifiers_preserved'] is True; "
        "assert p['immutable_artifacts_preserved'] is True; "
        "assert p['negative_and_superseded_available'] is True"
    )
    _run(
        (
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "--no-TTY",
            "--entrypoint",
            "python",
            "orchestrator-api",
            "-c",
            source,
        ),
        cwd=repository_root,
        environment=environment,
        timeout_seconds=120,
    )


def _expect_compose_red(*, expected: str, **arguments: object) -> None:
    try:
        execute_compose_storage_command(**arguments)  # type: ignore[arg-type]
    except RuntimeError as error:
        if expected not in str(error):
            raise AssertionError(f"Erreur Compose inattendue: {error}") from error
        return
    raise AssertionError("L'opération Compose altérée devait être RED")


def _smoke_entries() -> tuple[BackupArchiveEntry, ...]:
    return tuple(
        BackupArchiveEntry(
            entry_id=f"SMOKE-{index:02d}",
            context=context,
            artifact_kind=artifact_kind,
            stable_identifier=stable_identifier,
            authority=authority,
            immutable=immutable,
            regenerable_projection=regenerable_projection,
            retained_negative_or_superseded=retained,
            payload=f"smoke-compose-{stable_identifier}".encode("utf-8"),
        )
        for index, (
            context,
            artifact_kind,
            stable_identifier,
            authority,
            immutable,
            regenerable_projection,
            retained,
        ) in enumerate(_ARTIFACTS, start=1)
    )


def _write_manifest(
    path: Path,
    *,
    archive: bytes,
    entries: tuple[BackupArchiveEntry, ...],
) -> None:
    document = {
        "contract_version": "M013-BackupManifest-1.1",
        "manifest_id": "M013-BACKUP-COMPOSE-SMOKE",
        "environment": "test",
        "deployment_id": "ostrading-test-ci",
        "backup_command": "uv run backup-v1 --manifest manifest.json --archive backup.m013.aesgcm --key-file <hors-depot> --config config/environments/test.yaml",
        "restore_command": "uv run restore-v1 --manifest manifest.json --archive backup.m013.aesgcm --key-file <hors-depot> --target data/environments/test/reports/restore-drills/smoke --config config/environments/test.yaml",
        "restore_target": "local_isolated",
        "archive_encrypted": True,
        "archive_format": "M013-AES256GCM-TAR-1.0",
        "ciphertext_sha256": sha256(archive).hexdigest(),
        "key_reference": "hors_depot://smoke/ephemere",
        "key_git_tracked": False,
        "complete": True,
        "entries": [
            {
                "entry_id": entry.entry_id,
                "context": entry.context,
                "artifact_kind": entry.artifact_kind,
                "stable_identifier": entry.stable_identifier,
                "archive_member": f"entries/{entry.entry_id}.json",
                "storage_host": "docker-local",
                "authority": entry.authority,
                "immutable": entry.immutable,
                "regenerable_projection": entry.regenerable_projection,
                "retained_negative_or_superseded": entry.retained_negative_or_superseded,
                "backup_sha256": archive_entry_sha256(entry),
                "contains_plain_secret": False,
                "git_tracked_key_material": False,
                "spark_business_storage": False,
                "destructive_restore": False,
            }
            for entry in entries
        ],
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_no_project_resources(*, docker: str, repository_root: Path) -> None:
    for resource, command in (
        (
            "containers",
            (docker, "ps", "--all", "--quiet", "--filter", f"label=com.docker.compose.project={_PROJECT}"),
        ),
        (
            "volumes",
            (docker, "volume", "ls", "--quiet", "--filter", f"label=com.docker.compose.project={_PROJECT}"),
        ),
    ):
        completed = subprocess.run(
            command,
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"BACKUP_SMOKE_RESOURCE_QUERY_FAILED:{resource}")
        if completed.stdout.strip():
            raise RuntimeError(f"BACKUP_SMOKE_TEST_RESOURCES_PRESENT:{resource}")


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: object,
    timeout_seconds: int,
) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,  # type: ignore[arg-type]
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"BACKUP_SMOKE_COMPOSE_FAILED:{completed.returncode}")


__all__ = ["run_backup_restore_compose_smoke"]
