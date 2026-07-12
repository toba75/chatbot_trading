"""File PostgreSQL durable des jobs techniques M-002."""

from __future__ import annotations

import json
from collections.abc import Mapping
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
from app.platform.postgres import PostgresConnectionFactory


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
        connection: Any,
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
                    code_version, model_version, payload, status,
                    recalculation_number
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, 'pending',
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


def _ensure_request(value: Any) -> JobRequest:
    if not isinstance(value, JobRequest):
        raise ValueError("request invalide")
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


__all__ = ["PostgresJobQueue"]
