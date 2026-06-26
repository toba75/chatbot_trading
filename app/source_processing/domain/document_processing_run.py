"""Tentative de traitement documentaire et manifeste de pages SP."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.source_processing.domain.source_document import DocumentId, SourceDocument


_PROCESSING_RUN_ID_PATTERN = re.compile(r"^RUN-[A-Z0-9][A-Z0-9-]*$")


class DocumentProcessingRunStatus(str, Enum):
    """État métier explicite d'une tentative de traitement documentaire."""

    CREATED = "CREATED"
    DIAGNOSED = "DIAGNOSED"


class PageManifestEntryState(str, Enum):
    """État minimal d'une page dans le manifeste avant diagnostic."""

    PRESENT = "PRESENT"
    EMPTY = "EMPTY"
    UNREADABLE = "UNREADABLE"
    REJECTED = "REJECTED"

    @classmethod
    def from_value(cls, value: "PageManifestEntryState | str") -> "PageManifestEntryState":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("état de page manifeste inconnu")
        for state in cls:
            if state.value == value:
                return state
        raise ValueError("état de page manifeste inconnu")


@dataclass(frozen=True)
class ProcessingRunId:
    """Identifiant interne d'une tentative de traitement SP."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "ProcessingRunId":
        return cls(value=_ensure_processing_run_id_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_processing_run_id_value(self.value))


@dataclass(frozen=True)
class PageNumber:
    """Numéro de page PDF strictement positif."""

    value: int

    @classmethod
    def from_value(cls, value: int) -> "PageNumber":
        return cls(value=_ensure_page_number_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_page_number_value(self.value))


@dataclass(frozen=True)
class PageManifestEntry:
    """Entrée explicite d'une page dans le manifeste."""

    page_number: PageNumber
    state: PageManifestEntryState

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "state", PageManifestEntryState.from_value(self.state))


@dataclass(frozen=True)
class PageManifest:
    """Inventaire complet et ordonné des pages attendues."""

    source_page_count: int
    entries: tuple[PageManifestEntry, ...]

    @classmethod
    def from_entries(
        cls,
        source_page_count: int,
        entries: Sequence[PageManifestEntry],
    ) -> "PageManifest":
        return cls(source_page_count=source_page_count, entries=tuple(entries))

    def __post_init__(self) -> None:
        source_page_count = _ensure_source_page_count(self.source_page_count)
        entries = _ensure_manifest_entries(self.entries)
        _ensure_manifest_completeness(
            source_page_count=source_page_count,
            entries=entries,
        )
        object.__setattr__(self, "source_page_count", source_page_count)
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class DocumentProcessingStarted:
    """Événement produit lors du démarrage d'une tentative de traitement."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    source_page_count: int

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "source_page_count",
            _ensure_source_page_count(self.source_page_count),
        )


@dataclass(frozen=True)
class DocumentProcessingRun:
    """Agrégat SP qui porte une tentative de traitement d'un SourceDocument."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_manifest: PageManifest
    status: DocumentProcessingRunStatus
    events: tuple[DocumentProcessingStarted, ...]

    @classmethod
    def start(
        cls,
        processing_run_id: ProcessingRunId,
        source_document: SourceDocument,
        page_manifest: PageManifest,
    ) -> "DocumentProcessingRun":
        parsed_processing_run_id = _ensure_processing_run_id(processing_run_id)
        parsed_source_document = _ensure_source_document(source_document)
        parsed_manifest = _ensure_page_manifest(page_manifest)
        started_event = DocumentProcessingStarted(
            processing_run_id=parsed_processing_run_id,
            document_id=parsed_source_document.document_id,
            source_page_count=parsed_manifest.source_page_count,
        )
        return cls(
            processing_run_id=parsed_processing_run_id,
            document_id=parsed_source_document.document_id,
            page_manifest=parsed_manifest,
            status=DocumentProcessingRunStatus.CREATED,
            events=(started_event,),
        )

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_manifest(self.page_manifest)
        if not isinstance(self.status, DocumentProcessingRunStatus):
            raise ValueError("document_processing_run_status invalide")
        if not isinstance(self.events, tuple):
            raise ValueError("events DocumentProcessingRun non tuple")
        if len(self.events) == 0:
            raise ValueError("events DocumentProcessingRun vide")
        for event in self.events:
            if not isinstance(event, DocumentProcessingStarted):
                raise ValueError("event DocumentProcessingRun invalide")


def _ensure_processing_run_id_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("processing_run_id invalide")
    if value.strip() == "":
        raise ValueError("processing_run_id invalide")
    if value != value.strip():
        raise ValueError("processing_run_id invalide")
    if _PROCESSING_RUN_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("processing_run_id invalide")
    return value


def _ensure_page_number_value(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("page_number invalide")
    return value


def _ensure_source_page_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("nombre de pages source invalide")
    return value


def _ensure_manifest_entries(
    value: Sequence[PageManifestEntry],
) -> tuple[PageManifestEntry, ...]:
    if value is None:
        raise ValueError("entrées de manifeste absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("entrées de manifeste invalides")
    entries = tuple(value)
    if len(entries) == 0:
        raise ValueError("entrées de manifeste vides")
    for entry in entries:
        if not isinstance(entry, PageManifestEntry):
            raise ValueError("entrée de manifeste invalide")
    return entries


def _ensure_manifest_completeness(
    source_page_count: int,
    entries: tuple[PageManifestEntry, ...],
) -> None:
    for entry in entries:
        if entry.page_number.value > source_page_count:
            raise ValueError("page_number hors plage")

    for index, entry in enumerate(entries, start=1):
        if entry.page_number.value != index:
            raise ValueError("ordre strict du manifeste invalide")

    if len(entries) != source_page_count:
        raise ValueError("nombre de pages du manifeste discordant")


def _ensure_processing_run_id(value: ProcessingRunId) -> ProcessingRunId:
    if not isinstance(value, ProcessingRunId):
        raise ValueError("processing_run_id invalide")
    return value


def _ensure_page_number(value: PageNumber) -> PageNumber:
    if not isinstance(value, PageNumber):
        raise ValueError("page_number invalide")
    return value


def _ensure_document_id(value: DocumentId) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_page_manifest(value: PageManifest) -> PageManifest:
    if not isinstance(value, PageManifest):
        raise ValueError("page_manifest invalide")
    return value


def _ensure_source_document(value: SourceDocument) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


__all__ = [
    "DocumentProcessingRun",
    "DocumentProcessingRunStatus",
    "DocumentProcessingStarted",
    "PageManifest",
    "PageManifestEntry",
    "PageManifestEntryState",
    "PageNumber",
    "ProcessingRunId",
]
