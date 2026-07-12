"""Point d'entrée du worker documentaire appartenant au bounded context SP."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.platform.configuration import ApplicationConfiguration, load_application_configuration
from app.platform.job_runtime.postgres import JobLeaseConflictError
from app.platform.postgres_migrations import build_configured_postgres_migration_runner
from app.source_processing.adapters.postgres_document_persistence import build_document_persistence
from app.source_processing.application.document_worker import DocumentDiagnosticWorker


def _run_worker(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    lease_seconds: int,
    poll_seconds: float,
    max_jobs: int | None,
) -> None:
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("application_configuration worker invalide")
    if not isinstance(owner_id, str) or owner_id.strip() == "" or owner_id != owner_id.strip():
        raise ValueError("owner_id worker invalide")
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
        raise ValueError("lease_seconds worker invalide")
    if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)) or poll_seconds <= 0:
        raise ValueError("poll_seconds worker invalide")
    if max_jobs is not None and (
        isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 1
    ):
        raise ValueError("max_jobs worker invalide")

    build_configured_postgres_migration_runner(application_configuration).run()
    persistence = build_document_persistence(application_configuration)
    worker = DocumentDiagnosticWorker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        original_source_store=persistence.original_source_store,
    )
    processed = 0
    while max_jobs is None or processed < max_jobs:
        persistence.job_queue.relay_pending_outbox(limit=16)
        claimed = persistence.job_queue.claim_next(
            owner_id=owner_id,
            lease_seconds=lease_seconds,
            job_names=("DIAGNOSE",),
        )
        if claimed is None:
            if max_jobs is not None:
                return
            time.sleep(poll_seconds)
            continue
        try:
            result = worker.execute(claimed)
            persistence.job_queue.mark_succeeded(
                job_id=claimed.job.job_id,
                owner_id=owner_id,
                result=result,
            )
            status = "succeeded"
        except JobLeaseConflictError:
            raise
        except Exception as exc:
            failure_reason = str(exc) if str(exc) != "" else exc.__class__.__name__
            persistence.job_queue.mark_failed(
                job_id=claimed.job.job_id,
                owner_id=owner_id,
                failure_reason=failure_reason,
            )
            status = "failed"
        print(
            json.dumps(
                {
                    "event_type": "document_worker_job",
                    "job_id": claimed.job.job_id,
                    "owner_id": owner_id,
                    "status": status,
                    "trace_id": claimed.trace_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        processed += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker documentaire SP PostgreSQL.")
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
