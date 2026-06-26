"""Cas d'usage de démarrage d'une tentative de traitement documentaire."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import OriginalStorageRef, SourceDocument


class DocumentInspector(Protocol):
    """Port d'inspection technique du PDF original."""

    def inspect(self, original_storage_ref: OriginalStorageRef) -> "DocumentInspection":
        """Retourne le nombre de pages source et les pages observées."""


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save(self, processing_run: DocumentProcessingRun) -> None:
        """Persiste une nouvelle tentative sans réécrire l'historique."""


@dataclass(frozen=True)
class InspectedPage:
    """Page observée par le port d'inspection avant diagnostic métier."""

    page_number: int
    state: str

    def __post_init__(self) -> None:
        PageNumber.from_value(self.page_number)
        PageManifestEntryState.from_value(self.state)


@dataclass(frozen=True)
class DocumentInspection:
    """Résultat explicite d'une inspection du PDF original."""

    source_page_count: int | None
    pages: tuple[InspectedPage, ...]

    def __post_init__(self) -> None:
        if self.source_page_count is not None:
            _ensure_source_page_count(self.source_page_count)
        object.__setattr__(self, "pages", _ensure_inspected_pages(self.pages))


@dataclass(frozen=True)
class StartDocumentProcessingCommand:
    """Commande applicative de démarrage d'une tentative de traitement."""

    processing_run_id: ProcessingRunId
    source_document: SourceDocument

    def __post_init__(self) -> None:
        if not isinstance(self.processing_run_id, ProcessingRunId):
            raise ValueError("processing_run_id invalide")
        if not isinstance(self.source_document, SourceDocument):
            raise ValueError("source_document invalide")


class StartDocumentProcessingHandler:
    """Handler applicatif de la commande StartDocumentProcessing."""

    def __init__(
        self,
        document_inspector: DocumentInspector,
        processing_run_repository: ProcessingRunRepository,
    ) -> None:
        if not callable(getattr(document_inspector, "inspect", None)):
            raise ValueError("document_inspector invalide")
        if not callable(getattr(processing_run_repository, "save", None)):
            raise ValueError("processing_run_repository invalide")
        self._document_inspector = document_inspector
        self._processing_run_repository = processing_run_repository

    def handle(self, command: StartDocumentProcessingCommand) -> DocumentProcessingRun:
        if not isinstance(command, StartDocumentProcessingCommand):
            raise ValueError("commande StartDocumentProcessing invalide")

        inspection = self._document_inspector.inspect(
            command.source_document.original_storage_ref
        )
        if not isinstance(inspection, DocumentInspection):
            raise ValueError("inspection documentaire invalide")
        if inspection.source_page_count is None:
            raise ValueError("nombre de pages source inconnu")

        page_manifest = PageManifest.from_entries(
            source_page_count=inspection.source_page_count,
            entries=tuple(_manifest_entry_from_inspected_page(page) for page in inspection.pages),
        )
        processing_run = DocumentProcessingRun.start(
            processing_run_id=command.processing_run_id,
            source_document=command.source_document,
            page_manifest=page_manifest,
        )
        self._processing_run_repository.save(processing_run)
        return processing_run


def _manifest_entry_from_inspected_page(page: InspectedPage) -> PageManifestEntry:
    if not isinstance(page, InspectedPage):
        raise ValueError("page inspectée invalide")
    return PageManifestEntry(
        page_number=PageNumber.from_value(page.page_number),
        state=PageManifestEntryState.from_value(page.state),
    )


def _ensure_source_page_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("nombre de pages source invalide")
    return value


def _ensure_inspected_pages(value: Sequence[InspectedPage]) -> tuple[InspectedPage, ...]:
    if value is None:
        raise ValueError("pages inspectées absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("pages inspectées invalides")
    pages = tuple(value)
    for page in pages:
        if not isinstance(page, InspectedPage):
            raise ValueError("page inspectée invalide")
    return pages


__all__ = [
    "DocumentInspection",
    "DocumentInspector",
    "InspectedPage",
    "ProcessingRunRepository",
    "StartDocumentProcessingCommand",
    "StartDocumentProcessingHandler",
]
