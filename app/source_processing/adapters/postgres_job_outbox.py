"""Outbox PostgreSQL propriétaire du contexte source_processing."""

from __future__ import annotations

from collections.abc import Mapping

from app.platform.job_runtime.relay import ClaimedRelayMessage, RelayedJobMessage
from app.platform.postgres import PostgresConnectionFactory
from app.platform.worker_environment import WORKER_ENVIRONMENT_MISMATCH


class JobOutboxLeaseConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("JOB_OUTBOX_LEASE_LOST")


class PostgresJobOutbox:
    """Réclame et acquitte localement les messages SP avec une lease courte."""

    _ALLOWED_TABLE_NAMES = frozenset(
        {
            "source_processing.job_outbox",
            "knowledge_access.job_outbox",
        }
    )

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        table_name: str = "source_processing.job_outbox",
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory outbox invalide")
        if table_name not in self._ALLOWED_TABLE_NAMES:
            raise ValueError("table outbox invalide")
        self._connection_factory = connection_factory
        self._table_name = table_name

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedRelayMessage | None:
        parsed_owner = _required_text(owner_id, "owner_id")
        parsed_lease = _positive_integer(lease_seconds, "lease_seconds")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH candidate AS (
                        SELECT sequence
                          FROM {self._table_name}
                         WHERE status = 'pending'
                            OR (status = 'relaying'
                                AND relay_lease_expires_at <= CURRENT_TIMESTAMP)
                         ORDER BY sequence
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    )
                    UPDATE {self._table_name} AS message
                       SET status = 'relaying', relay_owner = %s,
                           relay_lease_expires_at =
                               CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                           relay_attempts = relay_attempts + 1,
                           relay_claim_generation = relay_claim_generation + 1,
                           relay_claim_token = gen_random_uuid()
                      FROM candidate
                     WHERE message.sequence = candidate.sequence
                    RETURNING message.outbox_id, message.job_name, message.priority,
                              message.input_hash, message.configuration_hash,
                              message.code_version, message.model_version,
                              message.payload, message.trace_id,
                              message.environment, message.deployment_id,
                              message.relay_claim_generation,
                              message.relay_claim_token
                    """,
                    (parsed_owner, parsed_lease),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return ClaimedRelayMessage(
            message=RelayedJobMessage(
                message_id=row[0],
                environment=row[9],
                deployment_id=row[10],
                job_name=row[1],
                priority=row[2],
                input_hash=row[3],
                configuration_hash=row[4],
                code_version=row[5],
                model_version=row[6],
                payload=row[7],
                trace_id=row[8],
            ),
            owner_id=parsed_owner,
            claim_generation=row[11],
            claim_token=str(row[12]),
        )

    def acknowledge(
        self,
        claim: ClaimedRelayMessage,
        *,
        platform_job_id: str,
    ) -> None:
        if not isinstance(claim, ClaimedRelayMessage):
            raise ValueError("claim outbox invalide")
        parsed_job_id = _required_text(platform_job_id, "platform_job_id")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {self._table_name}
                       SET status = 'relayed', platform_job_id = %s,
                           relayed_at = CURRENT_TIMESTAMP,
                           relay_owner = NULL, relay_lease_expires_at = NULL,
                           relay_claim_token = NULL
                     WHERE outbox_id = %s AND status = 'relaying'
                       AND relay_owner = %s
                       AND relay_claim_generation = %s
                       AND relay_claim_token = %s::uuid
                       AND relay_lease_expires_at > CURRENT_TIMESTAMP
                    """,
                    (
                        parsed_job_id,
                        claim.message.message_id,
                        claim.owner_id,
                        claim.claim_generation,
                        claim.claim_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise JobOutboxLeaseConflictError()

    def reject_environment_mismatch(self, claim: ClaimedRelayMessage) -> None:
        """Persiste le refus et l'échec public dans la transaction productrice."""

        if not isinstance(claim, ClaimedRelayMessage):
            raise ValueError("claim outbox invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {self._table_name}
                       SET status = 'failed', failure_error_code = %s,
                           relay_owner = NULL, relay_lease_expires_at = NULL,
                           relay_claim_token = NULL
                     WHERE outbox_id = %s AND status = 'relaying'
                       AND relay_owner = %s
                       AND relay_claim_generation = %s
                       AND relay_claim_token = %s::uuid
                       AND relay_lease_expires_at > CURRENT_TIMESTAMP
                    RETURNING job_name, payload
                    """,
                    (
                        WORKER_ENVIRONMENT_MISMATCH,
                        claim.message.message_id,
                        claim.owner_id,
                        claim.claim_generation,
                        claim.claim_token,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise JobOutboxLeaseConflictError()
                self._persist_public_environment_failure(
                    cursor=cursor,
                    job_name=row[0],
                    payload=row[1],
                )

    def _persist_public_environment_failure(
        self,
        *,
        cursor: object,
        job_name: str,
        payload: object,
    ) -> None:
        if not isinstance(payload, Mapping):
            raise RuntimeError("JOB_OUTBOX_PAYLOAD_INVALID")
        if self._table_name == "source_processing.job_outbox" and job_name == "DIAGNOSE":
            cursor.execute(
                """
                UPDATE source_processing.document_processing_runs
                   SET status = 'FAILED', failure_error_code = %s,
                       manual_review_reason = NULL, blocking_policy_version = NULL,
                       aggregate_version = aggregate_version + 1
                 WHERE processing_run_id = %s
                   AND status IN ('MANIFEST_CREATED', 'DIAGNOSING')
                """,
                (WORKER_ENVIRONMENT_MISMATCH, _payload_text(payload, "processing_run_id")),
            )
        elif self._table_name == "source_processing.job_outbox" and job_name == "CONVERT_DOCUMENT":
            cursor.execute(
                """
                UPDATE source_processing.document_conversion_requests
                   SET conversion_status = 'QA_REJECTED', execution_phase = 'FAILED',
                       rejection_error_code = %s, failure_error_code = %s,
                       canonical_version_id = NULL
                 WHERE document_id = %s
                   AND conversion_status = 'CONVERSION_REQUESTED'
                """,
                (
                    WORKER_ENVIRONMENT_MISMATCH,
                    WORKER_ENVIRONMENT_MISMATCH,
                    _payload_text(payload, "document_id"),
                ),
            )
        elif self._table_name == "knowledge_access.job_outbox" and job_name == "PROJECT_DOCUMENT":
            cursor.execute(
                """
                UPDATE knowledge_access.knowledge_projections
                   SET status = 'FAILED', execution_phase = 'FAILED',
                       failure_error_code = %s, state_observed_at = CURRENT_TIMESTAMP,
                       aggregate_version = aggregate_version + 1
                 WHERE projection_id = %s AND status = 'REQUESTED'
                """,
                (WORKER_ENVIRONMENT_MISMATCH, _payload_text(payload, "projection_id")),
            )
        else:
            raise RuntimeError("JOB_OUTBOX_PUBLIC_FAILURE_UNSUPPORTED")
        if cursor.rowcount != 1:
            raise RuntimeError("JOB_OUTBOX_PUBLIC_FAILURE_CONFLICT")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _payload_text(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise RuntimeError(f"JOB_OUTBOX_PAYLOAD_INVALID:{field_name}")
    return value


__all__ = ["JobOutboxLeaseConflictError", "PostgresJobOutbox"]
