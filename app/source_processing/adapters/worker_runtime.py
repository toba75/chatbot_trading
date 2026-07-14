"""Point d'entrée résilient du worker documentaire SP."""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg import Error as PsycopgError, IntegrityError, OperationalError
from uuid import uuid4

from app.platform.configuration import ApplicationConfiguration, load_application_configuration
from app.platform.job_runtime import JobStatus
from app.platform.job_runtime.composition import build_postgres_job_runtime
from app.platform.job_runtime.postgres import JobLeaseConflictError
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import build_configured_postgres_migration_runner
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.source_processing.adapters.postgres_document_persistence import build_document_persistence
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactFileStore,
)
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox
from app.source_processing.adapters.pypdf_diagnostic_inspector import (
    PdfDiagnosticInspector,
)
from app.source_processing.adapters.pdf_inspection_process import build_m13_isolated_pdf_inspector
from app.source_processing.application.document_worker import (
    DocumentDiagnosticWorker,
    WorkerProcessingError,
)
from app.source_processing.domain.document_processing_run import (
    PageRoutingConfiguration,
    RoutingPolicyVersion,
)
from app.source_processing.application.routed_document_conversion_worker import (
    build_routed_document_conversion_worker,
)


MAX_TRANSIENT_ATTEMPTS = 3
DOCUMENT_ROUTING_POLICY_VERSION = "routing-v1"
DOCUMENT_ROUTING_AUTO_CONFIDENCE_MIN = 0.90
DOCUMENT_ROUTING_BENCHMARK_CONFIDENCE_MIN = 0.85


class JobLeaseHeartbeat:
    """Renouvelle une lease pendant tout calcul et sérialise sa finalisation."""

    def __init__(
        self,
        *,
        job_queue: Any,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        lease_seconds: int,
        heartbeat_seconds: float,
    ) -> None:
        if not callable(getattr(job_queue, "renew_lease", None)):
            raise ValueError("job_queue sans renouvellement")
        if not isinstance(job_id, str) or job_id.strip() == "":
            raise ValueError("job_id heartbeat invalide")
        if not isinstance(owner_id, str) or owner_id.strip() == "":
            raise ValueError("owner_id heartbeat invalide")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
            raise ValueError("lease_seconds heartbeat invalide")
        if (
            isinstance(heartbeat_seconds, bool)
            or not isinstance(heartbeat_seconds, (int, float))
            or heartbeat_seconds <= 0
            or heartbeat_seconds >= lease_seconds
        ):
            raise ValueError("heartbeat_seconds invalide")
        self._job_queue = job_queue
        self._job_id = job_id
        self._owner_id = owner_id
        if isinstance(claim_generation, bool) or not isinstance(claim_generation, int) or claim_generation < 1:
            raise ValueError("claim_generation heartbeat invalide")
        if not isinstance(claim_token, str) or claim_token.strip() == "":
            raise ValueError("claim_token heartbeat invalide")
        self._claim_generation = claim_generation
        self._claim_token = claim_token
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = float(heartbeat_seconds)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._failure: Exception | None = None
        self._finalized = False
        self._thread = threading.Thread(
            target=self._run,
            name=f"lease-heartbeat-{job_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def assert_owned(self) -> None:
        with self._lock:
            self._raise_failure()

    def finalize(self, transition: Callable[[], Any]) -> Any:
        if not callable(transition):
            raise ValueError("transition finale invalide")
        with self._lock:
            self._raise_failure()
            result = transition()
            self._finalized = True
            self._stop.set()
            return result

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self._heartbeat_seconds * 2))
        if self._thread.is_alive():
            raise RuntimeError("JOB_LEASE_HEARTBEAT_STOP_TIMEOUT")

    def _run(self) -> None:
        while not self._stop.wait(self._heartbeat_seconds):
            with self._lock:
                if self._finalized:
                    return
                try:
                    self._job_queue.renew_lease(
                        job_id=self._job_id,
                        owner_id=self._owner_id,
                        claim_generation=self._claim_generation,
                        claim_token=self._claim_token,
                        lease_seconds=self._lease_seconds,
                    )
                except Exception as exc:
                    self._failure = exc
                    self._stop.set()
                    return

    def _raise_failure(self) -> None:
        if self._failure is None:
            return
        if isinstance(self._failure, JobLeaseConflictError):
            raise self._failure
        raise RuntimeError("JOB_LEASE_RENEWAL_FAILED") from self._failure


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
    instance_owner_id = f"{owner_id}:{uuid4()}"

    build_configured_postgres_migration_runner(application_configuration).run()
    connection_factory = PsycopgConnectionFactory(
        connection_url=application_configuration.services.postgres.url,
        password_path=Path(application_configuration.security.secrets.postgres_password_path),
        connect_timeout_seconds=application_configuration.runtime.timeouts.startup_seconds,
    )
    persistence = build_document_persistence(
        application_configuration,
        connection_factory=connection_factory,
    )
    job_runtime = build_postgres_job_runtime(
        connection_factory=connection_factory,
        outbox=PostgresJobOutbox(connection_factory=connection_factory),
    )
    worker = DocumentDiagnosticWorker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        diagnostic_inspector=PdfDiagnosticInspector(
            original_source_store=persistence.original_source_store,
            inspector=build_m13_isolated_pdf_inspector(),
        ),
        routing_configuration=PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value(
                DOCUMENT_ROUTING_POLICY_VERSION
            ),
            auto_confidence_min=DOCUMENT_ROUTING_AUTO_CONFIDENCE_MIN,
            benchmark_confidence_min=DOCUMENT_ROUTING_BENCHMARK_CONFIDENCE_MIN,
        ),
    )
    routed_conversion_worker = build_routed_document_conversion_worker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        conversion_repository=persistence.document_conversion_repository,
        original_source_store=persistence.original_source_store,
        native_asset_manifest_path=Path("config/docling-assets.native.json"),
        native_assets_root=Path(application_configuration.paths.data_root) / "docling_assets" / "native",
        granite_asset_manifest_path=Path("config/docling-assets.granite.json"),
        granite_assets_root=Path(application_configuration.paths.data_root) / "docling_assets" / "granite",
        ocrmypdf_manifest_path=Path("config/ocrmypdf-image.json"),
        audit_root=Path(application_configuration.paths.data_root) / "docling_audit",
        timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
        llm_gateway_url=application_configuration.services.llm_gateway.url,
        llm_gateway_timeout_seconds=application_configuration.services.llm_gateway.timeout_seconds,
        llm_gateway_max_output_tokens=application_configuration.models.llm.max_output_tokens,
        expected_gemma_model_id=application_configuration.models.llm.reference_model,
        artifact_store=CanonicalArtifactFileStore(
            root=Path(application_configuration.paths.canonical_sources_root)
        ),
    )
    workers = {
        "DIAGNOSE": worker,
        "CONVERT_DOCUMENT": routed_conversion_worker,
    }
    processed = 0
    while max_jobs is None or processed < max_jobs:
        try:
            job_runtime.outbox_relay.relay_pending(
                limit=16,
                owner_id=f"{instance_owner_id}-OUTBOX",
                lease_seconds=lease_seconds,
            )
            claimed = job_runtime.queue.claim_next(
                owner_id=instance_owner_id,
                lease_seconds=lease_seconds,
                job_names=("DIAGNOSE", "CONVERT_DOCUMENT"),
            )
        except OperationalError:
            _log_runtime_error(owner_id=instance_owner_id, error_code="POSTGRES_TRANSIENT_FAILURE")
            time.sleep(poll_seconds)
            continue
        if claimed is None:
            if max_jobs is not None:
                return
            time.sleep(poll_seconds)
            continue

        started_ns = time.perf_counter_ns()
        trace_token = bind_trace_id(claimed.trace_id)
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
                claimed_worker = workers[claimed.job.request.job_name]
                result = claimed_worker.execute(claimed)
            except Exception as exc:
                error_code, retryable = _classify_processing_error(exc)
                status = _settle_processing_failure(
                    claimed=claimed,
                    error_code=error_code,
                    retryable=retryable,
                    max_attempts=MAX_TRANSIENT_ATTEMPTS,
                    worker=claimed_worker,
                    job_queue=job_runtime.queue,
                    heartbeat=heartbeat,
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

        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        _log_job_result(
            application_configuration=application_configuration,
            claimed=claimed,
            owner_id=instance_owner_id,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
        )
        processed += 1


def _classify_processing_error(error: Exception) -> tuple[str, bool]:
    if isinstance(error, WorkerProcessingError):
        return error.error_code, error.retryable
    if isinstance(error, OperationalError):
        return "POSTGRES_TRANSIENT_FAILURE", True
    if isinstance(error, IntegrityError):
        return "POSTGRES_INTEGRITY_FAILURE", False
    if isinstance(error, PsycopgError):
        return "POSTGRES_PERMANENT_FAILURE", False
    return "WORKER_UNEXPECTED_ERROR", False


def _settle_processing_failure(
    *,
    claimed: Any,
    error_code: str,
    retryable: bool,
    max_attempts: int,
    worker: Any,
    job_queue: Any,
    heartbeat: Any,
) -> str:
    """Publie SP avant tout échec terminal platform, puis permet la réconciliation."""

    if retryable and claimed.execution_attempts < max_attempts:
        job = heartbeat.finalize(
            lambda: job_queue.schedule_retry(
                job_id=claimed.job.job_id,
                owner_id=claimed.lease_owner,
                claim_generation=claimed.claim_generation,
                claim_token=claimed.claim_token,
                max_attempts=max_attempts,
            )
        )
        if job.status is not JobStatus.PENDING:
            raise RuntimeError("JOB_RETRY_STATE_INVALID")
        return "retry_scheduled"

    def fail_after_sp_publication() -> Any:
        worker.mark_failed(claimed, error_code)
        return job_queue.mark_failed(
            job_id=claimed.job.job_id,
            owner_id=claimed.lease_owner,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            failure_reason=error_code,
        )

    job = heartbeat.finalize(fail_after_sp_publication)
    if job.status is not JobStatus.FAILED:
        raise RuntimeError("JOB_TERMINAL_STATE_INVALID")
    return "failed"


def _log_runtime_error(*, owner_id: str, error_code: str) -> None:
    print(
        json.dumps(
            {
                "event_type": "document_worker_runtime_error",
                "owner_id": owner_id,
                "status": "retrying",
                "error_code": error_code,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _log_job_result(
    *,
    application_configuration: ApplicationConfiguration,
    claimed: Any,
    owner_id: str,
    status: str,
    error_code: str | None,
    duration_ms: float,
) -> None:
    payload = {
        "event_type": "document_worker_job",
        "job_id": claimed.job.job_id,
        "owner_id": owner_id,
        "status": status,
        "trace_id": claimed.trace_id,
        "success_count": 1 if status == "succeeded" else 0,
        "error_count": 0 if status in ("succeeded", "retry_scheduled") else 1,
        "duration_ms": round(duration_ms, 3),
        "processed_volume": 1,
        "tracing_enabled": application_configuration.observability.tracing.enabled,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


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


__all__ = [
    "JobLeaseHeartbeat",
    "_classify_processing_error",
    "_run_worker",
    "_settle_processing_failure",
    "main",
]
