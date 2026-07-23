"""Tests unitaires T-004 du runtime Granite supervisé et terminal."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import subprocess
import threading
import time
from uuid import uuid4

import pytest
import yaml

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.platform.job_runtime.granite_capacity import (
    GraniteCapacityConfigurationError,
    GraniteCapacityController,
    GraniteModelStillRunning,
    GranitePageTerminalEnvelope,
    GranitePageTerminalStatus,
    GraniteSlotLease,
    GraniteSlotLeaseLostError,
    GraniteWorker,
    GraniteWorkerState,
)
from app.source_processing.adapters.docling_granite_conversion import (
    GraniteDoclingConversionError,
    GraniteDoclingConversionRequest,
    RunningGraniteDoclingConversion,
)
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactFileStore,
    NativeDoclingConversionResponse,
    NativeDoclingPage,
    NativeDoclingPageItem,
)
from app.source_processing.adapters.gemma_vision_conversion import (
    GemmaVisionConversionResponse,
    GemmaVisionPageItem,
    RunningGemmaVisionConversion,
)
from app.source_processing.application.convert_routed_pages import PageConversionRequest
from app.source_processing.application.routed_document_conversion_worker import (
    _RunningGraniteRouteConversion,
    build_routed_document_conversion_worker,
)
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRouteName,
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _requirements() -> JobExecutionRequirements:
    return JobExecutionRequirements(
        contract_name="CONVERT_PAGE",
        contract_version="1.0",
        capacity_capability="GRANITE_CUDA",
        capacity_slots=1,
        capacity_device="cuda:0",
        storage_environment="test",
        source_artifact_ref="artifact:source_processing.local/test/source.pdf",
        result_artifact_ref="artifact:source_processing.local/test/page-1.json",
        route_name="SCAN_GRANITE",
    )


def _lease() -> GraniteSlotLease:
    identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash="a" * 64,
    )
    request = JobRequest(
        environment=identity.environment,
        deployment_id=identity.deployment_id,
        job_name="CONVERT_PAGE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_PAGE",
            input_hash="b" * 64,
            configuration_hash=identity.configuration_hash,
            code_version="m014-runtime",
            model_version="granite-locked",
        ),
        execution_requirements=_requirements(),
        payload={"contract_version": "1.0"},
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    claimed = ClaimedJob(
        job=JobRecord(
            sequence=1,
            job_id="JOB-M002-000001",
            request=request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id="TRACE-M014-RUNTIME",
        lease_owner="worker-documents-1",
        lease_expires_at=expires_at,
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )
    return GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=1,
        slot_generation=1,
        slot_token=str(uuid4()),
        lease_until=expires_at,
    )


def _worker() -> GraniteWorker:
    return GraniteWorker(
        worker_instance_id="worker-documents-1",
        environment_identity=_lease().claimed_job.job.request.environment_identity,
        storage_environment="test",
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )


def _terminal(
    lease: GraniteSlotLease,
    status: GranitePageTerminalStatus,
    payload: dict[str, object],
) -> GranitePageTerminalEnvelope:
    return GranitePageTerminalEnvelope.from_payload(
        completion_id=f"COMPLETE-{lease.claimed_job.job.job_id}-{status.value}",
        status=status,
        payload=payload,
        failure_reason=(
            None if status is GranitePageTerminalStatus.SUCCEEDED else "MODEL_FAILED"
        ),
    )


class _Process:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = outcomes
        self.terminated = False
        self.wait_timeouts: list[float] = []

    def wait(self, *, timeout_seconds: float):
        self.wait_timeouts.append(timeout_seconds)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def terminate(self) -> None:
        self.terminated = True


class _Repository:
    def __init__(self, *, heartbeat_failure: Exception | None = None) -> None:
        self.lease = _lease()
        self.heartbeat_failure = heartbeat_failure
        self.heartbeats = 0
        self.terminals: list[GranitePageTerminalEnvelope] = []
        self.claim_enabled = True
        self.terminal_failure: Exception | None = None
        self.legacy_acquisitions: list[GraniteSlotLease | None] = []
        self.releases: list[GraniteSlotLease] = []

    def claim_compatible_job(self, **_arguments):
        return self.lease if self.claim_enabled else None

    def heartbeat(self, lease, *, lease_seconds):
        assert lease_seconds == 30
        self.heartbeats += 1
        if self.heartbeat_failure is not None:
            raise self.heartbeat_failure
        return lease

    def complete_page_execution(self, lease, envelope):
        assert lease == self.lease
        if self.terminal_failure is not None:
            raise self.terminal_failure
        self.terminals.append(envelope)
        return lease.claimed_job.job

    def acquire_for_claimed_job(self, *, worker, claimed_job):
        assert claimed_job == self.lease.claimed_job
        if self.legacy_acquisitions:
            return self.legacy_acquisitions.pop(0)
        return self.lease

    def release(self, lease):
        self.releases.append(lease)


def test_runtime_granite_supervise_heartbeat_annulation_et_terminal_atomique() -> None:
    """Given un job Granite leased, When il bloque ou perd sa lease, Then le processus reste supervisé."""

    repository = _Repository()
    process = _Process(
        [GraniteModelStillRunning(), GraniteModelStillRunning(), {"answer": "ok"}]
    )
    execution = GraniteCapacityController(repository=repository).execute_next(
        worker=_worker(),
        lease_seconds=30,
        heartbeat_seconds=0.01,
        job_names=("CONVERT_PAGE",),
        execution_requirements=_requirements(),
        start_model=lambda _lease: process,
        success_envelope=lambda lease, result: _terminal(
            lease,
            GranitePageTerminalStatus.SUCCEEDED,
            result,
        ),
        failure_envelope=lambda lease, _error: _terminal(
            lease,
            GranitePageTerminalStatus.FAILED,
            {"error_code": "MODEL_FAILED"},
        ),
    )
    assert execution is not None
    assert execution.model_result == {"answer": "ok"}
    assert repository.heartbeats == 2
    assert len(repository.terminals) == 1
    assert repository.terminals[0].status is GranitePageTerminalStatus.SUCCEEDED
    assert process.terminated is False

    lost_repository = _Repository(heartbeat_failure=GraniteSlotLeaseLostError())
    blocked_process = _Process([GraniteModelStillRunning()])
    with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
        GraniteCapacityController(repository=lost_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda _lease: blocked_process,
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
    assert blocked_process.terminated is True
    assert lost_repository.terminals == []

    primary = RuntimeError("GRANITE_MODEL_PRIMARY")
    compensation = RuntimeError("GRANITE_TERMINAL_COMPENSATION_FAILED")
    failing_repository = _Repository()
    failing_repository.terminal_failure = compensation
    with pytest.raises(ExceptionGroup) as captured:
        GraniteCapacityController(repository=failing_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda _lease: _Process([primary]),
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
    assert captured.value.exceptions == (primary, compensation)

    waiting_repository = _Repository()
    waiting_repository.claim_enabled = False
    model_started: list[object] = []
    assert (
        GraniteCapacityController(repository=waiting_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda lease: model_started.append(lease),
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
        is None
    )
    assert model_started == []

    legacy_repository = _Repository()
    legacy_repository.legacy_acquisitions = [None, legacy_repository.lease]
    legacy_model_starts: list[GraniteSlotLease] = []
    legacy_execution = GraniteCapacityController(
        repository=legacy_repository
    ).execute_claimed_job(
        worker=_worker(),
        claimed_job=legacy_repository.lease.claimed_job,
        lease_seconds=30,
        heartbeat_seconds=0.01,
        start_model=lambda lease: (
            legacy_model_starts.append(lease) or _Process([{"legacy": "ok"}])
        ),
    )
    assert legacy_execution.model_result == {"legacy": "ok"}
    assert legacy_model_starts == [legacy_repository.lease]
    assert legacy_repository.releases == [legacy_repository.lease]

    parameter = inspect.signature(JobRequest).parameters["execution_requirements"]
    assert parameter.default is inspect.Parameter.empty

    for relative_path in (
        "config/application.example.yaml",
        "config/environments/development.yaml",
        "config/environments/test.yaml",
        "config/environments/production.yaml",
        "deploy/local-compose/application.compose.yaml",
    ):
        configuration = yaml.safe_load(
            (REPOSITORY_ROOT / relative_path).read_text("utf-8")
        )
        assert configuration["services"]["workers"]["granite_concurrency"] == 1

    quota_source = (
        REPOSITORY_ROOT / "app/platform/job_runtime/granite_capacity.py"
    ).read_text("utf-8")
    assert "payload ->" not in quota_source
    assert "%(environment)s" in quota_source

    composition_source = (
        REPOSITORY_ROOT / "app/platform/job_runtime/composition.py"
    ).read_text("utf-8")
    assert "GraniteCapacityController" in composition_source
    assert "PostgresGraniteWorkerRegistry" in composition_source

    for converter_path in (
        "app/source_processing/adapters/docling_granite_conversion.py",
        "app/source_processing/adapters/gemma_vision_conversion.py",
    ):
        converter_source = (REPOSITORY_ROOT / converter_path).read_text("utf-8")
        assert "subprocess.Popen" in converter_source
        assert "subprocess.run(" not in converter_source


class _PopenBoundary:
    def __init__(self, *, terminate_failure: Exception | None = None) -> None:
        self.returncode = None
        self.terminate_failure = terminate_failure
        self.events: list[str] = []

    def communicate(self, *, input, timeout):
        self.events.append(f"communicate:{timeout}")
        raise subprocess.TimeoutExpired("granite", timeout)

    def poll(self):
        return None

    def terminate(self) -> None:
        self.events.append("terminate")
        if self.terminate_failure is not None:
            raise self.terminate_failure

    def wait(self, *, timeout):
        self.events.append(f"wait:{timeout}")
        if "kill" not in self.events:
            raise subprocess.TimeoutExpired("granite", timeout)
        return -9

    def kill(self) -> None:
        self.events.append("kill")


def _granite_request(source_path: Path) -> GraniteDoclingConversionRequest:
    return GraniteDoclingConversionRequest(
        document_id="DOC-AAAAAAAAAAAAAAAA",
        processing_run_id="RUN-M014-CYCLE3",
        source_sha256="a" * 64,
        source_pdf_path=source_path,
        page_number=1,
        source_page_number=1,
        route_name="SCAN_GRANITE",
        routing_policy_version="routing-cycle3-v1",
    )


@pytest.mark.parametrize(
    ("factory", "error_type", "error_code"),
    (
        (
            lambda process, source: RunningGraniteDoclingConversion(
                process=process,
                request=_granite_request(source),
                input_payload=b"{}",
                timeout_seconds=1.0,
            ),
            GraniteDoclingConversionError,
            "GRANITE_DOCLING_TIMEOUT",
        ),
        (
            lambda process, _source: RunningGemmaVisionConversion(
                process=process,
                input_payload=b"{}",
                timeout_seconds=1.0,
            ),
            Exception,
            "GEMMA_VISION_TIMEOUT",
        ),
    ),
)
def test_frontiere_popen_applique_une_deadline_totale_et_termine_une_seule_fois(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    factory,
    error_type,
    error_code: str,
) -> None:
    """Given un Popen encore actif, When sa deadline totale expire, Then terminate/wait/kill est unique."""

    now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\ncycle3\n%%EOF\n")
    process = _PopenBoundary()
    running = factory(process, source)

    with pytest.raises(GraniteModelStillRunning):
        running.wait(timeout_seconds=0.25)
    assert process.events == ["communicate:0.25"]

    now[0] = 101.0
    with pytest.raises(error_type) as captured:
        running.wait(timeout_seconds=0.25)
    assert getattr(captured.value, "code", str(captured.value)) == error_code
    assert process.events == [
        "communicate:0.25",
        "terminate",
        "wait:5.0",
        "kill",
        "wait:5.0",
    ]
    running.terminate()
    assert process.events.count("terminate") == 1
    assert process.events.count("kill") == 1


@pytest.mark.parametrize("legacy", (False, True))
def test_perte_lease_conserve_la_cause_primaire_si_terminate_echoue(
    legacy: bool,
) -> None:
    """Given une lease perdue, When l'arrêt échoue, Then JOB_LEASE_LOST reste la première cause."""

    lost = GraniteSlotLeaseLostError()
    repository = _Repository(heartbeat_failure=lost)
    process = _Process([GraniteModelStillRunning()])

    def terminate() -> None:
        raise RuntimeError("GRANITE_PROCESS_TERMINATION_FAILED")

    process.terminate = terminate  # type: ignore[method-assign]
    controller = GraniteCapacityController(repository=repository)
    with pytest.raises(ExceptionGroup) as captured:
        if legacy:
            controller.execute_claimed_job(
                worker=_worker(),
                claimed_job=repository.lease.claimed_job,
                lease_seconds=30,
                heartbeat_seconds=0.01,
                start_model=lambda _lease: process,
            )
        else:
            controller.execute_next(
                worker=_worker(),
                lease_seconds=30,
                heartbeat_seconds=0.01,
                job_names=("CONVERT_PAGE",),
                execution_requirements=_requirements(),
                start_model=lambda _lease: process,
                success_envelope=lambda lease, result: _terminal(
                    lease, GranitePageTerminalStatus.SUCCEEDED, result
                ),
                failure_envelope=lambda lease, _error: _terminal(
                    lease,
                    GranitePageTerminalStatus.FAILED,
                    {"error_code": "MODEL_FAILED"},
                ),
            )
    assert captured.value.exceptions[0] is lost
    assert str(captured.value.exceptions[1]) == "GRANITE_PROCESS_TERMINATION_FAILED"


class _ImmediateProcess:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def wait(self, *, timeout_seconds: float):
        del timeout_seconds
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def terminate(self) -> None:
        raise AssertionError("arrêt inattendu")


class _TransitionGraniteConverter:
    def start(self, request, *, lease):
        del request, lease
        return _ImmediateProcess(
            GraniteDoclingConversionError("GRANITE_DOCLING_UNAVAILABLE")
        )


class _TransitionGemmaConverter:
    def __init__(self) -> None:
        self.starts = 0

    def start(self, request, *, lease):
        del request, lease
        self.starts += 1
        return _ImmediateProcess(
            GemmaVisionConversionResponse(
                tool_version="gemma-cycle3-v1",
                items=(
                    GemmaVisionPageItem(
                        text="Texte Gemma supervisé.",
                        bbox=(0.1, 0.1, 0.9, 0.2),
                    ),
                ),
            )
        )


def test_transition_granite_vers_gemma_force_un_heartbeat_intermediaire(
    tmp_path: Path,
) -> None:
    """Given Granite finit vite, When Gemma prend le relais, Then le contrôleur renouvelle avant le second modèle."""

    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\ncycle3 transition\n%%EOF\n")
    request = PageConversionRequest(
        processing_run_id=ProcessingRunId.from_value("RUN-M014-CYCLE3"),
        document_id=DocumentId.from_value("DOC-AAAAAAAAAAAAAAAA"),
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.SCAN_GRANITE,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-cycle3-v1"),
        source_artifact_ref="artifact:source_processing.original/cycle3.pdf",
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            "RUN-M014-CYCLE3/page-001-scan_granite.json"
        ),
    )
    gemma = _TransitionGemmaConverter()
    running = _RunningGraniteRouteConversion(
        lease=_lease(),
        request=request,
        source_path=source,
        granite_converter=_TransitionGraniteConverter(),
        gemma_converter=gemma,
        gateway_endpoint_url="http://llm-gateway:8001/v1/infer",
        gateway_timeout_seconds=30,
        gateway_max_output_tokens=128,
        expected_model_id="google/gemma-3-27b-it",
    )
    with pytest.raises(GraniteModelStillRunning):
        running.wait(timeout_seconds=0.01)
    assert gemma.starts == 1
    assert running.wait(timeout_seconds=0.01).tool_name.value == "GEMMA_VISION"


def test_erreur_configuration_expose_un_motif_precis_sans_changer_le_code() -> None:
    with pytest.raises(GraniteCapacityConfigurationError) as captured:
        GraniteCapacityController(repository=object())
    assert captured.value.code == "GRANITE_CAPACITY_CONFIGURATION_INVALID"
    assert captured.value.reason == "REPOSITORY_PORT_INCOMPLETE"


class _BuiltSourceRepository:
    def __init__(self, source: SourceDocument) -> None:
        self.source = source

    def find_by_document_id(self, document_id: DocumentId):
        return self.source if document_id == self.source.document_id else None


class _BuiltRunRepository:
    def __init__(self, run: DocumentProcessingRun) -> None:
        self.run = run

    def find_by_document_id(self, document_id: DocumentId):
        return self.run if document_id == self.run.document_id else None


class _BuiltConversionRepository:
    def __init__(self, source: SourceDocument) -> None:
        self.state = DocumentConversionState(
            document_id=source.document_id,
            conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
            canonical_version_id=None,
            rejection_error_code=None,
            execution_phase=DocumentConversionExecutionPhase.QUEUED,
            completed_units=0,
            total_units=1,
            failure_error_code=None,
        )
        self.publication = None

    def find_conversion_by_document_id(self, document_id: DocumentId):
        return self.state if document_id == self.state.document_id else None

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        assert document_id == self.state.document_id

    def record_conversion_progress(
        self, *, document_id: DocumentId, completed_units: int
    ) -> None:
        assert document_id == self.state.document_id
        assert completed_units == 1

    def complete_native_conversion(self, publication) -> None:
        self.publication = publication

    def reject_native_conversion(
        self, *, document_id: DocumentId, error_code: str
    ) -> None:
        raise AssertionError((document_id, error_code))


class _BuiltOriginalStore:
    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def resolve_internal_path(self, storage_ref) -> Path:
        del storage_ref
        return self.source_path


class _UnusedNativeConverter:
    def convert(self, request):
        raise AssertionError(request)


class _ForbiddenGemmaConverter:
    def start(self, request, *, lease):
        raise AssertionError((request, lease))


class _BlockingGraniteProcess:
    def __init__(self, release_models: threading.Event) -> None:
        self.release_models = release_models

    def wait(self, *, timeout_seconds: float):
        if not self.release_models.wait(timeout_seconds):
            raise GraniteModelStillRunning()
        return NativeDoclingConversionResponse(
            tool_version="granite-cycle3-v1",
            pages=(
                NativeDoclingPage(
                    page_number=1,
                    items=(
                        NativeDoclingPageItem(
                            text="Texte Granite sous quota durable.",
                            bbox=(0.1, 0.1, 0.9, 0.2),
                            provenance={"page_number": 1, "source": "granite"},
                        ),
                    ),
                ),
            ),
        )

    def terminate(self) -> None:
        self.release_models.set()


class _BlockingGraniteConverter:
    def __init__(
        self,
        *,
        events: list[str],
        events_lock: threading.Lock,
        release_models: threading.Event,
    ) -> None:
        self.events = events
        self.events_lock = events_lock
        self.release_models = release_models

    def start(self, request, *, lease):
        del request
        with self.events_lock:
            self.events.append(f"start:{lease.claimed_job.lease_owner}")
        return _BlockingGraniteProcess(self.release_models)


class _TwoSlotRepository:
    def __init__(self, *, events: list[str], events_lock: threading.Lock) -> None:
        self.events = events
        self.lock = events_lock
        self.held: dict[int, GraniteSlotLease] = {}

    def claim_compatible_job(self, **_arguments):
        raise AssertionError("claim page T-005 interdit")

    def complete_page_execution(self, *_arguments):
        raise AssertionError("terminal page T-005 interdit")

    def acquire_for_claimed_job(self, *, worker, claimed_job):
        with self.lock:
            if any(
                lease.claimed_job.lease_owner == worker.worker_instance_id
                for lease in self.held.values()
            ):
                raise AssertionError("un worker ne peut détenir deux slots")
            available = next(
                (slot for slot in (1, 2) if slot not in self.held),
                None,
            )
            if available is None:
                return None
            lease = GraniteSlotLease(
                claimed_job=claimed_job,
                slot_ordinal=available,
                slot_generation=1,
                slot_token=str(uuid4()),
                lease_until=claimed_job.lease_expires_at,
            )
            self.held[available] = lease
            self.events.append(f"acquire:{worker.worker_instance_id}:{available}")
            return lease

    def heartbeat(self, lease, *, lease_seconds):
        assert lease_seconds == 30
        with self.lock:
            if self.held.get(lease.slot_ordinal) != lease:
                raise GraniteSlotLeaseLostError()
        return lease

    def release(self, lease) -> None:
        with self.lock:
            if self.held.pop(lease.slot_ordinal, None) != lease:
                raise GraniteSlotLeaseLostError()
            self.events.append(f"release:{lease.claimed_job.lease_owner}")


class _BuiltHeartbeatControl:
    def __init__(self, *, worker_id: str, events: list[str], lock: threading.Lock):
        self.worker_id = worker_id
        self.events = events
        self.lock = lock

    def pause(self) -> None:
        with self.lock:
            self.events.append(f"pause:{self.worker_id}")

    def resume(self) -> None:
        with self.lock:
            self.events.append(f"resume:{self.worker_id}")


def _built_scan_fixture(index: int, root: Path):
    content = f"%PDF-1.7\ncycle3 builder {index}\n%%EOF\n".encode()
    source_path = root / f"source-{index}.pdf"
    source_path.write_bytes(content)
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            "artifact:source_processing.original_sources/"
            f"{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": f"Builder Granite {index}",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )
    run = (
        DocumentProcessingRun.start(
            processing_run_id=ProcessingRunId.from_value(
                f"RUN-M014-CYCLE3-BUILDER-{index}"
            ),
            source_document=source,
            page_manifest=PageManifest.from_entries(
                source_page_count=1,
                entries=(
                    PageManifestEntry(
                        PageNumber.from_value(1),
                        PageManifestEntryState.PRESENT,
                    ),
                ),
            ),
        )
        .record_page_diagnostics(
            (
                PageDecision(
                    page_number=PageNumber.from_value(1),
                    page_state=PageDecisionState.SCAN_CLEAN,
                    signals=PageDiagnosticSignals(
                        native_text_state="ABSENT",
                        image_state="SCAN_CLEAN",
                        existing_ocr_state="NONE",
                        layout_complexity="SIMPLE",
                        corruption_state="NONE",
                        mixed_content_detected=False,
                        has_table=False,
                        has_formula=False,
                    ),
                    diagnostic_version=DiagnosticVersion.from_value("diag-cycle3-v1"),
                    justification="Scan propre pour quota comportemental.",
                ),
            )
        )
        .decide_route_plan(
            PageRoutingConfiguration(
                routing_policy_version=RoutingPolicyVersion.from_value(
                    "routing-cycle3-v1"
                ),
                auto_confidence_min=0.9,
                benchmark_confidence_min=0.85,
            )
        )
    )
    claimed = ClaimedJob(
        job=JobRecord(
            sequence=index,
            job_id=f"JOB-M002-{index:06d}",
            request=JobRequest(
                environment="test",
                deployment_id="ostrading-test-local",
                job_name="CONVERT_DOCUMENT",
                priority=JobPriority.P1,
                idempotence_key=JobIdempotenceKey(
                    job_name="CONVERT_DOCUMENT",
                    input_hash=fingerprint.value,
                    configuration_hash="a" * 64,
                    code_version="m014-cycle3-builder",
                    model_version="granite-locked",
                ),
                execution_requirements=None,
                payload={
                    "document_id": document_id.value,
                    "processing_run_id": run.processing_run_id.value,
                    "source_sha256": fingerprint.value,
                    "routing_policy_version": (
                        run.route_plan.routing_policy_version.value
                    ),
                    "route_count": 1,
                },
            ),
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id=f"TRACE-M014-CYCLE3-{index}",
        lease_owner=f"worker-documents-{index}",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )
    return source, run, source_path, claimed


def test_builder_reel_scan_granite_ne_demarre_jamais_avant_un_des_deux_slots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Given trois workers réels SCAN_GRANITE, When deux slots sont pris, Then le troisième attend sans modèle."""

    import app.source_processing.adapters.ocrmypdf_container as ocrmypdf_module
    import app.source_processing.application.routed_document_conversion_worker as worker_module

    events: list[str] = []
    events_lock = threading.Lock()
    release_models = threading.Event()
    repository = _TwoSlotRepository(events=events, events_lock=events_lock)
    controller = GraniteCapacityController(repository=repository)
    monkeypatch.setattr(
        ocrmypdf_module.OcrmyPdfImageManifest,
        "load",
        lambda **_arguments: object(),
    )
    monkeypatch.setattr(
        worker_module,
        "IsolatedNativeDoclingConverter",
        lambda **_arguments: _UnusedNativeConverter(),
    )
    monkeypatch.setattr(
        worker_module,
        "IsolatedGraniteDoclingConverter",
        lambda **_arguments: _BlockingGraniteConverter(
            events=events,
            events_lock=events_lock,
            release_models=release_models,
        ),
    )
    monkeypatch.setattr(
        worker_module,
        "IsolatedGemmaVisionPageConverter",
        lambda **_arguments: _ForbiddenGemmaConverter(),
    )

    identity = _lease().claimed_job.job.request.environment_identity
    fixtures = tuple(_built_scan_fixture(index, tmp_path) for index in (1, 2, 3))
    workers = []
    for index, (source, run, source_path, claimed) in enumerate(fixtures, start=1):
        worker_id = f"worker-documents-{index}"
        workers.append(
            (
                build_routed_document_conversion_worker(
                    source_document_repository=_BuiltSourceRepository(source),
                    processing_run_repository=_BuiltRunRepository(run),
                    conversion_repository=_BuiltConversionRepository(source),
                    original_source_store=_BuiltOriginalStore(source_path),
                    native_asset_manifest_path=tmp_path / "native.json",
                    native_assets_root=tmp_path / "native",
                    granite_asset_manifest_path=tmp_path / "granite.json",
                    granite_assets_root=tmp_path / "granite",
                    ocrmypdf_manifest_path=tmp_path / "ocr.json",
                    audit_root=tmp_path / "audit",
                    timeout_seconds=30,
                    llm_gateway_url="http://llm-gateway:8001/v1/infer",
                    llm_gateway_timeout_seconds=30,
                    llm_gateway_max_output_tokens=128,
                    expected_gemma_model_id="google/gemma-3-27b-it",
                    artifact_store=CanonicalArtifactFileStore(
                        root=tmp_path / f"canonical-{index}"
                    ),
                    max_parallel_pages=1,
                    docling_max_concurrency=1,
                    granite_max_concurrency=1,
                    granite_capacity_controller=controller,
                    granite_worker=GraniteWorker(
                        worker_instance_id=worker_id,
                        environment_identity=identity,
                        storage_environment="test",
                        state=GraniteWorkerState.READY,
                        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
                    ),
                    granite_lease_seconds=30,
                    granite_heartbeat_seconds=0.01,
                    job_heartbeat_control=_BuiltHeartbeatControl(
                        worker_id=worker_id,
                        events=events,
                        lock=events_lock,
                    ),
                ),
                claimed,
            )
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = tuple(
            executor.submit(worker.execute, claimed) for worker, claimed in workers
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with events_lock:
                starts = tuple(event for event in events if event.startswith("start:"))
            if len(starts) == 2:
                break
            time.sleep(0.01)
        assert len(starts) == 2
        assert len(set(starts)) == 2
        with events_lock:
            snapshot = tuple(events)
        for start in starts:
            worker_id = start.removeprefix("start:")
            assert (
                snapshot.index(f"pause:{worker_id}")
                < snapshot.index(
                    next(
                        event
                        for event in snapshot
                        if event.startswith(f"acquire:{worker_id}:")
                    )
                )
                < snapshot.index(start)
            )
        assert "start:worker-documents-3" not in snapshot

        release_models.set()
        results = tuple(future.result(timeout=10) for future in futures)

    assert all(
        result["conversion_status"] == "CANONICAL_ACCEPTED" for result in results
    )
    assert sum(event.startswith("start:") for event in events) == 3
    assert repository.held == {}
