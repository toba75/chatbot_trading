"""Worker KA réel : relais de l'outbox, projection canonique et index Qdrant."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg import OperationalError

from app.knowledge_access.adapters.projection_runtime import (
    LOCAL_PROJECTION_PROFILE,
    PROJECT_DOCUMENT_JOB_NAME,
    ProjectionRetryableError,
    ProjectionRuntimeError,
    ProjectionRuntimeService,
)
from app.knowledge_access.adapters.postgres_canonical_publication_relay import (
    PostgresCanonicalPublicationRelay,
)
from app.platform.configuration import ApplicationConfiguration, load_application_configuration
from app.platform.configured_datastore_identity import build_configured_datastore_preflight
from app.platform.job_runtime.composition import build_postgres_job_runtime
from app.platform.job_runtime.heartbeat import JobLeaseHeartbeat
from app.platform.job_runtime.postgres import JobLeaseConflictError
from app.platform.job_runtime.reconciliation import reconcile_stale_configuration_jobs
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import build_configured_postgres_migration_runner
from app.platform.llm_gateway.orchestrator_http import UrllibLlmInferenceGateway
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.platform.secret_file import read_required_secret
from app.platform.worker_environment import (
    WorkerHealthFilePublisher,
    build_worker_environment_binding,
    job_environment_identity_from_configuration,
)
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox


MAX_STARTUP_ENVIRONMENT_RECONCILIATIONS = 256


def _run_worker(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    lease_seconds: int,
    poll_seconds: float,
    max_jobs: int | None,
    health_path: Path,
    health_interval_seconds: float,
) -> None:
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("configuration worker KA invalide")
    if not isinstance(owner_id, str) or owner_id.strip() == "" or owner_id != owner_id.strip():
        raise ValueError("owner_id worker KA invalide")
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
        raise ValueError("lease_seconds worker KA invalide")
    if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)) or poll_seconds <= 0:
        raise ValueError("poll_seconds worker KA invalide")
    if max_jobs is not None and (isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 1):
        raise ValueError("max_jobs worker KA invalide")
    build_configured_datastore_preflight(
        application_configuration,
        include_postgres=True,
        include_qdrant=True,
        file_root_names=("canonical_sources_root",),
    ).run(initialize_if_empty=True)
    build_configured_postgres_migration_runner(
        application_configuration,
        initialize_identity_if_empty=False,
        adopt_legacy_if_unidentified=False,
    ).run()
    connection_factory = PsycopgConnectionFactory(
        connection_url=application_configuration.services.postgres.url,
        password_path=Path(application_configuration.security.secrets.postgres_password_path),
        connect_timeout_seconds=application_configuration.runtime.timeouts.startup_seconds,
    )
    runtime = ProjectionRuntimeService(
        connection_factory=connection_factory,
        canonical_sources_root=Path(application_configuration.paths.canonical_sources_root),
        environment=application_configuration.application.environment,
        deployment_id=application_configuration.application.deployment_id,
        configuration_hash=application_configuration.configuration_hash,
        qdrant_url=application_configuration.services.qdrant.url,
        qdrant_collection_name=application_configuration.services.qdrant.collections.knowledge_access,
        qdrant_timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
        qdrant_api_key=read_required_secret(
            path=Path(application_configuration.security.secrets.qdrant_api_key_path),
            error_code="QDRANT_SECRET_UNREADABLE",
        ),
        max_parallel_workers=application_configuration.services.workers.concurrency,
        inference_gateway=UrllibLlmInferenceGateway(
            endpoint_url=f"{application_configuration.services.llm_gateway.url.rstrip('/')}/v1/infer",
            timeout_seconds=application_configuration.services.llm_gateway.timeout_seconds,
        ),
    )
    environment_identity = job_environment_identity_from_configuration(
        application_configuration
    )
    outbox = PostgresJobOutbox(
        connection_factory=connection_factory,
        environment_identity=environment_identity,
        table_name="knowledge_access.job_outbox",
    )
    publication_relay = PostgresCanonicalPublicationRelay(
        connection_factory=connection_factory,
        environment_identity=environment_identity,
        projection_profile=LOCAL_PROJECTION_PROFILE,
        configured_collection_name=(
            application_configuration.services.qdrant.collections.knowledge_access
        ),
        observation_sink=_emit_publication_relay_observation,
    )
    job_runtime = build_postgres_job_runtime(
        connection_factory=connection_factory,
        outbox=outbox,
        application_configuration=application_configuration,
    )
    worker_binding = build_worker_environment_binding(
        application_configuration,
        worker_id=owner_id,
    )
    instance_owner_id = worker_binding.instance_owner_id(str(uuid4()))
    reconcile_stale_configuration_jobs(
        job_queue=job_runtime.queue,
        job_names=(PROJECT_DOCUMENT_JOB_NAME,),
        owner_id=f"{instance_owner_id}-RECONCILE",
        lease_seconds=lease_seconds,
        maximum_jobs=MAX_STARTUP_ENVIRONMENT_RECONCILIATIONS,
        persist_public_failure=outbox.persist_environment_failure,
    )
    WorkerHealthFilePublisher(
        binding=worker_binding,
        path=health_path,
        heartbeat_interval_seconds=health_interval_seconds,
    ).start()
    print(
        json.dumps(worker_binding.health_snapshot().to_mapping(), sort_keys=True),
        flush=True,
    )
    processed = 0
    while max_jobs is None or processed < max_jobs:
        try:
            publication_relay.relay_pending(
                limit=16,
                owner_id=f"{instance_owner_id}-PUBLICATION",
                lease_seconds=lease_seconds,
            )
            job_runtime.outbox_relay.relay_pending(
                limit=16,
                owner_id=f"{instance_owner_id}-OUTBOX",
                lease_seconds=lease_seconds,
            )
            claimed = job_runtime.queue.claim_next(
                owner_id=instance_owner_id,
                lease_seconds=lease_seconds,
                job_names=(PROJECT_DOCUMENT_JOB_NAME,),
            )
        except OperationalError:
            _log_runtime_error(
                application_configuration=application_configuration,
                owner_id=instance_owner_id,
                error_code="POSTGRES_TRANSIENT_FAILURE",
            )
            time.sleep(poll_seconds)
            continue
        if claimed is None:
            if max_jobs is not None:
                return
            time.sleep(poll_seconds)
            continue
        worker_binding.require_job_request(claimed.job.request)
        trace_token = bind_trace_id(claimed.trace_id)
        started = time.perf_counter_ns()
        heartbeat = JobLeaseHeartbeat(
            job_queue=job_runtime.queue,
            job_id=claimed.job.job_id,
            owner_id=instance_owner_id,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            lease_seconds=lease_seconds,
            heartbeat_seconds=max(0.05, lease_seconds / 3),
        )
        heartbeat.start()
        status = "failed"
        error_code: str | None = None
        try:
            try:
                result = runtime.execute_projection(request=claimed.job.request)
            except ProjectionRetryableError as exc:
                error_code = exc.error_code
                status = "retrying"
            except Exception as exc:
                error_code = (
                    exc.error_code
                    if isinstance(exc, ProjectionRuntimeError)
                    else "PROJECTION_WORKER_UNEXPECTED_ERROR"
                )
                heartbeat.finalize(
                    lambda: job_runtime.queue.mark_failed(
                        job_id=claimed.job.job_id,
                        owner_id=instance_owner_id,
                        claim_generation=claimed.claim_generation,
                        claim_token=claimed.claim_token,
                        failure_reason=error_code,
                    )
                )
            else:
                heartbeat.finalize(
                    lambda: job_runtime.queue.mark_succeeded(
                        job_id=claimed.job.job_id,
                        owner_id=instance_owner_id,
                        claim_generation=claimed.claim_generation,
                        claim_token=claimed.claim_token,
                        result=result,
                    )
                )
                status = "succeeded"
        except JobLeaseConflictError:
            status = "lease_lost"
            error_code = "JOB_LEASE_LOST"
        finally:
            heartbeat.stop()
            reset_trace_id(trace_token)
        _log(
            application_configuration=application_configuration,
            claimed=claimed,
            status=status,
            error_code=error_code,
            started=started,
        )
        processed += 1


def _log_runtime_error(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    error_code: str,
) -> None:
    print(
        json.dumps(
            {
                "error_code": error_code,
                "environment": application_configuration.application.environment,
                "deployment_id": application_configuration.application.deployment_id,
                "configuration_hash": application_configuration.configuration_hash,
                "event_type": "knowledge_projection_worker_runtime_error",
                "owner_id": owner_id,
                "status": "retrying",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _emit_publication_relay_observation(
    observation: dict[str, object] | Any,
) -> None:
    if not isinstance(observation, dict):
        observation = dict(observation)
    print(json.dumps(observation, ensure_ascii=False, sort_keys=True), flush=True)


def _log(
    *,
    application_configuration: ApplicationConfiguration,
    claimed: Any,
    status: str,
    error_code: str | None,
    started: int,
) -> None:
    payload: dict[str, object] = {
        "event_type": "knowledge_projection_worker_job",
        "job_id": claimed.job.job_id,
        "status": status,
        "trace_id": claimed.trace_id,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
        "success_count": 1 if status == "succeeded" else 0,
        "error_count": 0 if status == "succeeded" else 1,
        "environment": application_configuration.application.environment,
        "deployment_id": application_configuration.application.deployment_id,
        "configuration_hash": application_configuration.configuration_hash,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker PostgreSQL de projection KA.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-seconds", required=True, type=int)
    parser.add_argument("--poll-seconds", required=True, type=float)
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--health-path", required=True, type=Path)
    parser.add_argument("--health-interval-seconds", required=True, type=float)
    arguments = parser.parse_args()
    configuration = load_application_configuration(
        config_path=Path(arguments.config),
        environment_snapshot=dict(os.environ),
    )
    _run_worker(
        application_configuration=configuration,
        owner_id=arguments.worker_id,
        lease_seconds=arguments.lease_seconds,
        poll_seconds=arguments.poll_seconds,
        max_jobs=arguments.max_jobs,
        health_path=arguments.health_path,
        health_interval_seconds=arguments.health_interval_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["_run_worker", "main"]
