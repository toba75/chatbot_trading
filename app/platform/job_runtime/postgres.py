"""File PostgreSQL durable des jobs techniques M-002."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.platform.job_runtime import (
    JobCatalog,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
    JobSubmissionDecision,
)
from app.platform.postgres import PostgresConnection, PostgresConnectionFactory
from app.platform.request_context import current_trace_id


class JobLeaseConflictError(RuntimeError):
    """Le worker ne possède plus la lease nécessaire à la transition."""

    def __init__(self) -> None:
        super().__init__("JOB_LEASE_LOST")


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    """Job réclamé et corrélé, sans exposer son payload dans les logs."""

    job: JobRecord
    trace_id: str
    lease_owner: str
    lease_expires_at: datetime


class PostgresJobQueue:
    """File priorisée partagée par l'API et les workers via PostgreSQL."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        catalog: JobCatalog,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        if not isinstance(catalog, JobCatalog):
            raise ValueError("catalog invalide")
        self._connection_factory = connection_factory
        self._catalog = catalog

    def submit(self, request: JobRequest, *, recalculate: bool) -> JobSubmissionDecision:
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                return self.submit_in_transaction(
                    connection,
                    request,
                    recalculate=recalculate,
                )

    def submit_in_transaction(
        self,
        connection: PostgresConnection,
        request: JobRequest,
        *,
        recalculate: bool,
    ) -> JobSubmissionDecision:
        parsed_request = _ensure_request(request)
        if not isinstance(recalculate, bool):
            raise ValueError("recalculate non booléen")
        self._catalog.require_known_job(parsed_request.job_name)

        identity = parsed_request.idempotence_key.identity_tuple()
        lock_key = "|".join(identity)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )
            cursor.execute(
                """
                SELECT sequence, job_id, job_name, priority, input_hash,
                       configuration_hash, code_version, model_version,
                       payload, status, result, failure_reason
                  FROM platform.technical_jobs
                 WHERE job_name = %s
                   AND input_hash = %s
                   AND configuration_hash = %s
                   AND code_version = %s
                   AND model_version = %s
                 ORDER BY recalculation_number DESC
                 LIMIT 1
                 FOR UPDATE
                """,
                identity,
            )
            existing_row = cursor.fetchone()
            if existing_row is not None:
                existing = _job_from_row(existing_row)
                if not recalculate and existing.status in {
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                    JobStatus.SUCCEEDED,
                }:
                    return JobSubmissionDecision(
                        job=existing,
                        created=False,
                        recalculation_refused=existing.status is JobStatus.SUCCEEDED,
                    )

            cursor.execute(
                """
                INSERT INTO platform.technical_jobs (
                    job_name, priority, input_hash, configuration_hash,
                    code_version, model_version, payload, trace_id, status,
                    recalculation_number
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending',
                    COALESCE((
                        SELECT MAX(recalculation_number) + 1
                          FROM platform.technical_jobs
                         WHERE job_name = %s
                           AND input_hash = %s
                           AND configuration_hash = %s
                           AND code_version = %s
                           AND model_version = %s
                    ), 0)
                )
                RETURNING sequence, job_id, job_name, priority, input_hash,
                          configuration_hash, code_version, model_version,
                          payload, status, result, failure_reason
                """,
                (
                    parsed_request.job_name,
                    parsed_request.priority.value,
                    *identity[1:],
                    json.dumps(dict(parsed_request.payload), separators=(",", ":"), sort_keys=True),
                    current_trace_id(),
                    *identity,
                ),
            )
            created_row = cursor.fetchone()
        if created_row is None:
            raise RuntimeError("JOB_PERSISTENCE_FAILED")
        return JobSubmissionDecision(
            job=_job_from_row(created_row),
            created=True,
            recalculation_refused=False,
        )

    def job_for(self, job_id: str) -> JobRecord:
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sequence, job_id, job_name, priority, input_hash,
                           configuration_hash, code_version, model_version,
                           payload, status, result, failure_reason
                      FROM platform.technical_jobs
                     WHERE job_id = %s
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
        if row is None:
            raise ValueError(f"job inconnu: {job_id}")
        return _job_from_row(row)

    def find_by_idempotence_key(self, key: JobIdempotenceKey) -> JobRecord | None:
        if not isinstance(key, JobIdempotenceKey):
            raise ValueError("idempotence_key invalide")
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sequence, job_id, job_name, priority, input_hash,
                           configuration_hash, code_version, model_version,
                           payload, status, result, failure_reason
                      FROM platform.technical_jobs
                     WHERE job_name = %s
                       AND input_hash = %s
                       AND configuration_hash = %s
                       AND code_version = %s
                       AND model_version = %s
                     ORDER BY recalculation_number DESC
                     LIMIT 1
                    """,
                    key.identity_tuple(),
                )
                row = cursor.fetchone()
        return None if row is None else _job_from_row(row)

    def relay_pending_outbox(self, *, limit: int) -> int:
        """Relaie dans l'ordre les messages SP sans transaction inter-propriétaires."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("relay limit invalide")
        relayed = 0
        for _ in range(limit):
            with self._connection_factory.connect() as connection:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT sequence, outbox_id, job_name, priority, input_hash,
                                   configuration_hash, code_version, model_version,
                                   payload, trace_id
                              FROM source_processing.job_outbox
                             WHERE status = 'pending'
                             ORDER BY sequence
                             FOR UPDATE SKIP LOCKED
                             LIMIT 1
                            """,
                            (),
                        )
                        message = cursor.fetchone()
                        if message is None:
                            return relayed
                        cursor.execute(
                            """
                            INSERT INTO platform.technical_jobs (
                                job_name, priority, input_hash, configuration_hash,
                                code_version, model_version, payload, trace_id, status,
                                recalculation_number
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', 0)
                            ON CONFLICT (
                                job_name, input_hash, configuration_hash,
                                code_version, model_version, recalculation_number
                            ) DO NOTHING
                            RETURNING job_id
                            """,
                            (
                                message[2],
                                message[3],
                                message[4],
                                message[5],
                                message[6],
                                message[7],
                                json.dumps(dict(message[8]), separators=(",", ":"), sort_keys=True),
                                message[9],
                            ),
                        )
                        inserted = cursor.fetchone()
                        if inserted is None:
                            cursor.execute(
                                """
                                SELECT job_id
                                  FROM platform.technical_jobs
                                 WHERE job_name = %s
                                   AND input_hash = %s
                                   AND configuration_hash = %s
                                   AND code_version = %s
                                   AND model_version = %s
                                   AND recalculation_number = 0
                                """,
                                (message[2], message[4], message[5], message[6], message[7]),
                            )
                            inserted = cursor.fetchone()
                        if inserted is None:
                            raise RuntimeError("JOB_OUTBOX_RELAY_FAILED")
                        cursor.execute(
                            """
                            UPDATE source_processing.job_outbox
                               SET status = 'relayed', platform_job_id = %s,
                                   relayed_at = CURRENT_TIMESTAMP,
                                   relay_attempts = relay_attempts + 1
                             WHERE sequence = %s AND status = 'pending'
                            """,
                            (inserted[0], message[0]),
                        )
                        if cursor.rowcount != 1:
                            raise RuntimeError("JOB_OUTBOX_RELAY_CONFLICT")
            relayed += 1
        return relayed

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
        job_names: tuple[str, ...],
    ) -> ClaimedJob | None:
        parsed_owner = _ensure_text(owner_id, "owner_id")
        parsed_lease = _ensure_positive_integer(lease_seconds, "lease_seconds")
        parsed_names = _ensure_job_names(job_names, self._catalog)
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        WITH candidate AS (
                            SELECT sequence
                              FROM platform.technical_jobs
                             WHERE job_name = ANY(%s)
                               AND (
                                   status = 'pending'
                                   OR (status = 'running' AND lease_expires_at <= CURRENT_TIMESTAMP)
                               )
                             ORDER BY CASE priority
                                 WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2
                                 WHEN 'P3' THEN 3 WHEN 'P4' THEN 4 WHEN 'P5' THEN 5
                             END, sequence
                             FOR UPDATE SKIP LOCKED
                             LIMIT 1
                        )
                        UPDATE platform.technical_jobs AS job
                           SET status = 'running', lease_owner = %s,
                               lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                               execution_attempts = execution_attempts + 1
                          FROM candidate
                         WHERE job.sequence = candidate.sequence
                        RETURNING job.sequence, job.job_id, job.job_name, job.priority,
                                  job.input_hash, job.configuration_hash, job.code_version,
                                  job.model_version, job.payload, job.status, job.result,
                                  job.failure_reason, job.trace_id, job.lease_owner,
                                  job.lease_expires_at
                        """,
                        (list(parsed_names), parsed_owner, parsed_lease),
                    )
                    row = cursor.fetchone()
        if row is None:
            return None
        return ClaimedJob(
            job=_job_from_row(row),
            trace_id=row[12],
            lease_owner=row[13],
            lease_expires_at=row[14],
        )

    def renew_lease(self, *, job_id: str, owner_id: str, lease_seconds: int) -> ClaimedJob:
        return self._transition_lease(
            job_id=job_id,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    def mark_succeeded(
        self,
        *,
        job_id: str,
        owner_id: str,
        result: Mapping[str, Any],
    ) -> JobRecord:
        parsed_result = _required_mapping(result, "result")
        return self._finish(
            job_id=job_id,
            owner_id=owner_id,
            status="succeeded",
            result=json.dumps(dict(parsed_result), separators=(",", ":"), sort_keys=True),
            failure_reason=None,
        )

    def mark_failed(self, *, job_id: str, owner_id: str, failure_reason: str) -> JobRecord:
        return self._finish(
            job_id=job_id,
            owner_id=owner_id,
            status="failed",
            result=None,
            failure_reason=_ensure_text(failure_reason, "failure_reason"),
        )

    def _transition_lease(
        self,
        *,
        job_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedJob:
        parsed_job_id = _ensure_text(job_id, "job_id")
        parsed_owner = _ensure_text(owner_id, "owner_id")
        parsed_lease = _ensure_positive_integer(lease_seconds, "lease_seconds")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE platform.technical_jobs
                           SET lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                         WHERE job_id = %s AND status = 'running'
                           AND lease_owner = %s AND lease_expires_at > CURRENT_TIMESTAMP
                        RETURNING sequence, job_id, job_name, priority, input_hash,
                                  configuration_hash, code_version, model_version,
                                  payload, status, result, failure_reason, trace_id,
                                  lease_owner, lease_expires_at
                        """,
                        (parsed_lease, parsed_job_id, parsed_owner),
                    )
                    row = cursor.fetchone()
        if row is None:
            raise JobLeaseConflictError()
        return ClaimedJob(_job_from_row(row), row[12], row[13], row[14])

    def _finish(
        self,
        *,
        job_id: str,
        owner_id: str,
        status: str,
        result: str | None,
        failure_reason: str | None,
    ) -> JobRecord:
        parsed_job_id = _ensure_text(job_id, "job_id")
        parsed_owner = _ensure_text(owner_id, "owner_id")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE platform.technical_jobs
                           SET status = %s, result = %s::jsonb, failure_reason = %s,
                               lease_owner = NULL, lease_expires_at = NULL
                         WHERE job_id = %s AND status = 'running'
                           AND lease_owner = %s AND lease_expires_at > CURRENT_TIMESTAMP
                        RETURNING sequence, job_id, job_name, priority, input_hash,
                                  configuration_hash, code_version, model_version,
                                  payload, status, result, failure_reason
                        """,
                        (status, result, failure_reason, parsed_job_id, parsed_owner),
                    )
                    row = cursor.fetchone()
        if row is None:
            raise JobLeaseConflictError()
        return _job_from_row(row)


def _ensure_request(value: Any) -> JobRequest:
    if not isinstance(value, JobRequest):
        raise ValueError("request invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_job_names(value: Any, catalog: JobCatalog) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) == 0:
        raise ValueError("job_names invalides")
    return tuple(catalog.require_known_job(item) for item in value)


def _required_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _mapping(value: Any, field_name: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = value
    if not isinstance(decoded, Mapping):
        raise RuntimeError(f"{field_name} PostgreSQL invalide")
    return decoded


def _job_from_row(row: Any) -> JobRecord:
    payload = _mapping(row[8], "payload")
    if payload is None:
        raise RuntimeError("payload PostgreSQL absent")
    status = JobStatus(row[9])
    result = _mapping(row[10], "result")
    return JobRecord(
        sequence=row[0],
        job_id=row[1],
        request=JobRequest(
            job_name=row[2],
            priority=JobPriority(row[3]),
            idempotence_key=JobIdempotenceKey(
                job_name=row[2],
                input_hash=row[4],
                configuration_hash=row[5],
                code_version=row[6],
                model_version=row[7],
            ),
            payload=payload,
        ),
        status=status,
        result=result,
        failure_reason=row[11],
    )


__all__ = ["ClaimedJob", "JobLeaseConflictError", "PostgresJobQueue"]
