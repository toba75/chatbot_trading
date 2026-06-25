"""File locale de jobs techniques priorises et idempotents M-002."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_JOB_ID_PATTERN = re.compile(r"^JOB-M002-[0-9]{6}$")
_LOCAL_JOB_NAMES = (
    "INVENTORY",
    "DIAGNOSE",
    "PREPROCESS",
    "CONVERT_STANDARD",
    "CONVERT_GRANITE",
    "MERGE_DOCUMENT",
    "POST_QA",
    "CHUNK",
    "EMBED",
    "INDEX",
    "EXTRACT_CLAIMS",
    "VERIFY_CLAIMS",
    "DEEP_RESEARCH",
    "COMPILE_STRATEGY",
    "BACKTEST",
    "VERIFY_RESPONSE",
)


class JobPriority(str, Enum):
    """Priorite technique explicite d'un job local."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"

    @property
    def rank(self) -> int:
        return _PRIORITY_RANKS[self]


class JobStatus(str, Enum):
    """Statut explicite d'un job local."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_PRIORITY_RANKS = {
    JobPriority.P0: 0,
    JobPriority.P1: 1,
    JobPriority.P2: 2,
    JobPriority.P3: 3,
    JobPriority.P4: 4,
    JobPriority.P5: 5,
}


@dataclass(frozen=True)
class JobCatalog:
    """Catalogue strict des jobs techniques autorises."""

    job_names: frozenset[str]

    @classmethod
    def from_job_names(cls, job_names: Iterable[str]) -> "JobCatalog":
        if job_names is None:
            raise ValueError("job_names absent")
        parsed_names: list[str] = []
        parsed_name_set: set[str] = set()
        for job_name in job_names:
            parsed_name = _ensure_text(job_name, "job_name")
            if parsed_name in parsed_name_set:
                raise ValueError(f"job duplique dans le catalogue: {parsed_name}")
            parsed_names.append(parsed_name)
            parsed_name_set.add(parsed_name)
        if len(parsed_names) == 0:
            raise ValueError("job_names vide")
        return cls(job_names=frozenset(parsed_names))

    def includes(self, job_name: str) -> bool:
        parsed_name = _ensure_text(job_name, "job_name")
        return parsed_name in self.job_names

    def require_known_job(self, job_name: str) -> str:
        parsed_name = _ensure_text(job_name, "job_name")
        if parsed_name not in self.job_names:
            raise ValueError(f"job inconnu: {parsed_name}")
        return parsed_name


@dataclass(frozen=True)
class JobIdempotenceKey:
    """Cle complete empechant le recalcul implicite d'un job reussi."""

    job_name: str
    input_hash: str
    configuration_hash: str
    code_version: str
    model_version: str

    def __post_init__(self) -> None:
        _ensure_text(self.job_name, "job_name")
        _ensure_hash(self.input_hash, "input_hash")
        _ensure_hash(self.configuration_hash, "configuration_hash")
        _ensure_text(self.code_version, "code_version")
        _ensure_text(self.model_version, "model_version")

    def identity_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            self.job_name,
            self.input_hash,
            self.configuration_hash,
            self.code_version,
            self.model_version,
        )


@dataclass(frozen=True)
class JobRequest:
    """Demande technique d'execution d'un job."""

    job_name: str
    priority: JobPriority
    idempotence_key: JobIdempotenceKey
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        job_name = _ensure_text(self.job_name, "job_name")
        if not isinstance(self.priority, JobPriority):
            raise ValueError("priority invalide")
        if not isinstance(self.idempotence_key, JobIdempotenceKey):
            raise ValueError("idempotence_key invalide")
        if self.idempotence_key.job_name != job_name:
            raise ValueError("idempotence_key incoherente avec job_name")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))


@dataclass(frozen=True)
class JobRecord:
    """Etat observable d'un job technique local."""

    sequence: int
    job_id: str
    request: JobRequest
    status: JobStatus
    result: Mapping[str, Any] | None
    failure_reason: str | None

    def __post_init__(self) -> None:
        _ensure_positive_integer(self.sequence, "sequence")
        _ensure_job_id(self.job_id)
        if not isinstance(self.request, JobRequest):
            raise ValueError("request invalide")
        if not isinstance(self.status, JobStatus):
            raise ValueError("status invalide")

        if self.status is JobStatus.SUCCEEDED:
            if self.result is None:
                raise ValueError("result absent")
            object.__setattr__(self, "result", _freeze_mapping(self.result, "result"))
        elif self.result is not None:
            raise ValueError("result interdit sans statut succeeded")

        if self.status is JobStatus.FAILED:
            _ensure_text(self.failure_reason, "failure_reason")
        elif self.failure_reason is not None:
            raise ValueError("failure_reason interdit sans statut failed")


@dataclass(frozen=True)
class JobSubmissionDecision:
    """Decision observable apres soumission d'un job."""

    job: JobRecord
    created: bool
    recalculation_refused: bool

    def __post_init__(self) -> None:
        if not isinstance(self.job, JobRecord):
            raise ValueError("job invalide")
        if not isinstance(self.created, bool):
            raise ValueError("created non booleen")
        if not isinstance(self.recalculation_refused, bool):
            raise ValueError("recalculation_refused non booleen")
        if self.created and self.recalculation_refused:
            raise ValueError("decision de soumission incoherente")


class InMemoryJobQueue:
    """File de jobs locale, priorisee et idempotente."""

    def __init__(
        self,
        catalog: JobCatalog,
        jobs: Iterable[JobRecord],
    ) -> None:
        if not isinstance(catalog, JobCatalog):
            raise ValueError("catalog invalide")
        if jobs is None:
            raise ValueError("jobs absent")

        self._catalog = catalog
        self._records_by_job_id: dict[str, JobRecord] = {}
        self._job_order: list[str] = []
        self._active_job_id_by_key: dict[tuple[str, str, str, str, str], str] = {}
        self._successful_job_id_by_key: dict[tuple[str, str, str, str, str], str] = {}

        for job in jobs:
            self._store_initial_job(job)

    @classmethod
    def empty(cls, *, catalog: JobCatalog) -> "InMemoryJobQueue":
        return cls(catalog=catalog, jobs=())

    def submit(self, request: JobRequest, *, recalculate: bool) -> JobSubmissionDecision:
        parsed_request = _ensure_job_request(request)
        if not isinstance(recalculate, bool):
            raise ValueError("recalculate non booleen")
        self._catalog.require_known_job(parsed_request.job_name)

        key = parsed_request.idempotence_key.identity_tuple()
        if not recalculate and key in self._successful_job_id_by_key:
            existing_job = self.job_for(self._successful_job_id_by_key[key])
            return JobSubmissionDecision(
                job=existing_job,
                created=False,
                recalculation_refused=True,
            )
        if not recalculate and key in self._active_job_id_by_key:
            existing_job = self.job_for(self._active_job_id_by_key[key])
            return JobSubmissionDecision(
                job=existing_job,
                created=False,
                recalculation_refused=False,
            )

        job = JobRecord(
            sequence=len(self._job_order) + 1,
            job_id=f"JOB-M002-{len(self._job_order) + 1:06d}",
            request=parsed_request,
            status=JobStatus.PENDING,
            result=None,
            failure_reason=None,
        )
        self._records_by_job_id[job.job_id] = job
        self._job_order.append(job.job_id)
        self._active_job_id_by_key[key] = job.job_id
        return JobSubmissionDecision(
            job=job,
            created=True,
            recalculation_refused=False,
        )

    def created_job_count(self) -> int:
        return len(self._job_order)

    def pending_jobs(self) -> tuple[JobRecord, ...]:
        pending = (
            self._records_by_job_id[job_id]
            for job_id in self._job_order
            if self._records_by_job_id[job_id].status is JobStatus.PENDING
        )
        return tuple(
            sorted(
                pending,
                key=lambda job: (job.request.priority.rank, job.sequence),
            )
        )

    def job_for(self, job_id: str) -> JobRecord:
        parsed_job_id = _ensure_job_id(job_id)
        if parsed_job_id not in self._records_by_job_id:
            raise ValueError(f"job inconnu: {parsed_job_id}")
        return self._records_by_job_id[parsed_job_id]

    def status_of(self, job_id: str) -> JobStatus:
        return self.job_for(job_id).status

    def mark_running(self, job_id: str) -> JobRecord:
        job = self.job_for(job_id)
        if job.status is not JobStatus.PENDING:
            raise ValueError(f"transition job invalide vers running: {job.job_id}")
        running_job = JobRecord(
            sequence=job.sequence,
            job_id=job.job_id,
            request=job.request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        )
        self._records_by_job_id[job.job_id] = running_job
        return running_job

    def mark_succeeded(self, job_id: str, result: Mapping[str, Any]) -> JobRecord:
        job = self.job_for(job_id)
        if job.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
            raise ValueError(f"transition job invalide vers succeeded: {job.job_id}")
        succeeded_job = JobRecord(
            sequence=job.sequence,
            job_id=job.job_id,
            request=job.request,
            status=JobStatus.SUCCEEDED,
            result=result,
            failure_reason=None,
        )
        self._records_by_job_id[job.job_id] = succeeded_job
        key = job.request.idempotence_key.identity_tuple()
        if key in self._active_job_id_by_key:
            del self._active_job_id_by_key[key]
        self._successful_job_id_by_key[key] = job.job_id
        return succeeded_job

    def mark_failed(self, job_id: str, failure_reason: str) -> JobRecord:
        job = self.job_for(job_id)
        if job.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
            raise ValueError(f"transition job invalide vers failed: {job.job_id}")
        failed_job = JobRecord(
            sequence=job.sequence,
            job_id=job.job_id,
            request=job.request,
            status=JobStatus.FAILED,
            result=None,
            failure_reason=failure_reason,
        )
        self._records_by_job_id[job.job_id] = failed_job
        key = job.request.idempotence_key.identity_tuple()
        if key in self._active_job_id_by_key:
            del self._active_job_id_by_key[key]
        return failed_job

    def execute_next(self, *, worker_registry: "InMemoryJobWorkerRegistry") -> JobRecord:
        if not isinstance(worker_registry, InMemoryJobWorkerRegistry):
            raise ValueError("worker_registry invalide")
        pending_jobs = self.pending_jobs()
        if len(pending_jobs) == 0:
            raise ValueError("job pending absent")
        next_job = pending_jobs[0]
        running_job = self.mark_running(next_job.job_id)
        worker = worker_registry.worker_for(running_job.request.job_name)
        result = worker(running_job)
        return self.mark_succeeded(job_id=running_job.job_id, result=result)

    def _store_initial_job(self, job: JobRecord) -> None:
        if not isinstance(job, JobRecord):
            raise ValueError("job invalide")
        self._catalog.require_known_job(job.request.job_name)
        if job.job_id in self._records_by_job_id:
            raise ValueError(f"job_id duplique: {job.job_id}")
        self._records_by_job_id[job.job_id] = job
        self._job_order.append(job.job_id)
        key = job.request.idempotence_key.identity_tuple()
        if job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            self._active_job_id_by_key[key] = job.job_id
        if job.status is JobStatus.SUCCEEDED:
            self._successful_job_id_by_key[key] = job.job_id


class InMemoryJobWorkerRegistry:
    """Registre explicite de workers techniques injectes par job."""

    def __init__(
        self,
        workers: Mapping[str, Callable[[JobRecord], Mapping[str, Any]]],
        catalog: JobCatalog,
    ) -> None:
        if not isinstance(catalog, JobCatalog):
            raise ValueError("catalog invalide")
        if not isinstance(workers, Mapping):
            raise ValueError("workers non objet")
        self._catalog = catalog
        self._workers: dict[str, Callable[[JobRecord], Mapping[str, Any]]] = {}
        for job_name, worker in workers.items():
            parsed_job_name = self._catalog.require_known_job(job_name)
            if not callable(worker):
                raise ValueError(f"worker non appelable: {parsed_job_name}")
            self._workers[parsed_job_name] = worker

    @classmethod
    def from_workers(
        cls,
        *,
        workers: Mapping[str, Callable[[JobRecord], Mapping[str, Any]]],
        catalog: JobCatalog,
    ) -> "InMemoryJobWorkerRegistry":
        return cls(workers=workers, catalog=catalog)

    def worker_for(self, job_name: str) -> Callable[[JobRecord], Mapping[str, Any]]:
        parsed_job_name = self._catalog.require_known_job(job_name)
        if parsed_job_name not in self._workers:
            raise ValueError(f"worker absent: {parsed_job_name}")
        return self._workers[parsed_job_name]


def _ensure_job_request(value: JobRequest) -> JobRequest:
    if not isinstance(value, JobRequest):
        raise ValueError("request invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_hash(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if _HASH_PATTERN.fullmatch(text_value) is None:
        raise ValueError(f"{field_name} invalide")
    return text_value


def _ensure_job_id(value: Any) -> str:
    text_value = _ensure_text(value, "job_id")
    if _JOB_ID_PATTERN.fullmatch(text_value) is None:
        raise ValueError("job_id invalide")
    return text_value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _freeze_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    frozen_values = {
        _ensure_text(key, f"{field_name}.cle"): _freeze_payload_value(
            nested_value,
            f"{field_name}.{key}",
        )
        for key, nested_value in value.items()
    }
    return MappingProxyType(frozen_values)


def _freeze_payload_value(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_freeze_payload_value(item, f"{field_name}[]") for item in value)
    raise ValueError(f"{field_name} invalide")


JOB_RUNTIME_CATALOG = JobCatalog.from_job_names(_LOCAL_JOB_NAMES)


__all__ = [
    "InMemoryJobQueue",
    "InMemoryJobWorkerRegistry",
    "JOB_RUNTIME_CATALOG",
    "JobCatalog",
    "JobIdempotenceKey",
    "JobPriority",
    "JobRecord",
    "JobRequest",
    "JobStatus",
    "JobSubmissionDecision",
]
