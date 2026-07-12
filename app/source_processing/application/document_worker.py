"""Exécution réelle et idempotente des diagnostics documentaires SP."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.platform.job_runtime import JobStatus
from app.platform.job_runtime.postgres import ClaimedJob
from app.source_processing.adapters.postgres_document_persistence import (
    CorpusOriginalSourceStore,
    PostgresProcessingRunRepository,
)
from app.source_processing.application.record_page_diagnostics import (
    PageDiagnosticInput,
    RecordPageDiagnosticsCommand,
    RecordPageDiagnosticsHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRunStatus,
    PageDiagnosticSignals,
)
from app.source_processing.domain.source_document import DocumentId


class DocumentDiagnosticWorker:
    """Consomme un job DIAGNOSE et persiste les sorties page par page dans SP."""

    def __init__(
        self,
        *,
        source_document_repository: Any,
        processing_run_repository: PostgresProcessingRunRepository,
        original_source_store: CorpusOriginalSourceStore,
    ) -> None:
        if not callable(getattr(source_document_repository, "find_by_document_id", None)):
            raise ValueError("source_document_repository invalide")
        if not callable(getattr(processing_run_repository, "find_by_document_id", None)):
            raise ValueError("processing_run_repository invalide")
        if not callable(getattr(processing_run_repository, "save", None)):
            raise ValueError("processing_run_repository sans sauvegarde")
        if not isinstance(original_source_store, CorpusOriginalSourceStore):
            raise ValueError("original_source_store invalide")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._original_source_store = original_source_store
        self._diagnostics_handler = RecordPageDiagnosticsHandler(
            processing_run_repository=processing_run_repository
        )

    def execute(self, claimed_job: ClaimedJob) -> Mapping[str, Any]:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        job = claimed_job.job
        if job.status is not JobStatus.RUNNING or job.request.job_name != "DIAGNOSE":
            raise ValueError("job DIAGNOSE running requis")
        payload = dict(job.request.payload)
        document_id = DocumentId.from_value(_required_text(payload, "document_id"))
        processing_run_id = _required_text(payload, "processing_run_id")
        original_storage_ref = _required_text(payload, "original_storage_ref")
        source_sha256 = _required_text(payload, "source_sha256")

        source = self._source_document_repository.find_by_document_id(document_id)
        if source is None:
            raise RuntimeError("SOURCE_NOT_FOUND")
        if source.fingerprint.value != source_sha256:
            raise RuntimeError("SOURCE_FINGERPRINT_MISMATCH")
        if source.original_storage_ref.value != original_storage_ref:
            raise RuntimeError("ORIGINAL_STORAGE_REF_MISMATCH")
        processing_run = self._processing_run_repository.find_by_document_id(document_id)
        if processing_run is None:
            raise RuntimeError("PROCESSING_RUN_NOT_FOUND")
        if processing_run.processing_run_id.value != processing_run_id:
            raise RuntimeError("PROCESSING_RUN_ID_MISMATCH")

        if processing_run.status is DocumentProcessingRunStatus.DIAGNOSED:
            return _diagnosis_result(processing_run)
        if processing_run.status is not DocumentProcessingRunStatus.MANIFEST_CREATED:
            raise RuntimeError(f"PROCESSING_RUN_STATUS_INVALID:{processing_run.status.value}")

        diagnostics = self._inspect_pages(source.original_storage_ref.value)
        diagnosed = self._diagnostics_handler.handle(
            RecordPageDiagnosticsCommand(
                processing_run=processing_run,
                diagnostics=diagnostics,
            )
        )
        return _diagnosis_result(diagnosed)

    def _inspect_pages(self, original_storage_ref: str) -> tuple[PageDiagnosticInput, ...]:
        storage_ref = self._original_source_store.storage_ref(original_storage_ref)
        path = self._original_source_store.resolve_internal_path(storage_ref)
        try:
            with path.open("rb") as stream:
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted:
                    raise RuntimeError("PDF_ENCRYPTED")
                return tuple(
                    _diagnostic_for_page(page_number, page)
                    for page_number, page in enumerate(reader.pages, start=1)
                )
        except OSError as exc:
            raise RuntimeError("PDF_UNREADABLE") from exc
        except PdfReadError as exc:
            raise RuntimeError("PDF_CORRUPTED") from exc


def _diagnostic_for_page(page_number: int, page: Any) -> PageDiagnosticInput:
    try:
        extracted_text = page.extract_text() or ""
        has_image = len(page.images) > 0
    except Exception as exc:
        raise RuntimeError(f"PDF_PAGE_INSPECTION_FAILED:{page_number}") from exc
    has_native_text = extracted_text.strip() != ""
    native_text_state = "RELIABLE" if len(extracted_text.strip()) >= 20 else "SUSPECT"
    image_state = "SCAN_CLEAN" if has_image else "NONE"
    justification = (
        "Inspection pypdf: couche texte native et image présentes."
        if has_native_text and has_image
        else "Inspection pypdf: couche texte native présente."
        if has_native_text
        else "Inspection pypdf: couche texte absente ou trop courte."
    )
    return PageDiagnosticInput(
        page_number=page_number,
        signals=PageDiagnosticSignals(
            native_text_state=native_text_state,
            image_state=image_state,
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=has_native_text and has_image,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version="pypdf-live-v1",
        justification=justification,
    )


def _diagnosis_result(processing_run: Any) -> Mapping[str, Any]:
    return {
        "document_id": processing_run.document_id.value,
        "processing_run_id": processing_run.processing_run_id.value,
        "diagnosed_page_count": len(processing_run.page_decisions),
        "diagnostic_status": processing_run.status.value,
        "aggregate_version": processing_run.aggregate_version,
    }


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise RuntimeError(f"JOB_PAYLOAD_INVALID:{field_name}")
    return value


__all__ = ["DocumentDiagnosticWorker"]
