"""Worker KA réel : relais de l'outbox, projection canonique et index Qdrant."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.knowledge_access.adapters.projection_runtime import (
    PROJECT_DOCUMENT_JOB_NAME,
    ProjectionRuntimeError,
    ProjectionRuntimeService,
)
from app.platform.configuration import ApplicationConfiguration, load_application_configuration
from app.platform.job_runtime.composition import build_postgres_job_runtime
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import build_configured_postgres_migration_runner
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox


def _run_worker(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    lease_seconds: int,
    poll_seconds: float,
    max_jobs: int | None,
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
    build_configured_postgres_migration_runner(application_configuration).run()
    connection_factory = PsycopgConnectionFactory(
        connection_url=application_configuration.services.postgres.url,
        password_path=Path(application_configuration.security.secrets.postgres_password_path),
        connect_timeout_seconds=application_configuration.runtime.timeouts.startup_seconds,
    )
    runtime = ProjectionRuntimeService(
        connection_factory=connection_factory,
        canonical_sources_root=Path(application_configuration.paths.canonical_sources_root),
        configuration_hash=application_configuration.configuration_hash,
        qdrant_url=application_configuration.services.qdrant.url,
        qdrant_timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
    )
    job_runtime = build_postgres_job_runtime(
        connection_factory=connection_factory,
        outbox=PostgresJobOutbox(
            connection_factory=connection_factory,
            table_name="knowledge_access.job_outbox",
        ),
    )
    instance_owner_id = f"{owner_id}:{uuid4()}"
    processed = 0
    while max_jobs is None or processed < max_jobs:
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
        if claimed is None:
            if max_jobs is not None:
                return
            time.sleep(poll_seconds)
            continue
        trace_token = bind_trace_id(claimed.trace_id)
        started = time.perf_counter_ns()
        try:
            payload = claimed.job.request.payload
            projection_id = payload.get("projection_id") if isinstance(payload, Mapping) else None
            if not isinstance(projection_id, str):
                raise ProjectionRuntimeError("PROJECTION_JOB_PAYLOAD_INVALID")
            result = runtime.execute_projection(projection_id=projection_id)
        except Exception as exc:
            error_code = exc.error_code if isinstance(exc, ProjectionRuntimeError) else "PROJECTION_WORKER_UNEXPECTED_ERROR"
            job_runtime.queue.mark_failed(
                job_id=claimed.job.job_id,
                owner_id=instance_owner_id,
                claim_generation=claimed.claim_generation,
                claim_token=claimed.claim_token,
                failure_reason=error_code,
            )
            _log(claimed=claimed, status="failed", error_code=error_code, started=started)
        else:
            job_runtime.queue.mark_succeeded(
                job_id=claimed.job.job_id,
                owner_id=instance_owner_id,
                claim_generation=claimed.claim_generation,
                claim_token=claimed.claim_token,
                result=result,
            )
            _log(claimed=claimed, status="succeeded", error_code=None, started=started)
        finally:
            reset_trace_id(trace_token)
        processed += 1


def _log(*, claimed: Any, status: str, error_code: str | None, started: int) -> None:
    payload: dict[str, object] = {
        "event_type": "knowledge_projection_worker_job",
        "job_id": claimed.job.job_id,
        "status": status,
        "trace_id": claimed.trace_id,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
        "success_count": 1 if status == "succeeded" else 0,
        "error_count": 0 if status == "succeeded" else 1,
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
    arguments = parser.parse_args()
    configuration = load_application_configuration(
        config_path=Path(arguments.config),
        environment_snapshot={},
    )
    _run_worker(
        application_configuration=configuration,
        owner_id=arguments.worker_id,
        lease_seconds=arguments.lease_seconds,
        poll_seconds=arguments.poll_seconds,
        max_jobs=arguments.max_jobs,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["_run_worker", "main"]
