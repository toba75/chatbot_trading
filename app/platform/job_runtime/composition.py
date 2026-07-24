"""Composition plateforme de la file durable et du relais SP."""

from __future__ import annotations

from dataclasses import dataclass

from app.platform.configuration import ApplicationConfiguration
from app.platform.job_runtime import JOB_RUNTIME_CATALOG, JobEnvironmentIdentity
from app.platform.job_runtime.granite_capacity import (
    GraniteCapacityController,
    PostgresGraniteSlotRepository,
    PostgresGraniteWorkerRegistry,
)
from app.platform.job_runtime.page_completion import (
    PostgresPageCompletionOutbox,
    PostgresStandardPageExecutionRepository,
)
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay, RelayOutbox
from app.platform.postgres import PostgresConnectionFactory


@dataclass(frozen=True, slots=True)
class PostgresJobRuntime:
    queue: PostgresJobQueue
    outbox_relay: JobOutboxRelay
    granite_worker_registry: PostgresGraniteWorkerRegistry
    granite_slot_repository: PostgresGraniteSlotRepository
    granite_capacity_controller: GraniteCapacityController
    standard_page_repository: PostgresStandardPageExecutionRepository
    page_completion_outbox: PostgresPageCompletionOutbox


def build_postgres_job_runtime(
    *,
    connection_factory: PostgresConnectionFactory,
    outbox: RelayOutbox,
    application_configuration: ApplicationConfiguration,
) -> PostgresJobRuntime:
    if not callable(getattr(connection_factory, "connect", None)):
        raise ValueError("connection_factory runtime invalide")
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("configuration runtime jobs invalide")
    environment_identity = JobEnvironmentIdentity(
        environment=application_configuration.application.environment,
        deployment_id=application_configuration.application.deployment_id,
        configuration_hash=application_configuration.configuration_hash,
    )
    queue = PostgresJobQueue(
        connection_factory=connection_factory,
        catalog=JOB_RUNTIME_CATALOG,
        environment_identity=environment_identity,
    )
    granite_worker_registry = PostgresGraniteWorkerRegistry(
        connection_factory=connection_factory,
        environment_identity=environment_identity,
    )
    granite_slot_repository = PostgresGraniteSlotRepository(
        connection_factory=connection_factory,
        catalog=JOB_RUNTIME_CATALOG,
        environment_identity=environment_identity,
    )
    return PostgresJobRuntime(
        queue=queue,
        outbox_relay=JobOutboxRelay(
            outbox=outbox,
            consumer=queue,
        ),
        granite_worker_registry=granite_worker_registry,
        granite_slot_repository=granite_slot_repository,
        granite_capacity_controller=GraniteCapacityController(
            repository=granite_slot_repository,
        ),
        standard_page_repository=PostgresStandardPageExecutionRepository(
            connection_factory=connection_factory,
            catalog=JOB_RUNTIME_CATALOG,
            environment_identity=environment_identity,
        ),
        page_completion_outbox=PostgresPageCompletionOutbox(
            connection_factory=connection_factory,
            environment_identity=environment_identity,
        ),
    )


__all__ = ["PostgresJobRuntime", "build_postgres_job_runtime"]
