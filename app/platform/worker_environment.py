"""Liaison stricte des workers, jobs et preuves de santé à une installation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
from types import MappingProxyType
from typing import Any, Final
from uuid import UUID

from app.contracts.technical_jobs import JobEnvironmentIdentity, JobRequest
from app.platform.configuration import ApplicationConfiguration


WORKER_ENVIRONMENT_MISMATCH: Final = "WORKER_ENVIRONMENT_MISMATCH"
WORKER_JOB_NAMES: Final = MappingProxyType(
    {
        "worker-documents": ("DIAGNOSE", "CONVERT_DOCUMENT", "CONVERT_PAGE"),
        "worker-projection": ("PROJECT_DOCUMENT",),
    }
)


class WorkerEnvironmentMismatchError(RuntimeError):
    """Refus stable avant claim ou callback d'un travail étranger."""

    code = WORKER_ENVIRONMENT_MISMATCH

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class WorkerHealthSnapshot:
    service: str
    status: str
    identity: JobEnvironmentIdentity

    def __post_init__(self) -> None:
        if self.service not in WORKER_JOB_NAMES:
            raise ValueError("worker_id invalide")
        if self.status != "ready":
            raise ValueError("worker health status invalide")
        if not isinstance(self.identity, JobEnvironmentIdentity):
            raise ValueError("identité worker invalide")

    def to_mapping(self) -> dict[str, str]:
        return {
            "service": self.service,
            "status": self.status,
            **self.identity.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class WorkerEnvironmentBinding:
    worker_id: str
    identity: JobEnvironmentIdentity
    job_names: tuple[str, ...]

    def __post_init__(self) -> None:
        expected_job_names = WORKER_JOB_NAMES.get(self.worker_id)
        if expected_job_names is None:
            raise ValueError("worker_id invalide")
        if not isinstance(self.identity, JobEnvironmentIdentity):
            raise ValueError("identité worker invalide")
        if self.job_names != expected_job_names:
            raise ValueError("jobs worker invalides")

    def require_job_request(self, request: JobRequest) -> JobRequest:
        if not isinstance(request, JobRequest):
            raise ValueError("job_request invalide")
        if request.job_name not in self.job_names:
            raise ValueError("job non supporté par le worker")
        if request.environment_identity != self.identity:
            raise WorkerEnvironmentMismatchError()
        return request

    def instance_owner_id(self, instance_id: str) -> str:
        if not isinstance(instance_id, str):
            raise ValueError("instance_id worker invalide")
        try:
            parsed = UUID(instance_id)
        except ValueError as exc:
            raise ValueError("instance_id worker invalide") from exc
        if parsed.version != 4:
            raise ValueError("instance_id worker invalide")
        return (
            f"{self.identity.environment}:{self.identity.deployment_id}:"
            f"{self.worker_id}:{instance_id}"
        )

    def health_snapshot(self) -> WorkerHealthSnapshot:
        return WorkerHealthSnapshot(
            service=self.worker_id,
            status="ready",
            identity=self.identity,
        )


class WorkerHealthFilePublisher:
    """Publie la santé du processus worker long-vivant dans son propre conteneur."""

    def __init__(
        self,
        *,
        binding: WorkerEnvironmentBinding,
        path: Path,
        heartbeat_interval_seconds: float,
    ) -> None:
        if not isinstance(binding, WorkerEnvironmentBinding):
            raise ValueError("binding de santé worker invalide")
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("chemin de santé worker invalide")
        if (
            isinstance(heartbeat_interval_seconds, bool)
            or not isinstance(heartbeat_interval_seconds, (int, float))
            or heartbeat_interval_seconds <= 0
        ):
            raise ValueError("intervalle de santé worker invalide")
        self.binding = binding
        self._path = path
        self._heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._thread = threading.Thread(
            target=self._publish_forever,
            name=f"health-{binding.worker_id}",
            daemon=True,
        )

    def publish_once(self) -> None:
        payload: dict[str, object] = {
            **self.binding.health_snapshot().to_mapping(),
            "updated_at_epoch": time.time(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_name(f".{self._path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        temporary_path.replace(self._path)

    def start(self) -> None:
        self.publish_once()
        self._thread.start()

    def _publish_forever(self) -> None:
        while True:
            time.sleep(self._heartbeat_interval_seconds)
            self.publish_once()


def read_worker_health_file(
    *,
    path: Path,
    expected_identity: JobEnvironmentIdentity,
    expected_worker_id: str,
    maximum_age_seconds: float,
) -> Mapping[str, object]:
    """Valide la preuve produite par le participant, sans reconstruire sa santé."""

    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise ValueError("chemin de santé worker invalide")
    if not isinstance(expected_identity, JobEnvironmentIdentity):
        raise ValueError("identité de santé worker invalide")
    if expected_worker_id not in WORKER_JOB_NAMES:
        raise ValueError("worker_id invalide")
    if (
        isinstance(maximum_age_seconds, bool)
        or not isinstance(maximum_age_seconds, (int, float))
        or maximum_age_seconds <= 0
    ):
        raise ValueError("ancienneté de santé worker invalide")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("WORKER_HEALTH_UNAVAILABLE") from exc
    if not isinstance(payload, Mapping) or frozenset(payload) != {
        "service",
        "status",
        "environment",
        "deployment_id",
        "configuration_hash",
        "updated_at_epoch",
    }:
        raise ValueError("WORKER_HEALTH_INVALID")
    observed_identity = JobEnvironmentIdentity(
        environment=payload["environment"],
        deployment_id=payload["deployment_id"],
        configuration_hash=payload["configuration_hash"],
    )
    if (
        payload["service"] != expected_worker_id
        or payload["status"] != "ready"
        or observed_identity != expected_identity
    ):
        raise WorkerEnvironmentMismatchError()
    updated_at = payload["updated_at_epoch"]
    if isinstance(updated_at, bool) or not isinstance(updated_at, (int, float)):
        raise ValueError("WORKER_HEALTH_INVALID")
    age_seconds = time.time() - float(updated_at)
    if age_seconds < 0 or age_seconds > maximum_age_seconds:
        raise ValueError("WORKER_HEALTH_STALE")
    return MappingProxyType(dict(payload))


@dataclass(frozen=True, slots=True)
class EnvironmentBoundJobExecutionOutcome:
    executed: bool
    result: Mapping[str, Any] | None
    error_code: str | None

    def __post_init__(self) -> None:
        if self.executed:
            if not isinstance(self.result, Mapping) or len(self.result) == 0:
                raise ValueError("résultat job lié invalide")
            if self.error_code is not None:
                raise ValueError("erreur interdite pour un job exécuté")
        elif self.result is not None or self.error_code != WORKER_ENVIRONMENT_MISMATCH:
            raise ValueError("refus job lié invalide")


def job_environment_identity_from_configuration(
    configuration: ApplicationConfiguration,
) -> JobEnvironmentIdentity:
    if not isinstance(configuration, ApplicationConfiguration):
        raise ValueError("configuration worker invalide")
    return JobEnvironmentIdentity(
        environment=configuration.application.environment,
        deployment_id=configuration.application.deployment_id,
        configuration_hash=configuration.configuration_hash,
    )


def build_worker_environment_binding(
    configuration: ApplicationConfiguration,
    *,
    worker_id: str,
) -> WorkerEnvironmentBinding:
    job_names = WORKER_JOB_NAMES.get(worker_id)
    if job_names is None:
        raise ValueError("worker_id invalide")
    return WorkerEnvironmentBinding(
        worker_id=worker_id,
        identity=job_environment_identity_from_configuration(configuration),
        job_names=job_names,
    )


def execute_environment_bound_job(
    *,
    binding: WorkerEnvironmentBinding,
    job_request: JobRequest,
    execute: Callable[[JobRequest], Mapping[str, Any]],
    persist_terminal_failure: Callable[[JobRequest, str], None],
) -> EnvironmentBoundJobExecutionOutcome:
    """Évalue l'identité avant le callback et persiste tout refus terminal."""

    if not isinstance(binding, WorkerEnvironmentBinding):
        raise ValueError("binding worker invalide")
    if not callable(execute):
        raise ValueError("callback worker invalide")
    if not callable(persist_terminal_failure):
        raise ValueError("publication terminale worker invalide")
    try:
        accepted = binding.require_job_request(job_request)
    except WorkerEnvironmentMismatchError:
        persist_terminal_failure(job_request, WORKER_ENVIRONMENT_MISMATCH)
        return EnvironmentBoundJobExecutionOutcome(
            executed=False,
            result=None,
            error_code=WORKER_ENVIRONMENT_MISMATCH,
        )
    result = execute(accepted)
    return EnvironmentBoundJobExecutionOutcome(
        executed=True,
        result=result,
        error_code=None,
    )


__all__ = [
    "EnvironmentBoundJobExecutionOutcome",
    "WORKER_ENVIRONMENT_MISMATCH",
    "WORKER_JOB_NAMES",
    "WorkerEnvironmentBinding",
    "WorkerEnvironmentMismatchError",
    "WorkerHealthSnapshot",
    "WorkerHealthFilePublisher",
    "build_worker_environment_binding",
    "execute_environment_bound_job",
    "job_environment_identity_from_configuration",
    "read_worker_health_file",
]
