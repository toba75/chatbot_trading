"""Outbox PostgreSQL propriétaire du contexte source_processing."""

from __future__ import annotations

from app.platform.job_runtime.relay import ClaimedRelayMessage, RelayedJobMessage
from app.platform.postgres import PostgresConnectionFactory


class JobOutboxLeaseConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("JOB_OUTBOX_LEASE_LOST")


class PostgresJobOutbox:
    """Réclame et acquitte localement les messages SP avec une lease courte."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory outbox invalide")
        self._connection_factory = connection_factory

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
                    """
                    WITH candidate AS (
                        SELECT sequence
                          FROM source_processing.job_outbox
                         WHERE status = 'pending'
                            OR (status = 'relaying'
                                AND relay_lease_expires_at <= CURRENT_TIMESTAMP)
                         ORDER BY sequence
                         FOR UPDATE SKIP LOCKED
                         LIMIT 1
                    )
                    UPDATE source_processing.job_outbox AS message
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
            claim_generation=row[9],
            claim_token=str(row[10]),
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
                    """
                    UPDATE source_processing.job_outbox
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


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["JobOutboxLeaseConflictError", "PostgresJobOutbox"]
