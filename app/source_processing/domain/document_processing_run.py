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


class PageDecisionState(str, Enum):
    """État diagnostique métier publié pour une page source."""

    NATIVE_OK = "NATIVE_OK"
    NATIVE_SUSPECT = "NATIVE_SUSPECT"
    SCAN_CLEAN = "SCAN_CLEAN"
    SCAN_DEGRADED = "SCAN_DEGRADED"
    OCR_BAD = "OCR_BAD"
    MIXED_CONTENT = "MIXED_CONTENT"
    COMPLEX_VISUAL = "COMPLEX_VISUAL"
    UNSUPPORTED_OR_CORRUPT = "UNSUPPORTED_OR_CORRUPT"

    @classmethod
    def from_value(cls, value: "PageDecisionState | str") -> "PageDecisionState":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("état de diagnostic inconnu")
        for state in cls:
            if state.value == value:
                return state
        raise ValueError("état de diagnostic inconnu")


class NativeTextSignal(str, Enum):
    """Signal technique inspecté pour la couche texte native."""

    RELIABLE = "RELIABLE"
    SUSPECT = "SUSPECT"
    ABSENT = "ABSENT"

    @classmethod
    def from_value(cls, value: "NativeTextSignal | str") -> "NativeTextSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal texte natif inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal texte natif inconnu")


class PageImageSignal(str, Enum):
    """Signal technique inspecté pour la présence d'image scannée."""

    NONE = "NONE"
    SCAN_CLEAN = "SCAN_CLEAN"
    SCAN_DEGRADED = "SCAN_DEGRADED"

    @classmethod
    def from_value(cls, value: "PageImageSignal | str") -> "PageImageSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal image inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal image inconnu")


class ExistingOcrSignal(str, Enum):
    """Signal technique inspecté pour une couche OCR déjà présente."""

    NONE = "NONE"
    VALID = "VALID"
    BAD = "BAD"

    @classmethod
    def from_value(cls, value: "ExistingOcrSignal | str") -> "ExistingOcrSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal OCR existant inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal OCR existant inconnu")


class LayoutComplexitySignal(str, Enum):
    """Signal technique inspecté pour la complexité visuelle."""

    SIMPLE = "SIMPLE"
    COMPLEX = "COMPLEX"

    @classmethod
    def from_value(cls, value: "LayoutComplexitySignal | str") -> "LayoutComplexitySignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal complexité visuelle inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal complexité visuelle inconnu")


class PageCorruptionSignal(str, Enum):
    """Signal technique inspecté pour une page corrompue."""

    NONE = "NONE"
    CORRUPT = "CORRUPT"

    @classmethod
    def from_value(cls, value: "PageCorruptionSignal | str") -> "PageCorruptionSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal corruption inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal corruption inconnu")


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
class DiagnosticVersion:
    """Version explicite de la politique de diagnostic appliquée."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "DiagnosticVersion":
        return cls(value=_ensure_diagnostic_version_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _ensure_diagnostic_version_value(self.value),
        )


@dataclass(frozen=True)
class PageDiagnosticSignals:
    """Signaux techniques conservés pour justifier une décision de page."""

    native_text_state: NativeTextSignal
    image_state: PageImageSignal
    existing_ocr_state: ExistingOcrSignal
    layout_complexity: LayoutComplexitySignal
    corruption_state: PageCorruptionSignal
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "native_text_state",
            NativeTextSignal.from_value(self.native_text_state),
        )
        object.__setattr__(
            self,
            "image_state",
            PageImageSignal.from_value(self.image_state),
        )
        object.__setattr__(
            self,
            "existing_ocr_state",
            ExistingOcrSignal.from_value(self.existing_ocr_state),
        )
        object.__setattr__(
            self,
            "layout_complexity",
            LayoutComplexitySignal.from_value(self.layout_complexity),
        )
        object.__setattr__(
            self,
            "corruption_state",
            PageCorruptionSignal.from_value(self.corruption_state),
        )
        _ensure_bool(self.mixed_content_detected, "mixed_content_detected")
        _ensure_bool(self.has_table, "has_table")
        _ensure_bool(self.has_formula, "has_formula")


@dataclass(frozen=True)
class PageDecision:
    """Décision diagnostique explicite pour une page source."""

    page_number: PageNumber
    page_state: PageDecisionState
    signals: PageDiagnosticSignals
    diagnostic_version: DiagnosticVersion
    justification: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "page_state",
            PageDecisionState.from_value(self.page_state),
        )
        _ensure_page_diagnostic_signals(self.signals)
        _ensure_diagnostic_version(self.diagnostic_version)
        object.__setattr__(
            self,
            "justification",
            _ensure_diagnostic_justification(self.justification),
        )


class PageDiagnosticPolicy:
    """Politique de classification des signaux en états diagnostiques publiés."""

    def classify(
        self,
        page_number: PageNumber,
        signals: PageDiagnosticSignals,
        diagnostic_version: DiagnosticVersion,
        justification: str,
    ) -> PageDecision:
        parsed_page_number = _ensure_page_number(page_number)
        parsed_signals = _ensure_page_diagnostic_signals(signals)
        parsed_diagnostic_version = _ensure_diagnostic_version(diagnostic_version)
        parsed_justification = _ensure_diagnostic_justification(justification)

        if parsed_signals.corruption_state is PageCorruptionSignal.CORRUPT:
            page_state = PageDecisionState.UNSUPPORTED_OR_CORRUPT
        elif parsed_signals.mixed_content_detected:
            page_state = PageDecisionState.MIXED_CONTENT
        elif parsed_signals.layout_complexity is LayoutComplexitySignal.COMPLEX:
            page_state = PageDecisionState.COMPLEX_VISUAL
        elif parsed_signals.existing_ocr_state is ExistingOcrSignal.BAD:
            page_state = PageDecisionState.OCR_BAD
        elif parsed_signals.image_state is PageImageSignal.SCAN_DEGRADED:
            page_state = PageDecisionState.SCAN_DEGRADED
        elif parsed_signals.image_state is PageImageSignal.SCAN_CLEAN:
            page_state = PageDecisionState.SCAN_CLEAN
        elif parsed_signals.native_text_state is NativeTextSignal.SUSPECT:
            page_state = PageDecisionState.NATIVE_SUSPECT
        elif parsed_signals.native_text_state is NativeTextSignal.RELIABLE:
            page_state = PageDecisionState.NATIVE_OK
        else:
            raise ValueError("signaux diagnostiques insuffisants")

        return PageDecision(
            page_number=parsed_page_number,
            page_state=page_state,
            signals=parsed_signals,
            diagnostic_version=parsed_diagnostic_version,
            justification=parsed_justification,
        )


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
class PageDiagnosticRecorded:
    """Événement produit pour chaque diagnostic de page enregistré."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    page_state: PageDecisionState
    diagnostic_version: DiagnosticVersion

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "page_state",
            PageDecisionState.from_value(self.page_state),
        )
        _ensure_diagnostic_version(self.diagnostic_version)


@dataclass(frozen=True)
class DocumentProcessingRun:
    """Agrégat SP qui porte une tentative de traitement d'un SourceDocument."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_manifest: PageManifest
    page_decisions: tuple[PageDecision, ...]
    status: DocumentProcessingRunStatus
    events: tuple[DocumentProcessingStarted | PageDiagnosticRecorded, ...]

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
            page_decisions=(),
            status=DocumentProcessingRunStatus.CREATED,
            events=(started_event,),
        )

    def record_page_diagnostics(
        self,
        page_decisions: Sequence[PageDecision],
    ) -> "DocumentProcessingRun":
        if self.status is not DocumentProcessingRunStatus.CREATED:
            raise ValueError("transition de diagnostic interdite")

        parsed_page_decisions = _ensure_page_decisions(page_decisions)
        _ensure_page_diagnostic_completeness(
            page_manifest=self.page_manifest,
            page_decisions=parsed_page_decisions,
        )
        diagnostic_events = tuple(
            PageDiagnosticRecorded(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_number=page_decision.page_number,
                page_state=page_decision.page_state,
                diagnostic_version=page_decision.diagnostic_version,
            )
            for page_decision in parsed_page_decisions
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=parsed_page_decisions,
            status=DocumentProcessingRunStatus.DIAGNOSED,
            events=self.events + diagnostic_events,
        )

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_manifest(self.page_manifest)
        page_decisions = _ensure_page_decisions(self.page_decisions, allow_empty=True)
        if not isinstance(self.status, DocumentProcessingRunStatus):
            raise ValueError("document_processing_run_status invalide")
        if not isinstance(self.events, tuple):
            raise ValueError("events DocumentProcessingRun non tuple")
        if len(self.events) == 0:
            raise ValueError("events DocumentProcessingRun vide")
        for event in self.events:
            if not isinstance(event, DocumentProcessingStarted | PageDiagnosticRecorded):
                raise ValueError("event DocumentProcessingRun invalide")
        if self.status is DocumentProcessingRunStatus.CREATED and len(page_decisions) != 0:
            raise ValueError("diagnostics interdits sur tentative créée")
        if self.status is DocumentProcessingRunStatus.DIAGNOSED:
            _ensure_page_diagnostic_completeness(
                page_manifest=self.page_manifest,
                page_decisions=page_decisions,
            )
        object.__setattr__(self, "page_decisions", page_decisions)


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


def _ensure_diagnostic_version_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("version de diagnostic invalide")
    if value.strip() == "":
        raise ValueError("version de diagnostic invalide")
    if value != value.strip():
        raise ValueError("version de diagnostic invalide")
    return value


def _ensure_diagnostic_justification(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("justification de diagnostic invalide")
    if value.strip() == "":
        raise ValueError("justification de diagnostic invalide")
    if value != value.strip():
        raise ValueError("justification de diagnostic invalide")
    return value


def _ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} invalide")
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


def _ensure_page_decisions(
    value: Sequence[PageDecision],
    *,
    allow_empty: bool = False,
) -> tuple[PageDecision, ...]:
    if value is None:
        raise ValueError("diagnostics de pages absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("diagnostics de pages invalides")
    page_decisions = tuple(value)
    if len(page_decisions) == 0 and not allow_empty:
        raise ValueError("diagnostics de pages vides")
    for page_decision in page_decisions:
        if not isinstance(page_decision, PageDecision):
            raise ValueError("diagnostic de page invalide")
    return page_decisions


def _ensure_page_diagnostic_completeness(
    page_manifest: PageManifest,
    page_decisions: tuple[PageDecision, ...],
) -> None:
    manifest_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    diagnostic_pages = tuple(
        page_decision.page_number.value for page_decision in page_decisions
    )
    diagnostic_page_set = set(diagnostic_pages)
    manifest_page_set = set(manifest_pages)

    if len(diagnostic_pages) != len(diagnostic_page_set):
        raise ValueError("diagnostic de page dupliqué")

    if not diagnostic_page_set.issubset(manifest_page_set):
        raise ValueError("diagnostic hors manifeste")

    if diagnostic_page_set != manifest_page_set:
        raise ValueError("diagnostic de page manquant")

    if diagnostic_pages != manifest_pages:
        raise ValueError("ordre strict des diagnostics invalide")


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


def _ensure_diagnostic_version(value: DiagnosticVersion) -> DiagnosticVersion:
    if not isinstance(value, DiagnosticVersion):
        raise ValueError("version de diagnostic invalide")
    return value


def _ensure_page_diagnostic_signals(
    value: PageDiagnosticSignals,
) -> PageDiagnosticSignals:
    if not isinstance(value, PageDiagnosticSignals):
        raise ValueError("signaux diagnostiques invalides")
    return value


def _ensure_source_document(value: SourceDocument) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


__all__ = [
    "DiagnosticVersion",
    "DocumentProcessingRun",
    "DocumentProcessingRunStatus",
    "DocumentProcessingStarted",
    "ExistingOcrSignal",
    "LayoutComplexitySignal",
    "NativeTextSignal",
    "PageCorruptionSignal",
    "PageDecision",
    "PageDecisionState",
    "PageDiagnosticPolicy",
    "PageDiagnosticRecorded",
    "PageDiagnosticSignals",
    "PageImageSignal",
    "PageManifest",
    "PageManifestEntry",
    "PageManifestEntryState",
    "PageNumber",
    "ProcessingRunId",
]
