"""Cas d'usage d'approbation du plan de routage documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageRoutingConfiguration,
)


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save_transition(
        self,
        processing_run: DocumentProcessingRun,
        *,
        expected_status: DocumentProcessingRunStatus,
    ) -> None:
        """Persiste une transition si la tentative est encore au statut attendu."""


@dataclass(frozen=True)
class ApproveRoutePlanCommand:
    """Commande applicative de décision du plan de routage."""

    processing_run: DocumentProcessingRun
    routing_configuration: PageRoutingConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        if not isinstance(self.routing_configuration, PageRoutingConfiguration):
            raise ValueError("configuration de routage invalide")


class ApproveRoutePlanHandler:
    """Handler applicatif de la commande ApproveRoutePlan."""

    def __init__(self, processing_run_repository: ProcessingRunRepository) -> None:
        if not callable(getattr(processing_run_repository, "save_transition", None)):
            raise ValueError("processing_run_repository invalide")
        self._processing_run_repository = processing_run_repository

    def handle(self, command: ApproveRoutePlanCommand) -> DocumentProcessingRun:
        if not isinstance(command, ApproveRoutePlanCommand):
            raise ValueError("commande ApproveRoutePlan invalide")

        routed_run = command.processing_run.decide_route_plan(
            command.routing_configuration
        )
        self._processing_run_repository.save_transition(
            routed_run,
            expected_status=command.processing_run.status,
        )
        return routed_run


__all__ = [
    "ApproveRoutePlanCommand",
    "ApproveRoutePlanHandler",
    "ProcessingRunRepository",
]
