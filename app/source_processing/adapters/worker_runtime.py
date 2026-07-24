"""Point d'entrée résilient du worker documentaire SP."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg import Error as PsycopgError, IntegrityError, OperationalError
from uuid import uuid4

from app.contracts.technical_jobs import ClaimedJob
from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.configured_datastore_identity import (
    build_configured_datastore_preflight,
)
from app.platform.job_runtime import JobExecutionRequirements, JobStatus
from app.platform.job_runtime.composition import build_postgres_job_runtime
from app.platform.job_runtime.granite_capacity import (
    GraniteCapacityConfigurationError,
    GraniteWorker,
    GraniteWorkerPresenceHeartbeat,
    GraniteWorkerState,
    GraniteSlotLease,
    GraniteSlotLeaseLostError,
)
from app.platform.job_runtime.page_completion import PageCompletionRelay
from app.platform.job_runtime.heartbeat import JobHeartbeatCoordinator, JobLeaseHeartbeat
from app.platform.job_runtime.postgres import JobLeaseConflictError
from app.platform.job_runtime.reconciliation import reconcile_stale_configuration_jobs
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import build_configured_postgres_migration_runner
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.platform.worker_environment import (
    WorkerHealthFilePublisher,
    build_worker_environment_binding,
    job_environment_identity_from_configuration,
)
from app.source_processing.adapters.postgres_document_persistence import (
    build_document_persistence,
)
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactFileStore,
    IsolatedNativeDoclingConverter,
)
from app.source_processing.adapters.docling_granite_conversion import (
    IsolatedGraniteDoclingConverter,
)
from app.source_processing.adapters.gemma_vision_conversion import (
    IsolatedGemmaVisionPageConverter,
)
from app.source_processing.adapters.distributed_page_conversion import (
    M004RoutedPageConverter,
    load_runtime_locked_assets,
)
from app.source_processing.adapters.local_page_artifacts import LocalPageArtifactStore
from app.source_processing.adapters.postgres_page_completion import (
    PostgresPageResultRepository,
)
from app.source_processing.adapters.postgres_canonical_assembly import (
    PostgresCanonicalAssemblyRepository,
)
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox
from app.source_processing.adapters.pypdf_diagnostic_inspector import (
    PdfDiagnosticInspector,
)
from app.source_processing.adapters.pdf_inspection_process import (
    build_m13_isolated_pdf_inspector,
)
from app.source_processing.application.document_worker import (
    DocumentDiagnosticWorker,
    WorkerProcessingError,
)
from app.source_processing.application.execute_document_page import (
    ExecuteDocumentPageHandler,
    PageRouteConverters,
)
from app.source_processing.application.fan_out_document_pages import (
    DistributedDocumentConversionWorker,
    VersionedDocumentConversionWorker,
)
from app.source_processing.application.record_page_completion import (
    RecordPageCompletionHandler,
)
from app.source_processing.application.assemble_canonical_document import (
    AssembleCanonicalDocumentHandler,
    CanonicalAssemblyWorker,
)
from app.source_processing.domain.distribution_contracts import (
    ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
    CONVERT_PAGE_CONTRACT_VERSION,
    CONVERT_PAGE_JOB_NAME,
    ExecutionCapability,
    PageResultStatus,
)
from app.source_processing.application.routed_document_conversion_worker import (
    build_routed_document_conversion_worker,
)
from app.source_processing.application.routing_policy import (
    build_document_routing_configuration,
)


MAX_TRANSIENT_ATTEMPTS = 3
MAX_STARTUP_ENVIRONMENT_RECONCILIATIONS = 256
GEMMA_GATEWAY_LOCAL_SUPERVISION_OVERHEAD_SECONDS = 30


class RegisteredDocumentWorkerLifecycle:
    """Cycle enregistré d'un replica : présence, admissions et drainage ADR-052."""

    def __init__(
        self,
        *,
        worker_registry: Any,
        capacity_controller: Any,
        job_heartbeat_coordinator: Any,
        worker: GraniteWorker,
        presence_heartbeat: Any,
        presence_lease_seconds: int,
        shutdown_seconds: int,
        now: Callable[[], datetime],
    ) -> None:
        for port, method_names in (
            (worker_registry, ("register", "begin_draining")),
            (capacity_controller, ("begin_draining",)),
            (job_heartbeat_coordinator, ("freeze_for_drain",)),
            (presence_heartbeat, ("start", "assert_alive", "stop")),
        ):
            if not all(callable(getattr(port, name, None)) for name in method_names):
                raise ValueError("port lifecycle worker incomplet")
        if not isinstance(worker, GraniteWorker):
            raise ValueError("worker lifecycle invalide")
        if (
            isinstance(presence_lease_seconds, bool)
            or not isinstance(presence_lease_seconds, int)
            or presence_lease_seconds < 1
        ):
            raise ValueError("presence_lease_seconds lifecycle invalide")
        if (
            isinstance(shutdown_seconds, bool)
            or not isinstance(shutdown_seconds, int)
            or shutdown_seconds < 1
        ):
            raise ValueError("shutdown_seconds lifecycle invalide")
        if not callable(now):
            raise ValueError("horloge lifecycle invalide")
        self._worker_registry = worker_registry
        self._capacity_controller = capacity_controller
        self._job_heartbeat_coordinator = job_heartbeat_coordinator
        self._worker = worker
        self._presence_heartbeat = presence_heartbeat
        self._presence_lease_seconds = presence_lease_seconds
        self._shutdown_seconds = shutdown_seconds
        self._now = now
        self._lock = threading.RLock()
        self._drain_request = threading.Event()
        self._drain_supervisor = threading.Thread(
            target=self._supervise_drain_request,
            name=f"document-worker-drain-{worker.worker_instance_id}",
            daemon=True,
        )
        self._started = False
        self._drained = False
        self._closed = False
        self._admissions_open = False

    @property
    def admissions_open(self) -> bool:
        with self._lock:
            return self._admissions_open

    def start(self) -> None:
        with self._lock:
            if self._started:
                raise RuntimeError("DOCUMENT_WORKER_LIFECYCLE_ALREADY_STARTED")
            self._worker_registry.register(
                self._worker,
                presence_lease_seconds=self._presence_lease_seconds,
            )
            self._presence_heartbeat.start()
            self._started = True
            self._admissions_open = True
            self._drain_supervisor.start()

    def assert_admission_allowed(self) -> None:
        with self._lock:
            if not self._started or not self._admissions_open:
                raise GraniteSlotLeaseLostError()
        try:
            self._presence_heartbeat.assert_alive()
        except Exception:
            self.request_drain()
            raise

    def request_drain(self) -> None:
        self._drain_request.set()
        with self._lock:
            if self._drained:
                return
            if not self._started:
                raise RuntimeError("DOCUMENT_WORKER_LIFECYCLE_NOT_STARTED")
            self._admissions_open = False
            self._job_heartbeat_coordinator.freeze_for_drain()
            self._capacity_controller.begin_draining()
            drain_deadline = self._now() + timedelta(seconds=self._shutdown_seconds)
            self._worker_registry.begin_draining(
                worker_instance_id=self._worker.worker_instance_id,
                drain_deadline=drain_deadline,
            )
            self._presence_heartbeat.stop()
            self._drained = True

    def handle_termination(self, _signal_number: int, _frame: object) -> None:
        with self._lock:
            self._admissions_open = False
        self._drain_request.set()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self.request_drain()
            self._closed = True
        if self._drain_supervisor.is_alive():
            self._drain_supervisor.join(timeout=self._shutdown_seconds)
        if self._drain_supervisor.is_alive():
            raise RuntimeError("DOCUMENT_WORKER_DRAIN_SUPERVISOR_STOP_TIMEOUT")

    def _supervise_drain_request(self) -> None:
        self._drain_request.wait()
        self.request_drain()


def _gemma_gateway_supervision_timeout_seconds(
    *,
    spark_attempt_timeout_seconds: int,
    retry_before_first_token: int,
) -> int:
    if (
        isinstance(spark_attempt_timeout_seconds, bool)
        or not isinstance(spark_attempt_timeout_seconds, int)
        or spark_attempt_timeout_seconds < 1
    ):
        raise ValueError("timeout de tentative Spark invalide")
    if (
        isinstance(retry_before_first_token, bool)
        or not isinstance(retry_before_first_token, int)
        or retry_before_first_token < 0
    ):
        raise ValueError("nombre de retries avant premier token invalide")
    return (
        spark_attempt_timeout_seconds * (retry_before_first_token + 1)
        + GEMMA_GATEWAY_LOCAL_SUPERVISION_OVERHEAD_SECONDS
    )


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
    _validate_worker_runtime_arguments(
        application_configuration=application_configuration,
        owner_id=owner_id,
        lease_seconds=lease_seconds,
        poll_seconds=poll_seconds,
        max_jobs=max_jobs,
    )
    build_configured_datastore_preflight(
        application_configuration,
        include_postgres=True,
        include_qdrant=False,
        file_root_names=("data_root", "corpus_root", "canonical_sources_root"),
    ).run(initialize_if_empty=True)
    build_configured_postgres_migration_runner(
        application_configuration,
        initialize_identity_if_empty=False,
        adopt_legacy_if_unidentified=False,
    ).run()
    _run_validated_worker_and_claim_next(
        application_configuration=application_configuration,
        owner_id=owner_id,
        lease_seconds=lease_seconds,
        poll_seconds=poll_seconds,
        max_jobs=max_jobs,
        health_path=health_path,
        health_interval_seconds=health_interval_seconds,
    )


def _validate_worker_runtime_arguments(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    lease_seconds: int,
    poll_seconds: float,
    max_jobs: int | None,
) -> None:
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("application_configuration worker invalide")
    _require_worker_owner_id(owner_id)
    _require_worker_positive_integer(lease_seconds, "lease_seconds")
    _require_worker_positive_number(poll_seconds, "poll_seconds")
    if max_jobs is not None and (
        isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 1
    ):
        raise ValueError("max_jobs worker invalide")


def _require_worker_owner_id(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("owner_id worker invalide")
    return value


def _require_worker_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} worker invalide")
    return value


def _require_worker_positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field_name} worker invalide")
    return float(value)


def _run_validated_worker_and_claim_next(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    lease_seconds: int,
    poll_seconds: float,
    max_jobs: int | None,
    health_path: Path,
    health_interval_seconds: float,
) -> None:
    worker_binding = build_worker_environment_binding(
        application_configuration,
        worker_id=owner_id,
    )
    instance_owner_id = worker_binding.instance_owner_id(str(uuid4()))
    connection_factory = PsycopgConnectionFactory(
        connection_url=application_configuration.services.postgres.url,
        password_path=Path(
            application_configuration.security.secrets.postgres_password_path
        ),
        connect_timeout_seconds=application_configuration.runtime.timeouts.startup_seconds,
    )
    persistence = build_document_persistence(
        application_configuration,
        connection_factory=connection_factory,
    )
    environment_identity = job_environment_identity_from_configuration(
        application_configuration
    )
    outbox = PostgresJobOutbox(
        connection_factory=connection_factory,
        environment_identity=environment_identity,
    )
    job_runtime = build_postgres_job_runtime(
        connection_factory=connection_factory,
        outbox=outbox,
        application_configuration=application_configuration,
    )
    granite_worker = GraniteWorker(
        worker_instance_id=instance_owner_id,
        environment_identity=environment_identity,
        storage_environment=environment_identity.environment,
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )
    shutdown_seconds = application_configuration.runtime.timeouts.shutdown_seconds
    job_heartbeat_coordinator = JobHeartbeatCoordinator()
    presence_heartbeat = GraniteWorkerPresenceHeartbeat(
        registry=job_runtime.granite_worker_registry,
        worker=granite_worker,
        presence_lease_seconds=shutdown_seconds,
        heartbeat_seconds=shutdown_seconds / 3.0,
    )
    lifecycle = RegisteredDocumentWorkerLifecycle(
        worker_registry=job_runtime.granite_worker_registry,
        capacity_controller=job_runtime.granite_capacity_controller,
        job_heartbeat_coordinator=job_heartbeat_coordinator,
        worker=granite_worker,
        presence_heartbeat=presence_heartbeat,
        presence_lease_seconds=shutdown_seconds,
        shutdown_seconds=shutdown_seconds,
        now=lambda: datetime.now(UTC),
    )
    lifecycle.start()
    atexit.register(lifecycle.close)
    signal.signal(signal.SIGTERM, lifecycle.handle_termination)
    reconcile_stale_configuration_jobs(
        job_queue=job_runtime.queue,
        job_names=(
            "DIAGNOSE",
            "CONVERT_DOCUMENT",
            "CONVERT_PAGE",
            ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
        ),
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
    worker = DocumentDiagnosticWorker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        diagnostic_inspector=PdfDiagnosticInspector(
            original_source_store=persistence.original_source_store,
            inspector=build_m13_isolated_pdf_inspector(),
        ),
        routing_configuration=build_document_routing_configuration(),
    )
    canonical_artifact_store = CanonicalArtifactFileStore(
        root=Path(application_configuration.paths.canonical_sources_root)
    )
    page_artifact_store = LocalPageArtifactStore(
        profile_root=(
            Path(application_configuration.paths.data_root) / "page_artifacts"
        ).resolve()
    )
    native_manifest_path = Path("config/docling-assets.native.json")
    native_assets_root = (
        Path(application_configuration.paths.data_root) / "docling_assets" / "native"
    )
    granite_manifest_path = Path("config/docling-assets.granite.json")
    granite_assets_root = (
        Path(application_configuration.paths.data_root) / "docling_assets" / "granite"
    )
    ocrmypdf_manifest_path = Path("config/ocrmypdf-image.json")
    locked_assets = load_runtime_locked_assets(
        native_manifest_path=native_manifest_path,
        native_assets_root=native_assets_root,
        granite_manifest_path=granite_manifest_path,
        granite_assets_root=granite_assets_root,
        ocrmypdf_manifest_path=ocrmypdf_manifest_path,
    )
    routed_conversion_worker = build_routed_document_conversion_worker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        conversion_repository=persistence.document_conversion_repository,
        original_source_store=persistence.original_source_store,
        native_asset_manifest_path=native_manifest_path,
        native_assets_root=native_assets_root,
        granite_asset_manifest_path=granite_manifest_path,
        granite_assets_root=granite_assets_root,
        ocrmypdf_manifest_path=ocrmypdf_manifest_path,
        audit_root=Path(application_configuration.paths.data_root) / "docling_audit",
        timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
        llm_gateway_url=application_configuration.services.llm_gateway.url,
        llm_gateway_timeout_seconds=_gemma_gateway_supervision_timeout_seconds(
            spark_attempt_timeout_seconds=(
                application_configuration.services.llm_gateway.timeout_seconds
            ),
            retry_before_first_token=(
                application_configuration.services.llm_gateway.retry_before_first_token
            ),
        ),
        llm_gateway_max_output_tokens=application_configuration.models.llm.max_output_tokens,
        expected_gemma_model_id=application_configuration.models.llm.reference_model,
        artifact_store=canonical_artifact_store,
        max_parallel_pages=application_configuration.services.workers.concurrency,
        docling_max_concurrency=application_configuration.services.workers.docling_concurrency,
        granite_max_concurrency=application_configuration.services.workers.granite_concurrency,
        granite_capacity_controller=job_runtime.granite_capacity_controller,
        granite_worker=granite_worker,
        granite_lease_seconds=lease_seconds,
        granite_heartbeat_seconds=lease_seconds / 3.0,
        job_heartbeat_control=job_heartbeat_coordinator,
    )
    routed_page_converter = M004RoutedPageConverter(
        native_converter=IsolatedNativeDoclingConverter(
            asset_manifest_path=native_manifest_path,
            assets_root=native_assets_root,
            timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
        ),
        granite_converter=IsolatedGraniteDoclingConverter(
            asset_manifest_path=granite_manifest_path,
            assets_root=granite_assets_root,
            timeout_seconds=application_configuration.runtime.timeouts.request_seconds,
        ),
        gemma_converter=IsolatedGemmaVisionPageConverter(
            timeout_seconds=_gemma_gateway_supervision_timeout_seconds(
                spark_attempt_timeout_seconds=(
                    application_configuration.services.llm_gateway.timeout_seconds
                ),
                retry_before_first_token=(
                    application_configuration.services.llm_gateway.retry_before_first_token
                ),
            ),
        ),
        capacity_controller=job_runtime.granite_capacity_controller,
        granite_worker=granite_worker,
        granite_lease_seconds=lease_seconds,
        granite_heartbeat_seconds=lease_seconds / 3.0,
        ocrmypdf_manifest_path=ocrmypdf_manifest_path,
        audit_root=Path(application_configuration.paths.data_root) / "docling_audit",
        ocrmypdf_timeout_seconds=(
            application_configuration.runtime.timeouts.request_seconds
        ),
        gateway_endpoint_url=application_configuration.services.llm_gateway.url,
        gateway_timeout_seconds=_gemma_gateway_supervision_timeout_seconds(
            spark_attempt_timeout_seconds=(
                application_configuration.services.llm_gateway.timeout_seconds
            ),
            retry_before_first_token=(
                application_configuration.services.llm_gateway.retry_before_first_token
            ),
        ),
        gateway_max_output_tokens=application_configuration.models.llm.max_output_tokens,
        expected_model_id=application_configuration.models.llm.reference_model,
    )
    page_converters = PageRouteConverters.from_routed(routed_page_converter)
    page_worker = ExecuteDocumentPageHandler(
        artifact_reader=page_artifact_store,
        artifact_writer=page_artifact_store,
        converters=page_converters,
        standard_completion=job_runtime.standard_page_repository,
        granite_completion=job_runtime.granite_slot_repository,
        expected_locked_assets=locked_assets,
    )
    page_completion_relay = PageCompletionRelay(
        outbox=job_runtime.page_completion_outbox,
        consumer=RecordPageCompletionHandler(
            repository=PostgresPageResultRepository(
                connection_factory=connection_factory
            )
        ),
    )
    canonical_assembly_worker = CanonicalAssemblyWorker(
        handler=AssembleCanonicalDocumentHandler(
            repository=PostgresCanonicalAssemblyRepository(
                connection_factory=connection_factory
            ),
            page_artifact_reader=page_artifact_store,
            canonical_artifact_store=canonical_artifact_store,
        )
    )
    standard_page_requirements = JobExecutionRequirements(
        contract_name=CONVERT_PAGE_JOB_NAME,
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        capacity_capability=ExecutionCapability.DOCUMENT_STANDARD.value,
        capacity_slots=0,
        capacity_device=None,
        storage_environment=environment_identity.environment,
    )
    granite_page_requirements = JobExecutionRequirements(
        contract_name=CONVERT_PAGE_JOB_NAME,
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        capacity_capability=ExecutionCapability.GRANITE_CUDA.value,
        capacity_slots=1,
        capacity_device="cuda:0",
        storage_environment=environment_identity.environment,
    )
    distributed_conversion_worker = DistributedDocumentConversionWorker(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        page_fan_out_repository=persistence.document_conversion_repository,
        original_source_store=persistence.original_source_store,
        source_artifact_store=page_artifact_store,
        locked_assets=locked_assets,
    )
    versioned_conversion_worker = VersionedDocumentConversionWorker(
        legacy_worker=routed_conversion_worker,
        distributed_worker=distributed_conversion_worker,
    )
    workers = {
        "DIAGNOSE": worker,
        "CONVERT_DOCUMENT": versioned_conversion_worker,
        ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME: canonical_assembly_worker,
    }
    processed = 0
    while lifecycle.admissions_open and (max_jobs is None or processed < max_jobs):
        try:
            lifecycle.assert_admission_allowed()
            job_runtime.outbox_relay.relay_pending(
                limit=16,
                owner_id=f"{instance_owner_id}-OUTBOX",
                lease_seconds=lease_seconds,
            )
            page_completion_relay.relay_pending(
                limit=16,
                owner_id=f"{instance_owner_id}-PAGE-RESULTS",
                lease_seconds=lease_seconds,
            )
            page_authorization = job_runtime.granite_slot_repository.claim_compatible_job(
                worker=granite_worker,
                lease_seconds=lease_seconds,
                job_names=(CONVERT_PAGE_JOB_NAME,),
                execution_requirements=granite_page_requirements,
            )
            if page_authorization is None:
                page_authorization = (
                    job_runtime.standard_page_repository.claim_compatible_job(
                        worker=granite_worker,
                        lease_seconds=lease_seconds,
                        job_names=(CONVERT_PAGE_JOB_NAME,),
                        execution_requirements=standard_page_requirements,
                    )
                )
            claimed = (
                None
                if page_authorization is not None
                else job_runtime.queue.claim_next(
                    owner_id=instance_owner_id,
                    lease_seconds=lease_seconds,
                    job_names=(
                        "DIAGNOSE",
                        "CONVERT_DOCUMENT",
                        ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
                    ),
                )
            )
        except OperationalError:
            _log_runtime_error(
                application_configuration=application_configuration,
                owner_id=instance_owner_id,
                error_code="POSTGRES_TRANSIENT_FAILURE",
            )
            time.sleep(poll_seconds)
            continue
        if page_authorization is not None:
            _execute_claimed_page(
                application_configuration=application_configuration,
                authorization=page_authorization,
                page_worker=page_worker,
                worker_binding=worker_binding,
                job_queue=job_runtime.queue,
                lease_seconds=lease_seconds,
            )
            processed += 1
            continue
        if claimed is None:
            if max_jobs is not None:
                lifecycle.close()
                atexit.unregister(lifecycle.close)
                return
            time.sleep(poll_seconds)
            continue
        if not lifecycle.admissions_open:
            break

        worker_binding.require_job_request(claimed.job.request)

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
        job_heartbeat_coordinator.bind(heartbeat)
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
            job_heartbeat_coordinator.unbind(heartbeat)
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
    lifecycle.close()
    atexit.unregister(lifecycle.close)


def _execute_claimed_page(
    *,
    application_configuration: ApplicationConfiguration,
    authorization: ClaimedJob | GraniteSlotLease,
    page_worker: ExecuteDocumentPageHandler,
    worker_binding: Any,
    job_queue: Any,
    lease_seconds: int,
) -> None:
    """Exécute une page sans réutiliser la terminalisation des jobs historiques."""

    if isinstance(authorization, GraniteSlotLease):
        claimed = authorization.claimed_job
        standard_heartbeat = None
    elif isinstance(authorization, ClaimedJob):
        claimed = authorization
        standard_heartbeat = JobLeaseHeartbeat(
            job_queue=job_queue,
            job_id=claimed.job.job_id,
            owner_id=claimed.lease_owner,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            lease_seconds=lease_seconds,
            heartbeat_seconds=max(0.05, lease_seconds / 3),
        )
    else:
        raise ValueError("PAGE_EXECUTION_AUTHORIZATION_INVALID")
    worker_binding.require_job_request(claimed.job.request)
    started_ns = time.perf_counter_ns()
    trace_token = bind_trace_id(claimed.trace_id)
    status = "failed"
    error_code: str | None = None
    if standard_heartbeat is not None:
        standard_heartbeat.start()
    try:
        if isinstance(authorization, GraniteSlotLease):
            outcome = page_worker.execute_granite(authorization)
        else:
            outcome = page_worker.execute_standard(claimed)
        if outcome.result.status is PageResultStatus.SUCCEEDED:
            status = "succeeded"
        else:
            error_code = outcome.result.error_code.value
    except (JobLeaseConflictError, GraniteSlotLeaseLostError):
        status = "lease_lost"
        error_code = "JOB_LEASE_LOST"
    finally:
        if standard_heartbeat is not None:
            standard_heartbeat.stop()
        reset_trace_id(trace_token)
        _log_job_result(
            application_configuration=application_configuration,
            claimed=claimed,
            owner_id=claimed.lease_owner,
            status=status,
            error_code=error_code,
            duration_ms=(time.perf_counter_ns() - started_ns) / 1_000_000,
        )


def _classify_processing_error(error: Exception) -> tuple[str, bool]:
    error = _primary_processing_error(error)
    if isinstance(error, GraniteSlotLeaseLostError):
        return "JOB_LEASE_LOST", True
    if isinstance(error, GraniteCapacityConfigurationError):
        return error.code, False
    if isinstance(error, WorkerProcessingError):
        return error.error_code, error.retryable
    if isinstance(error, OperationalError):
        return "POSTGRES_TRANSIENT_FAILURE", True
    if isinstance(error, IntegrityError):
        return "POSTGRES_INTEGRITY_FAILURE", False
    if isinstance(error, PsycopgError):
        return "POSTGRES_PERMANENT_FAILURE", False
    if (
        isinstance(error, RuntimeError)
        and str(error) == "CONVERSION_PERSISTENCE_CONFLICT"
    ):
        return "CONVERSION_PERSISTENCE_CONFLICT", False
    stable_code = getattr(error, "code", None)
    if isinstance(stable_code, str) and stable_code.strip() != "":
        return stable_code, False
    return "WORKER_UNEXPECTED_ERROR", False


def _primary_processing_error(error: Exception) -> Exception:
    primary = error
    while isinstance(primary, ExceptionGroup):
        nested = primary.exceptions[0]
        if not isinstance(nested, Exception):
            return primary
        primary = nested
    return primary


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


def _log_runtime_error(
    *,
    application_configuration: ApplicationConfiguration,
    owner_id: str,
    error_code: str,
) -> None:
    print(
        json.dumps(
            {
                "event_type": "document_worker_runtime_error",
                "owner_id": owner_id,
                "status": "retrying",
                "error_code": error_code,
                "environment": application_configuration.application.environment,
                "deployment_id": application_configuration.application.deployment_id,
                "configuration_hash": application_configuration.configuration_hash,
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
        "environment": application_configuration.application.environment,
        "deployment_id": application_configuration.application.deployment_id,
        "configuration_hash": application_configuration.configuration_hash,
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


__all__ = [
    "JobLeaseHeartbeat",
    "RegisteredDocumentWorkerLifecycle",
    "_classify_processing_error",
    "_run_worker",
    "_settle_processing_failure",
    "main",
]
