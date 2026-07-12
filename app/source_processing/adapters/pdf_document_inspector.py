"""Inspection réelle et bornée de la structure d'un PDF original SP."""

from __future__ import annotations

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.source_processing.adapters.postgres_document_persistence import (
    CorpusOriginalSourceStore,
)
from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
)
from app.source_processing.domain.source_document import OriginalStorageRef


class CorpusPdfDocumentInspector:
    """Lit le PDF immuable du corpus et publie son manifeste observé."""

    def __init__(self, *, original_source_store: CorpusOriginalSourceStore) -> None:
        if not isinstance(original_source_store, CorpusOriginalSourceStore):
            raise ValueError("original_source_store invalide")
        self._original_source_store = original_source_store

    def inspect(self, original_storage_ref: OriginalStorageRef) -> DocumentInspection:
        if not isinstance(original_storage_ref, OriginalStorageRef):
            raise ValueError("original_storage_ref invalide")
        original_path = self._original_source_store.resolve_internal_path(
            original_storage_ref
        )
        try:
            with original_path.open("rb") as stream:
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted:
                    raise ValueError("PDF_ENCRYPTED")
                source_page_count = len(reader.pages)
        except OSError as exc:
            raise ValueError("PDF_UNREADABLE") from exc
        except PdfReadError as exc:
            raise ValueError("PDF_CORRUPTED") from exc
        if source_page_count < 1:
            raise ValueError("PDF_WITHOUT_PAGE")
        return DocumentInspection(
            source_page_count=source_page_count,
            pages=tuple(
                InspectedPage(page_number=page_number, state="PRESENT")
                for page_number in range(1, source_page_count + 1)
            ),
        )


__all__ = ["CorpusPdfDocumentInspector"]
