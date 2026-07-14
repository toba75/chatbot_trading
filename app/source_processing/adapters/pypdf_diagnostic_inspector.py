"""Adaptateur de diagnostic fondé sur l'inspection pypdf isolée."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_processing.adapters.pdf_inspection_process import (
    IsolatedPdfInspector,
    PdfInspectionBudget,
    PdfInspectionProcessError,
)
from app.source_processing.application.document_worker import WorkerProcessingError
from app.source_processing.application.record_page_diagnostics import PageDiagnosticInput
from app.source_processing.domain.document_processing_run import PageDiagnosticSignals


class PdfInspectionError(WorkerProcessingError):
    def __init__(self, error_code: str, *, retryable: bool = False) -> None:
        super().__init__(error_code, retryable=retryable)


class PdfDiagnosticInspector:
    """Traduit le rapport isolé en signaux diagnostiques SP."""

    def __init__(self, *, original_source_store: Any, inspector: IsolatedPdfInspector) -> None:
        if not callable(getattr(original_source_store, "storage_ref", None)):
            raise ValueError("original_source_store sans storage_ref")
        if not callable(getattr(original_source_store, "resolve_internal_path", None)):
            raise ValueError("original_source_store sans résolution")
        if not isinstance(inspector, IsolatedPdfInspector):
            raise ValueError("inspecteur PDF isolé invalide")
        self._original_source_store = original_source_store
        self._inspector = inspector

    def inspect(self, original_storage_ref: str) -> tuple[PageDiagnosticInput, ...]:
        storage_ref = self._original_source_store.storage_ref(original_storage_ref)
        path = self._original_source_store.resolve_internal_path(storage_ref)
        if not isinstance(path, Path):
            raise PdfInspectionError("PDF_STORAGE_PATH_INVALID")
        try:
            report = self._inspector.inspect_path(path)
        except PdfInspectionProcessError as exc:
            raise PdfInspectionError(exc.error_code) from exc
        return tuple(
            PageDiagnosticInput(
                page_number=page.page_number,
                signals=PageDiagnosticSignals(
                    native_text_state=page.native_text_state,
                    image_state=page.image_state,
                    existing_ocr_state=page.existing_ocr_state,
                    layout_complexity=page.layout_complexity,
                    corruption_state=page.corruption_state,
                    mixed_content_detected=page.mixed_content_detected,
                    has_table=page.has_table,
                    has_formula=page.has_formula,
                ),
                diagnostic_version="pypdf-isolated-v4",
                justification=(
                    "Inspection pypdf isolée et bornée: "
                    f"texte={page.text_characters}; images={page.image_count}; "
                    f"ocr={page.existing_ocr_state}; tableau={str(page.has_table).lower()}; "
                    f"formule={str(page.has_formula).lower()}."
                ),
            )
            for page in report.pages
        )


__all__ = ["PdfDiagnosticInspector", "PdfInspectionBudget", "PdfInspectionError"]
