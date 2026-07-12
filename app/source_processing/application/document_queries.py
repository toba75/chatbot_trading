"""Read-models publics propriétaires du bounded context SP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.document_public_statuses import (
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
    PageDecision,
    PageRoute,
)
from app.source_processing.domain.source_document import DocumentId, SourceDocument


class SourceDocumentReadRepository(Protocol):
    """Port de lecture des sources enregistrées appartenant à SP."""

    def list_documents(self) -> tuple[SourceDocument, ...]:
        """Retourne les sources persistées sans exposer leur stockage."""

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        """Retourne une source à partir de son identité publique."""


class ProcessingRunReadRepository(Protocol):
    """Port de lecture des diagnostics et routes appartenant à SP."""

    def find_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None:
        """Retourne la tentative persistée du document."""


class DocumentConversionReadRepository(Protocol):
    """Port de lecture des conversions canoniques appartenant à SP."""

    def find_conversion_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentConversionState | None:
        """Retourne l'état persistant de conversion du document."""


@dataclass(frozen=True, slots=True)
class DocumentStateSnapshot:
    """Snapshot cohérent du parent SP et de ses sorties persistées."""

    source_document: SourceDocument
    processing_run: DocumentProcessingRun | None
    conversion: DocumentConversionState | None


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


@dataclass(frozen=True, slots=True)
class DocumentCorpusView:
    """Liste immuable des documents visibles par un client public."""

    documents: tuple[DocumentCorpusItem, ...]


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
    manifest: tuple[PageManifestEntryView, ...]
    pages: tuple[DiagnosticPageView, ...]


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
    ) -> None:
        if not callable(getattr(document_snapshot_repository, "list_document_snapshots", None)):
            raise ValueError("document_snapshot_repository sans liste")
        if not callable(getattr(document_snapshot_repository, "find_document_snapshot", None)):
            raise ValueError("document_snapshot_repository sans lecture")
        self._document_snapshot_repository = document_snapshot_repository

    def list_documents(self) -> DocumentCorpusView:
        snapshots = tuple(
            self._document_snapshot_repository.list_document_snapshots(
                limit=100,
                after_document_id=None,
            )
        )
        items = tuple(
            self._corpus_item(snapshot)
            for snapshot in sorted(
                snapshots,
                key=lambda candidate: candidate.source_document.document_id.value,
            )
        )
        return DocumentCorpusView(documents=items)

    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView:
        parsed_document_id = DocumentId.from_value(document_id)
        snapshot = self._require_snapshot(parsed_document_id)
        if snapshot.processing_run is None:
            raise DiagnosticNotRequestedError(parsed_document_id.value)
        parsed_processing_run = _ensure_processing_run(snapshot.processing_run)
        return _diagnostic_view(parsed_processing_run)

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
        manifest=manifest,
        pages=pages,
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
    "DocumentConversionReadRepository",
    "DocumentConversionView",
    "DocumentCorpusItem",
    "DocumentCorpusView",
    "DocumentDiagnosticView",
    "DocumentQueryService",
    "DocumentSnapshotRepository",
    "DocumentStateSnapshot",
    "PageDiagnosticView",
    "PageManifestEntryView",
    "PageRouteView",
    "ProcessingRunReadRepository",
    "SourceDocumentReadRepository",
    "SourceNotFoundError",
]
