"""Relais transactionnel SP vers KA de CanonicalSourcePublished (ADR-024)."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.contracts.event_envelope import EventEnvelope
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.knowledge_access.application.project_published_canonical import (
    CanonicalPublicationMessage,
    ProjectionPublicationError,
    PublishedCanonicalProjectionRequest,
    canonical_publication_fingerprint,
    job_request_payload,
)
from app.knowledge_access.domain.knowledge_projection import ProjectionProfile
from app.platform.postgres import PostgresConnectionFactory


_PROJECTION_CODE_VERSION = "m014-local-projection-v1"


@dataclass(frozen=True, slots=True)
class ClaimedCanonicalPublication:
    message: CanonicalPublicationMessage
    owner_id: str
    claim_generation: int
    claim_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.message, CanonicalPublicationMessage):
            raise ValueError("PROJECTION_EVENT_CLAIM_INVALID")
        _text(self.owner_id, "PROJECTION_EVENT_CLAIM_OWNER_INVALID")
        if (
            isinstance(self.claim_generation, bool)
            or not isinstance(self.claim_generation, int)
            or self.claim_generation < 1
        ):
            raise ValueError("PROJECTION_EVENT_CLAIM_GENERATION_INVALID")
        _text(self.claim_token, "PROJECTION_EVENT_CLAIM_TOKEN_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalProjectionConsumption:
    projection_id: str
    created: bool
    duplicate: bool

    def __post_init__(self) -> None:
        _text(self.projection_id, "PROJECTION_ID_INVALID")
        if not isinstance(self.created, bool) or not isinstance(self.duplicate, bool):
            raise ValueError("PROJECTION_CONSUMPTION_DECISION_INVALID")
        if self.created and self.duplicate:
            raise ValueError("PROJECTION_CONSUMPTION_DECISION_INVALID")


class PostgresCanonicalPublicationRelay:
    """Claim SP, consommation atomique KA, puis ACK SP dans trois transactions."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        environment_identity: JobEnvironmentIdentity,
        projection_profile: ProjectionProfile,
        configured_collection_name: str,
        observation_sink: Callable[[Mapping[str, object]], None],
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("PROJECTION_RELAY_CONNECTION_FACTORY_INVALID")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise ValueError("PROJECTION_RELAY_ENVIRONMENT_INVALID")
        if not isinstance(projection_profile, ProjectionProfile):
            raise ValueError("PROJECTION_RELAY_PROFILE_INVALID")
        if not callable(observation_sink):
            raise ValueError("PROJECTION_RELAY_OBSERVATION_SINK_INVALID")
        self._connection_factory = connection_factory
        self._identity = environment_identity
        self._profile = projection_profile
        self._observation_sink = observation_sink
        self._configured_collection_name = _text(
            configured_collection_name,
            "PROJECTION_COLLECTION_INVALID",
        )

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedCanonicalPublication | None:
        owner = _text(owner_id, "PROJECTION_EVENT_CLAIM_OWNER_INVALID")
        lease = _positive_int(lease_seconds, "PROJECTION_EVENT_LEASE_INVALID")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT sequence
                          FROM source_processing.canonical_publication_outbox
                         WHERE environment = %s
                           AND deployment_id = %s
                           AND configuration_hash = %s
                           AND (
                               status = 'pending'
                               OR (status = 'relaying'
                                   AND relay_lease_until <= CURRENT_TIMESTAMP)
                           )
                         ORDER BY sequence
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    )
                    UPDATE source_processing.canonical_publication_outbox AS message
                       SET status = 'relaying', relay_owner = %s,
                           relay_lease_until =
                               CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                           relay_generation = relay_generation + 1,
                           relay_token = gen_random_uuid()
                      FROM candidate
                     WHERE message.sequence = candidate.sequence
                    RETURNING message.event_id, message.event_payload,
                              message.event_fingerprint, message.environment,
                              message.deployment_id, message.configuration_hash,
                              message.relay_generation, message.relay_token,
                              message.canonical_artifact_ref
                    """,
                    (
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                        owner,
                        lease,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                event = EventEnvelope.from_payload(_mapping(row[1]))
                if event.event_id != row[0]:
                    raise ProjectionPublicationError("PROJECTION_EVENT_REPLAY_DIVERGENCE")
                stored_fingerprint = _sha256(row[2])
                if hashlib.sha256(event.to_json().encode("utf-8")).hexdigest() != stored_fingerprint:
                    raise ProjectionPublicationError("PROJECTION_EVENT_REPLAY_DIVERGENCE")
        identity = JobEnvironmentIdentity(
            environment=row[3],
            deployment_id=row[4],
            configuration_hash=row[5],
        )
        fingerprint = canonical_publication_fingerprint(
            event=event,
            canonical_artifact_ref=row[8],
            environment_identity=identity,
        )
        return ClaimedCanonicalPublication(
            message=CanonicalPublicationMessage(
                event=event,
                canonical_artifact_ref=row[8],
                environment_identity=identity,
                event_fingerprint=fingerprint,
            ),
            owner_id=owner,
            claim_generation=row[6],
            claim_token=str(row[7]),
        )

    def consume(
        self,
        claim: ClaimedCanonicalPublication,
    ) -> CanonicalProjectionConsumption:
        if not isinstance(claim, ClaimedCanonicalPublication):
            raise ValueError("PROJECTION_EVENT_CLAIM_INVALID")
        decision = PublishedCanonicalProjectionRequest.from_message(
            message=claim.message,
            projection_profile=self._profile,
            configured_identity=self._identity,
            configured_collection_name=self._configured_collection_name,
            code_version=_PROJECTION_CODE_VERSION,
        )
        event = claim.message.event
        canonical_ref = claim.message.canonical_ref
        projection = decision.projection
        request = decision.job_request
        event_payload = json.loads(event.to_json())
        job_payload = job_request_payload(request)
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"ka-canonical-publication|{event.event_id}",),
                )
                cursor.execute(
                    """
                    SELECT inbox.event_fingerprint, inbox.canonical_version_id,
                           inbox.document_id, inbox.canonical_artifact_ref,
                           inbox.canonical_artifact_sha256,
                           inbox.environment, inbox.deployment_id,
                           inbox.configuration_hash, inbox.event_payload,
                           receipt.projection_id
                      FROM knowledge_access.canonical_publication_inbox AS inbox
                      JOIN knowledge_access.projection_event_receipts AS receipt
                        ON receipt.event_id = inbox.event_id
                     WHERE inbox.event_id = %s
                     FOR UPDATE OF inbox, receipt
                    """,
                    (event.event_id,),
                )
                existing = cursor.fetchone()
                expected = (
                    claim.message.event_fingerprint,
                    canonical_ref.canonical_version_id,
                    canonical_ref.document_id,
                    claim.message.canonical_artifact_ref,
                    canonical_ref.canonical_artifact_sha256,
                    self._identity.environment,
                    self._identity.deployment_id,
                    self._identity.configuration_hash,
                    event_payload,
                    projection.projection_id,
                )
                if existing is not None:
                    if tuple(existing) != expected:
                        raise ProjectionPublicationError(
                            "PROJECTION_EVENT_REPLAY_DIVERGENCE"
                        )
                    cursor.execute(
                        """
                        UPDATE knowledge_access.projection_event_receipts
                           SET delivery_count = delivery_count + 1,
                               last_delivered_at = CURRENT_TIMESTAMP
                         WHERE event_id = %s
                        """,
                        (event.event_id,),
                    )
                    return CanonicalProjectionConsumption(
                        projection_id=projection.projection_id,
                        created=False,
                        duplicate=True,
                    )
                cursor.execute(
                    """
                    SELECT event_id, event_fingerprint
                      FROM knowledge_access.canonical_publication_inbox
                     WHERE canonical_version_id = %s
                     FOR UPDATE
                    """,
                    (canonical_ref.canonical_version_id,),
                )
                conflicting_version = cursor.fetchone()
                if conflicting_version is not None:
                    raise ProjectionPublicationError(
                        "PROJECTION_EVENT_REPLAY_DIVERGENCE"
                    )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.canonical_publication_inbox (
                        event_id, event_fingerprint, canonical_version_id,
                        document_id, canonical_artifact_ref,
                        canonical_artifact_sha256, environment, deployment_id,
                        configuration_hash, event_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        event.event_id,
                        claim.message.event_fingerprint,
                        canonical_ref.canonical_version_id,
                        canonical_ref.document_id,
                        claim.message.canonical_artifact_ref,
                        canonical_ref.canonical_artifact_sha256,
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                        _canonical_json(event_payload),
                    ),
                )
                profile = projection.projection_profile
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version,
                        execution_phase, completed_units, total_units,
                        failure_error_code, environment, deployment_id,
                        configuration_hash, qdrant_collection_name
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'REQUESTED',
                        0, CURRENT_TIMESTAMP, 0, 'QUEUED', 0, 1, NULL,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (build_fingerprint) DO NOTHING
                    RETURNING projection_id
                    """,
                    (
                        projection.projection_id,
                        projection.document_id,
                        projection.canonical_version_id,
                        profile.projection_profile_id,
                        profile.chunking_profile,
                        profile.embedding_model,
                        profile.sparse_profile,
                        profile.index_schema,
                        projection.build_fingerprint.value,
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                        self._configured_collection_name,
                    ),
                )
                projection_created = cursor.fetchone() is not None
                if not projection_created:
                    cursor.execute(
                        """
                        SELECT projection_id, canonical_version_id, environment,
                               deployment_id, configuration_hash,
                               qdrant_collection_name
                          FROM knowledge_access.knowledge_projections
                         WHERE build_fingerprint = %s
                         FOR UPDATE
                        """,
                        (projection.build_fingerprint.value,),
                    )
                    replay = cursor.fetchone()
                    if replay != (
                        projection.projection_id,
                        projection.canonical_version_id,
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                        self._configured_collection_name,
                    ):
                        raise ProjectionPublicationError(
                            "PROJECTION_BUILD_REPLAY_DIVERGENCE"
                        )
                cursor.execute(
                    """
                    UPDATE knowledge_access.job_outbox
                       SET payload = %s::jsonb,
                           trace_id = %s,
                           status = 'pending', platform_job_id = NULL,
                           relayed_at = NULL, relay_owner = NULL,
                           relay_lease_expires_at = NULL,
                           relay_claim_generation = relay_claim_generation + 1,
                           relay_claim_token = NULL
                     WHERE job_name = 'PROJECT_DOCUMENT'
                       AND input_hash = %s
                       AND configuration_hash = %s
                       AND NOT (payload ? 'contract_version')
                    """,
                    (
                        _canonical_json(job_payload),
                        event.correlation_id,
                        request.idempotence_key.input_hash,
                        request.idempotence_key.configuration_hash,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.job_outbox (
                        environment, deployment_id, job_name, priority,
                        input_hash, configuration_hash, code_version,
                        model_version, payload, trace_id, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')
                    ON CONFLICT (
                        job_name, input_hash, configuration_hash,
                        code_version, model_version
                    ) DO NOTHING
                    RETURNING outbox_id
                    """,
                    (
                        request.environment,
                        request.deployment_id,
                        request.job_name,
                        request.priority.value,
                        request.idempotence_key.input_hash,
                        request.idempotence_key.configuration_hash,
                        request.idempotence_key.code_version,
                        request.idempotence_key.model_version,
                        _canonical_json(job_payload),
                        event.correlation_id,
                    ),
                )
                job_created = cursor.fetchone() is not None
                if projection_created != job_created:
                    raise ProjectionPublicationError("PROJECTION_JOB_ATOMICITY_CONFLICT")
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.projection_event_receipts (
                        event_id, event_fingerprint, projection_id, delivery_count
                    ) VALUES (%s, %s, %s, 1)
                    """,
                    (
                        event.event_id,
                        claim.message.event_fingerprint,
                        projection.projection_id,
                    ),
                )
        return CanonicalProjectionConsumption(
            projection_id=projection.projection_id,
            created=projection_created,
            duplicate=False,
        )

    def acknowledge(self, claim: ClaimedCanonicalPublication) -> None:
        if not isinstance(claim, ClaimedCanonicalPublication):
            raise ValueError("PROJECTION_EVENT_CLAIM_INVALID")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.canonical_publication_outbox
                       SET status = 'relayed', relayed_at = CURRENT_TIMESTAMP,
                           relay_owner = NULL, relay_lease_until = NULL,
                           relay_token = NULL
                     WHERE event_id = %s AND status = 'relaying'
                       AND relay_owner = %s AND relay_generation = %s
                       AND relay_token = %s::uuid
                       AND relay_lease_until > CURRENT_TIMESTAMP
                    """,
                    (
                        claim.message.event.event_id,
                        claim.owner_id,
                        claim.claim_generation,
                        claim.claim_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ProjectionPublicationError("PROJECTION_EVENT_LEASE_LOST")

    def relay_pending(
        self,
        *,
        limit: int,
        owner_id: str,
        lease_seconds: int,
    ) -> int:
        maximum = _positive_int(limit, "PROJECTION_EVENT_RELAY_LIMIT_INVALID")
        relayed = 0
        for _ in range(maximum):
            started = time.perf_counter_ns()
            claim: ClaimedCanonicalPublication | None = None
            try:
                claim = self.claim_next(owner_id=owner_id, lease_seconds=lease_seconds)
                if claim is None:
                    break
                consumption = self.consume(claim)
                self.acknowledge(claim)
            except Exception as error:
                self._observe(
                    claim=claim,
                    status="failed",
                    duration_ns=time.perf_counter_ns() - started,
                    relayed_count=0,
                    redelivery_count=0,
                    conflict_count=(
                        1
                        if _relay_error_code(error)
                        in {
                            "PROJECTION_EVENT_REPLAY_DIVERGENCE",
                            "PROJECTION_BUILD_REPLAY_DIVERGENCE",
                            "PROJECTION_JOB_ATOMICITY_CONFLICT",
                        }
                        else 0
                    ),
                    lease_lost_count=(
                        1
                        if _relay_error_code(error) == "PROJECTION_EVENT_LEASE_LOST"
                        else 0
                    ),
                    error_code=_relay_error_code(error),
                )
                raise
            self._observe(
                claim=claim,
                status="relayed",
                duration_ns=time.perf_counter_ns() - started,
                relayed_count=1,
                redelivery_count=1 if consumption.duplicate else 0,
                conflict_count=0,
                lease_lost_count=0,
                error_code=None,
            )
            relayed += 1
        return relayed

    def _observe(
        self,
        *,
        claim: ClaimedCanonicalPublication | None,
        status: str,
        duration_ns: int,
        relayed_count: int,
        redelivery_count: int,
        conflict_count: int,
        lease_lost_count: int,
        error_code: str | None,
    ) -> None:
        observation: dict[str, object] = {
            "event_type": "canonical_publication_relay",
            "status": status,
            "duration_ms": round(duration_ns / 1_000_000, 3),
            "relayed_count": relayed_count,
            "redelivery_count": redelivery_count,
            "conflict_count": conflict_count,
            "lease_lost_count": lease_lost_count,
            "environment": self._identity.environment,
            "deployment_id": self._identity.deployment_id,
            "configuration_hash": self._identity.configuration_hash,
        }
        if claim is not None:
            observation.update(
                {
                    "message_id": claim.message.event.event_id,
                    "correlation_id": claim.message.event.correlation_id,
                    "claim_generation": claim.claim_generation,
                }
            )
        if error_code is not None:
            observation["error_code"] = error_code
        self._observation_sink(observation)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ProjectionPublicationError("PROJECTION_EVENT_INVALID")
    return dict(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: Any) -> str:
    text = _text(value, "PROJECTION_EVENT_FINGERPRINT_INVALID")
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ProjectionPublicationError("PROJECTION_EVENT_FINGERPRINT_INVALID")
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(code)
    return value


def _relay_error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str):
        return code
    return "PROJECTION_RELAY_UNEXPECTED_ERROR"


__all__ = [
    "CanonicalProjectionConsumption",
    "ClaimedCanonicalPublication",
    "PostgresCanonicalPublicationRelay",
]
