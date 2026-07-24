"""Relais durable des enveloppes de complétion ``platform`` vers SP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobRecord,
    JobStatus,
)
from app.platform.job_runtime import JobCatalog
from app.platform.job_runtime.granite_capacity import (
    GranitePageCompletionConflictError,
    GranitePageTerminalEnvelope,
    GraniteSlotLease,
    GraniteWorker,
)
from app.platform.job_runtime.postgres import JobLeaseConflictError, PostgresJobQueue
from app.platform.postgres import PostgresConnectionFactory


@dataclass(frozen=True, slots=True)
class PageCompletionMessage:
    """Fait platform immutable, transporté sans transaction intercontexte."""

    completion_id: str
    environment: str
    deployment_id: str
    job_id: str
    claim_generation: int
    claim_token: str
    worker_instance_id: str
    slot_ordinal: int | None
    slot_generation: int | None
    slot_token: str | None
    payload: Mapping[str, Any]
    payload_fingerprint: str
    terminal_status: str
    failure_reason: str | None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.completion_id, "completion_id"),
            (self.environment, "environment"),
            (self.deployment_id, "deployment_id"),
            (self.job_id, "job_id"),
            (self.claim_token, "claim_token"),
            (self.worker_instance_id, "worker_instance_id"),
            (self.payload_fingerprint, "payload_fingerprint"),
            (self.terminal_status, "terminal_status"),
        ):
            _text(value, field_name)
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("environment invalide")
        if isinstance(self.claim_generation, bool) or self.claim_generation < 1:
            raise ValueError("claim_generation invalide")
        _uuid4(self.claim_token, "claim_token")
        _validate_slot_identity(
            ordinal=self.slot_ordinal,
            generation=self.slot_generation,
            token=self.slot_token,
        )
        if not isinstance(self.payload, Mapping) or len(self.payload) == 0:
            raise ValueError("payload invalide")
        fingerprint = hashlib.sha256(
            _canonical_payload(self.payload).encode("utf-8")
        ).hexdigest()
        if fingerprint != self.payload_fingerprint:
            raise ValueError("payload_fingerprint invalide")
        if self.terminal_status == "succeeded":
            if self.failure_reason is not None:
                raise ValueError("failure_reason interdit")
        elif self.terminal_status in {"failed", "abandoned"}:
            _text(self.failure_reason, "failure_reason")
        else:
            raise ValueError("terminal_status invalide")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @classmethod
    def from_execution(
        cls,
        *,
        claimed_job: ClaimedJob,
        granite_lease: GraniteSlotLease | None,
        envelope: GranitePageTerminalEnvelope,
    ) -> "PageCompletionMessage":
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        if not isinstance(envelope, GranitePageTerminalEnvelope):
            raise ValueError("envelope invalide")
        if granite_lease is not None and granite_lease.claimed_job != claimed_job:
            raise ValueError("granite_lease divergente")
        request = claimed_job.job.request
        return cls(
            completion_id=envelope.completion_id,
            environment=request.environment,
            deployment_id=request.deployment_id,
            job_id=claimed_job.job.job_id,
            claim_generation=claimed_job.claim_generation,
            claim_token=claimed_job.claim_token,
            worker_instance_id=claimed_job.lease_owner,
            slot_ordinal=None if granite_lease is None else granite_lease.slot_ordinal,
            slot_generation=(
                None if granite_lease is None else granite_lease.slot_generation
            ),
            slot_token=None if granite_lease is None else granite_lease.slot_token,
            payload=envelope.payload,
            payload_fingerprint=envelope.payload_fingerprint,
            terminal_status=envelope.status.value,
            failure_reason=envelope.failure_reason,
        )


@dataclass(frozen=True, slots=True)
class ClaimedPageCompletion:
    message: PageCompletionMessage
    owner_id: str
    relay_generation: int
    relay_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.message, PageCompletionMessage):
            raise ValueError("message invalide")
        _text(self.owner_id, "owner_id")
        if isinstance(self.relay_generation, bool) or self.relay_generation < 1:
            raise ValueError("relay_generation invalide")
        _uuid4(self.relay_token, "relay_token")


class PageCompletionOutbox(Protocol):
    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedPageCompletion | None: ...

    def acknowledge(self, claim: ClaimedPageCompletion) -> None: ...


class PageCompletionConsumer(Protocol):
    def record_page_completion(self, message: PageCompletionMessage) -> bool: ...


class PageCompletionRelay:
    """Committe SP avant l'ACK platform, puis tolère toute redélivrance."""

    def __init__(
        self,
        *,
        outbox: PageCompletionOutbox,
        consumer: PageCompletionConsumer,
    ) -> None:
        if not callable(getattr(outbox, "claim_next", None)) or not callable(
            getattr(outbox, "acknowledge", None)
        ):
            raise ValueError("PAGE_COMPLETION_OUTBOX_INCOMPLETE")
        if not callable(getattr(consumer, "record_page_completion", None)):
            raise ValueError("PAGE_COMPLETION_CONSUMER_INCOMPLETE")
        self._outbox = outbox
        self._consumer = consumer

    def relay_pending(self, *, limit: int, owner_id: str, lease_seconds: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit invalide")
        _text(owner_id, "owner_id")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or lease_seconds < 1
        ):
            raise ValueError("lease_seconds invalide")
        relayed = 0
        for _ in range(limit):
            claim = self._outbox.claim_next(
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
            if claim is None:
                return relayed
            self.relay_claim(claim)
            relayed += 1
        return relayed

    def relay_claim(self, claim: ClaimedPageCompletion) -> bool:
        if not isinstance(claim, ClaimedPageCompletion):
            raise ValueError("claim invalide")
        created = self._consumer.record_page_completion(claim.message)
        self._outbox.acknowledge(claim)
        return created


class PostgresStandardPageExecutionRepository:
    """Claim et complétion platform des routes sans slot Granite."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        catalog: JobCatalog,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        if not isinstance(catalog, JobCatalog):
            raise ValueError("catalog invalide")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise ValueError("environment_identity invalide")
        self._connection_factory = connection_factory
        self._environment_identity = environment_identity
        self._queue = PostgresJobQueue(
            connection_factory=connection_factory,
            catalog=catalog,
            environment_identity=environment_identity,
        )

    def claim_compatible_job(
        self,
        *,
        worker: GraniteWorker,
        lease_seconds: int,
        job_names: tuple[str, ...],
        execution_requirements: JobExecutionRequirements,
    ) -> ClaimedJob | None:
        if (
            not isinstance(worker, GraniteWorker)
            or worker.environment_identity != self._environment_identity
        ):
            raise ValueError("WORKER_IDENTITY_MISMATCH")
        if (
            not isinstance(execution_requirements, JobExecutionRequirements)
            or execution_requirements.capacity_slots != 0
            or execution_requirements.capacity_device is not None
            or execution_requirements.storage_environment
            != self._environment_identity.environment
        ):
            raise ValueError("STANDARD_EXECUTION_REQUIREMENTS_INVALID")
        return self._queue.claim_next_compatible(
            owner_id=worker.worker_instance_id,
            lease_seconds=lease_seconds,
            job_names=job_names,
            execution_requirements=execution_requirements,
        )

    def complete_standard_page_execution(
        self,
        claimed_job: ClaimedJob,
        envelope: GranitePageTerminalEnvelope,
    ) -> JobRecord:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        if not isinstance(envelope, GranitePageTerminalEnvelope):
            raise ValueError("envelope invalide")
        requirements = claimed_job.job.request.execution_requirements
        if (
            requirements is None
            or requirements.capacity_slots != 0
            or requirements.capacity_device is not None
        ):
            raise ValueError("STANDARD_EXECUTION_REQUIREMENTS_INVALID")
        payload = envelope.canonical_payload_json()
        expected = PageCompletionMessage.from_execution(
            claimed_job=claimed_job,
            granite_lease=None,
            envelope=envelope,
        )
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (envelope.completion_id,),
                )
                cursor.execute(
                    """
                    SELECT environment, deployment_id, job_id, claim_generation,
                           claim_token::text, worker_instance_id, slot_ordinal,
                           slot_generation, slot_token::text, payload,
                           payload_fingerprint, terminal_status, failure_reason
                      FROM platform.page_completion_outbox
                     WHERE completion_id = %s
                     FOR UPDATE
                    """,
                    (envelope.completion_id,),
                )
                replay = cursor.fetchone()
                if replay is not None:
                    actual = _completion_message_from_row(
                        completion_id=envelope.completion_id,
                        row=replay,
                    )
                    if actual != expected:
                        raise GranitePageCompletionConflictError()
                    return _terminal_record(claimed_job, envelope)
                cursor.execute(
                    """
                    WITH active_job AS (
                        SELECT job_id
                          FROM platform.technical_jobs
                         WHERE job_id = %(job_id)s
                           AND environment = %(environment)s
                           AND deployment_id = %(deployment_id)s
                           AND configuration_hash = %(configuration_hash)s
                           AND status = 'running'
                           AND lease_owner = %(worker_instance_id)s
                           AND claim_generation = %(claim_generation)s
                           AND claim_token = %(claim_token)s::uuid
                           AND lease_expires_at > CURRENT_TIMESTAMP
                           AND capacity_slots = 0
                           AND capacity_device IS NULL
                         FOR UPDATE
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
                            NULL, NULL, NULL, %(payload)s::jsonb,
                            %(payload_fingerprint)s, %(terminal_status)s,
                            %(failure_reason)s, 'pending', NULL, NULL, 0, NULL, NULL
                          FROM active_job
                        RETURNING completion_id
                    )
                    UPDATE platform.technical_jobs AS job
                       SET status = CASE
                               WHEN %(terminal_status)s = 'succeeded'
                               THEN 'succeeded' ELSE 'failed' END,
                           result = CASE
                               WHEN %(terminal_status)s = 'succeeded'
                               THEN jsonb_build_object(
                                   'completion_id', %(completion_id)s
                               ) ELSE NULL END,
                           failure_reason = %(failure_reason)s,
                           lease_owner = NULL,
                           lease_expires_at = NULL,
                           claim_token = NULL
                      FROM immutable_outbox
                     WHERE job.job_id = %(job_id)s
                    RETURNING immutable_outbox.completion_id
                    """,
                    {
                        "completion_id": envelope.completion_id,
                        "environment": self._environment_identity.environment,
                        "deployment_id": self._environment_identity.deployment_id,
                        "configuration_hash": self._environment_identity.configuration_hash,
                        "job_id": claimed_job.job.job_id,
                        "worker_instance_id": claimed_job.lease_owner,
                        "claim_generation": claimed_job.claim_generation,
                        "claim_token": claimed_job.claim_token,
                        "payload": payload,
                        "payload_fingerprint": envelope.payload_fingerprint,
                        "terminal_status": envelope.status.value,
                        "failure_reason": envelope.failure_reason,
                    },
                )
                if cursor.fetchone() is None:
                    raise JobLeaseConflictError()
        return _terminal_record(claimed_job, envelope)


class PostgresPageCompletionOutbox:
    """Outbox platform fenced, acquittée seulement après le commit SP."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise ValueError("environment_identity invalide")
        self._connection_factory = connection_factory
        self._environment_identity = environment_identity

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedPageCompletion | None:
        owner = _text(owner_id, "owner_id")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or lease_seconds < 1
        ):
            raise ValueError("lease_seconds invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT sequence
                          FROM platform.page_completion_outbox
                         WHERE environment = %s
                           AND deployment_id = %s
                           AND (
                               status = 'pending'
                               OR (status = 'relaying'
                                   AND relay_lease_until <= CURRENT_TIMESTAMP)
                           )
                         ORDER BY sequence
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    )
                    UPDATE platform.page_completion_outbox AS completion
                       SET status = 'relaying', relay_owner = %s,
                           relay_lease_until =
                               CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                           relay_generation = relay_generation + 1,
                           relay_token = gen_random_uuid()
                      FROM candidate
                     WHERE completion.sequence = candidate.sequence
                    RETURNING completion.completion_id, completion.environment,
                              completion.deployment_id, completion.job_id,
                              completion.claim_generation,
                              completion.claim_token::text,
                              completion.worker_instance_id,
                              completion.slot_ordinal,
                              completion.slot_generation,
                              completion.slot_token::text,
                              completion.payload,
                              completion.payload_fingerprint,
                              completion.terminal_status,
                              completion.failure_reason,
                              completion.relay_generation,
                              completion.relay_token::text
                    """,
                    (
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        owner,
                        lease_seconds,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return ClaimedPageCompletion(
            message=PageCompletionMessage(
                completion_id=row[0],
                environment=row[1],
                deployment_id=row[2],
                job_id=row[3],
                claim_generation=row[4],
                claim_token=row[5],
                worker_instance_id=row[6],
                slot_ordinal=row[7],
                slot_generation=row[8],
                slot_token=row[9],
                payload=row[10],
                payload_fingerprint=row[11],
                terminal_status=row[12],
                failure_reason=row[13],
            ),
            owner_id=owner,
            relay_generation=row[14],
            relay_token=row[15],
        )

    def acknowledge(self, claim: ClaimedPageCompletion) -> None:
        if not isinstance(claim, ClaimedPageCompletion):
            raise ValueError("claim invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.page_completion_outbox
                       SET status = 'relayed', relay_owner = NULL,
                           relay_lease_until = NULL, relay_token = NULL,
                           relayed_at = CURRENT_TIMESTAMP
                     WHERE completion_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND status = 'relaying'
                       AND relay_owner = %s
                       AND relay_generation = %s
                       AND relay_token = %s::uuid
                       AND relay_lease_until > CURRENT_TIMESTAMP
                    RETURNING completion_id
                    """,
                    (
                        claim.message.completion_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        claim.owner_id,
                        claim.relay_generation,
                        claim.relay_token,
                    ),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("PAGE_COMPLETION_LEASE_LOST")


class InMemoryPageCompletionOutbox:
    """Double déterministe réservé aux tests de protocole du relais."""

    def __init__(self, messages: Sequence[PageCompletionMessage]) -> None:
        parsed = tuple(messages)
        if len(parsed) == 0 or any(
            not isinstance(message, PageCompletionMessage) for message in parsed
        ):
            raise ValueError("messages invalides")
        self._messages = {message.completion_id: message for message in parsed}
        if len(self._messages) != len(parsed):
            raise ValueError("completion_id dupliqué")
        self._pending = [message.completion_id for message in parsed]
        self._claimed: dict[str, ClaimedPageCompletion] = {}
        self._relay_generation = {message.completion_id: 0 for message in parsed}

    @classmethod
    def from_envelopes(cls, executions: Sequence[tuple[Any, Any, Any]]):
        return cls(
            tuple(
                PageCompletionMessage.from_execution(
                    claimed_job=claimed,
                    granite_lease=lease,
                    envelope=envelope,
                )
                for claimed, lease, envelope in executions
            )
        )

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedPageCompletion | None:
        _text(owner_id, "owner_id")
        if isinstance(lease_seconds, bool) or lease_seconds < 1:
            raise ValueError("lease_seconds invalide")
        if len(self._pending) == 0:
            return None
        completion_id = self._pending.pop(0)
        generation = self._relay_generation[completion_id] + 1
        self._relay_generation[completion_id] = generation
        claim = ClaimedPageCompletion(
            message=self._messages[completion_id],
            owner_id=owner_id,
            relay_generation=generation,
            relay_token=str(UUID(int=generation, version=4)),
        )
        self._claimed[completion_id] = claim
        return claim

    def acknowledge(self, claim: ClaimedPageCompletion) -> None:
        current = self._claimed.get(claim.message.completion_id)
        if current != claim:
            raise RuntimeError("PAGE_COMPLETION_LEASE_LOST")
        del self._claimed[claim.message.completion_id]

    def replay(self, completion_id: str) -> ClaimedPageCompletion:
        message = self._messages[_text(completion_id, "completion_id")]
        generation = self._relay_generation[completion_id] + 1
        self._relay_generation[completion_id] = generation
        claim = ClaimedPageCompletion(
            message=message,
            owner_id="relay-pages-replay",
            relay_generation=generation,
            relay_token=str(UUID(int=generation, version=4)),
        )
        self._claimed[completion_id] = claim
        return claim

    def divergent_replay(
        self,
        completion_id: str,
        *,
        claim_token: str,
    ) -> ClaimedPageCompletion:
        claim = self.replay(completion_id)
        divergent = replace(claim.message, claim_token=claim_token)
        result = replace(claim, message=divergent)
        self._claimed[completion_id] = result
        return result


def _validate_slot_identity(
    *,
    ordinal: int | None,
    generation: int | None,
    token: str | None,
) -> None:
    if ordinal is None and generation is None and token is None:
        return
    if (
        ordinal not in {1, 2}
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or token is None
    ):
        raise ValueError("slot identity invalide")
    _uuid4(token, "slot_token")


def _canonical_payload(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_json_value(item) for item in value]
    return value


def _completion_message_from_row(
    *,
    completion_id: str,
    row: Any,
) -> PageCompletionMessage:
    if not isinstance(row, tuple) or len(row) != 13:
        raise RuntimeError("PAGE_COMPLETION_ROW_INVALID")
    return PageCompletionMessage(
        completion_id=completion_id,
        environment=row[0],
        deployment_id=row[1],
        job_id=row[2],
        claim_generation=row[3],
        claim_token=row[4],
        worker_instance_id=row[5],
        slot_ordinal=row[6],
        slot_generation=row[7],
        slot_token=row[8],
        payload=row[9],
        payload_fingerprint=row[10],
        terminal_status=row[11],
        failure_reason=row[12],
    )


def _terminal_record(
    claimed_job: ClaimedJob,
    envelope: GranitePageTerminalEnvelope,
) -> JobRecord:
    succeeded = envelope.status.value == "succeeded"
    return JobRecord(
        sequence=claimed_job.job.sequence,
        job_id=claimed_job.job.job_id,
        request=claimed_job.job.request,
        status=JobStatus.SUCCEEDED if succeeded else JobStatus.FAILED,
        result=(
            {"completion_id": envelope.completion_id}
            if succeeded
            else None
        ),
        failure_reason=None if succeeded else envelope.failure_reason,
    )


def _uuid4(value: Any, field_name: str) -> str:
    try:
        parsed = UUID(_text(value, field_name))
    except ValueError as error:
        raise ValueError(f"{field_name} invalide") from error
    if parsed.version != 4:
        raise ValueError(f"{field_name} invalide")
    return str(parsed)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = [
    "ClaimedPageCompletion",
    "InMemoryPageCompletionOutbox",
    "PageCompletionConsumer",
    "PageCompletionMessage",
    "PageCompletionOutbox",
    "PageCompletionRelay",
    "PostgresPageCompletionOutbox",
    "PostgresStandardPageExecutionRepository",
]
