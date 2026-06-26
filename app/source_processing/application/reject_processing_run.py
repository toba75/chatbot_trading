"""Cas d'usage de rejet d'une tentative documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    RoutingPolicyVersion,
)


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save_transition(
        self,
        processing_run: DocumentProcessingRun,
        *,
        expected_status: DocumentProcessingRunStatus,
    ) -> None:
        """Persiste le rejet si la tentative est encore au statut attendu."""


@dataclass(frozen=True)
class RejectProcessingRunCommand:
    """Commande applicative de rejet d'une tentative documentaire."""

    processing_run: DocumentProcessingRun
    routing_policy_version: RoutingPolicyVersion
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        if not isinstance(self.routing_policy_version, RoutingPolicyVersion):
            raise ValueError("version de politique de routage invalide")
        _ensure_blocking_reason(self.reason)


class RejectProcessingRunHandler:
    """Handler applicatif de la commande RejectProcessingRun."""

    def __init__(self, processing_run_repository: ProcessingRunRepository) -> None:
        if not callable(getattr(processing_run_repository, "save_transition", None)):
            raise ValueError("processing_run_repository invalide")
        self._processing_run_repository = processing_run_repository

    def handle(self, command: RejectProcessingRunCommand) -> DocumentProcessingRun:
        if not isinstance(command, RejectProcessingRunCommand):
            raise ValueError("commande RejectProcessingRun invalide")

        rejected_run = command.processing_run.reject(
            routing_policy_version=command.routing_policy_version,
            reason=command.reason,
        )
        self._processing_run_repository.save_transition(
            rejected_run,
            expected_status=command.processing_run.status,
        )
        return rejected_run


def _ensure_blocking_reason(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("justification bloquante invalide")
    if value.strip() == "":
        raise ValueError("justification bloquante invalide")
    if value != value.strip():
        raise ValueError("justification bloquante invalide")
    return value


__all__ = [
    "ProcessingRunRepository",
    "RejectProcessingRunCommand",
    "RejectProcessingRunHandler",
]
