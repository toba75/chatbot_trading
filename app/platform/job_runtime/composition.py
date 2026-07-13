"""Composition plateforme de la file durable et du relais SP."""

from __future__ import annotations

from dataclasses import dataclass

from app.platform.job_runtime import JOB_RUNTIME_CATALOG
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay, RelayOutbox
from app.platform.postgres import PostgresConnectionFactory


@dataclass(frozen=True, slots=True)
class PostgresJobRuntime:
    queue: PostgresJobQueue
    outbox_relay: JobOutboxRelay


def build_postgres_job_runtime(
    *,
    connection_factory: PostgresConnectionFactory,
    outbox: RelayOutbox,
) -> PostgresJobRuntime:
    if not callable(getattr(connection_factory, "connect", None)):
        raise ValueError("connection_factory runtime invalide")
    queue = PostgresJobQueue(
        connection_factory=connection_factory,
        catalog=JOB_RUNTIME_CATALOG,
    )
    return PostgresJobRuntime(
        queue=queue,
        outbox_relay=JobOutboxRelay(
            outbox=outbox,
            consumer=queue,
        ),
    )


__all__ = ["PostgresJobRuntime", "build_postgres_job_runtime"]
