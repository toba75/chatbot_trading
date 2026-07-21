"""Liaison stricte des workers, jobs et preuves de santé à une installation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final
from uuid import UUID

from app.contracts.technical_jobs import JobEnvironmentIdentity, JobRequest
from app.platform.configuration import ApplicationConfiguration


WORKER_ENVIRONMENT_MISMATCH: Final = "WORKER_ENVIRONMENT_MISMATCH"
WORKER_JOB_NAMES: Final = MappingProxyType(
    {
        "worker-documents": ("DIAGNOSE", "CONVERT_DOCUMENT"),
        "worker-projection": ("PROJECT_DOCUMENT",),
        "worker-research": ("DEEP_RESEARCH", "VERIFY_RESPONSE"),
        "worker-backtest": ("BACKTEST",),
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
    "build_worker_environment_binding",
    "execute_environment_bound_job",
    "job_environment_identity_from_configuration",
]
