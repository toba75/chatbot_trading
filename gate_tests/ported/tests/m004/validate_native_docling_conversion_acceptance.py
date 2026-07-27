"""Parcours d'acceptation d'un PDF natif réellement converti par Docling."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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
    IsolatedNativeDoclingConverter,
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
        self._source = source

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        return self._source if document_id == self._source.document_id else None


class _RunRepository:
    def __init__(self, run: DocumentProcessingRun) -> None:
        self._run = run

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self._run if document_id == self._run.document_id else None


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
        self._path = path

    def resolve_internal_path(self, storage_ref: OriginalStorageRef) -> Path:
        return self._path


def _write_native_pdf(path: Path) -> None:
    """Produit un vrai PDF avec couche texte native, sans fixture Docling."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 16 Tf 72 720 Td (Conversion native Docling reelle) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(contents)
    with path.open("wb") as stream:
        writer.write(stream)


def _source_and_run(source_path: Path) -> tuple[SourceDocument, DocumentProcessingRun]:
    fingerprint = SourceFingerprint.from_content(source_path.read_bytes())
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Conversion native Docling réelle",
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
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T003-ACCEPTANCE"),
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
        environment="development",
        deployment_id="ostrading-development-local",
        job_name="CONVERT_DOCUMENT",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_DOCUMENT",
            input_hash=source.fingerprint.value,
            configuration_hash="a" * 64,
            code_version="m004-native-acceptance",
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
        trace_id="TRACE-M004-T003-ACCEPTANCE",
        lease_owner="worker-acceptance",
        lease_expires_at=datetime.now(UTC),
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )


def test_native_pdf_is_converted_and_published_by_the_real_uv_isolated_worker(tmp_path: Path) -> None:
    # Given un PDF natif réel et les actifs Docling préchargés, hachés et scellés.
    # When le worker CONVERT_DOCUMENT appelle le runner isolé du même environnement uv.
    # Then son artefact immuable est haché et l'état durable devient CANONICAL_ACCEPTED.
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    manifest_path = repository_root / "config" / "docling-assets.native.json"
    assets_root = repository_root / "data" / "docling_assets" / "native"
    assert manifest_path.is_file(), "CONVERSION_ASSET_MANIFEST_INVALID: manifeste Docling natif absent."
    assert assets_root.is_dir(), "CONVERSION_ASSET_MANIFEST_INVALID: actifs Docling natifs absents."

    source_path = tmp_path / "native.pdf"
    _write_native_pdf(source_path)
    source, run = _source_and_run(source_path)
    conversion_repository = _ConversionRepository(source)
    worker = NativeDocumentConversionWorker(
        source_document_repository=_SourceRepository(source),
        processing_run_repository=_RunRepository(run),
        conversion_repository=conversion_repository,
        original_source_store=_OriginalStore(source_path),
        native_converter=IsolatedNativeDoclingConverter(
            asset_manifest_path=manifest_path,
            assets_root=assets_root,
            timeout_seconds=120.0,
        ),
        artifact_store=CanonicalArtifactFileStore(root=tmp_path / "canonical"),
    )

    result = worker.execute(_claimed_job(source, run))

    assert result["conversion_status"] == "CANONICAL_ACCEPTED"
    assert conversion_repository.state.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED
    assert conversion_repository.publication is not None
    artifact_path = (
        tmp_path
        / "canonical"
        / conversion_repository.publication.canonical_source_id
        / conversion_repository.publication.canonical_version_id
        / "docling.json"
    )
    assert artifact_path.is_file()
    assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == result["canonical_artifact_sha256"]
