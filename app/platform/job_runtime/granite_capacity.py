"""Quota PostgreSQL de deux slots Granite avec double fencing ADR-052."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generic, NamedTuple, Protocol, TypeVar
from uuid import UUID

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobEnvironmentIdentity,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.platform.job_runtime import JobCatalog
from app.platform.postgres import PostgresConnectionFactory


_GENERALIST_CAPABILITIES = frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA"))
_GRANITE_CAPABILITY = "GRANITE_CUDA"
_GRANITE_DEVICE = "cuda:0"
_GRANITE_CAPACITY_ERROR = "GRANITE_CAPACITY_CONFIGURATION_INVALID"
_JOB_LEASE_LOST = "JOB_LEASE_LOST"

ModelResultT = TypeVar("ModelResultT")


class GraniteCapacityConfigurationError(ValueError):
    """La capacité locale ne respecte pas le contrat strict T-003."""

    code = _GRANITE_CAPACITY_ERROR

    def __init__(self) -> None:
        super().__init__(self.code)


class GraniteSlotLeaseLostError(RuntimeError):
    """Le claim ou le slot ne correspond plus au détenteur courant."""

    code = _JOB_LEASE_LOST

    def __init__(self) -> None:
        super().__init__(self.code)


class GraniteWorkerState(str, Enum):
    READY = "READY"
    DRAINING = "DRAINING"


@dataclass(frozen=True, slots=True)
class GraniteWorker:
    """Identité explicite d'un replica documentaire généraliste."""

    worker_instance_id: str
    environment_identity: JobEnvironmentIdentity
    storage_environment: str
    state: GraniteWorkerState
    capabilities: frozenset[str]

    def __post_init__(self) -> None:
        worker_instance_id = _text(self.worker_instance_id)
        if not isinstance(self.environment_identity, JobEnvironmentIdentity):
            raise GraniteCapacityConfigurationError()
        if self.storage_environment != self.environment_identity.environment:
            raise GraniteCapacityConfigurationError()
        if not isinstance(self.state, GraniteWorkerState):
            raise GraniteCapacityConfigurationError()
        if self.capabilities != _GENERALIST_CAPABILITIES:
            raise GraniteCapacityConfigurationError()
        object.__setattr__(self, "worker_instance_id", worker_instance_id)


@dataclass(frozen=True, slots=True)
class GraniteSlotLease:
    """Couple claim-slot immutable transporté pendant une conversion Granite."""

    claimed_job: ClaimedJob
    slot_ordinal: int
    slot_generation: int
    slot_token: str
    lease_until: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.claimed_job, ClaimedJob):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if (
            isinstance(self.slot_ordinal, bool)
            or not isinstance(self.slot_ordinal, int)
            or self.slot_ordinal not in (1, 2)
        ):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if (
            isinstance(self.slot_generation, bool)
            or not isinstance(self.slot_generation, int)
            or self.slot_generation < 1
        ):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        try:
            token = UUID(_text(self.slot_token))
        except (TypeError, ValueError) as exc:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID") from exc
        if token.version != 4:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if not isinstance(self.lease_until, datetime) or self.lease_until.tzinfo is None:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if self.lease_until != self.claimed_job.lease_expires_at:
            raise ValueError("GRANITE_SLOT_LEASE_DEADLINE_MISMATCH")
        object.__setattr__(self, "slot_token", str(token))


@dataclass(frozen=True, slots=True)
class GraniteExecution(Generic[ModelResultT]):
    """Résultat non persistant du contrôleur de capacité T-004."""

    lease: GraniteSlotLease
    model_result: ModelResultT

    def __post_init__(self) -> None:
        if not isinstance(self.lease, GraniteSlotLease):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")


class ClaimCompatibleTechnicalJob(Protocol):
    def claim_compatible_job(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        job_names: tuple[str, ...],
    ) -> GraniteSlotLease | None: ...


class HeartbeatClaimAndGraniteSlot(Protocol):
    def heartbeat(
        self,
        lease: GraniteSlotLease,
        *,
        lease_seconds: int,
    ) -> GraniteSlotLease: ...


class ReleaseGraniteSlot(Protocol):
    def release(self, lease: GraniteSlotLease) -> None: ...


class _AcquiredRow(NamedTuple):
    sequence: int
    job_id: str
    environment: str
    deployment_id: str
    job_name: str
    priority: str
    input_hash: str
    configuration_hash: str
    code_version: str
    model_version: str
    payload: Any
    status: str
    result: Any
    failure_reason: str | None
    trace_id: str
    lease_owner: str
    lease_expires_at: datetime
    claim_generation: int
    claim_token: Any
    execution_attempts: int
    slot_ordinal: int
    slot_generation: int
    slot_token: Any
    slot_lease_until: datetime


_CLAIMED_JOB_COLUMN_NAMES = _AcquiredRow._fields[:20]
_QUALIFIED_CLAIMED_JOB_COLUMNS = ", ".join(
    f"job.{column}" for column in _CLAIMED_JOB_COLUMN_NAMES
)


class PostgresGraniteSlotRepository(
    ClaimCompatibleTechnicalJob,
    HeartbeatClaimAndGraniteSlot,
    ReleaseGraniteSlot,
):
    """Adaptateur platform atomique; PostgreSQL est l'unique autorité du quota."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        catalog: JobCatalog,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise GraniteCapacityConfigurationError()
        if not isinstance(catalog, JobCatalog):
            raise GraniteCapacityConfigurationError()
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise GraniteCapacityConfigurationError()
        self._connection_factory = connection_factory
        self._catalog = catalog
        self._environment_identity = environment_identity

    def claim_compatible_job(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        job_names: tuple[str, ...],
    ) -> GraniteSlotLease | None:
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_job_names = _job_names(job_names, self._catalog)
        self._require_worker(worker)
        if worker.state is GraniteWorkerState.DRAINING:
            return None

        # LOCK_ORDER: technical_job -> granite_slot. Le verrou advisory court
        # sérialise seulement deux claims concurrents de la même instance.
        worker_lock = "|".join(
            (
                self._environment_identity.environment,
                self._environment_identity.deployment_id,
                worker.worker_instance_id,
                "granite-slot",
            )
        )
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (worker_lock,),
                )
                cursor.execute(
                    f"""
                    WITH candidate_job AS MATERIALIZED (
                        SELECT job.sequence, job.job_id
                          FROM platform.technical_jobs AS job
                         WHERE job.environment = %s
                           AND job.deployment_id = %s
                           AND job.configuration_hash = %s
                           AND job.job_name = ANY(%s)
                           AND job.payload -> 'required_capacity'
                               ->> 'capability' = %s
                           AND job.payload -> 'required_capacity'
                               -> 'slots' = '1'::jsonb
                           AND job.payload -> 'required_capacity'
                               ->> 'device' = %s
                           AND job.payload -> 'environment_identity'
                               ->> 'environment' = %s
                           AND job.payload -> 'environment_identity'
                               ->> 'deployment_id' = %s
                           AND job.payload -> 'environment_identity'
                               ->> 'configuration_hash' = %s
                           AND job.payload -> 'source_artifact' -> 'identity'
                               ->> 'environment' = %s
                           AND job.payload -> 'expected_result_artifact'
                               ->> 'environment' = %s
                           AND (
                               job.status = 'pending'
                               OR (
                                   job.status = 'running'
                                   AND job.lease_expires_at <= CURRENT_TIMESTAMP
                               )
                           )
                           AND EXISTS (
                               SELECT 1
                                 FROM platform.datastore_identity AS identity
                                WHERE identity.environment = %s
                                  AND identity.deployment_id = %s
                           )
                         ORDER BY
                               job.priority,
                               CASE WHEN job.status = 'pending' THEN 0 ELSE 1 END,
                               job.sequence
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    ),
                    candidate_slot AS MATERIALIZED (
                        SELECT slot.environment, slot.deployment_id,
                               slot.slot_ordinal
                          FROM platform.granite_slots AS slot
                         WHERE slot.environment = %s
                           AND slot.deployment_id = %s
                           AND EXISTS (SELECT 1 FROM candidate_job)
                           AND (
                               slot.lease_owner IS NULL
                               OR slot.lease_until <= CURRENT_TIMESTAMP
                           )
                           AND NOT EXISTS (
                               SELECT 1
                                 FROM platform.granite_slots AS held
                                WHERE held.environment = %s
                                  AND held.deployment_id = %s
                                  AND held.lease_owner = %s
                                  AND held.lease_until > CURRENT_TIMESTAMP
                           )
                           AND (
                               slot.lease_owner = %s
                               OR NOT EXISTS (
                                   SELECT 1
                                     FROM platform.granite_slots AS owned
                                    WHERE owned.environment = %s
                                      AND owned.deployment_id = %s
                                      AND owned.lease_owner = %s
                               )
                           )
                         ORDER BY
                               CASE WHEN slot.lease_owner = %s THEN 0 ELSE 1 END,
                               CASE
                                   WHEN slot.job_id = (
                                       SELECT job_id FROM candidate_job
                                   ) THEN 0
                                   ELSE 1
                               END,
                               slot.slot_ordinal
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    ),
                    claimed_job AS (
                        UPDATE platform.technical_jobs AS job
                           SET status = 'running',
                               lease_owner = %s,
                               lease_expires_at = CURRENT_TIMESTAMP
                                   + (%s * INTERVAL '1 second'),
                               execution_attempts = execution_attempts + 1,
                               claim_generation = claim_generation + 1,
                               claim_token = gen_random_uuid()
                          FROM candidate_job, candidate_slot
                         WHERE job.sequence = candidate_job.sequence
                        RETURNING {_QUALIFIED_CLAIMED_JOB_COLUMNS}
                    ),
                    leased_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_owner = %s,
                               job_id = claimed_job.job_id,
                               claim_generation = claimed_job.claim_generation,
                               claim_token = claimed_job.claim_token,
                               slot_generation = slot.slot_generation + 1,
                               slot_token = gen_random_uuid(),
                               lease_until = claimed_job.lease_expires_at,
                               updated_at = CURRENT_TIMESTAMP
                          FROM candidate_slot, claimed_job
                         WHERE slot.environment = candidate_slot.environment
                           AND slot.deployment_id = candidate_slot.deployment_id
                           AND slot.slot_ordinal = candidate_slot.slot_ordinal
                        RETURNING slot.slot_ordinal, slot.slot_generation,
                                  slot.slot_token,
                                  slot.lease_until AS slot_lease_until
                    )
                    SELECT claimed_job.*, leased_slot.*
                      FROM claimed_job
                      JOIN leased_slot ON true
                    """,
                    (
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.configuration_hash,
                        list(parsed_job_names),
                        _GRANITE_CAPABILITY,
                        _GRANITE_DEVICE,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.configuration_hash,
                        worker.storage_environment,
                        worker.storage_environment,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        worker.worker_instance_id,
                        worker.worker_instance_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        worker.worker_instance_id,
                        worker.worker_instance_id,
                        worker.worker_instance_id,
                        parsed_lease_seconds,
                        worker.worker_instance_id,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return _lease_from_row(row)

    def heartbeat(
        self,
        lease: GraniteSlotLease,
        *,
        lease_seconds: int,
    ) -> GraniteSlotLease:
        parsed_lease = _require_lease(lease)
        parsed_seconds = _positive_integer(lease_seconds)
        claimed = parsed_lease.claimed_job
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH renewed_job AS (
                        UPDATE platform.technical_jobs AS job
                           SET lease_expires_at = CURRENT_TIMESTAMP
                               + (%s * INTERVAL '1 second')
                         WHERE job.job_id = %s
                           AND job.environment = %s
                           AND job.deployment_id = %s
                           AND job.configuration_hash = %s
                           AND job.status = 'running'
                           AND job.lease_owner = %s
                           AND job.claim_generation = %s
                           AND job.claim_token = %s::uuid
                           AND job.lease_expires_at > CURRENT_TIMESTAMP
                        RETURNING job.lease_expires_at
                    ),
                    renewed_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_until = renewed_job.lease_expires_at,
                               updated_at = CURRENT_TIMESTAMP
                          FROM renewed_job
                         WHERE slot.environment = %s
                           AND slot.deployment_id = %s
                           AND slot.slot_ordinal = %s
                           AND slot.lease_owner = %s
                           AND slot.job_id = %s
                           AND slot.claim_generation = %s
                           AND slot.claim_token = %s::uuid
                           AND slot.slot_generation = %s
                           AND slot.slot_token = %s::uuid
                           AND slot.lease_until > CURRENT_TIMESTAMP
                        RETURNING slot.lease_until
                    )
                    SELECT renewed_job.lease_expires_at,
                           renewed_slot.lease_until
                      FROM renewed_job
                      JOIN renewed_slot ON true
                    """,
                    (
                        parsed_seconds,
                        claimed.job.job_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.configuration_hash,
                        claimed.lease_owner,
                        claimed.claim_generation,
                        claimed.claim_token,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        parsed_lease.slot_ordinal,
                        claimed.lease_owner,
                        claimed.job.job_id,
                        claimed.claim_generation,
                        claimed.claim_token,
                        parsed_lease.slot_generation,
                        parsed_lease.slot_token,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise GraniteSlotLeaseLostError()
                lease_expires_at, slot_lease_until = _row_values(row, 2, "HEARTBEAT")
                if lease_expires_at != slot_lease_until:
                    raise RuntimeError("GRANITE_SLOT_LEASE_DEADLINE_MISMATCH")
        renewed_claim = ClaimedJob(
            job=claimed.job,
            trace_id=claimed.trace_id,
            lease_owner=claimed.lease_owner,
            lease_expires_at=lease_expires_at,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            execution_attempts=claimed.execution_attempts,
        )
        return GraniteSlotLease(
            claimed_job=renewed_claim,
            slot_ordinal=parsed_lease.slot_ordinal,
            slot_generation=parsed_lease.slot_generation,
            slot_token=parsed_lease.slot_token,
            lease_until=slot_lease_until,
        )

    def release(self, lease: GraniteSlotLease) -> None:
        parsed_lease = _require_lease(lease)
        claimed = parsed_lease.claimed_job
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH active_job AS (
                        SELECT job.job_id
                          FROM platform.technical_jobs AS job
                         WHERE job.job_id = %s
                           AND job.environment = %s
                           AND job.deployment_id = %s
                           AND job.configuration_hash = %s
                           AND job.status = 'running'
                           AND job.lease_owner = %s
                           AND job.claim_generation = %s
                           AND job.claim_token = %s::uuid
                           AND job.lease_expires_at > CURRENT_TIMESTAMP
                         FOR UPDATE OF job
                    ),
                    released_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_owner = NULL,
                               job_id = NULL,
                               claim_generation = NULL,
                               claim_token = NULL,
                               slot_token = NULL,
                               lease_until = NULL,
                               updated_at = CURRENT_TIMESTAMP
                          FROM active_job
                         WHERE slot.environment = %s
                           AND slot.deployment_id = %s
                           AND slot.slot_ordinal = %s
                           AND slot.lease_owner = %s
                           AND slot.job_id = active_job.job_id
                           AND slot.claim_generation = %s
                           AND slot.claim_token = %s::uuid
                           AND slot.slot_generation = %s
                           AND slot.slot_token = %s::uuid
                           AND slot.lease_until > CURRENT_TIMESTAMP
                        RETURNING slot.slot_ordinal
                    )
                    SELECT slot_ordinal FROM released_slot
                    """,
                    (
                        claimed.job.job_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        self._environment_identity.configuration_hash,
                        claimed.lease_owner,
                        claimed.claim_generation,
                        claimed.claim_token,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        parsed_lease.slot_ordinal,
                        claimed.lease_owner,
                        claimed.claim_generation,
                        claimed.claim_token,
                        parsed_lease.slot_generation,
                        parsed_lease.slot_token,
                    ),
                )
                if cursor.fetchone() is None:
                    raise GraniteSlotLeaseLostError()

    def _require_worker(self, worker: GraniteWorker) -> None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError()


class GraniteCapacityController:
    """Contrôleur unique autour d'un appel modèle nécessitant Granite."""

    def __init__(self, *, repository: Any) -> None:
        for method_name in ("claim_compatible_job", "heartbeat", "release"):
            if not callable(getattr(repository, method_name, None)):
                raise GraniteCapacityConfigurationError()
        self._repository = repository

    def execute_next(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        heartbeat_seconds: float,
        job_names: tuple[str, ...],
        execute_model: Callable[[GraniteSlotLease], ModelResultT],
    ) -> GraniteExecution[ModelResultT] | None:
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_heartbeat_seconds = _heartbeat_seconds(
            heartbeat_seconds,
            lease_seconds=parsed_lease_seconds,
        )
        if not callable(execute_model):
            raise GraniteCapacityConfigurationError()
        lease = self._repository.claim_compatible_job(
            worker=worker,
            lease_seconds=parsed_lease_seconds,
            job_names=job_names,
        )
        if lease is None:
            return None
        heartbeat = _GraniteSlotHeartbeat(
            repository=self._repository,
            lease=lease,
            lease_seconds=parsed_lease_seconds,
            heartbeat_seconds=parsed_heartbeat_seconds,
        )
        heartbeat.start()
        try:
            try:
                result = execute_model(lease)
            except Exception:
                heartbeat.finalize(self._repository.release)
                raise
            active_lease = heartbeat.finalize(self._repository.release)
            return GraniteExecution(lease=active_lease, model_result=result)
        finally:
            heartbeat.stop()


class _GraniteSlotHeartbeat:
    def __init__(
        self,
        *,
        repository: Any,
        lease: GraniteSlotLease,
        lease_seconds: int,
        heartbeat_seconds: float,
    ) -> None:
        self._repository = repository
        self._lease = lease
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._failure: Exception | None = None
        self._finalized = False
        self._thread = threading.Thread(
            target=self._run,
            name=f"granite-slot-heartbeat-{lease.claimed_job.job.job_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def finalize(
        self,
        transition: Callable[[GraniteSlotLease], None],
    ) -> GraniteSlotLease:
        with self._lock:
            self._raise_failure()
            transition(self._lease)
            self._finalized = True
            self._stop.set()
            return self._lease

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self._heartbeat_seconds * 2))
        if self._thread.is_alive():
            raise RuntimeError("GRANITE_SLOT_HEARTBEAT_STOP_TIMEOUT")

    def _run(self) -> None:
        while not self._stop.wait(self._heartbeat_seconds):
            with self._lock:
                if self._finalized:
                    return
                try:
                    self._lease = self._repository.heartbeat(
                        self._lease,
                        lease_seconds=self._lease_seconds,
                    )
                except Exception as exc:
                    self._failure = exc
                    self._stop.set()
                    return

    def _raise_failure(self) -> None:
        if self._failure is None:
            return
        if isinstance(self._failure, GraniteSlotLeaseLostError):
            raise self._failure
        raise RuntimeError("GRANITE_SLOT_HEARTBEAT_FAILED") from self._failure


def _lease_from_row(row: Any) -> GraniteSlotLease:
    parsed = _AcquiredRow(*_row_values(row, len(_AcquiredRow._fields), "ACQUIRE"))
    job = _job_from_acquired_row(parsed)
    claimed = ClaimedJob(
        job=job,
        trace_id=parsed.trace_id,
        lease_owner=parsed.lease_owner,
        lease_expires_at=parsed.lease_expires_at,
        claim_generation=parsed.claim_generation,
        claim_token=str(parsed.claim_token),
        execution_attempts=parsed.execution_attempts,
    )
    return GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=parsed.slot_ordinal,
        slot_generation=parsed.slot_generation,
        slot_token=str(parsed.slot_token),
        lease_until=parsed.slot_lease_until,
    )


def _job_from_acquired_row(row: _AcquiredRow) -> JobRecord:
    payload = _mapping(row.payload, "payload")
    result = None if row.result is None else _mapping(row.result, "result")
    return JobRecord(
        sequence=row.sequence,
        job_id=row.job_id,
        request=JobRequest(
            environment=row.environment,
            deployment_id=row.deployment_id,
            job_name=row.job_name,
            priority=JobPriority(row.priority),
            idempotence_key=JobIdempotenceKey(
                job_name=row.job_name,
                input_hash=row.input_hash,
                configuration_hash=row.configuration_hash,
                code_version=row.code_version,
                model_version=row.model_version,
            ),
            payload=payload,
        ),
        status=JobStatus(row.status),
        result=result,
        failure_reason=row.failure_reason,
    )


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, Mapping):
        raise RuntimeError(f"{field_name} PostgreSQL invalide")
    return decoded


def _row_values(row: Any, expected_length: int, row_name: str) -> tuple[Any, ...]:
    if not isinstance(row, (tuple, list)) or len(row) != expected_length:
        actual = len(row) if isinstance(row, (tuple, list)) else "non-sequence"
        raise RuntimeError(
            f"SQL_ROW_SHAPE_INVALID:{row_name}:expected={expected_length}:actual={actual}"
        )
    return tuple(row)


def _text(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise GraniteCapacityConfigurationError()
    return value


def _positive_integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GraniteCapacityConfigurationError()
    return value


def _heartbeat_seconds(value: Any, *, lease_seconds: int) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or value >= lease_seconds
    ):
        raise GraniteCapacityConfigurationError()
    return float(value)


def _job_names(value: Any, catalog: JobCatalog) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) == 0:
        raise GraniteCapacityConfigurationError()
    parsed = tuple(catalog.require_known_job(_text(name)) for name in value)
    if len(set(parsed)) != len(parsed):
        raise GraniteCapacityConfigurationError()
    return parsed


def _require_lease(value: Any) -> GraniteSlotLease:
    if not isinstance(value, GraniteSlotLease):
        raise GraniteCapacityConfigurationError()
    return value


__all__ = [
    "ClaimCompatibleTechnicalJob",
    "GraniteCapacityConfigurationError",
    "GraniteCapacityController",
    "GraniteExecution",
    "GraniteSlotLease",
    "GraniteSlotLeaseLostError",
    "GraniteWorker",
    "GraniteWorkerState",
    "HeartbeatClaimAndGraniteSlot",
    "PostgresGraniteSlotRepository",
    "ReleaseGraniteSlot",
]
