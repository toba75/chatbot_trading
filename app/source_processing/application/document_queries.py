"""Read-models publics propriétaires du bounded context SP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.document_public_statuses import (
    PublicActionPhase,
    PublicConversionStatus,
    PublicDiagnosticStatus,
    PublicSourceStatus,
)

from app.source_processing.application.document_commands import (
    DocumentConversionState,
    SourceNotFoundError,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDecision,
    PageRoute,
)
from app.source_processing.domain.source_document import DocumentId, SourceDocument


@dataclass(frozen=True, slots=True)
class DocumentStateSnapshot:
    """Snapshot cohérent du parent SP et de ses sorties persistées."""

    source_document: SourceDocument
    processing_run: DocumentProcessingRun | None
    conversion: DocumentConversionState | None

    def __post_init__(self) -> None:
        source = _ensure_source_document(self.source_document)
        if self.processing_run is not None:
            processing_run = _ensure_processing_run(self.processing_run)
            if processing_run.document_id != source.document_id:
                raise ValueError("processing_run hors document parent")
        if self.conversion is not None:
            conversion = _ensure_conversion_state(self.conversion)
            if conversion.document_id != source.document_id:
                raise ValueError("conversion hors document parent")


class DocumentSnapshotRepository(Protocol):
    def list_document_snapshots(
        self,
        *,
        limit: int,
        after_document_id: str | None,
    ) -> tuple[DocumentStateSnapshot, ...]:
        """Retourne tous les états sous un même snapshot transactionnel."""

    def find_document_snapshot(
        self,
        document_id: DocumentId,
    ) -> DocumentStateSnapshot | None:
        """Retourne le parent et ses enfants depuis un même snapshot."""


class DocumentCorpusStatusRepository(Protocol):
    def list_document_status_rows(
        self,
        *,
        limit: int,
        after_document_id: str | None,
    ) -> tuple[Any, ...]:
        """Retourne uniquement les statuts nécessaires à une page de corpus."""


class DiagnosticNotRequestedError(ValueError):
    """Erreur publique produite quand aucune tentative persistée n'existe."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        super().__init__(f"diagnostic non demandé: {self.document_id}")


class ConversionNotRequestedError(ValueError):
    """Erreur publique produite quand aucune conversion persistée n'existe."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        super().__init__(f"conversion non demandée: {self.document_id}")


@dataclass(frozen=True, slots=True)
class DocumentCorpusItem:
    """État public minimal d'un document dans le corpus."""

    document_id: str
    title: str
    document_status: str
    diagnostic_status: str
    conversion_status: str
    canonical_version_id: str | None
    manual_review_reason: str | None
    failure_error_code: str | None


@dataclass(frozen=True, slots=True)
class DocumentCorpusPageView:
    """Page SP bornée; le curseur est l'identifiant du dernier élément rendu."""

    documents: tuple[DocumentCorpusItem, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class PageManifestEntryView:
    """Entrée publique du manifeste persistant."""

    page_number: int
    manifest_status: str


@dataclass(frozen=True, slots=True)
class PageDiagnosticView:
    """Signaux publics réellement enregistrés pour une page."""

    page_state: str
    native_text_state: str
    image_state: str
    existing_ocr_state: str
    layout_complexity: str
    corruption_state: str
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool
    diagnostic_version: str
    justification: str


@dataclass(frozen=True, slots=True)
class PageRouteView:
    """Route publique réellement décidée pour une page."""

    route_name: str
    decision_mode: str
    confidence_score: float
    preprocessing_action: str
    routing_policy_version: str
    justification: str


@dataclass(frozen=True, slots=True)
class DiagnosticPageView:
    """Entrée de manifeste enrichie seulement des sorties persistées disponibles."""

    page_number: int
    manifest_status: str
    diagnostic: PageDiagnosticView | None
    route: PageRouteView | None


@dataclass(frozen=True, slots=True)
class DocumentDiagnosticView:
    """Diagnostic public complet, ordonné par le manifeste de pages."""

    document_id: str
    diagnostic_status: str
    source_page_count: int
    diagnosed_page_count: int
    manual_review_reason: str | None
    failure_error_code: str | None
    manifest: tuple[PageManifestEntryView, ...]
    pages: tuple[DiagnosticPageView, ...]


@dataclass(frozen=True, slots=True)
class DocumentActionProgressView:
    """Progression publique générique, issue exclusivement de l'état SP."""

    action_name: str
    phase: PublicActionPhase
    completed_units: int
    total_units: int | None
    failure_error_code: str | None

    def __post_init__(self) -> None:
        if self.action_name != "DIAGNOSE":
            raise ValueError("action publique inconnue")
        object.__setattr__(self, "phase", PublicActionPhase.from_value(self.phase))
        if isinstance(self.completed_units, bool) or not isinstance(self.completed_units, int):
            raise ValueError("unités réalisées invalides")
        if self.completed_units < 0:
            raise ValueError("unités réalisées invalides")
        if self.total_units is not None:
            if isinstance(self.total_units, bool) or not isinstance(self.total_units, int):
                raise ValueError("total d'unités invalide")
            if self.total_units < 1 or self.completed_units > self.total_units:
                raise ValueError("total d'unités incohérent")
        if self.phase is PublicActionPhase.NOT_REQUESTED:
            if self.completed_units != 0 or self.total_units is not None or self.failure_error_code is not None:
                raise ValueError("progression non demandée incohérente")
            return
        if self.total_units is None:
            raise ValueError("total d'unités requis")
        if self.phase is PublicActionPhase.SUCCEEDED and self.completed_units != self.total_units:
            raise ValueError("progression réussie incomplète")
        if self.phase is PublicActionPhase.FAILED:
            _ensure_text(self.failure_error_code, "code d'échec progression requis")
            return
        if self.failure_error_code is not None:
            raise ValueError("code d'échec interdit hors échec")

    @classmethod
    def from_processing_run(
        cls,
        processing_run: DocumentProcessingRun | None,
    ) -> "DocumentActionProgressView":
        return _document_action_progress(processing_run)


@dataclass(frozen=True, slots=True)
class DocumentConversionView:
    """État public de conversion et décision QA disponible."""

    document_id: str
    conversion_status: str
    qa_rejection_error_code: str | None
    canonical_version_id: str | None


class DocumentQueryService:
    """Projette les agrégats SP persistés vers des DTO publics immuables."""

    def __init__(
        self,
        *,
        document_snapshot_repository: DocumentSnapshotRepository,
        document_corpus_status_repository: DocumentCorpusStatusRepository,
    ) -> None:
        if not callable(getattr(document_snapshot_repository, "find_document_snapshot", None)):
            raise ValueError("document_snapshot_repository sans lecture")
        if not callable(getattr(document_corpus_status_repository, "list_document_status_rows", None)):
            raise ValueError("document_corpus_status_repository sans projection légère")
        self._document_snapshot_repository = document_snapshot_repository
        self._document_corpus_status_repository = document_corpus_status_repository

    def list_documents(
        self,
        *,
        limit: int,
        cursor: str | None,
    ) -> DocumentCorpusPageView:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("limit corpus invalide")
        if cursor is not None:
            DocumentId.from_value(cursor)
        rows = tuple(
            self._document_corpus_status_repository.list_document_status_rows(
                limit=limit + 1,
                after_document_id=cursor,
            )
        )
        has_next_page = len(rows) > limit
        visible_rows = rows[:limit]
        items = tuple(
            self._corpus_item_from_status_row(row)
            for row in sorted(
                visible_rows,
                key=lambda candidate: candidate.document_id,
            )
        )
        return DocumentCorpusPageView(
            documents=items,
            next_cursor=items[-1].document_id if has_next_page else None,
        )

    def _corpus_item_from_status_row(self, row: Any) -> DocumentCorpusItem:
        required = (
            "document_id", "title", "document_status", "diagnostic_status",
            "conversion_status", "canonical_version_id", "manual_review_reason",
            "failure_error_code",
        )
        if any(not hasattr(row, field) for field in required):
            raise TypeError("projection légère de corpus invalide")
        return DocumentCorpusItem(
            document_id=DocumentId.from_value(row.document_id).value,
            title=_ensure_text(row.title, "title"),
            document_status=PublicSourceStatus.from_value(row.document_status).value,
            diagnostic_status=PublicDiagnosticStatus.from_value(row.diagnostic_status).value,
            conversion_status=PublicConversionStatus.from_value(row.conversion_status).value,
            canonical_version_id=row.canonical_version_id,
            manual_review_reason=row.manual_review_reason,
            failure_error_code=row.failure_error_code,
        )

    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView:
        parsed_document_id = DocumentId.from_value(document_id)
        snapshot = self._require_snapshot(parsed_document_id)
        if snapshot.processing_run is None:
            raise DiagnosticNotRequestedError(parsed_document_id.value)
        parsed_processing_run = _ensure_processing_run(snapshot.processing_run)
        return _diagnostic_view(parsed_processing_run)

    def read_document_action_progress(self, document_id: str) -> DocumentActionProgressView:
        parsed_document_id = DocumentId.from_value(document_id)
        snapshot = self._require_snapshot(parsed_document_id)
        return DocumentActionProgressView.from_processing_run(snapshot.processing_run)

    def read_conversion(self, document_id: str) -> DocumentConversionView:
        parsed_document_id = DocumentId.from_value(document_id)
        snapshot = self._require_snapshot(parsed_document_id)
        if snapshot.conversion is None:
            raise ConversionNotRequestedError(parsed_document_id.value)
        parsed_conversion = _ensure_conversion_state(snapshot.conversion)
        return DocumentConversionView(
            document_id=parsed_conversion.document_id.value,
            conversion_status=parsed_conversion.conversion_status.value,
            qa_rejection_error_code=parsed_conversion.rejection_error_code,
            canonical_version_id=parsed_conversion.canonical_version_id,
        )

    def _require_snapshot(self, document_id: DocumentId) -> DocumentStateSnapshot:
        snapshot = self._document_snapshot_repository.find_document_snapshot(document_id)
        if snapshot is None:
            raise SourceNotFoundError(document_id.value)
        return snapshot

    def _corpus_item(self, snapshot: DocumentStateSnapshot) -> DocumentCorpusItem:
        source_document = _ensure_source_document(snapshot.source_document)
        document_id = source_document.document_id
        processing_run = snapshot.processing_run
        conversion = snapshot.conversion
        parsed_processing_run = (
            None if processing_run is None else _ensure_processing_run(processing_run)
        )
        parsed_conversion = (
            None if conversion is None else _ensure_conversion_state(conversion)
        )
        return DocumentCorpusItem(
            document_id=document_id.value,
            title=source_document.metadata.title,
            document_status=PublicSourceStatus.from_value(source_document.status.value).value,
            diagnostic_status=(
                PublicDiagnosticStatus.DIAGNOSTIC_NOT_REQUESTED.value
                if parsed_processing_run is None
                else PublicDiagnosticStatus.from_value(parsed_processing_run.status.value).value
            ),
            conversion_status=(
                PublicConversionStatus.CONVERSION_NOT_REQUESTED.value
                if parsed_conversion is None
                else PublicConversionStatus.from_value(
                    parsed_conversion.conversion_status.value
                ).value
            ),
            canonical_version_id=(
                None
                if parsed_conversion is None
                else parsed_conversion.canonical_version_id
            ),
            manual_review_reason=(
                None if parsed_processing_run is None else parsed_processing_run.manual_review_reason
            ),
            failure_error_code=(
                None if parsed_processing_run is None else parsed_processing_run.failure_error_code
            ),
        )


def _diagnostic_view(processing_run: DocumentProcessingRun) -> DocumentDiagnosticView:
    decisions = {
        decision.page_number.value: decision for decision in processing_run.page_decisions
    }
    routes = (
        {}
        if processing_run.route_plan is None
        else {
            route.page_number.value: route
            for route in processing_run.route_plan.page_routes
        }
    )
    ordered_manifest_entries = tuple(
        sorted(
            processing_run.page_manifest.entries,
            key=lambda candidate: candidate.page_number.value,
        )
    )
    manifest = tuple(
        PageManifestEntryView(
            page_number=entry.page_number.value,
            manifest_status=entry.state.value,
        )
        for entry in ordered_manifest_entries
    )
    pages = tuple(
        DiagnosticPageView(
            page_number=entry.page_number.value,
            manifest_status=entry.state.value,
            diagnostic=_page_diagnostic_view(decisions.get(entry.page_number.value)),
            route=_page_route_view(routes.get(entry.page_number.value)),
        )
        for entry in ordered_manifest_entries
    )
    return DocumentDiagnosticView(
        document_id=processing_run.document_id.value,
        diagnostic_status=processing_run.status.value,
        source_page_count=processing_run.page_manifest.source_page_count,
        diagnosed_page_count=len(processing_run.page_decisions),
        manual_review_reason=processing_run.manual_review_reason,
        failure_error_code=processing_run.failure_error_code,
        manifest=manifest,
        pages=pages,
    )


def _document_action_progress(
    processing_run: DocumentProcessingRun | None,
) -> DocumentActionProgressView:
    if processing_run is None:
        return DocumentActionProgressView(
            action_name="DIAGNOSE",
            phase=PublicActionPhase.NOT_REQUESTED,
            completed_units=0,
            total_units=None,
            failure_error_code=None,
        )
    source_page_count = processing_run.page_manifest.source_page_count
    completed_units = len(processing_run.page_decisions)
    if processing_run.status is DocumentProcessingRunStatus.MANIFEST_CREATED:
        phase = PublicActionPhase.QUEUED
    elif processing_run.status is DocumentProcessingRunStatus.DIAGNOSING:
        phase = PublicActionPhase.RUNNING
    elif processing_run.status is DocumentProcessingRunStatus.FAILED:
        phase = PublicActionPhase.FAILED
    else:
        phase = PublicActionPhase.SUCCEEDED
        completed_units = source_page_count
    return DocumentActionProgressView(
        action_name="DIAGNOSE",
        phase=phase,
        completed_units=completed_units,
        total_units=source_page_count,
        failure_error_code=processing_run.failure_error_code,
    )


def _page_diagnostic_view(decision: PageDecision | None) -> PageDiagnosticView | None:
    if decision is None:
        return None
    signals = decision.signals
    return PageDiagnosticView(
        page_state=decision.page_state.value,
        native_text_state=signals.native_text_state.value,
        image_state=signals.image_state.value,
        existing_ocr_state=signals.existing_ocr_state.value,
        layout_complexity=signals.layout_complexity.value,
        corruption_state=signals.corruption_state.value,
        mixed_content_detected=signals.mixed_content_detected,
        has_table=signals.has_table,
        has_formula=signals.has_formula,
        diagnostic_version=decision.diagnostic_version.value,
        justification=decision.justification,
    )


def _page_route_view(route: PageRoute | None) -> PageRouteView | None:
    if route is None:
        return None
    return PageRouteView(
        route_name=route.route_name.value,
        decision_mode=route.decision_mode.value,
        confidence_score=route.confidence_score,
        preprocessing_action=route.preprocessing_action.value,
        routing_policy_version=route.routing_policy_version.value,
        justification=route.justification,
    )


def _ensure_source_document(value: Any) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


def _ensure_processing_run(value: Any) -> DocumentProcessingRun:
    if not isinstance(value, DocumentProcessingRun):
        raise ValueError("processing_run invalide")
    return value


def _ensure_conversion_state(value: Any) -> DocumentConversionState:
    if not isinstance(value, DocumentConversionState):
        raise ValueError("conversion_state invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = [
    "ConversionNotRequestedError",
    "DiagnosticNotRequestedError",
    "DiagnosticPageView",
    "DocumentConversionView",
    "DocumentCorpusItem",
    "DocumentCorpusPageView",
    "DocumentActionProgressView",
    "DocumentDiagnosticView",
    "DocumentQueryService",
    "DocumentSnapshotRepository",
    "DocumentCorpusStatusRepository",
    "DocumentStateSnapshot",
    "PageDiagnosticView",
    "PageManifestEntryView",
    "PageRouteView",
    "SourceNotFoundError",
]
