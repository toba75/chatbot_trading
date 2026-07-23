"""Quota PostgreSQL de deux slots Granite avec double fencing ADR-052."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Generic, NamedTuple, Protocol, TypeVar
from uuid import UUID

from app.contracts.technical_jobs import (
    ClaimedJob,
    GraniteModelStillRunning,
    JobEnvironmentIdentity,
    JobExecutionRequirements,
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


class GranitePageTerminalStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class GranitePageTerminalEnvelope:
    """Enveloppe platform immutable produite sous le double fencing actif."""

    completion_id: str
    status: GranitePageTerminalStatus
    payload: Mapping[str, Any]
    payload_fingerprint: str
    failure_reason: str | None

    def __post_init__(self) -> None:
        completion_id = _text(self.completion_id)
        if not isinstance(self.status, GranitePageTerminalStatus):
            raise GraniteCapacityConfigurationError()
        payload = _mapping(self.payload, "terminal_payload")
        canonical_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        fingerprint = sha256(canonical_payload.encode("utf-8")).hexdigest()
        if self.payload_fingerprint != fingerprint:
            raise GraniteCapacityConfigurationError()
        if self.status is GranitePageTerminalStatus.SUCCEEDED:
            if self.failure_reason is not None:
                raise GraniteCapacityConfigurationError()
        else:
            _text(self.failure_reason)
        object.__setattr__(self, "completion_id", completion_id)

    @classmethod
    def from_payload(
        cls,
        *,
        completion_id: str,
        status: GranitePageTerminalStatus,
        payload: Mapping[str, Any],
        failure_reason: str | None,
    ) -> "GranitePageTerminalEnvelope":
        parsed_payload = _mapping(payload, "terminal_payload")
        serialized = json.dumps(
            parsed_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(
            completion_id=completion_id,
            status=status,
            payload=parsed_payload,
            payload_fingerprint=sha256(serialized.encode("utf-8")).hexdigest(),
            failure_reason=failure_reason,
        )


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
        if (
            not isinstance(self.lease_until, datetime)
            or self.lease_until.tzinfo is None
        ):
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
        execution_requirements: JobExecutionRequirements | None = None,
    ) -> GraniteSlotLease | None: ...


class AcquireGraniteSlotForClaimedJob(Protocol):
    def acquire_for_claimed_job(
        self,
        *,
        worker: GraniteWorker,
        claimed_job: ClaimedJob,
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


class CompletePageExecution(Protocol):
    def complete_page_execution(
        self,
        lease: GraniteSlotLease,
        envelope: GranitePageTerminalEnvelope,
    ) -> JobRecord: ...


class SupervisedGraniteProcess(Protocol[ModelResultT]):
    def wait(self, *, timeout_seconds: float) -> ModelResultT: ...

    def terminate(self) -> None: ...


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
    execution_contract_name: str | None
    execution_contract_version: str | None
    capacity_capability: str | None
    capacity_slots: int | None
    capacity_device: str | None
    storage_environment: str | None
    source_artifact_ref: str | None
    result_artifact_ref: str | None
    execution_route_name: str | None
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


_CLAIMED_JOB_COLUMN_NAMES = _AcquiredRow._fields[:-4]
_QUALIFIED_CLAIMED_JOB_COLUMNS = ", ".join(
    f"job.{column}" for column in _CLAIMED_JOB_COLUMN_NAMES
)


class PostgresGraniteWorkerRegistry:
    """Autorité durable de présence, capacités et drainage des replicas."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise GraniteCapacityConfigurationError()
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise GraniteCapacityConfigurationError()
        self._connection_factory = connection_factory
        self._environment_identity = environment_identity

    def register(self, worker: GraniteWorker) -> None:
        self._require_worker(worker)
        if worker.state is not GraniteWorkerState.READY:
            raise GraniteCapacityConfigurationError()
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO platform.document_workers (
                        environment, deployment_id, worker_instance_id,
                        configuration_hash, storage_environment, state,
                        capabilities, drain_deadline
                    ) VALUES (
                        %(environment)s, %(deployment_id)s, %(worker_instance_id)s,
                        %(configuration_hash)s, %(storage_environment)s, 'READY',
                        %(capabilities)s, NULL
                    )
                    ON CONFLICT (environment, deployment_id, worker_instance_id)
                    DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                      WHERE document_workers.configuration_hash =
                            EXCLUDED.configuration_hash
                        AND document_workers.storage_environment =
                            EXCLUDED.storage_environment
                        AND document_workers.state = 'READY'
                        AND document_workers.capabilities = EXCLUDED.capabilities
                    RETURNING worker_instance_id
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "worker_instance_id": worker.worker_instance_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "storage_environment": worker.storage_environment,
                        "capabilities": sorted(worker.capabilities),
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteCapacityConfigurationError()

    def begin_draining(
        self,
        *,
        worker_instance_id: str,
        drain_deadline: datetime,
    ) -> None:
        parsed_worker = _text(worker_instance_id)
        if not isinstance(drain_deadline, datetime) or drain_deadline.tzinfo is None:
            raise GraniteCapacityConfigurationError()
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.document_workers
                       SET state = 'DRAINING',
                           drain_deadline = %(drain_deadline)s,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE environment = %(environment)s
                       AND deployment_id = %(deployment_id)s
                       AND worker_instance_id = %(worker_instance_id)s
                       AND configuration_hash = %(configuration_hash)s
                       AND state = 'READY'
                       AND %(drain_deadline)s > CURRENT_TIMESTAMP
                    RETURNING worker_instance_id
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "worker_instance_id": parsed_worker,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "drain_deadline": drain_deadline,
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteCapacityConfigurationError()

    def _require_worker(self, worker: GraniteWorker) -> None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError()


class PostgresGraniteSlotRepository(
    ClaimCompatibleTechnicalJob,
    AcquireGraniteSlotForClaimedJob,
    HeartbeatClaimAndGraniteSlot,
    ReleaseGraniteSlot,
    CompletePageExecution,
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
        execution_requirements: JobExecutionRequirements | None = None,
    ) -> GraniteSlotLease | None:
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_job_names = _job_names(job_names, self._catalog)
        if execution_requirements is not None and not isinstance(
            execution_requirements,
            JobExecutionRequirements,
        ):
            raise GraniteCapacityConfigurationError()
        requirements_filter = ""
        if execution_requirements is not None:
            requirements_filter = """
                           AND job.source_artifact_ref = %(source_artifact_ref)s
                           AND job.result_artifact_ref = %(result_artifact_ref)s
                           AND job.execution_route_name = %(execution_route_name)s
            """
        self._require_worker(worker)
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    -- LOCK_ORDER: document_worker -> technical_job -> granite_slot
                    WITH locked_worker AS MATERIALIZED (
                        SELECT worker.worker_instance_id
                          FROM platform.document_workers AS worker
                         WHERE worker.environment = %(environment)s
                           AND worker.deployment_id = %(deployment_id)s
                           AND worker.worker_instance_id = %(worker_instance_id)s
                           AND worker.configuration_hash = %(configuration_hash)s
                           AND worker.storage_environment = %(storage_environment)s
                           AND worker.state = 'READY'
                           AND worker.drain_deadline IS NULL
                           AND worker.capabilities =
                               ARRAY['DOCUMENT_STANDARD', 'GRANITE_CUDA']::text[]
                         FOR UPDATE OF worker
                    ),
                    candidate_job AS MATERIALIZED (
                        SELECT job.sequence, job.job_id
                          FROM platform.technical_jobs AS job
                          JOIN locked_worker ON true
                         WHERE job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.configuration_hash = %(configuration_hash)s
                           AND job.job_name = ANY(%(job_names)s)
                           AND job.execution_contract_name = 'CONVERT_PAGE'
                           AND job.execution_contract_version = '1.0'
                           AND job.capacity_capability = %(capacity_capability)s
                           AND job.capacity_slots = 1
                           AND job.capacity_device = %(capacity_device)s
                           AND job.storage_environment = %(storage_environment)s
                           AND job.source_artifact_ref IS NOT NULL
                           AND job.result_artifact_ref IS NOT NULL
                           {requirements_filter}
                           AND (
                                job.status = 'pending'
                               OR (
                                   job.status = 'running'
                                   AND job.lease_expires_at <= CURRENT_TIMESTAMP
                               )
                           )
                          ORDER BY
                               job.priority,
                               CASE WHEN job.status = 'pending' THEN 0 ELSE 1 END,
                               job.sequence
                         FOR UPDATE OF job SKIP LOCKED
                         LIMIT 1
                    ),
                    candidate_slot AS MATERIALIZED (
                        SELECT slot.environment, slot.deployment_id,
                               slot.slot_ordinal
                          FROM platform.granite_slots AS slot
                          WHERE slot.environment = %(environment)s
                            AND slot.deployment_id = %(deployment_id)s
                           AND EXISTS (SELECT 1 FROM candidate_job)
                           AND (
                               slot.lease_owner IS NULL
                               OR slot.lease_until <= CURRENT_TIMESTAMP
                           )
                           AND NOT EXISTS (
                               SELECT 1
                                 FROM platform.granite_slots AS held
                                 WHERE held.environment = %(environment)s
                                   AND held.deployment_id = %(deployment_id)s
                                   AND held.lease_owner = %(worker_instance_id)s
                                  AND held.lease_until > CURRENT_TIMESTAMP
                           )
                           AND (
                                slot.lease_owner = %(worker_instance_id)s
                               OR NOT EXISTS (
                                   SELECT 1
                                     FROM platform.granite_slots AS owned
                                     WHERE owned.environment = %(environment)s
                                       AND owned.deployment_id = %(deployment_id)s
                                       AND owned.lease_owner = %(worker_instance_id)s
                               )
                           )
                         ORDER BY
                               CASE
                                   WHEN slot.lease_owner = %(worker_instance_id)s
                                   THEN 0 ELSE 1
                               END,
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
                               lease_owner = %(worker_instance_id)s,
                               lease_expires_at = CURRENT_TIMESTAMP
                                   + (%(lease_seconds)s * INTERVAL '1 second'),
                               execution_attempts = execution_attempts + 1,
                               claim_generation = claim_generation + 1,
                               claim_token = gen_random_uuid()
                          FROM candidate_job, candidate_slot
                         WHERE job.sequence = candidate_job.sequence
                        RETURNING {_QUALIFIED_CLAIMED_JOB_COLUMNS}
                    ),
                    leased_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_owner = %(worker_instance_id)s,
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
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "worker_instance_id": worker.worker_instance_id,
                        "storage_environment": worker.storage_environment,
                        "job_names": list(parsed_job_names),
                        "capacity_capability": _GRANITE_CAPABILITY,
                        "capacity_device": _GRANITE_DEVICE,
                        "lease_seconds": parsed_lease_seconds,
                        "source_artifact_ref": (
                            execution_requirements.source_artifact_ref
                            if execution_requirements is not None
                            else None
                        ),
                        "result_artifact_ref": (
                            execution_requirements.result_artifact_ref
                            if execution_requirements is not None
                            else None
                        ),
                        "execution_route_name": (
                            execution_requirements.route_name
                            if execution_requirements is not None
                            else None
                        ),
                    },
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return _lease_from_row(row)

    def acquire_for_claimed_job(
        self,
        *,
        worker: GraniteWorker,
        claimed_job: ClaimedJob,
    ) -> GraniteSlotLease | None:
        """Pont M-004 : réserve un slot sans créer le fan-out page de T-005."""

        self._require_worker(worker)
        if (
            not isinstance(claimed_job, ClaimedJob)
            or claimed_job.job.request.environment_identity
            != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError()
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    -- LOCK_ORDER: document_worker -> technical_job -> granite_slot
                    WITH locked_worker AS MATERIALIZED (
                        SELECT worker.worker_instance_id
                          FROM platform.document_workers AS worker
                         WHERE worker.environment = %(environment)s
                           AND worker.deployment_id = %(deployment_id)s
                           AND worker.worker_instance_id = %(worker_instance_id)s
                           AND worker.configuration_hash = %(configuration_hash)s
                           AND worker.storage_environment = %(environment)s
                           AND worker.state = 'READY'
                           AND worker.drain_deadline IS NULL
                           AND worker.capabilities =
                               ARRAY['DOCUMENT_STANDARD', 'GRANITE_CUDA']::text[]
                         FOR UPDATE OF worker
                    ),
                    active_job AS MATERIALIZED (
                        SELECT job.job_id, job.lease_expires_at
                          FROM platform.technical_jobs AS job
                          JOIN locked_worker ON true
                         WHERE job.job_id = %(job_id)s
                           AND job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.configuration_hash = %(configuration_hash)s
                           AND job.status = 'running'
                           AND job.lease_owner = %(worker_instance_id)s
                           AND job.claim_generation = %(claim_generation)s
                           AND job.claim_token = %(claim_token)s::uuid
                           AND job.lease_expires_at > CURRENT_TIMESTAMP
                         FOR UPDATE OF job
                    ),
                    candidate_slot AS MATERIALIZED (
                        SELECT slot.slot_ordinal
                          FROM platform.granite_slots AS slot
                          JOIN active_job ON true
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND (
                                slot.lease_owner IS NULL
                               OR slot.lease_until <= CURRENT_TIMESTAMP
                           )
                           AND NOT EXISTS (
                               SELECT 1
                                 FROM platform.granite_slots AS held
                                WHERE held.environment = %(environment)s
                                  AND held.deployment_id = %(deployment_id)s
                                  AND held.lease_owner = %(worker_instance_id)s
                                  AND held.lease_until > CURRENT_TIMESTAMP
                           )
                         ORDER BY slot.slot_ordinal
                         FOR UPDATE OF slot SKIP LOCKED
                         LIMIT 1
                    ),
                    leased_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_owner = %(worker_instance_id)s,
                               job_id = active_job.job_id,
                               claim_generation = %(claim_generation)s,
                               claim_token = %(claim_token)s::uuid,
                               slot_generation = slot.slot_generation + 1,
                               slot_token = gen_random_uuid(),
                               lease_until = active_job.lease_expires_at,
                               updated_at = CURRENT_TIMESTAMP
                          FROM active_job, candidate_slot
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.slot_ordinal = candidate_slot.slot_ordinal
                        RETURNING slot.slot_ordinal, slot.slot_generation,
                                  slot.slot_token, slot.lease_until
                    )
                    SELECT leased_slot.slot_ordinal,
                           leased_slot.slot_generation,
                           leased_slot.slot_token,
                           active_job.lease_expires_at
                      FROM active_job
                      LEFT JOIN leased_slot ON true
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "worker_instance_id": worker.worker_instance_id,
                        "job_id": claimed_job.job.job_id,
                        "claim_generation": claimed_job.claim_generation,
                        "claim_token": claimed_job.claim_token,
                    },
                )
                row = cursor.fetchone()
        if row is None:
            raise GraniteSlotLeaseLostError()
        slot_ordinal, slot_generation, slot_token, lease_until = _row_values(
            row,
            4,
            "ACQUIRE_LEGACY",
        )
        if slot_ordinal is None:
            return None
        active_claim = ClaimedJob(
            job=claimed_job.job,
            trace_id=claimed_job.trace_id,
            lease_owner=claimed_job.lease_owner,
            lease_expires_at=lease_until,
            claim_generation=claimed_job.claim_generation,
            claim_token=claimed_job.claim_token,
            execution_attempts=claimed_job.execution_attempts,
        )
        return GraniteSlotLease(
            claimed_job=active_claim,
            slot_ordinal=slot_ordinal,
            slot_generation=slot_generation,
            slot_token=str(slot_token),
            lease_until=lease_until,
        )

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
                    WITH locked_worker AS MATERIALIZED (
                        SELECT worker.state, worker.drain_deadline
                          FROM platform.document_workers AS worker
                         WHERE worker.environment = %(environment)s
                           AND worker.deployment_id = %(deployment_id)s
                           AND worker.worker_instance_id = %(worker_instance_id)s
                           AND worker.configuration_hash = %(configuration_hash)s
                           AND worker.storage_environment = %(storage_environment)s
                           AND (
                                worker.state = 'READY'
                               OR (
                                   worker.state = 'DRAINING'
                                   AND worker.drain_deadline > CURRENT_TIMESTAMP
                               )
                           )
                         FOR UPDATE OF worker
                    ),
                    renewed_job AS (
                        UPDATE platform.technical_jobs AS job
                           SET lease_expires_at = CASE
                               WHEN locked_worker.state = 'DRAINING'
                               THEN LEAST(
                                   CURRENT_TIMESTAMP
                                       + (%(lease_seconds)s * INTERVAL '1 second'),
                                   locked_worker.drain_deadline
                               )
                               ELSE CURRENT_TIMESTAMP
                                   + (%(lease_seconds)s * INTERVAL '1 second')
                           END
                          FROM locked_worker
                         WHERE job.job_id = %(job_id)s
                           AND job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.configuration_hash = %(configuration_hash)s
                           AND job.status = 'running'
                           AND job.lease_owner = %(worker_instance_id)s
                           AND job.claim_generation = %(claim_generation)s
                           AND job.claim_token = %(claim_token)s::uuid
                           AND job.lease_expires_at > CURRENT_TIMESTAMP
                        RETURNING job.lease_expires_at
                    ),
                    renewed_slot AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_until = renewed_job.lease_expires_at,
                               updated_at = CURRENT_TIMESTAMP
                          FROM renewed_job
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.slot_ordinal = %(slot_ordinal)s
                           AND slot.lease_owner = %(worker_instance_id)s
                           AND slot.job_id = %(job_id)s
                           AND slot.claim_generation = %(claim_generation)s
                           AND slot.claim_token = %(claim_token)s::uuid
                           AND slot.slot_generation = %(slot_generation)s
                           AND slot.slot_token = %(slot_token)s::uuid
                           AND slot.lease_until > CURRENT_TIMESTAMP
                        RETURNING slot.lease_until
                    )
                    SELECT renewed_job.lease_expires_at,
                           renewed_slot.lease_until
                      FROM renewed_job
                      JOIN renewed_slot ON true
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "storage_environment": self._environment_identity.environment,
                        "worker_instance_id": claimed.lease_owner,
                        "job_id": claimed.job.job_id,
                        "claim_generation": claimed.claim_generation,
                        "claim_token": claimed.claim_token,
                        "slot_ordinal": parsed_lease.slot_ordinal,
                        "slot_generation": parsed_lease.slot_generation,
                        "slot_token": parsed_lease.slot_token,
                        "lease_seconds": parsed_seconds,
                    },
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
                         WHERE job.job_id = %(job_id)s
                           AND job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.configuration_hash = %(configuration_hash)s
                           AND job.status = 'running'
                           AND job.lease_owner = %(worker_instance_id)s
                           AND job.claim_generation = %(claim_generation)s
                           AND job.claim_token = %(claim_token)s::uuid
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
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.slot_ordinal = %(slot_ordinal)s
                           AND slot.lease_owner = %(worker_instance_id)s
                           AND slot.job_id = active_job.job_id
                           AND slot.claim_generation = %(claim_generation)s
                           AND slot.claim_token = %(claim_token)s::uuid
                           AND slot.slot_generation = %(slot_generation)s
                           AND slot.slot_token = %(slot_token)s::uuid
                           AND slot.lease_until > CURRENT_TIMESTAMP
                        RETURNING slot.slot_ordinal
                    )
                    SELECT slot_ordinal FROM released_slot
                    """,
                    {
                        "job_id": claimed.job.job_id,
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "worker_instance_id": claimed.lease_owner,
                        "claim_generation": claimed.claim_generation,
                        "claim_token": claimed.claim_token,
                        "slot_ordinal": parsed_lease.slot_ordinal,
                        "slot_generation": parsed_lease.slot_generation,
                        "slot_token": parsed_lease.slot_token,
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteSlotLeaseLostError()

    def complete_page_execution(
        self,
        lease: GraniteSlotLease,
        envelope: GranitePageTerminalEnvelope,
    ) -> JobRecord:
        parsed_lease = _require_lease(lease)
        if not isinstance(envelope, GranitePageTerminalEnvelope):
            raise GraniteCapacityConfigurationError()
        claimed = parsed_lease.claimed_job
        terminal_status = (
            JobStatus.SUCCEEDED
            if envelope.status is GranitePageTerminalStatus.SUCCEEDED
            else JobStatus.FAILED
        )
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH active_job AS MATERIALIZED (
                        SELECT job.job_id
                          FROM platform.technical_jobs AS job
                         WHERE job.job_id = %(job_id)s
                           AND job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.configuration_hash = %(configuration_hash)s
                           AND job.status = 'running'
                           AND job.lease_owner = %(worker_instance_id)s
                           AND job.claim_generation = %(claim_generation)s
                           AND job.claim_token = %(claim_token)s::uuid
                           AND job.lease_expires_at > CURRENT_TIMESTAMP
                         FOR UPDATE OF job
                    ),
                    active_slot AS MATERIALIZED (
                        SELECT slot.slot_ordinal
                          FROM platform.granite_slots AS slot
                          JOIN active_job ON active_job.job_id = slot.job_id
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.slot_ordinal = %(slot_ordinal)s
                           AND slot.lease_owner = %(worker_instance_id)s
                           AND slot.claim_generation = %(claim_generation)s
                           AND slot.claim_token = %(claim_token)s::uuid
                           AND slot.slot_generation = %(slot_generation)s
                           AND slot.slot_token = %(slot_token)s::uuid
                           AND slot.lease_until > CURRENT_TIMESTAMP
                         FOR UPDATE OF slot
                    ),
                    immutable_outbox AS (
                        INSERT INTO platform.page_completion_outbox (
                            completion_id, environment, deployment_id, job_id,
                            claim_generation, claim_token, worker_instance_id,
                            slot_ordinal, slot_generation, slot_token, payload,
                            payload_fingerprint, terminal_status, failure_reason,
                            status, relay_owner, relay_lease_until,
                            relay_generation, relay_token, relayed_at
                        )
                        SELECT
                            %(completion_id)s, %(environment)s, %(deployment_id)s,
                            active_job.job_id, %(claim_generation)s,
                            %(claim_token)s::uuid, %(worker_instance_id)s,
                            active_slot.slot_ordinal, %(slot_generation)s,
                            %(slot_token)s::uuid, %(payload)s::jsonb,
                            %(payload_fingerprint)s, %(terminal_status)s,
                            %(failure_reason)s, 'pending', NULL, NULL, 0, NULL, NULL
                          FROM active_job
                          JOIN active_slot ON true
                        RETURNING completion_id
                    ),
                    terminal_job AS (
                        UPDATE platform.technical_jobs AS job
                           SET status = CASE
                                   WHEN %(terminal_status)s = 'succeeded'
                                   THEN 'succeeded'
                                   ELSE 'failed'
                               END,
                               result = CASE
                                   WHEN %(terminal_status)s = 'succeeded'
                                   THEN jsonb_build_object(
                                       'completion_id', %(completion_id)s
                                   )
                                   ELSE NULL
                               END,
                               failure_reason = %(failure_reason)s,
                               lease_owner = NULL,
                               lease_expires_at = NULL,
                               claim_token = NULL
                          FROM immutable_outbox
                         WHERE job.job_id = %(job_id)s
                        RETURNING immutable_outbox.completion_id
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
                          FROM terminal_job
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.slot_ordinal = %(slot_ordinal)s
                           AND slot.slot_generation = %(slot_generation)s
                           AND slot.slot_token = %(slot_token)s::uuid
                        RETURNING terminal_job.completion_id
                    )
                    SELECT completion_id FROM released_slot
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": (
                            self._environment_identity.configuration_hash
                        ),
                        "job_id": claimed.job.job_id,
                        "worker_instance_id": claimed.lease_owner,
                        "claim_generation": claimed.claim_generation,
                        "claim_token": claimed.claim_token,
                        "slot_ordinal": parsed_lease.slot_ordinal,
                        "slot_generation": parsed_lease.slot_generation,
                        "slot_token": parsed_lease.slot_token,
                        "completion_id": envelope.completion_id,
                        "payload": json.dumps(
                            envelope.payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        "payload_fingerprint": envelope.payload_fingerprint,
                        "terminal_status": envelope.status.value,
                        "failure_reason": envelope.failure_reason,
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteSlotLeaseLostError()
        result = (
            {"completion_id": envelope.completion_id}
            if terminal_status is JobStatus.SUCCEEDED
            else None
        )
        return JobRecord(
            sequence=claimed.job.sequence,
            job_id=claimed.job.job_id,
            request=claimed.job.request,
            status=terminal_status,
            result=result,
            failure_reason=envelope.failure_reason,
        )

    def _require_worker(self, worker: GraniteWorker) -> None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError()


class GraniteCapacityController:
    """Contrôleur unique autour d'un appel modèle nécessitant Granite."""

    def __init__(self, *, repository: Any) -> None:
        for method_name in (
            "claim_compatible_job",
            "heartbeat",
            "complete_page_execution",
        ):
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
        execution_requirements: JobExecutionRequirements,
        start_model: Callable[
            [GraniteSlotLease], SupervisedGraniteProcess[ModelResultT]
        ],
        success_envelope: Callable[
            [GraniteSlotLease, ModelResultT], GranitePageTerminalEnvelope
        ],
        failure_envelope: Callable[
            [GraniteSlotLease, Exception], GranitePageTerminalEnvelope
        ],
    ) -> GraniteExecution[ModelResultT] | None:
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_heartbeat_seconds = _heartbeat_seconds(
            heartbeat_seconds,
            lease_seconds=parsed_lease_seconds,
        )
        if not all(
            callable(callback)
            for callback in (start_model, success_envelope, failure_envelope)
        ):
            raise GraniteCapacityConfigurationError()
        if not isinstance(execution_requirements, JobExecutionRequirements):
            raise GraniteCapacityConfigurationError()
        lease = self._repository.claim_compatible_job(
            worker=worker,
            lease_seconds=parsed_lease_seconds,
            job_names=job_names,
            execution_requirements=execution_requirements,
        )
        if lease is None:
            return None
        try:
            process = start_model(lease)
        except Exception as model_error:
            self._complete_failed_execution(
                lease=lease,
                model_error=model_error,
                failure_envelope=failure_envelope,
            )
            raise AssertionError("unreachable")
        if not callable(getattr(process, "wait", None)) or not callable(
            getattr(process, "terminate", None)
        ):
            raise GraniteCapacityConfigurationError()
        while True:
            try:
                result = process.wait(timeout_seconds=parsed_heartbeat_seconds)
                break
            except GraniteModelStillRunning:
                try:
                    lease = self._repository.heartbeat(
                        lease,
                        lease_seconds=parsed_lease_seconds,
                    )
                except Exception:
                    process.terminate()
                    raise
            except Exception as model_error:
                self._complete_failed_execution(
                    lease=lease,
                    model_error=model_error,
                    failure_envelope=failure_envelope,
                )
                raise AssertionError("unreachable")
        envelope = success_envelope(lease, result)
        self._repository.complete_page_execution(lease, envelope)
        return GraniteExecution(lease=lease, model_result=result)

    def execute_claimed_job(
        self,
        *,
        worker: GraniteWorker,
        claimed_job: ClaimedJob,
        lease_seconds: int,
        heartbeat_seconds: float,
        start_model: Callable[
            [GraniteSlotLease], SupervisedGraniteProcess[ModelResultT]
        ],
    ) -> GraniteExecution[ModelResultT]:
        """Protège le parcours M-004 sans produire les jobs page réservés à T-005."""

        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_heartbeat_seconds = _heartbeat_seconds(
            heartbeat_seconds,
            lease_seconds=parsed_lease_seconds,
        )
        acquire = getattr(self._repository, "acquire_for_claimed_job", None)
        if not callable(acquire) or not callable(start_model):
            raise GraniteCapacityConfigurationError()
        lease = acquire(worker=worker, claimed_job=claimed_job)
        while lease is None:
            time.sleep(parsed_heartbeat_seconds)
            lease = acquire(worker=worker, claimed_job=claimed_job)
        try:
            process = start_model(lease)
        except Exception as model_error:
            self._release_legacy_after_model_error(lease, model_error)
            raise AssertionError("unreachable")
        if not callable(getattr(process, "wait", None)) or not callable(
            getattr(process, "terminate", None)
        ):
            raise GraniteCapacityConfigurationError()
        while True:
            try:
                result = process.wait(timeout_seconds=parsed_heartbeat_seconds)
                break
            except GraniteModelStillRunning:
                try:
                    lease = self._repository.heartbeat(
                        lease,
                        lease_seconds=parsed_lease_seconds,
                    )
                except Exception:
                    process.terminate()
                    raise
            except Exception as model_error:
                self._release_legacy_after_model_error(lease, model_error)
                raise AssertionError("unreachable")
        self._repository.release(lease)
        return GraniteExecution(lease=lease, model_result=result)

    def _release_legacy_after_model_error(
        self,
        lease: GraniteSlotLease,
        model_error: Exception,
    ) -> None:
        try:
            self._repository.release(lease)
        except Exception as compensation_error:
            raise ExceptionGroup(
                "GRANITE_MODEL_AND_RELEASE_FAILURE",
                [model_error, compensation_error],
            ) from model_error
        raise model_error

    def _complete_failed_execution(
        self,
        *,
        lease: GraniteSlotLease,
        model_error: Exception,
        failure_envelope: Callable[
            [GraniteSlotLease, Exception], GranitePageTerminalEnvelope
        ],
    ) -> None:
        try:
            envelope = failure_envelope(lease, model_error)
            self._repository.complete_page_execution(lease, envelope)
        except Exception as compensation_error:
            raise ExceptionGroup(
                "GRANITE_MODEL_AND_TERMINAL_FAILURE",
                [model_error, compensation_error],
            ) from model_error
        raise model_error


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
            execution_requirements=JobExecutionRequirements(
                contract_name=_required_database_text(
                    row.execution_contract_name,
                    "execution_contract_name",
                ),
                contract_version=_required_database_text(
                    row.execution_contract_version,
                    "execution_contract_version",
                ),
                capacity_capability=_required_database_text(
                    row.capacity_capability,
                    "capacity_capability",
                ),
                capacity_slots=_required_database_integer(
                    row.capacity_slots,
                    "capacity_slots",
                ),
                capacity_device=_required_database_text(
                    row.capacity_device,
                    "capacity_device",
                ),
                storage_environment=_required_database_text(
                    row.storage_environment,
                    "storage_environment",
                ),
                source_artifact_ref=_required_database_text(
                    row.source_artifact_ref,
                    "source_artifact_ref",
                ),
                result_artifact_ref=_required_database_text(
                    row.result_artifact_ref,
                    "result_artifact_ref",
                ),
                route_name=_required_database_text(
                    row.execution_route_name,
                    "execution_route_name",
                ),
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


def _required_database_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise RuntimeError(f"{field_name} PostgreSQL invalide")
    return value


def _required_database_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{field_name} PostgreSQL invalide")
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
    "CompletePageExecution",
    "GraniteCapacityConfigurationError",
    "GraniteCapacityController",
    "GraniteExecution",
    "GraniteModelStillRunning",
    "GranitePageTerminalEnvelope",
    "GranitePageTerminalStatus",
    "GraniteSlotLease",
    "GraniteSlotLeaseLostError",
    "GraniteWorker",
    "GraniteWorkerState",
    "HeartbeatClaimAndGraniteSlot",
    "PostgresGraniteWorkerRegistry",
    "PostgresGraniteSlotRepository",
    "ReleaseGraniteSlot",
    "SupervisedGraniteProcess",
]
