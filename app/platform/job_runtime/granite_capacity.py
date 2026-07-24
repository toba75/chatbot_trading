"""Quota PostgreSQL de deux slots Granite avec double fencing ADR-052."""

from __future__ import annotations

import json
import math
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Generic, NamedTuple, Protocol, TypeVar
from uuid import UUID

from app.contracts.technical_jobs import (
    ClaimedJob,
    GraniteExecutionCapability,
    GraniteModelStillRunning,
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
    _issue_granite_execution_capability,
)
from app.platform.job_runtime import JobCatalog
from app.platform.postgres import PostgresConnectionFactory


_GENERALIST_CAPABILITIES = frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA"))
_GRANITE_CAPACITY_ERROR = "GRANITE_CAPACITY_CONFIGURATION_INVALID"
_JOB_LEASE_LOST = "JOB_LEASE_LOST"

ModelResultT = TypeVar("ModelResultT")


class GraniteCapacityConfigurationError(ValueError):
    """La capacité locale ne respecte pas le contrat strict T-003."""

    code = _GRANITE_CAPACITY_ERROR

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or reason.strip() == "":
            raise ValueError("motif Granite invalide")
        self.reason = reason
        super().__init__(f"{self.code}:{reason}")


class GraniteSlotLeaseLostError(RuntimeError):
    """Le claim ou le slot ne correspond plus au détenteur courant."""

    code = _JOB_LEASE_LOST

    def __init__(self) -> None:
        super().__init__(self.code)


class GranitePageCompletionConflictError(RuntimeError):
    """La même complétion terminale désigne une enveloppe divergente."""

    code = "GRANITE_PAGE_COMPLETION_CONFLICT"

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
            raise GraniteCapacityConfigurationError("TERMINAL_STATUS_INVALID")
        payload = _freeze_json_mapping(self.payload)
        canonical_payload = _canonical_json(payload)
        fingerprint = sha256(canonical_payload.encode("utf-8")).hexdigest()
        if self.payload_fingerprint != fingerprint:
            raise GraniteCapacityConfigurationError("TERMINAL_FINGERPRINT_MISMATCH")
        if self.status is GranitePageTerminalStatus.SUCCEEDED:
            if self.failure_reason is not None:
                raise GraniteCapacityConfigurationError("TERMINAL_FAILURE_FORBIDDEN")
        else:
            _text(self.failure_reason)
        object.__setattr__(self, "completion_id", completion_id)
        object.__setattr__(self, "payload", payload)

    @classmethod
    def from_payload(
        cls,
        *,
        completion_id: str,
        status: GranitePageTerminalStatus,
        payload: Mapping[str, Any],
        failure_reason: str | None,
    ) -> "GranitePageTerminalEnvelope":
        parsed_payload = _freeze_json_mapping(payload)
        serialized = _canonical_json(parsed_payload)
        return cls(
            completion_id=completion_id,
            status=status,
            payload=parsed_payload,
            payload_fingerprint=sha256(serialized.encode("utf-8")).hexdigest(),
            failure_reason=failure_reason,
        )

    def canonical_payload_json(self) -> str:
        """Revalide le hash immédiatement avant toute persistance."""

        serialized = _canonical_json(self.payload)
        if sha256(serialized.encode("utf-8")).hexdigest() != self.payload_fingerprint:
            raise GraniteCapacityConfigurationError("TERMINAL_FINGERPRINT_MISMATCH")
        return serialized


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
            raise GraniteCapacityConfigurationError("WORKER_ENVIRONMENT_IDENTITY_INVALID")
        if self.storage_environment != self.environment_identity.environment:
            raise GraniteCapacityConfigurationError("WORKER_STORAGE_ENVIRONMENT_MISMATCH")
        if not isinstance(self.state, GraniteWorkerState):
            raise GraniteCapacityConfigurationError("WORKER_STATE_INVALID")
        if self.capabilities != _GENERALIST_CAPABILITIES:
            raise GraniteCapacityConfigurationError("WORKER_CAPABILITIES_INVALID")
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
        execution_requirements: JobExecutionRequirements,
    ) -> GraniteSlotLease | None: ...


class AcquireGraniteSlotForClaimedJob(Protocol):
    def acquire_for_claimed_job(
        self,
        *,
        worker: GraniteWorker,
        claimed_job: ClaimedJob,
        lease_seconds: int,
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

_CLAIM_COMPATIBLE_JOB_SQL = f"""
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
       AND worker.presence_lease_until > CURRENT_TIMESTAMP
       AND worker.capabilities = ARRAY['DOCUMENT_STANDARD', 'GRANITE_CUDA']::text[]
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
       AND job.execution_contract_name = %(execution_contract_name)s
       AND job.execution_contract_version = %(execution_contract_version)s
       AND job.capacity_capability = %(capacity_capability)s
       AND job.capacity_slots = %(capacity_slots)s
       AND job.capacity_device = %(capacity_device)s
       AND job.storage_environment = %(storage_environment)s
       AND (
            job.status = 'pending'
           OR (job.status = 'running' AND job.lease_expires_at <= CURRENT_TIMESTAMP)
       )
     ORDER BY job.priority,
              CASE WHEN job.status = 'pending' THEN 0 ELSE 1 END,
              job.sequence
     FOR UPDATE OF job SKIP LOCKED
     LIMIT 1
),
owned_expired_slot AS MATERIALIZED (
    SELECT slot.environment, slot.deployment_id, slot.slot_ordinal
      FROM platform.granite_slots AS slot
     WHERE slot.environment = %(environment)s
       AND slot.deployment_id = %(deployment_id)s
       AND EXISTS (SELECT 1 FROM candidate_job)
       AND slot.lease_owner = %(worker_instance_id)s
       AND slot.lease_until <= CURRENT_TIMESTAMP
     FOR UPDATE OF slot SKIP LOCKED
     LIMIT 1
), fallback_slot AS MATERIALIZED (
    SELECT slot.environment, slot.deployment_id, slot.slot_ordinal
      FROM platform.granite_slots AS slot
     WHERE slot.environment = %(environment)s
       AND slot.deployment_id = %(deployment_id)s
       AND EXISTS (SELECT 1 FROM candidate_job)
       AND NOT EXISTS (SELECT 1 FROM owned_expired_slot)
       AND (slot.lease_owner IS NULL OR slot.lease_until <= CURRENT_TIMESTAMP)
       AND NOT EXISTS (
            SELECT 1 FROM platform.granite_slots AS held
             WHERE held.environment = %(environment)s
               AND held.deployment_id = %(deployment_id)s
               AND held.lease_owner = %(worker_instance_id)s
       )
     ORDER BY slot.slot_ordinal
     FOR UPDATE OF slot SKIP LOCKED
     LIMIT 1
), candidate_slot AS MATERIALIZED (
    SELECT * FROM owned_expired_slot
    UNION ALL
    SELECT * FROM fallback_slot
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
    RETURNING slot.slot_ordinal, slot.slot_generation, slot.slot_token,
              slot.lease_until AS slot_lease_until
)
SELECT claimed_job.*, leased_slot.*
  FROM claimed_job
  JOIN leased_slot ON true
"""


def _claim_compatible_job_parameters(
    *,
    environment_identity: JobEnvironmentIdentity,
    worker: GraniteWorker,
    lease_seconds: int,
    job_names: tuple[str, ...],
    execution_requirements: JobExecutionRequirements,
) -> dict[str, Any]:
    if not isinstance(environment_identity, JobEnvironmentIdentity):
        raise GraniteCapacityConfigurationError("ENVIRONMENT_IDENTITY_INVALID")
    if (
        not isinstance(worker, GraniteWorker)
        or worker.environment_identity != environment_identity
    ):
        raise GraniteCapacityConfigurationError("WORKER_IDENTITY_MISMATCH")
    if not isinstance(execution_requirements, JobExecutionRequirements):
        raise GraniteCapacityConfigurationError("EXECUTION_REQUIREMENTS_INVALID")
    parsed_seconds = _positive_integer(lease_seconds)
    if not isinstance(job_names, tuple) or not job_names:
        raise GraniteCapacityConfigurationError("JOB_NAMES_INVALID")
    parsed_names = tuple(_text(name) for name in job_names)
    return {
        "environment": environment_identity.environment,
        "deployment_id": environment_identity.deployment_id,
        "configuration_hash": environment_identity.configuration_hash,
        "worker_instance_id": worker.worker_instance_id,
        "storage_environment": execution_requirements.storage_environment,
        "job_names": list(parsed_names),
        "execution_contract_name": execution_requirements.contract_name,
        "execution_contract_version": execution_requirements.contract_version,
        "capacity_capability": execution_requirements.capacity_capability,
        "capacity_slots": execution_requirements.capacity_slots,
        "capacity_device": execution_requirements.capacity_device,
        "lease_seconds": parsed_seconds,
    }


class PostgresGraniteWorkerRegistry:
    """Autorité durable de présence, capacités et drainage des replicas."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise GraniteCapacityConfigurationError("CONNECTION_FACTORY_PORT_INCOMPLETE")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise GraniteCapacityConfigurationError("ENVIRONMENT_IDENTITY_INVALID")
        self._connection_factory = connection_factory
        self._environment_identity = environment_identity

    def register(self, worker: GraniteWorker, *, presence_lease_seconds: int) -> None:
        self._require_worker(worker)
        parsed_presence_seconds = _positive_integer(presence_lease_seconds)
        if worker.state is not GraniteWorkerState.READY:
            raise GraniteCapacityConfigurationError("WORKER_REGISTER_STATE_INVALID")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO platform.document_workers (
                        environment, deployment_id, worker_instance_id,
                        configuration_hash, storage_environment, state,
                        capabilities, presence_lease_until, drain_deadline
                    ) VALUES (
                        %(environment)s, %(deployment_id)s, %(worker_instance_id)s,
                        %(configuration_hash)s, %(storage_environment)s, 'READY',
                        %(capabilities)s,
                        CURRENT_TIMESTAMP + (%(presence_lease_seconds)s * INTERVAL '1 second'),
                        NULL
                    )
                    ON CONFLICT (environment, deployment_id, worker_instance_id)
                    DO UPDATE SET presence_lease_until =
                                      EXCLUDED.presence_lease_until,
                                  updated_at = CURRENT_TIMESTAMP
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
                        "presence_lease_seconds": parsed_presence_seconds,
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteCapacityConfigurationError("WORKER_REGISTER_CONFLICT")

    def heartbeat_presence(
        self,
        worker: GraniteWorker,
        *,
        presence_lease_seconds: int,
    ) -> datetime:
        self._require_worker(worker)
        parsed_presence_seconds = _positive_integer(presence_lease_seconds)
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.document_workers
                       SET presence_lease_until = CURRENT_TIMESTAMP
                               + (%(presence_lease_seconds)s * INTERVAL '1 second'),
                           updated_at = CURRENT_TIMESTAMP
                     WHERE environment = %(environment)s
                       AND deployment_id = %(deployment_id)s
                       AND worker_instance_id = %(worker_instance_id)s
                       AND configuration_hash = %(configuration_hash)s
                       AND state = 'READY'
                       AND presence_lease_until > CURRENT_TIMESTAMP
                    RETURNING presence_lease_until
                    """,
                    {
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "worker_instance_id": worker.worker_instance_id,
                        "configuration_hash": self._environment_identity.configuration_hash,
                        "presence_lease_seconds": parsed_presence_seconds,
                    },
                )
                row = cursor.fetchone()
        if row is None:
            raise GraniteSlotLeaseLostError()
        (presence_lease_until,) = _row_values(row, 1, "WORKER_PRESENCE")
        return presence_lease_until

    def begin_draining(
        self,
        *,
        worker_instance_id: str,
        drain_deadline: datetime,
    ) -> None:
        parsed_worker = _text(worker_instance_id)
        if not isinstance(drain_deadline, datetime) or drain_deadline.tzinfo is None:
            raise GraniteCapacityConfigurationError("DRAIN_DEADLINE_INVALID")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH draining_worker AS (
                        UPDATE platform.document_workers
                           SET state = 'DRAINING',
                               drain_deadline = %(drain_deadline)s,
                               presence_lease_until = LEAST(
                                   presence_lease_until,
                                   %(drain_deadline)s
                               ),
                               updated_at = CURRENT_TIMESTAMP
                         WHERE environment = %(environment)s
                           AND deployment_id = %(deployment_id)s
                           AND worker_instance_id = %(worker_instance_id)s
                           AND configuration_hash = %(configuration_hash)s
                           AND state = 'READY'
                           AND %(drain_deadline)s > CURRENT_TIMESTAMP
                        RETURNING worker_instance_id
                    ), bounded_jobs AS (
                        UPDATE platform.technical_jobs AS job
                           SET lease_expires_at = LEAST(
                                   job.lease_expires_at,
                                   %(drain_deadline)s
                               )
                          FROM draining_worker
                         WHERE job.environment = %(environment)s
                           AND job.deployment_id = %(deployment_id)s
                           AND job.lease_owner = draining_worker.worker_instance_id
                           AND job.status = 'running'
                        RETURNING job.job_id
                    ), bounded_slots AS (
                        UPDATE platform.granite_slots AS slot
                           SET lease_until = LEAST(
                                   slot.lease_until,
                                   %(drain_deadline)s
                               ),
                               updated_at = CURRENT_TIMESTAMP
                          FROM draining_worker
                         WHERE slot.environment = %(environment)s
                           AND slot.deployment_id = %(deployment_id)s
                           AND slot.lease_owner = draining_worker.worker_instance_id
                        RETURNING slot.slot_ordinal
                    )
                    SELECT worker_instance_id FROM draining_worker
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
                    raise GraniteCapacityConfigurationError("WORKER_DRAIN_TRANSITION_INVALID")

    def _require_worker(self, worker: GraniteWorker) -> None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError("WORKER_IDENTITY_MISMATCH")


class GraniteWorkerPresenceHeartbeat:
    """Renouvelle la présence durable; un crash laisse expirer son autorité."""

    def __init__(
        self,
        *,
        registry: PostgresGraniteWorkerRegistry,
        worker: GraniteWorker,
        presence_lease_seconds: int,
        heartbeat_seconds: float,
    ) -> None:
        if not isinstance(registry, PostgresGraniteWorkerRegistry):
            raise GraniteCapacityConfigurationError("WORKER_REGISTRY_INVALID")
        if not isinstance(worker, GraniteWorker):
            raise GraniteCapacityConfigurationError("WORKER_IDENTITY_INVALID")
        parsed_lease_seconds = _positive_integer(presence_lease_seconds)
        parsed_heartbeat_seconds = _heartbeat_seconds(
            heartbeat_seconds,
            lease_seconds=parsed_lease_seconds,
        )
        self._registry = registry
        self._worker = worker
        self._presence_lease_seconds = parsed_lease_seconds
        self._heartbeat_seconds = parsed_heartbeat_seconds
        self._stop = threading.Event()
        self._failure: Exception | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"granite-presence-{worker.worker_instance_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def assert_alive(self) -> None:
        if self._failure is not None:
            raise RuntimeError("GRANITE_WORKER_PRESENCE_HEARTBEAT_FAILED") from self._failure

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self._heartbeat_seconds * 2))
        if self._thread.is_alive():
            raise RuntimeError("GRANITE_WORKER_PRESENCE_HEARTBEAT_STOP_TIMEOUT")

    def _run(self) -> None:
        while not self._stop.wait(self._heartbeat_seconds):
            try:
                self._registry.heartbeat_presence(
                    self._worker,
                    presence_lease_seconds=self._presence_lease_seconds,
                )
            except Exception as error:
                self._failure = error
                self._stop.set()
                return


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
            raise GraniteCapacityConfigurationError("CONNECTION_FACTORY_PORT_INCOMPLETE")
        if not isinstance(catalog, JobCatalog):
            raise GraniteCapacityConfigurationError("JOB_CATALOG_INVALID")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise GraniteCapacityConfigurationError("ENVIRONMENT_IDENTITY_INVALID")
        self._connection_factory = connection_factory
        self._catalog = catalog
        self._environment_identity = environment_identity

    def claim_compatible_job(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        job_names: tuple[str, ...],
        execution_requirements: JobExecutionRequirements,
    ) -> GraniteSlotLease | None:
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_job_names = _job_names(job_names, self._catalog)
        if not isinstance(execution_requirements, JobExecutionRequirements):
            raise GraniteCapacityConfigurationError("EXECUTION_REQUIREMENTS_INVALID")
        self._require_worker(worker)
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    _CLAIM_COMPATIBLE_JOB_SQL,
                    _claim_compatible_job_parameters(
                        environment_identity=self._environment_identity,
                        worker=worker,
                        lease_seconds=parsed_lease_seconds,
                        job_names=parsed_job_names,
                        execution_requirements=execution_requirements,
                    ),
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
        lease_seconds: int,
    ) -> GraniteSlotLease | None:
        """Pont M-004 : réserve un slot sans créer le fan-out page de T-005."""

        self._require_worker(worker)
        parsed_lease_seconds = _positive_integer(lease_seconds)
        if (
            not isinstance(claimed_job, ClaimedJob)
            or claimed_job.job.request.environment_identity
            != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError("CLAIMED_JOB_IDENTITY_MISMATCH")
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
                           AND worker.presence_lease_until > CURRENT_TIMESTAMP
                           AND worker.capabilities =
                               ARRAY['DOCUMENT_STANDARD', 'GRANITE_CUDA']::text[]
                         FOR UPDATE OF worker
                    ),
                    active_job AS MATERIALIZED (
                        UPDATE platform.technical_jobs AS job
                           SET lease_expires_at = CURRENT_TIMESTAMP
                               + (%(lease_seconds)s * INTERVAL '1 second')
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
                        RETURNING job.job_id, job.lease_expires_at
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
                        "lease_seconds": parsed_lease_seconds,
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
                           AND worker.presence_lease_until > CURRENT_TIMESTAMP
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
            raise GraniteCapacityConfigurationError("TERMINAL_ENVELOPE_INVALID")
        claimed = parsed_lease.claimed_job
        canonical_payload = envelope.canonical_payload_json()
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (envelope.completion_id,),
                )
                cursor.execute(
                    """
                    SELECT job_id, claim_generation, claim_token::text,
                           worker_instance_id, slot_ordinal, slot_generation,
                           slot_token::text, payload, payload_fingerprint,
                           terminal_status, failure_reason
                      FROM platform.page_completion_outbox
                     WHERE completion_id = %(completion_id)s
                     FOR UPDATE
                    """,
                    {"completion_id": envelope.completion_id},
                )
                existing = cursor.fetchone()
                if existing is not None:
                    actual = _row_values(existing, 11, "EXISTING_COMPLETION")
                    expected = (
                        claimed.job.job_id,
                        claimed.claim_generation,
                        claimed.claim_token,
                        claimed.lease_owner,
                        parsed_lease.slot_ordinal,
                        parsed_lease.slot_generation,
                        parsed_lease.slot_token,
                        json.loads(canonical_payload),
                        envelope.payload_fingerprint,
                        envelope.status.value,
                        envelope.failure_reason,
                    )
                    actual_payload = _mapping(actual[7], "completion_payload")
                    comparable_actual = actual[:7] + (
                        json.loads(_canonical_json(actual_payload)),
                    ) + actual[8:]
                    if comparable_actual != expected:
                        raise GranitePageCompletionConflictError()
                    return _terminal_job_record(claimed, envelope)
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
                        "payload": canonical_payload,
                        "payload_fingerprint": envelope.payload_fingerprint,
                        "terminal_status": envelope.status.value,
                        "failure_reason": envelope.failure_reason,
                    },
                )
                if cursor.fetchone() is None:
                    raise GraniteSlotLeaseLostError()
        return _terminal_job_record(claimed, envelope)

    def _require_worker(self, worker: GraniteWorker) -> None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise GraniteCapacityConfigurationError("WORKER_IDENTITY_MISMATCH")


class GraniteCapacityController:
    """Contrôleur unique autour d'un appel modèle nécessitant Granite."""

    def __init__(self, *, repository: Any) -> None:
        for method_name in (
            "claim_compatible_job",
            "heartbeat",
            "complete_page_execution",
        ):
            if not callable(getattr(repository, method_name, None)):
                raise GraniteCapacityConfigurationError("REPOSITORY_PORT_INCOMPLETE")
        self._repository = repository
        self._process_lock = threading.Lock()
        self._active_process: SupervisedGraniteProcess[Any] | None = None
        self._draining = False

    def execute_next(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        heartbeat_seconds: float,
        job_names: tuple[str, ...],
        execution_requirements: JobExecutionRequirements,
        start_model: Callable[
            [GraniteExecutionCapability], SupervisedGraniteProcess[ModelResultT]
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
            raise GraniteCapacityConfigurationError("MODEL_CALLBACK_INVALID")
        if not isinstance(execution_requirements, JobExecutionRequirements):
            raise GraniteCapacityConfigurationError("EXECUTION_REQUIREMENTS_INVALID")
        lease = self._repository.claim_compatible_job(
            worker=worker,
            lease_seconds=parsed_lease_seconds,
            job_names=job_names,
            execution_requirements=execution_requirements,
        )
        if lease is None:
            return None
        lease, result = self._execute_supervised(
            lease=lease,
            lease_seconds=parsed_lease_seconds,
            heartbeat_seconds=parsed_heartbeat_seconds,
            start_model=start_model,
            on_model_error=lambda active_lease, error: self._complete_failed_execution(
                lease=active_lease,
                model_error=error,
                failure_envelope=failure_envelope,
            ),
        )
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
            [GraniteExecutionCapability], SupervisedGraniteProcess[ModelResultT]
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
            raise GraniteCapacityConfigurationError("LEGACY_EXECUTION_PORT_INCOMPLETE")
        self._require_admissions_open()
        lease = acquire(
            worker=worker,
            claimed_job=claimed_job,
            lease_seconds=parsed_lease_seconds,
        )
        while lease is None:
            self._require_admissions_open()
            time.sleep(parsed_heartbeat_seconds)
            lease = acquire(
                worker=worker,
                claimed_job=claimed_job,
                lease_seconds=parsed_lease_seconds,
            )
        lease, result = self._execute_supervised(
            lease=lease,
            lease_seconds=parsed_lease_seconds,
            heartbeat_seconds=parsed_heartbeat_seconds,
            start_model=start_model,
            on_model_error=self._release_legacy_after_model_error,
        )
        self._repository.release(lease)
        return GraniteExecution(lease=lease, model_result=result)

    def execute_acquired_page_job(
        self,
        *,
        lease: GraniteSlotLease,
        lease_seconds: int,
        heartbeat_seconds: float,
        start_model: Callable[
            [GraniteExecutionCapability], SupervisedGraniteProcess[ModelResultT]
        ],
    ) -> GraniteExecution[ModelResultT]:
        """Supervise un job page dont claim et slot ont été acquis atomiquement."""

        parsed_lease = _require_lease(lease)
        parsed_lease_seconds = _positive_integer(lease_seconds)
        parsed_heartbeat_seconds = _heartbeat_seconds(
            heartbeat_seconds,
            lease_seconds=parsed_lease_seconds,
        )
        if not callable(start_model):
            raise GraniteCapacityConfigurationError("MODEL_CALLBACK_INVALID")
        self._require_admissions_open()

        def propagate_model_error(
            _active_lease: GraniteSlotLease,
            model_error: Exception,
        ) -> None:
            raise model_error

        active_lease, result = self._execute_supervised(
            lease=parsed_lease,
            lease_seconds=parsed_lease_seconds,
            heartbeat_seconds=parsed_heartbeat_seconds,
            start_model=start_model,
            on_model_error=propagate_model_error,
        )
        return GraniteExecution(lease=active_lease, model_result=result)

    def begin_draining(self) -> None:
        """Interdit les admissions sans interrompre le couple actif."""

        with self._process_lock:
            self._draining = True

    def terminate_active_process(self) -> None:
        """Force l'arrêt du modèle après perte de lease ou échéance de drainage."""

        with self._process_lock:
            self._draining = True
            process = self._active_process
        if process is not None:
            process.terminate()

    def _execute_supervised(
        self,
        *,
        lease: GraniteSlotLease,
        lease_seconds: int,
        heartbeat_seconds: float,
        start_model: Callable[
            [GraniteExecutionCapability], SupervisedGraniteProcess[ModelResultT]
        ],
        on_model_error: Callable[[GraniteSlotLease, Exception], None],
    ) -> tuple[GraniteSlotLease, ModelResultT]:
        with self._process_lock:
            if self._draining:
                raise GraniteSlotLeaseLostError()
        try:
            process = start_model(_issue_granite_execution_capability())
        except Exception as model_error:
            on_model_error(lease, model_error)
            raise AssertionError("unreachable")
        if not callable(getattr(process, "wait", None)) or not callable(
            getattr(process, "terminate", None)
        ):
            raise GraniteCapacityConfigurationError("MODEL_PROCESS_PORT_INCOMPLETE")
        with self._process_lock:
            if self._draining:
                must_terminate = True
            else:
                self._active_process = process
                must_terminate = False
        if must_terminate:
            process.terminate()
            raise GraniteSlotLeaseLostError()
        try:
            while True:
                try:
                    return lease, process.wait(timeout_seconds=heartbeat_seconds)
                except GraniteModelStillRunning:
                    try:
                        lease = self._repository.heartbeat(
                            lease,
                            lease_seconds=lease_seconds,
                        )
                    except Exception as lease_error:
                        try:
                            process.terminate()
                        except Exception as termination_error:
                            raise ExceptionGroup(
                                "GRANITE_LEASE_AND_TERMINATION_FAILURE",
                                [lease_error, termination_error],
                            ) from lease_error
                        raise
                except Exception as model_error:
                    on_model_error(lease, model_error)
                    raise AssertionError("unreachable")
        finally:
            with self._process_lock:
                if self._active_process is process:
                    self._active_process = None

    def _require_admissions_open(self) -> None:
        with self._process_lock:
            if self._draining:
                raise GraniteSlotLeaseLostError()

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


def _terminal_job_record(
    claimed: ClaimedJob,
    envelope: GranitePageTerminalEnvelope,
) -> JobRecord:
    terminal_status = (
        JobStatus.SUCCEEDED
        if envelope.status is GranitePageTerminalStatus.SUCCEEDED
        else JobStatus.FAILED
    )
    return JobRecord(
        sequence=claimed.job.sequence,
        job_id=claimed.job.job_id,
        request=claimed.job.request,
        status=terminal_status,
        result=(
            {"completion_id": envelope.completion_id}
            if terminal_status is JobStatus.SUCCEEDED
            else None
        ),
        failure_reason=envelope.failure_reason,
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


def _freeze_json_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
    frozen = _freeze_json_value(value)
    if not isinstance(frozen, Mapping):
        raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
    return frozen


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
            frozen[key] = _freeze_json_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_FINITE")
        return value
    raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    return value


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_compatible(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _row_values(row: Any, expected_length: int, row_name: str) -> tuple[Any, ...]:
    if not isinstance(row, (tuple, list)) or len(row) != expected_length:
        actual = len(row) if isinstance(row, (tuple, list)) else "non-sequence"
        raise RuntimeError(
            f"SQL_ROW_SHAPE_INVALID:{row_name}:expected={expected_length}:actual={actual}"
        )
    return tuple(row)


def _text(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise GraniteCapacityConfigurationError("TEXT_VALUE_INVALID")
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
        raise GraniteCapacityConfigurationError("POSITIVE_INTEGER_REQUIRED")
    return value


def _heartbeat_seconds(value: Any, *, lease_seconds: int) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or value >= lease_seconds
    ):
        raise GraniteCapacityConfigurationError("HEARTBEAT_INTERVAL_INVALID")
    return float(value)


def _job_names(value: Any, catalog: JobCatalog) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) == 0:
        raise GraniteCapacityConfigurationError("JOB_NAMES_INVALID")
    parsed = tuple(catalog.require_known_job(_text(name)) for name in value)
    if len(set(parsed)) != len(parsed):
        raise GraniteCapacityConfigurationError("JOB_NAMES_DUPLICATED")
    return parsed


def _require_lease(value: Any) -> GraniteSlotLease:
    if not isinstance(value, GraniteSlotLease):
        raise GraniteCapacityConfigurationError("GRANITE_SLOT_LEASE_INVALID")
    return value


__all__ = [
    "ClaimCompatibleTechnicalJob",
    "CompletePageExecution",
    "GraniteCapacityConfigurationError",
    "GraniteCapacityController",
    "GraniteExecution",
    "GraniteModelStillRunning",
    "GranitePageTerminalEnvelope",
    "GranitePageCompletionConflictError",
    "GranitePageTerminalStatus",
    "GraniteSlotLease",
    "GraniteSlotLeaseLostError",
    "GraniteWorker",
    "GraniteWorkerPresenceHeartbeat",
    "GraniteWorkerState",
    "HeartbeatClaimAndGraniteSlot",
    "PostgresGraniteWorkerRegistry",
    "PostgresGraniteSlotRepository",
    "ReleaseGraniteSlot",
    "SupervisedGraniteProcess",
]
