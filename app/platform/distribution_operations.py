"""Commande publique de bascule et rollback du socle M14-distribution-core."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import time
from typing import Final, Protocol

from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.environment_compose import (
    ENVIRONMENTS,
    REQUIRED_SERVICE_IDS,
    EnvironmentStackDefinition,
    environment_stack_definition,
    run_environment_compose_command,
    technical_environment_from_repository,
)


PUBLIC_SERVICE_IDS = ("ui", "edge-gateway")
INTERNAL_SERVICE_IDS: Final = tuple(
    service_id
    for service_id in REQUIRED_SERVICE_IDS
    if service_id not in PUBLIC_SERVICE_IDS
)
_APPLICATION_CONFIGURATION_TARGET = "/workspace/config/application.yaml"
_CONFIGURED_SERVICE_IDS: Final = tuple(
    service_id
    for service_id in REQUIRED_SERVICE_IDS
    if service_id not in {"edge-gateway", "postgres", "qdrant", "ocr-runtime"}
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")

_DRAIN_INVENTORY_SQL = """
SELECT json_build_object(
    'technical_jobs', (
        SELECT COUNT(*) FROM platform.technical_jobs
         WHERE environment = :'environment'
           AND deployment_id = :'deployment_id'
           AND configuration_hash = :'configuration_hash'
           AND status IN ('pending', 'running')
    ),
    'source_processing_outbox', (
        SELECT COUNT(*) FROM source_processing.job_outbox
         WHERE environment = :'environment'
           AND deployment_id = :'deployment_id'
           AND configuration_hash = :'configuration_hash'
           AND status IN ('pending', 'relaying')
    ),
    'knowledge_access_outbox', (
        SELECT COUNT(*) FROM knowledge_access.job_outbox
         WHERE environment = :'environment'
           AND deployment_id = :'deployment_id'
           AND configuration_hash = :'configuration_hash'
           AND status IN ('pending', 'relaying')
    )
);
""".strip()

_READY_WORKERS_SQL = """
SELECT COUNT(*)
  FROM platform.document_workers
 WHERE environment = :'environment'
   AND deployment_id = :'deployment_id'
   AND configuration_hash = :'configuration_hash'
   AND state = 'READY'
   AND drain_deadline IS NULL
   AND presence_lease_until > CURRENT_TIMESTAMP;
""".strip()

_BEGIN_DRAINING_SQL = """
WITH draining_workers AS (
    UPDATE platform.document_workers
       SET state = 'DRAINING',
           drain_deadline = CURRENT_TIMESTAMP
               + make_interval(secs => :'deadline_seconds'::integer),
           presence_lease_until = LEAST(
               presence_lease_until,
               CURRENT_TIMESTAMP
                   + make_interval(secs => :'deadline_seconds'::integer)
           ),
           updated_at = CURRENT_TIMESTAMP
     WHERE environment = :'environment'
       AND deployment_id = :'deployment_id'
       AND configuration_hash = :'configuration_hash'
       AND state = 'READY'
    RETURNING worker_instance_id, drain_deadline
), bounded_jobs AS (
    UPDATE platform.technical_jobs AS job
       SET lease_expires_at = LEAST(job.lease_expires_at, worker.drain_deadline)
      FROM draining_workers AS worker
     WHERE job.environment = :'environment'
       AND job.deployment_id = :'deployment_id'
       AND job.configuration_hash = :'configuration_hash'
       AND job.status = 'running'
       AND job.lease_owner = worker.worker_instance_id
    RETURNING job.job_id
), bounded_slots AS (
    UPDATE platform.granite_slots AS slot
       SET lease_until = LEAST(slot.lease_until, worker.drain_deadline),
           updated_at = CURRENT_TIMESTAMP
      FROM draining_workers AS worker
     WHERE slot.environment = :'environment'
       AND slot.deployment_id = :'deployment_id'
       AND slot.lease_owner = worker.worker_instance_id
    RETURNING slot.slot_ordinal
)
SELECT COUNT(*) FROM draining_workers;
""".strip()

_ROLLBACK_INVENTORY_SQL = """
SELECT json_build_object(
    'active_jobs', (
        SELECT COUNT(*) FROM platform.technical_jobs
         WHERE environment = :'environment'
           AND deployment_id = :'deployment_id'
           AND configuration_hash = :'configuration_hash'
           AND status = 'running'
           AND lease_expires_at > CURRENT_TIMESTAMP
    ),
    'active_slots', (
        SELECT COUNT(*)
          FROM platform.granite_slots AS slot
          JOIN platform.technical_jobs AS job ON job.job_id = slot.job_id
         WHERE slot.environment = :'environment'
           AND slot.deployment_id = :'deployment_id'
           AND job.configuration_hash = :'configuration_hash'
           AND slot.lease_until > CURRENT_TIMESTAMP
    )
);
""".strip()

_SCHEMA_022_SQL = """
SELECT COUNT(*)
  FROM platform.schema_migrations
 WHERE version = 22
   AND filename = '022_granite_quota_and_page_results.sql'
   AND to_regclass('platform.document_workers') IS NOT NULL
   AND to_regclass('platform.granite_slots') IS NOT NULL
   AND to_regclass('platform.page_completion_outbox') IS NOT NULL;
""".strip()


@dataclass(frozen=True, slots=True)
class DistributionReleaseIdentity:
    revision: str
    schema_version: str
    configuration_hash: str

    def __post_init__(self) -> None:
        if _REVISION.fullmatch(self.revision) is None:
            raise ValueError("DISTRIBUTION_REVISION_INVALID")
        if self.schema_version != "022":
            raise ValueError("DISTRIBUTION_SCHEMA_022_REQUIRED")
        if _SHA256.fullmatch(self.configuration_hash) is None:
            raise ValueError("DISTRIBUTION_CONFIGURATION_HASH_INVALID")

    def technical_environment(self) -> Mapping[str, str]:
        return {
            "OSTRADING_IMAGE_REVISION": self.revision,
            "OSTRADING_POSTGRES_SCHEMA_VERSION": self.schema_version,
        }

    def to_mapping(self) -> dict[str, str]:
        return {
            "revision": self.revision,
            "schema_version": self.schema_version,
            "configuration_hash": self.configuration_hash,
        }


@dataclass(frozen=True, slots=True)
class DistributionDrainInventory:
    technical_jobs: int
    source_processing_outbox: int
    knowledge_access_outbox: int

    def __post_init__(self) -> None:
        _require_counts(
            self.technical_jobs,
            self.source_processing_outbox,
            self.knowledge_access_outbox,
        )

    @property
    def total(self) -> int:
        return (
            self.technical_jobs
            + self.source_processing_outbox
            + self.knowledge_access_outbox
        )


@dataclass(frozen=True, slots=True)
class DistributionRollbackInventory:
    active_jobs: int
    active_slots: int

    def __post_init__(self) -> None:
        _require_counts(self.active_jobs, self.active_slots)

    @property
    def total(self) -> int:
        return self.active_jobs + self.active_slots


class DistributionOperations(Protocol):
    def close_public(self) -> None: ...

    def read_drain_inventory(
        self, configuration_hash: str
    ) -> DistributionDrainInventory: ...

    def start_internal(self, release: DistributionReleaseIdentity) -> None: ...

    def live_ready_worker_count(self, configuration_hash: str) -> int: ...

    def activate_public(self, release: DistributionReleaseIdentity) -> None: ...

    def begin_draining(
        self, configuration_hash: str, deadline_seconds: int
    ) -> None: ...

    def read_rollback_inventory(
        self, configuration_hash: str
    ) -> DistributionRollbackInventory: ...

    def verify_schema_022_retained(self) -> None: ...

    def stop_internal(self) -> None: ...

    def verify_release(self, release: DistributionReleaseIdentity) -> None: ...


class DistributionCoreController:
    """Applique l'ordre fermé prepare/activate/rollback sans fallback."""

    def __init__(
        self,
        *,
        operations: DistributionOperations,
        sleep: Callable[[float], None],
    ) -> None:
        if not callable(sleep):
            raise ValueError("DISTRIBUTION_SLEEP_INVALID")
        self._operations = operations
        self._sleep = sleep

    def prepare(
        self,
        *,
        current: DistributionReleaseIdentity,
        previous_configuration_hash: str,
        timeout_seconds: int,
        poll_seconds: int,
    ) -> None:
        _require_hash(previous_configuration_hash)
        attempts = _attempt_count(timeout_seconds, poll_seconds)
        self._operations.close_public()
        try:
            self._wait_until_zero(
                read=lambda: (
                    self._operations.read_drain_inventory(
                        previous_configuration_hash
                    ).total
                ),
                attempts=attempts,
                poll_seconds=poll_seconds,
                error_code="DISTRIBUTION_DRAIN_TIMEOUT",
            )
            self._operations.start_internal(current)
            self._require_two_ready(current.configuration_hash)
        except Exception:
            self._operations.close_public()
            raise

    def activate(self, *, current: DistributionReleaseIdentity) -> None:
        self._operations.close_public()
        try:
            self._require_two_ready(current.configuration_hash)
            self._operations.activate_public(current)
        except Exception:
            self._operations.close_public()
            raise

    def rollback(
        self,
        *,
        current: DistributionReleaseIdentity,
        previous: DistributionReleaseIdentity,
        drain_deadline_seconds: int,
        timeout_seconds: int,
        poll_seconds: int,
    ) -> None:
        deadline = _require_positive_integer(
            drain_deadline_seconds, "DISTRIBUTION_DRAIN_DEADLINE_INVALID"
        )
        attempts = _attempt_count(timeout_seconds, poll_seconds)
        self._operations.close_public()
        try:
            self._operations.begin_draining(current.configuration_hash, deadline)
            self._wait_until_zero(
                read=lambda: (
                    self._operations.read_rollback_inventory(
                        current.configuration_hash
                    ).total
                ),
                attempts=attempts,
                poll_seconds=poll_seconds,
                error_code="DISTRIBUTION_ROLLBACK_DRAIN_TIMEOUT",
            )
            self._operations.verify_schema_022_retained()
            self._operations.stop_internal()
            self._operations.start_internal(previous)
            self._require_two_ready(previous.configuration_hash)
            self._operations.verify_release(previous)
            self._operations.activate_public(previous)
        except Exception:
            self._operations.close_public()
            raise

    def _require_two_ready(self, configuration_hash: str) -> None:
        count = self._operations.live_ready_worker_count(configuration_hash)
        if count != 2:
            raise ValueError(f"DISTRIBUTION_READY_WORKERS_INVALID: count={count}")

    def _wait_until_zero(
        self,
        *,
        read: Callable[[], int],
        attempts: int,
        poll_seconds: int,
        error_code: str,
    ) -> None:
        for index in range(attempts):
            if read() == 0:
                return
            if index + 1 < attempts:
                self._sleep(float(poll_seconds))
        raise ValueError(error_code)


class ComposeDistributionOperations:
    """Adaptateur réel Compose/PostgreSQL du protocole M14-core."""

    def __init__(
        self,
        *,
        definition: EnvironmentStackDefinition,
        configuration: ApplicationConfiguration,
        current_release: DistributionReleaseIdentity,
        release_overrides: Mapping[str, Path],
    ) -> None:
        self._definition = definition
        self._configuration = configuration
        self._current_release = current_release
        self._release_overrides = dict(release_overrides)

    def close_public(self) -> None:
        self._compose(
            ("stop", *PUBLIC_SERVICE_IDS),
            release=self._current_release,
            capture_output=True,
        )

    def read_drain_inventory(
        self, configuration_hash: str
    ) -> DistributionDrainInventory:
        payload = self._query_json(_DRAIN_INVENTORY_SQL, configuration_hash)
        return DistributionDrainInventory(
            technical_jobs=_json_count(payload, "technical_jobs"),
            source_processing_outbox=_json_count(payload, "source_processing_outbox"),
            knowledge_access_outbox=_json_count(payload, "knowledge_access_outbox"),
        )

    def start_internal(self, release: DistributionReleaseIdentity) -> None:
        build_mode = "--build" if release == self._current_release else "--no-build"
        self._compose(
            (
                "up",
                build_mode,
                "--detach",
                "--wait",
                "--wait-timeout",
                str(self._configuration.runtime.timeouts.startup_seconds),
                *INTERNAL_SERVICE_IDS,
            ),
            release=release,
            capture_output=False,
        )

    def live_ready_worker_count(self, configuration_hash: str) -> int:
        return self._query_integer(_READY_WORKERS_SQL, configuration_hash)

    def activate_public(self, release: DistributionReleaseIdentity) -> None:
        self._compose(
            (
                "up",
                "--no-build",
                "--detach",
                "--wait",
                "--wait-timeout",
                str(self._configuration.runtime.timeouts.startup_seconds),
                *PUBLIC_SERVICE_IDS,
            ),
            release=release,
            capture_output=False,
        )

    def begin_draining(self, configuration_hash: str, deadline_seconds: int) -> None:
        count = self._query_integer(
            _BEGIN_DRAINING_SQL,
            configuration_hash,
            extra_variables={"deadline_seconds": str(deadline_seconds)},
        )
        if count != 2:
            raise ValueError(f"DISTRIBUTION_DRAIN_WORKERS_INVALID: count={count}")

    def read_rollback_inventory(
        self, configuration_hash: str
    ) -> DistributionRollbackInventory:
        payload = self._query_json(_ROLLBACK_INVENTORY_SQL, configuration_hash)
        return DistributionRollbackInventory(
            active_jobs=_json_count(payload, "active_jobs"),
            active_slots=_json_count(payload, "active_slots"),
        )

    def verify_schema_022_retained(self) -> None:
        if (
            self._query_integer(
                _SCHEMA_022_SQL, self._current_release.configuration_hash
            )
            != 1
        ):
            raise ValueError("DISTRIBUTION_SCHEMA_022_NOT_RETAINED")

    def stop_internal(self) -> None:
        self._compose(
            ("stop", *tuple(s for s in INTERNAL_SERVICE_IDS if s != "postgres")),
            release=self._current_release,
            capture_output=True,
        )

    def verify_release(self, release: DistributionReleaseIdentity) -> None:
        result = self._compose(
            ("ps", "--all", "--format", "json"),
            release=release,
            capture_output=True,
        )
        required_counts = {"orchestrator-api": 1, "worker-documents": 2}
        observed = {service_id: 0 for service_id in required_counts}
        for line in result.stdout.splitlines():
            if line.strip() == "":
                continue
            row = json.loads(line)
            service = row.get("Service")
            if service not in observed:
                continue
            image = row.get("Image")
            if not isinstance(image, str) or release.revision not in image:
                raise ValueError("DISTRIBUTION_RELEASE_REVISION_MISMATCH")
            observed[service] += 1
        if observed != required_counts:
            raise ValueError("DISTRIBUTION_RELEASE_IDENTITY_INCOMPLETE")

    def gpu_preflight(self) -> None:
        self._compose(
            (
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "python",
                "worker-documents",
                "-c",
                "import torch; assert torch.backends.cuda.is_built(); "
                "assert torch.cuda.is_available(); assert torch.cuda.device_count() >= 1; "
                "print(torch.cuda.get_device_name(0))",
            ),
            release=self._current_release,
            capture_output=False,
        )

    def _query_json(self, sql: str, configuration_hash: str) -> Mapping[str, object]:
        result = self._psql(sql, configuration_hash)
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise ValueError("DISTRIBUTION_SQL_OUTPUT_INVALID") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("DISTRIBUTION_SQL_OUTPUT_INVALID")
        return payload

    def _query_integer(
        self,
        sql: str,
        configuration_hash: str,
        *,
        extra_variables: Mapping[str, str] | None = None,
    ) -> int:
        result = self._psql(sql, configuration_hash, extra_variables=extra_variables)
        try:
            value = int(result.stdout.strip())
        except ValueError as exc:
            raise ValueError("DISTRIBUTION_SQL_OUTPUT_INVALID") from exc
        return _require_non_negative(value)

    def _psql(
        self,
        sql: str,
        configuration_hash: str,
        *,
        extra_variables: Mapping[str, str] | None = None,
    ):
        _require_hash(configuration_hash)
        postgres = self._configuration.services.postgres
        variables = {
            "environment": self._configuration.application.environment,
            "deployment_id": self._configuration.application.deployment_id,
            "configuration_hash": configuration_hash,
            **(dict(extra_variables) if extra_variables is not None else {}),
        }
        arguments: list[str] = [
            "exec",
            "--no-TTY",
            "postgres",
            "psql",
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            postgres.role,
            "--dbname",
            postgres.database,
        ]
        for name, value in variables.items():
            arguments.extend(("--set", f"{name}={value}"))
        arguments.extend(("--command", sql))
        return self._compose(
            tuple(arguments),
            release=self._current_release,
            capture_output=True,
        )

    def _compose(
        self,
        arguments: Sequence[str],
        *,
        release: DistributionReleaseIdentity,
        capture_output: bool,
    ):
        override = self._release_overrides.get(release.revision)
        additional = () if override is None else (override,)
        return run_environment_compose_command(
            self._definition,
            arguments,
            technical_environment=release.technical_environment(),
            capture_output=capture_output,
            additional_compose_paths=additional,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    try:
        root = Path.cwd().resolve()
        environment = arguments.environment
        configuration_path = root / "config" / "environments" / f"{environment}.yaml"
        configuration = load_application_configuration(configuration_path, {})
        definition = environment_stack_definition(environment, repository_root=root)
        technical = technical_environment_from_repository(root)
        current = DistributionReleaseIdentity(
            revision=technical["OSTRADING_IMAGE_REVISION"],
            schema_version=technical["OSTRADING_POSTGRES_SCHEMA_VERSION"],
            configuration_hash=configuration.configuration_hash,
        )
        release_overrides: dict[str, Path] = {}
        previous: DistributionReleaseIdentity | None = None
        if arguments.action == "rollback":
            previous_configuration_path = Path(arguments.previous_config).resolve()
            previous_configuration = load_application_configuration(
                previous_configuration_path, {}
            )
            _require_same_environment(configuration, previous_configuration)
            previous = DistributionReleaseIdentity(
                revision=arguments.previous_revision,
                schema_version=current.schema_version,
                configuration_hash=arguments.previous_configuration_hash,
            )
            if previous_configuration.configuration_hash != previous.configuration_hash:
                raise ValueError("DISTRIBUTION_PREVIOUS_CONFIGURATION_MISMATCH")
            release_overrides[previous.revision] = _write_configuration_override(
                definition=definition,
                release=previous,
                configuration_path=previous_configuration_path,
            )
        operations = ComposeDistributionOperations(
            definition=definition,
            configuration=configuration,
            current_release=current,
            release_overrides=release_overrides,
        )
        controller = DistributionCoreController(operations=operations, sleep=time.sleep)
        if arguments.action == "identity":
            print(json.dumps(current.to_mapping(), sort_keys=True), flush=True)
        elif arguments.action == "gpu-preflight":
            operations.gpu_preflight()
        elif arguments.action == "prepare":
            controller.prepare(
                current=current,
                previous_configuration_hash=arguments.previous_configuration_hash,
                timeout_seconds=arguments.timeout_seconds,
                poll_seconds=arguments.poll_seconds,
            )
        elif arguments.action == "activate":
            controller.activate(current=current)
        elif arguments.action == "rollback" and previous is not None:
            controller.rollback(
                current=current,
                previous=previous,
                drain_deadline_seconds=arguments.drain_deadline_seconds,
                timeout_seconds=arguments.timeout_seconds,
                poll_seconds=arguments.poll_seconds,
            )
        else:
            raise ValueError("DISTRIBUTION_ACTION_INVALID")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="distribution-core")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("identity", "gpu-preflight", "activate"):
        action_parser = subparsers.add_parser(action)
        _add_environment_argument(action_parser)
    prepare = subparsers.add_parser("prepare")
    _add_environment_argument(prepare)
    prepare.add_argument("--previous-configuration-hash", required=True)
    _add_wait_arguments(prepare)
    rollback = subparsers.add_parser("rollback")
    _add_environment_argument(rollback)
    rollback.add_argument("--previous-revision", required=True)
    rollback.add_argument("--previous-configuration-hash", required=True)
    rollback.add_argument("--previous-config", required=True)
    rollback.add_argument(
        "--drain-deadline-seconds", required=True, type=_positive_argument
    )
    _add_wait_arguments(rollback)
    return parser


def _add_environment_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment", required=True, choices=ENVIRONMENTS)


def _add_wait_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout-seconds", required=True, type=_positive_argument)
    parser.add_argument("--poll-seconds", required=True, type=_positive_argument)


def _positive_argument(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("entier positif requis") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("entier positif requis")
    return parsed


def _write_configuration_override(
    *,
    definition: EnvironmentStackDefinition,
    release: DistributionReleaseIdentity,
    configuration_path: Path,
) -> Path:
    target = (
        definition.repository_root
        / ".tmp"
        / "distribution-core"
        / f"rollback-{definition.environment}-{release.revision}.compose.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "services": {
            service_id: {
                "volumes": [
                    {
                        "type": "bind",
                        "source": str(configuration_path),
                        "target": _APPLICATION_CONFIGURATION_TARGET,
                        "read_only": True,
                    }
                ]
            }
            for service_id in _CONFIGURED_SERVICE_IDS
        }
    }
    target.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return target


def _require_same_environment(
    current: ApplicationConfiguration, previous: ApplicationConfiguration
) -> None:
    if current.application != previous.application:
        raise ValueError("DISTRIBUTION_PREVIOUS_ENVIRONMENT_MISMATCH")


def _attempt_count(timeout_seconds: int, poll_seconds: int) -> int:
    timeout = _require_positive_integer(timeout_seconds, "DISTRIBUTION_TIMEOUT_INVALID")
    poll = _require_positive_integer(poll_seconds, "DISTRIBUTION_POLL_INVALID")
    return (timeout + poll - 1) // poll + 1


def _require_positive_integer(value: int, error_code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(error_code)
    return value


def _require_hash(value: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("DISTRIBUTION_CONFIGURATION_HASH_INVALID")
    return value


def _require_counts(*values: int) -> None:
    for value in values:
        _require_non_negative(value)


def _require_non_negative(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("DISTRIBUTION_COUNT_INVALID")
    return value


def _json_count(payload: Mapping[str, object], key: str) -> int:
    return _require_non_negative(payload.get(key))  # type: ignore[arg-type]


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ComposeDistributionOperations",
    "DistributionCoreController",
    "DistributionDrainInventory",
    "DistributionReleaseIdentity",
    "DistributionRollbackInventory",
    "INTERNAL_SERVICE_IDS",
    "PUBLIC_SERVICE_IDS",
    "main",
]
