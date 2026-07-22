"""File PostgreSQL durable avec relais idempotent et claims clôturés."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, NamedTuple

from app.platform.job_runtime import (
    JobCatalog,
    JobEnvironmentIdentity,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
    JobSubmissionDecision,
)
from app.contracts.technical_jobs import ClaimedJob
from app.platform.job_runtime.relay import RelayedJobMessage
from app.platform.postgres import PostgresConnection, PostgresConnectionFactory
from app.platform.request_context import current_trace_id
from app.platform.worker_environment import WorkerEnvironmentMismatchError


class _JobRow(NamedTuple):
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

    @classmethod
    def from_database(cls, row: Any) -> _JobRow:
        return cls(*_database_row_values(row, len(cls._fields), "JOB"))


class _ClaimedJobRow(NamedTuple):
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
    lease_expires_at: Any
    claim_generation: int
    claim_token: Any
    execution_attempts: int

    @classmethod
    def from_database(cls, row: Any) -> _ClaimedJobRow:
        return cls(*_database_row_values(row, len(cls._fields), "CLAIMED_JOB"))

    def job_row(self) -> _JobRow:
        return _JobRow(*self[: len(_JobRow._fields)])


class _ConsumedRelayRow(NamedTuple):
    job_id: str
    source_message_hash: str

    @classmethod
    def from_database(cls, row: Any) -> _ConsumedRelayRow:
        return cls(*_database_row_values(row, len(cls._fields), "CONSUMED_RELAY"))


class _ExistingRelayRow(NamedTuple):
    job_id: str
    priority: str
    payload: Any
    trace_id: str
    source_message_id: str | None
    source_message_hash: str | None

    @classmethod
    def from_database(cls, row: Any) -> _ExistingRelayRow:
        return cls(*_database_row_values(row, len(cls._fields), "EXISTING_RELAY"))


class _InsertedJobRow(NamedTuple):
    job_id: str

    @classmethod
    def from_database(cls, row: Any) -> _InsertedJobRow:
        return cls(*_database_row_values(row, len(cls._fields), "INSERTED_JOB"))


_JOB_COLUMNS_SQL = ", ".join(_JobRow._fields)
_CLAIMED_JOB_COLUMNS_SQL = ", ".join(_ClaimedJobRow._fields)
_QUALIFIED_CLAIMED_JOB_COLUMNS_SQL = ", ".join(
    f"job.{column}" for column in _ClaimedJobRow._fields
)
_CONSUMED_RELAY_COLUMNS_SQL = ", ".join(_ConsumedRelayRow._fields)
_EXISTING_RELAY_COLUMNS_SQL = ", ".join(_ExistingRelayRow._fields)
_INSERTED_JOB_COLUMNS_SQL = ", ".join(_InsertedJobRow._fields)


class JobLeaseConflictError(RuntimeError):
    """Le worker ne possède plus la lease nécessaire à la transition."""

    def __init__(self) -> None:
        super().__init__("JOB_LEASE_LOST")


class JobRelayMessageConflictError(RuntimeError):
    """Le même message de relais désigne un contenu technique différent."""

    def __init__(self) -> None:
        super().__init__("JOB_RELAY_MESSAGE_CONFLICT")


class PostgresJobQueue:
    """File priorisée partagée par l'API et les workers via PostgreSQL."""

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
            raise ValueError("identité environnement file invalide")
        self._connection_factory = connection_factory
        self._catalog = catalog
        self._environment_identity = environment_identity

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
        self._require_environment_identity(parsed_request)

        identity = parsed_request.idempotence_key.identity_tuple()
        lock_key = "|".join(
            (parsed_request.environment, parsed_request.deployment_id, *identity)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )
            cursor.execute(
                f"""
                SELECT {_JOB_COLUMNS_SQL}
                 FROM platform.technical_jobs
                 WHERE environment = %s
                   AND deployment_id = %s
                   AND job_name = %s
                   AND input_hash = %s
                   AND configuration_hash = %s
                   AND code_version = %s
                   AND model_version = %s
                 ORDER BY recalculation_number DESC
                 LIMIT 1
                 FOR UPDATE
                """,
                (parsed_request.environment, parsed_request.deployment_id, *identity),
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
                f"""
                INSERT INTO platform.technical_jobs (
                    environment, deployment_id,
                    job_name, priority, input_hash, configuration_hash,
                    code_version, model_version, payload, trace_id, status,
                    recalculation_number
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending',
                    COALESCE((
                        SELECT MAX(recalculation_number) + 1
                          FROM platform.technical_jobs
                         WHERE environment = %s
                           AND deployment_id = %s
                           AND job_name = %s
                           AND input_hash = %s
                           AND configuration_hash = %s
                           AND code_version = %s
                           AND model_version = %s
                    ), 0)
                )
                RETURNING {_JOB_COLUMNS_SQL}
                """,
                (
                    parsed_request.environment,
                    parsed_request.deployment_id,
                    parsed_request.job_name,
                    parsed_request.priority.value,
                    *identity[1:],
                    json.dumps(dict(parsed_request.payload), separators=(",", ":"), sort_keys=True),
                    current_trace_id(),
                    parsed_request.environment,
                    parsed_request.deployment_id,
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
                    f"""
                    SELECT {_JOB_COLUMNS_SQL}
                      FROM platform.technical_jobs
                     WHERE job_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                    """,
                    (
                        job_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                    ),
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
                    f"""
                    SELECT {_JOB_COLUMNS_SQL}
                     FROM platform.technical_jobs
                     WHERE environment = %s
                       AND deployment_id = %s
                       AND job_name = %s
                       AND input_hash = %s
                       AND configuration_hash = %s
                       AND code_version = %s
                       AND model_version = %s
                     ORDER BY recalculation_number DESC
                     LIMIT 1
                    """,
                    (
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        *key.identity_tuple(),
                    ),
                )
                row = cursor.fetchone()
        return None if row is None else _job_from_row(row)

    def consume_relay_message(self, message: RelayedJobMessage) -> str:
        """Consomme un message dans une transaction exclusivement ``platform``."""

        if not isinstance(message, RelayedJobMessage):
            raise ValueError("message relais invalide")
        request = message.as_job_request()
        self._catalog.require_known_job(request.job_name)
        self._require_environment_identity(request)
        serialized_payload = json.dumps(
            dict(request.payload),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (message.message_id,),
                )
                cursor.execute(
                    f"""
                    SELECT {_CONSUMED_RELAY_COLUMNS_SQL}
                      FROM platform.technical_jobs
                     WHERE source_message_id = %s
                    """,
                    (message.message_id,),
                )
                consumed = cursor.fetchone()
                if consumed is not None:
                    consumed_row = _ConsumedRelayRow.from_database(consumed)
                    if consumed_row.source_message_hash != message.content_hash:
                        raise JobRelayMessageConflictError()
                    return consumed_row.job_id

                cursor.execute(
                    f"""
                    SELECT {_EXISTING_RELAY_COLUMNS_SQL}
                     FROM platform.technical_jobs
                     WHERE environment = %s
                       AND deployment_id = %s
                       AND job_name = %s
                       AND input_hash = %s
                       AND configuration_hash = %s
                       AND code_version = %s
                       AND model_version = %s
                       AND recalculation_number = 0
                     FOR UPDATE
                    """,
                    (
                        request.environment,
                        request.deployment_id,
                        *request.idempotence_key.identity_tuple(),
                    ),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    existing_row = _ExistingRelayRow.from_database(existing)
                    if (
                        existing_row.priority != request.priority.value
                        or dict(existing_row.payload) != dict(request.payload)
                        or existing_row.trace_id != message.trace_id
                        or existing_row.source_message_id is not None
                        or existing_row.source_message_hash is not None
                    ):
                        raise JobRelayMessageConflictError()
                    cursor.execute(
                        """
                        UPDATE platform.technical_jobs
                           SET source_message_id = %s, source_message_hash = %s
                         WHERE job_id = %s AND source_message_id IS NULL
                           AND environment = %s AND deployment_id = %s
                        """,
                        (
                            message.message_id,
                            message.content_hash,
                            existing_row.job_id,
                            request.environment,
                            request.deployment_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise JobRelayMessageConflictError()
                    return existing_row.job_id

                cursor.execute(
                    f"""
                    INSERT INTO platform.technical_jobs (
                        environment, deployment_id,
                        job_name, priority, input_hash, configuration_hash,
                        code_version, model_version, payload, trace_id, status,
                        recalculation_number, source_message_id, source_message_hash
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', 0,
                        %s, %s
                    )
                    RETURNING {_INSERTED_JOB_COLUMNS_SQL}
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
                        serialized_payload,
                        message.trace_id,
                        message.message_id,
                        message.content_hash,
                    ),
                )
                inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("JOB_RELAY_PERSISTENCE_FAILED")
        return _InsertedJobRow.from_database(inserted).job_id

    def _require_environment_identity(self, request: JobRequest) -> None:
        if request.environment_identity != self._environment_identity:
            raise WorkerEnvironmentMismatchError()

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
                        f"""
                        WITH candidate AS (
                            SELECT sequence
                             FROM platform.technical_jobs
                              WHERE environment = %s
                                AND deployment_id = %s
                                AND configuration_hash = %s
                                AND job_name = ANY(%s)
                               AND (
                                   status = 'pending'
                                   OR (status = 'running' AND lease_expires_at <= CURRENT_TIMESTAMP)
                               )
                             ORDER BY priority, sequence
                             FOR UPDATE SKIP LOCKED
                             LIMIT 1
                        )
                        UPDATE platform.technical_jobs AS job
                           SET status = 'running', lease_owner = %s,
                               lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                               execution_attempts = execution_attempts + 1,
                               claim_generation = claim_generation + 1,
                               claim_token = gen_random_uuid()
                          FROM candidate
                         WHERE job.sequence = candidate.sequence
                        RETURNING {_QUALIFIED_CLAIMED_JOB_COLUMNS_SQL}
                        """,
                        (
                            self._environment_identity.environment,
                            self._environment_identity.deployment_id,
                            self._environment_identity.configuration_hash,
                            list(parsed_names),
                            parsed_owner,
                            parsed_lease,
                        ),
                    )
                    row = cursor.fetchone()
        if row is None:
            return None
        claimed_row = _ClaimedJobRow.from_database(row)
        return ClaimedJob(
            job=_job_from_row(claimed_row.job_row()),
            trace_id=claimed_row.trace_id,
            lease_owner=claimed_row.lease_owner,
            lease_expires_at=claimed_row.lease_expires_at,
            claim_generation=claimed_row.claim_generation,
            claim_token=str(claimed_row.claim_token),
            execution_attempts=claimed_row.execution_attempts,
        )

    def renew_lease(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        lease_seconds: int,
    ) -> ClaimedJob:
        return self._transition_lease(
            job_id=job_id,
            owner_id=owner_id,
            claim_generation=claim_generation,
            claim_token=claim_token,
            lease_seconds=lease_seconds,
        )

    def mark_succeeded(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        result: Mapping[str, Any],
    ) -> JobRecord:
        parsed_result = _required_mapping(result, "result")
        return self._finish(
            job_id=job_id,
            owner_id=owner_id,
            claim_generation=claim_generation,
            claim_token=claim_token,
            status="succeeded",
            result=json.dumps(dict(parsed_result), separators=(",", ":"), sort_keys=True),
            failure_reason=None,
        )

    def mark_failed(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        failure_reason: str,
    ) -> JobRecord:
        return self._finish(
            job_id=job_id,
            owner_id=owner_id,
            claim_generation=claim_generation,
            claim_token=claim_token,
            status="failed",
            result=None,
            failure_reason=_ensure_text(failure_reason, "failure_reason"),
        )

    def schedule_retry(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        max_attempts: int,
    ) -> JobRecord:
        """Relâche uniquement une tentative encore sous budget."""

        parsed_job_id = _ensure_text(job_id, "job_id")
        parsed_owner = _ensure_text(owner_id, "owner_id")
        parsed_generation = _ensure_positive_integer(claim_generation, "claim_generation")
        parsed_token = _ensure_text(claim_token, "claim_token")
        parsed_max_attempts = _ensure_positive_integer(max_attempts, "max_attempts")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE platform.technical_jobs
                       SET status = 'pending', result = NULL, failure_reason = NULL,
                           lease_owner = NULL, lease_expires_at = NULL,
                           claim_token = NULL
                     WHERE job_id = %s AND status = 'running'
                       AND environment = %s AND deployment_id = %s
                       AND lease_owner = %s AND lease_expires_at > CURRENT_TIMESTAMP
                       AND claim_generation = %s AND claim_token = %s::uuid
                       AND execution_attempts < %s
                    RETURNING {_JOB_COLUMNS_SQL}
                    """,
                    (
                        parsed_job_id,
                        self._environment_identity.environment,
                        self._environment_identity.deployment_id,
                        parsed_owner,
                        parsed_generation,
                        parsed_token,
                        parsed_max_attempts,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            raise JobLeaseConflictError()
        return _job_from_row(row)

    def _transition_lease(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        lease_seconds: int,
    ) -> ClaimedJob:
        parsed_job_id = _ensure_text(job_id, "job_id")
        parsed_owner = _ensure_text(owner_id, "owner_id")
        parsed_generation = _ensure_positive_integer(claim_generation, "claim_generation")
        parsed_token = _ensure_text(claim_token, "claim_token")
        parsed_lease = _ensure_positive_integer(lease_seconds, "lease_seconds")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE platform.technical_jobs
                           SET lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                         WHERE job_id = %s AND status = 'running'
                           AND environment = %s AND deployment_id = %s
                           AND lease_owner = %s AND lease_expires_at > CURRENT_TIMESTAMP
                           AND claim_generation = %s AND claim_token = %s::uuid
                        RETURNING {_CLAIMED_JOB_COLUMNS_SQL}
                        """,
                        (
                            parsed_lease,
                            parsed_job_id,
                            self._environment_identity.environment,
                            self._environment_identity.deployment_id,
                            parsed_owner,
                            parsed_generation,
                            parsed_token,
                        ),
                    )
                    row = cursor.fetchone()
        if row is None:
            raise JobLeaseConflictError()
        claimed_row = _ClaimedJobRow.from_database(row)
        return ClaimedJob(
            job=_job_from_row(claimed_row.job_row()),
            trace_id=claimed_row.trace_id,
            lease_owner=claimed_row.lease_owner,
            lease_expires_at=claimed_row.lease_expires_at,
            claim_generation=claimed_row.claim_generation,
            claim_token=str(claimed_row.claim_token),
            execution_attempts=claimed_row.execution_attempts,
        )

    def _finish(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        status: str,
        result: str | None,
        failure_reason: str | None,
    ) -> JobRecord:
        parsed_job_id = _ensure_text(job_id, "job_id")
        parsed_owner = _ensure_text(owner_id, "owner_id")
        parsed_generation = _ensure_positive_integer(claim_generation, "claim_generation")
        parsed_token = _ensure_text(claim_token, "claim_token")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE platform.technical_jobs
                           SET status = %s, result = %s::jsonb, failure_reason = %s,
                               lease_owner = NULL, lease_expires_at = NULL,
                               claim_token = NULL
                         WHERE job_id = %s AND status = 'running'
                           AND environment = %s AND deployment_id = %s
                           AND lease_owner = %s AND lease_expires_at > CURRENT_TIMESTAMP
                           AND claim_generation = %s AND claim_token = %s::uuid
                        RETURNING {_JOB_COLUMNS_SQL}
                        """,
                        (
                            status, result, failure_reason, parsed_job_id,
                            self._environment_identity.environment,
                            self._environment_identity.deployment_id,
                            parsed_owner,
                            parsed_generation, parsed_token,
                        ),
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


def _database_row_values(row: Any, expected_length: int, row_name: str) -> tuple[Any, ...]:
    if not isinstance(row, (tuple, list)) or len(row) != expected_length:
        actual_length = len(row) if isinstance(row, (tuple, list)) else "non-sequence"
        raise RuntimeError(
            f"SQL_ROW_SHAPE_INVALID:{row_name}:expected={expected_length}:actual={actual_length}"
        )
    return tuple(row)


def _job_from_row(row: Any) -> JobRecord:
    parsed_row = row if isinstance(row, _JobRow) else _JobRow.from_database(row)
    payload = _mapping(parsed_row.payload, "payload")
    if payload is None:
        raise RuntimeError("payload PostgreSQL absent")
    status = JobStatus(parsed_row.status)
    result = _mapping(parsed_row.result, "result")
    return JobRecord(
        sequence=parsed_row.sequence,
        job_id=parsed_row.job_id,
        request=JobRequest(
            environment=parsed_row.environment,
            deployment_id=parsed_row.deployment_id,
            job_name=parsed_row.job_name,
            priority=JobPriority(parsed_row.priority),
            idempotence_key=JobIdempotenceKey(
                job_name=parsed_row.job_name,
                input_hash=parsed_row.input_hash,
                configuration_hash=parsed_row.configuration_hash,
                code_version=parsed_row.code_version,
                model_version=parsed_row.model_version,
            ),
            payload=payload,
        ),
        status=status,
        result=result,
        failure_reason=parsed_row.failure_reason,
    )


__all__ = [
    "ClaimedJob",
    "JobLeaseConflictError",
    "JobRelayMessageConflictError",
    "PostgresJobQueue",
]
