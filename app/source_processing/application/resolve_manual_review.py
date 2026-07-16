"""Résolution publique et persistée d'une revue documentaire M-003."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    ManualReviewDecisionType,
    ManualReviewResolution,
    PageNumber,
    PageRouteName,
    PageRoutingConfiguration,
)
from app.source_processing.domain.source_document import DocumentId


class ManualReviewSourceNotFoundError(LookupError):
    """Le document demandé n'existe pas dans le dépôt SP."""


class ManualReviewConflictError(RuntimeError):
    """La décision n'est pas applicable à l'état courant."""


class ProcessingRunRepository(Protocol):
    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None: ...

    def save_transition(
        self,
        processing_run: DocumentProcessingRun,
        *,
        expected_status: DocumentProcessingRunStatus,
    ) -> None: ...


@dataclass(frozen=True)
class ResolveManualReviewCommand:
    """Commande métier stricte issue de l'action humaine publique."""

    document_id: DocumentId
    decision: ManualReviewDecisionType
    page_number: PageNumber | None
    route_name: PageRouteName | None
    reviewer_id: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, DocumentId):
            raise ValueError("document_id de revue invalide")
        parsed_decision = ManualReviewDecisionType.from_value(self.decision)
        parsed_page = self.page_number
        parsed_route = self.route_name
        if parsed_decision is ManualReviewDecisionType.REJECT_DOCUMENT:
            if parsed_page is not None or parsed_route is not None:
                raise ValueError("page ou route interdite pour le rejet du document")
        else:
            if not isinstance(parsed_page, PageNumber):
                raise ValueError("page de revue manuelle requise")
            if parsed_decision is ManualReviewDecisionType.CONFIRM_EMPTY:
                if parsed_route is not None:
                    raise ValueError("route interdite pour une page confirmée vide")
            elif parsed_route is None:
                raise ValueError("route manuelle requise")
            else:
                parsed_route = PageRouteName.from_value(parsed_route)
                if parsed_route is PageRouteName.SKIP_EMPTY:
                    raise ValueError("SKIP_EMPTY interdit comme route assignée")
        _required_text(self.reviewer_id, "reviewer_id invalide")
        _required_text(self.reason, "motif de revue invalide")
        object.__setattr__(self, "decision", parsed_decision)
        object.__setattr__(self, "route_name", parsed_route)


class ResolveManualReviewHandler:
    """Charge l'agrégat, applique la décision et persiste par version optimiste."""

    def __init__(
        self,
        *,
        processing_run_repository: ProcessingRunRepository,
        routing_configuration: PageRoutingConfiguration,
    ) -> None:
        if not callable(getattr(processing_run_repository, "find_by_document_id", None)):
            raise ValueError("processing_run_repository sans lecture")
        if not callable(getattr(processing_run_repository, "save_transition", None)):
            raise ValueError("processing_run_repository sans transition")
        if not isinstance(routing_configuration, PageRoutingConfiguration):
            raise ValueError("configuration de routage invalide")
        self._repository = processing_run_repository
        self._routing_configuration = routing_configuration

    def handle(self, command: ResolveManualReviewCommand) -> DocumentProcessingRun:
        if not isinstance(command, ResolveManualReviewCommand):
            raise ValueError("commande de revue manuelle invalide")
        processing_run = self._repository.find_by_document_id(command.document_id)
        if processing_run is None:
            raise ManualReviewSourceNotFoundError(command.document_id.value)
        if processing_run.status is not DocumentProcessingRunStatus.MANUAL_REVIEW:
            raise ManualReviewConflictError("DOCUMENT_NOT_IN_MANUAL_REVIEW")
        try:
            if command.decision is ManualReviewDecisionType.REJECT_DOCUMENT:
                resolved = processing_run.reject(
                    routing_policy_version=self._routing_configuration.routing_policy_version,
                    reason=f"{command.reason} [réviseur: {command.reviewer_id}]",
                )
            else:
                assert command.page_number is not None
                resolved = processing_run.resolve_manual_review(
                    page_number=command.page_number,
                    resolution=ManualReviewResolution(
                        decision=command.decision,
                        route_name=command.route_name,
                        reviewer_id=command.reviewer_id,
                        reason=command.reason,
                    ),
                    routing_configuration=self._routing_configuration,
                )
        except ValueError as exc:
            raise ManualReviewConflictError(str(exc)) from exc
        self._repository.save_transition(
            resolved,
            expected_status=DocumentProcessingRunStatus.MANUAL_REVIEW,
        )
        return resolved

    def resolve_manual_review(
        self,
        *,
        document_id: str,
        decision: str,
        page_number: int | None,
        route_name: str | None,
        reviewer_id: str,
        reason: str,
    ) -> dict[str, Any]:
        parsed_decision = ManualReviewDecisionType.from_value(decision)
        parsed_page = None if page_number is None else PageNumber.from_value(page_number)
        parsed_route = None if route_name is None else PageRouteName.from_value(route_name)
        resolved = self.handle(
            ResolveManualReviewCommand(
                document_id=DocumentId.from_value(document_id),
                decision=parsed_decision,
                page_number=parsed_page,
                route_name=parsed_route,
                reviewer_id=reviewer_id,
                reason=reason,
            )
        )
        return {
            "document_id": resolved.document_id.value,
            "diagnostic_status": resolved.status.value,
            "decision": parsed_decision.value,
            "page_number": None if parsed_page is None else parsed_page.value,
            "route_name": None if parsed_route is None else parsed_route.value,
        }


def _required_text(value: Any, message: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(message)
    if len(value) > 512:
        raise ValueError(message)
    return value


__all__ = [
    "ManualReviewConflictError",
    "ManualReviewSourceNotFoundError",
    "ResolveManualReviewCommand",
    "ResolveManualReviewHandler",
]
