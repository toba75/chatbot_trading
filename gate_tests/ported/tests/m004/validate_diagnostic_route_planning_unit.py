"""Le diagnostic asynchrone doit achever le plan de route public M-003."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.source_processing.application.document_worker import DocumentDiagnosticWorker
from app.source_processing.application.record_page_diagnostics import PageDiagnosticInput
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    DiagnosticVersion,
    PageDiagnosticPolicy,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageDecisionState,
    PageRouteName,
    PageRoutingConfiguration,
    PageRoutingPolicy,
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


class _SourceRepository:
    def __init__(self, source: SourceDocument) -> None:
        self._source = source

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        return self._source if document_id == self._source.document_id else None


class _RunRepository:
    def __init__(self, run: DocumentProcessingRun) -> None:
        self.run = run
        self.transitions: list[tuple[DocumentProcessingRunStatus, DocumentProcessingRun]] = []

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self.run if document_id == self.run.document_id else None

    def save(self, processing_run: DocumentProcessingRun) -> None:
        self.run = processing_run

    def save_transition(
        self,
        processing_run: DocumentProcessingRun,
        *,
        expected_status: DocumentProcessingRunStatus,
    ) -> None:
        self.transitions.append((expected_status, processing_run))
        self.run = processing_run


class _ScanInspector:
    def inspect(self, original_storage_ref: str) -> tuple[PageDiagnosticInput, ...]:
        assert original_storage_ref.startswith("artifact:source_processing.original_sources/")
        return (
            PageDiagnosticInput(
                page_number=1,
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
                diagnostic_version="diag-v1",
                justification="Scan propre attesté par l'inspecteur isolé.",
            ),
        )


def _source_and_run() -> tuple[SourceDocument, DocumentProcessingRun]:
    content = b"%PDF-1.7\ndiagnostic route plan\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Diagnostic et routage public",
                "authors": ["Codex"],
                "publication_year": 2026,
                "edition": "preuve",
            }
        ),
    )
    run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T005-ROUTE"),
        source_document=source,
        page_manifest=PageManifest.from_entries(
            source_page_count=1,
            entries=(
                PageManifestEntry(
                    page_number=PageNumber.from_value(1),
                    state=PageManifestEntryState.PRESENT,
                ),
            ),
        ),
    )
    return source, run


def _claimed_diagnosis_job(source: SourceDocument, run: DocumentProcessingRun) -> ClaimedJob:
    request = JobRequest(
        job_name="DIAGNOSE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="DIAGNOSE",
            input_hash=source.fingerprint.value,
            configuration_hash="a" * 64,
            code_version="m004-t005-route-chain",
            model_version="pypdf-isolated-v3",
        ),
        payload={
            "document_id": source.document_id.value,
            "processing_run_id": run.processing_run_id.value,
            "original_storage_ref": source.original_storage_ref.value,
            "source_sha256": source.fingerprint.value,
        },
    )
    return ClaimedJob(
        job=JobRecord(1, "JOB-M002-000005", request, JobStatus.RUNNING, None, None),
        trace_id="TRACE-M004-T005-ROUTE",
        lease_owner="worker-test",
        lease_expires_at=datetime.now(UTC),
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )


def test_diagnostic_worker_publishes_route_plan_after_inspection() -> None:
    # Given une action UI Diagnostiquer qui aboutit à une page SCAN_CLEAN réelle.
    # When le worker termine le diagnostic asynchrone.
    # Then le même job persiste le RoutePlan M-003, afin que l'action UI Convertir
    #      soit disponible publiquement sans transition cachée ni appel de stockage par l'UI.
    source, run = _source_and_run()
    repository = _RunRepository(run)
    worker = DocumentDiagnosticWorker(
        source_document_repository=_SourceRepository(source),
        processing_run_repository=repository,
        diagnostic_inspector=_ScanInspector(),
        routing_configuration=PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        ),
    )

    result = worker.execute(_claimed_diagnosis_job(source, run))

    assert result["diagnostic_status"] == "ROUTE_PLANNED"
    assert repository.run.status is DocumentProcessingRunStatus.ROUTE_PLANNED
    assert repository.run.route_plan is not None
    assert repository.run.route_plan.page_routes[0].route_name is PageRouteName.SCAN_GRANITE
    assert repository.transitions == [(DocumentProcessingRunStatus.DIAGNOSED, repository.run)]


def test_ocr_priority_keeps_degraded_scans_and_bad_ocr_routes_reachable() -> None:
    # Given des signaux réels se recouvrent : une couche OCR mauvaise sur un scan
    # physiquement dégradé est aussi techniquement une page mixte.
    # When PageDiagnosticPolicy les classe.
    # Then PREPROCESS_GRANITE garde la priorité sur ce mélange dégradé, tandis
    #      BAD_OCR_TO_GRANITE et MIXED_PAGEWISE restent atteignables dans leurs cas propres.
    configuration = PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=0.90,
        benchmark_confidence_min=0.85,
    )
    diagnostic_policy = PageDiagnosticPolicy()
    routing_policy = PageRoutingPolicy()

    degraded = diagnostic_policy.classify(
        page_number=PageNumber.from_value(1),
        signals=PageDiagnosticSignals(
            native_text_state="SUSPECT",
            image_state="SCAN_DEGRADED",
            existing_ocr_state="BAD",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=True,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-adr033-v1"),
        justification="Scan réel avec OCR dégradé et image présente.",
    )
    assert degraded.page_state is PageDecisionState.SCAN_DEGRADED
    assert (
        routing_policy.decide_page_route(degraded, configuration).route_name
        is PageRouteName.PREPROCESS_GRANITE
    )

    bad_ocr = diagnostic_policy.classify(
        page_number=PageNumber.from_value(2),
        signals=PageDiagnosticSignals(
            native_text_state="SUSPECT",
            image_state="SCAN_CLEAN",
            existing_ocr_state="BAD",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-adr033-v1"),
        justification="OCR mauvais sans dégradation physique du scan.",
    )
    assert bad_ocr.page_state is PageDecisionState.OCR_BAD
    assert (
        routing_policy.decide_page_route(bad_ocr, configuration).route_name
        is PageRouteName.BAD_OCR_TO_GRANITE
    )

    legitimate_mixed = diagnostic_policy.classify(
        page_number=PageNumber.from_value(3),
        signals=PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="SCAN_CLEAN",
            existing_ocr_state="VALID",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=True,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-adr033-v1"),
        justification="Texte et image sains sur une page mixte légitime.",
    )
    assert legitimate_mixed.page_state is PageDecisionState.MIXED_CONTENT
    assert (
        routing_policy.decide_page_route(legitimate_mixed, configuration).route_name
        is PageRouteName.MIXED_PAGEWISE
    )
