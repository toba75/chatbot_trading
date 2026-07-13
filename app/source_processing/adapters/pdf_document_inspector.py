"""Inspection isolée du PDF pour validation d'entrée et manifeste SP."""

from __future__ import annotations

from pathlib import Path

from app.source_processing.adapters.pdf_inspection_process import (
    IsolatedPdfInspector,
    PdfInspectionProcessError,
    PdfInspectionReport,
    build_m13_isolated_pdf_inspector,
)
from app.source_processing.adapters.postgres_document_persistence import CorpusOriginalSourceStore
from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
)
from app.source_processing.domain.source_document import OriginalStorageRef


class CorpusPdfDocumentInspector:
    def __init__(
        self,
        *,
        original_source_store: CorpusOriginalSourceStore,
        inspector: IsolatedPdfInspector,
    ) -> None:
        if not isinstance(original_source_store, CorpusOriginalSourceStore):
            raise ValueError("original_source_store invalide")
        if not isinstance(inspector, IsolatedPdfInspector):
            raise ValueError("inspecteur PDF isolé invalide")
        self._original_source_store = original_source_store
        self._inspector = inspector

    def inspect_content(self, original_content: bytes) -> None:
        try:
            self._inspector.inspect_content(original_content)
        except PdfInspectionProcessError as exc:
            raise ValueError(exc.error_code) from exc

    def inspect_path(self, original_path: Path) -> None:
        try:
            self._inspector.inspect_path(original_path)
        except PdfInspectionProcessError as exc:
            raise ValueError(exc.error_code) from exc

    def inspect(self, original_storage_ref: OriginalStorageRef) -> DocumentInspection:
        if not isinstance(original_storage_ref, OriginalStorageRef):
            raise ValueError("original_storage_ref invalide")
        path = self._original_source_store.resolve_internal_path(original_storage_ref)
        try:
            report = self._inspector.inspect_path(path)
        except PdfInspectionProcessError as exc:
            raise ValueError(exc.error_code) from exc
        return _manifest_from(report)


def build_m13_corpus_pdf_document_inspector(
    *,
    original_source_store: CorpusOriginalSourceStore,
) -> CorpusPdfDocumentInspector:
    """Construit la politique M13 unique sans exposer l'adaptateur de processus."""

    return CorpusPdfDocumentInspector(
        original_source_store=original_source_store,
        inspector=build_m13_isolated_pdf_inspector(),
    )


def _manifest_from(report: PdfInspectionReport) -> DocumentInspection:
    return DocumentInspection(
        source_page_count=len(report.pages),
        pages=tuple(
            InspectedPage(page_number=page.page_number, state=page.manifest_state)
            for page in report.pages
        ),
    )


__all__ = ["CorpusPdfDocumentInspector", "build_m13_corpus_pdf_document_inspector"]
