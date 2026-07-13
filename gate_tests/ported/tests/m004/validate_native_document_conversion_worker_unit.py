"""Worker M-004 : publication native atomique après conversion Docling réelle."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactFileStore,
    NativeDoclingConversionResponse,
    NativeDoclingPage,
    NativeDoclingPageItem,
)
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.native_document_conversion_worker import (
    NativeDocumentConversionWorker,
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


class _SourceRepository:
    def __init__(self, source: SourceDocument) -> None:
        self.source = source

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        return self.source if document_id == self.source.document_id else None


class _RunRepository:
    def __init__(self, run: DocumentProcessingRun) -> None:
        self.run = run

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self.run if document_id == self.run.document_id else None


class _ConversionRepository:
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

    def find_conversion_by_document_id(self, document_id: DocumentId) -> DocumentConversionState | None:
        return self.state if document_id == self.state.document_id else None

    def complete_native_conversion(self, publication) -> None:
        self.publication = publication
        self.state = DocumentConversionState(
            document_id=publication.document_id,
            conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
            canonical_version_id=publication.canonical_version_id,
            rejection_error_code=None,
            execution_phase=DocumentConversionExecutionPhase.SUCCEEDED,
            completed_units=1,
            total_units=1,
            failure_error_code=None,
        )

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        assert document_id == self.state.document_id
        self.state = DocumentConversionState(
            document_id=document_id,
            conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
            canonical_version_id=None,
            rejection_error_code=None,
            execution_phase=DocumentConversionExecutionPhase.RUNNING,
            completed_units=0,
            total_units=1,
            failure_error_code=None,
        )

    def reject_native_conversion(self, *, document_id: DocumentId, error_code: str) -> None:
        self.state = DocumentConversionState(
            document_id=document_id,
            conversion_status=DocumentConversionStatus.QA_REJECTED,
            canonical_version_id=None,
            rejection_error_code=error_code,
            execution_phase=DocumentConversionExecutionPhase.FAILED,
            completed_units=0,
            total_units=1,
            failure_error_code=error_code,
        )


class _OriginalStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def resolve_internal_path(self, storage_ref: OriginalStorageRef) -> Path:
        return self.path


class _RealProtocolConverter:
    """Double du port seulement : l'acceptance exécute le véritable sous-processus Docling."""

    def convert(self, request):
        assert request.expected_page_numbers == (1,)
        return NativeDoclingConversionResponse(
            tool_version="2.111.0",
            pages=(
                NativeDoclingPage(
                    page_number=1,
                    items=(
                        NativeDoclingPageItem(
                            text="Texte converti par Docling.",
                            bbox=(0.1, 0.1, 0.9, 0.2),
                            provenance={"page_number": 1, "source": "docling"},
                        ),
                    ),
                ),
            ),
        )


def _source_and_run() -> tuple[SourceDocument, DocumentProcessingRun]:
    content = b"%PDF-1.7\nconversion native worker\n%%EOF\n"
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
                "title": "Conversion native worker",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )
    manifest = PageManifest.from_entries(
        source_page_count=1,
        entries=(PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),),
    )
    run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T003-WORKER"),
        source_document=source,
        page_manifest=manifest,
    ).record_page_diagnostics(
        (
            PageDecision(
                page_number=PageNumber.from_value(1),
                page_state=PageDecisionState.NATIVE_OK,
                signals=PageDiagnosticSignals(
                    native_text_state="RELIABLE",
                    image_state="NONE",
                    existing_ocr_state="NONE",
                    layout_complexity="SIMPLE",
                    corruption_state="NONE",
                    mixed_content_detected=False,
                    has_table=False,
                    has_formula=False,
                ),
                diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
                justification="Couche texte native fiable.",
            ),
        )
    ).decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.9,
            benchmark_confidence_min=0.85,
        )
    )
    return source, run


def _claimed_job(source: SourceDocument, run: DocumentProcessingRun) -> ClaimedJob:
    request = JobRequest(
        job_name="CONVERT_DOCUMENT",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_DOCUMENT",
            input_hash=source.fingerprint.value,
            configuration_hash="a" * 64,
            code_version="m004-native-worker",
            model_version="docling-2.111.0",
        ),
        payload={
            "document_id": source.document_id.value,
            "processing_run_id": run.processing_run_id.value,
            "source_sha256": source.fingerprint.value,
            "routing_policy_version": run.route_plan.routing_policy_version.value,
            "route_count": 1,
        },
    )
    return ClaimedJob(
        job=JobRecord(1, "JOB-M002-000001", request, JobStatus.RUNNING, None, None),
        trace_id="TRACE-M004-T003-WORKER",
        lease_owner="worker-test",
        lease_expires_at=datetime.now(UTC),
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )


def test_native_worker_persists_hashed_immutable_canonical_acceptance(tmp_path: Path) -> None:
    # Given un job CONVERT_DOCUMENT dont le manifeste M-003 ne contient que NATIVE_STANDARD.
    # When le worker reçoit la sortie Docling contrôlée.
    # Then l'artefact est immuable, haché et la persistance marque CANONICAL_ACCEPTED atomiquement.
    source, run = _source_and_run()
    original_path = tmp_path / "original.pdf"
    original_path.write_bytes(b"%PDF-1.7\noriginal\n%%EOF\n")
    conversions = _ConversionRepository(source)
    worker = NativeDocumentConversionWorker(
        source_document_repository=_SourceRepository(source),
        processing_run_repository=_RunRepository(run),
        conversion_repository=conversions,
        original_source_store=_OriginalStore(original_path),
        native_converter=_RealProtocolConverter(),
        artifact_store=CanonicalArtifactFileStore(root=tmp_path / "canonical"),
    )

    result = worker.execute(_claimed_job(source, run))

    assert result["conversion_status"] == "CANONICAL_ACCEPTED"
    assert conversions.state.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED
    assert conversions.publication is not None
    stored = tmp_path / "canonical" / conversions.publication.canonical_source_id / conversions.publication.canonical_version_id / "docling.json"
    assert stored.is_file()
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == conversions.publication.canonical_artifact_sha256
