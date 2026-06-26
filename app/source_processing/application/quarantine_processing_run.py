"""Cas d'usage de mise en quarantaine d'une tentative documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    SourceDocument,
    SourceDocumentStatus,
)


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save_quarantine(
        self,
        source_document: SourceDocument,
        processing_run: DocumentProcessingRun,
        *,
        expected_processing_run_status: DocumentProcessingRunStatus,
        expected_source_document_status: SourceDocumentStatus,
    ) -> None:
        """Persiste atomiquement la quarantaine si les statuts attendus tiennent."""


@dataclass(frozen=True)
class QuarantineProcessingRunCommand:
    """Commande applicative de quarantaine d'une tentative documentaire."""

    processing_run: DocumentProcessingRun
    source_document: SourceDocument
    routing_policy_version: RoutingPolicyVersion
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        if not isinstance(self.source_document, SourceDocument):
            raise ValueError("source_document invalide")
        if self.source_document.document_id != self.processing_run.document_id:
            raise ValueError("source_document incohérent")
        if not isinstance(self.routing_policy_version, RoutingPolicyVersion):
            raise ValueError("version de politique de routage invalide")
        _ensure_blocking_reason(self.reason)


class QuarantineProcessingRunHandler:
    """Handler applicatif de la commande QuarantineProcessingRun."""

    def __init__(
        self,
        processing_run_repository: ProcessingRunRepository,
    ) -> None:
        if not callable(getattr(processing_run_repository, "save_quarantine", None)):
            raise ValueError("processing_run_repository invalide")
        self._processing_run_repository = processing_run_repository

    def handle(self, command: QuarantineProcessingRunCommand) -> DocumentProcessingRun:
        if not isinstance(command, QuarantineProcessingRunCommand):
            raise ValueError("commande QuarantineProcessingRun invalide")

        quarantined_source = command.source_document.quarantine(reason=command.reason)
        quarantined_run = command.processing_run.quarantine(
            routing_policy_version=command.routing_policy_version,
            reason=command.reason,
        )
        self._processing_run_repository.save_quarantine(
            source_document=quarantined_source,
            processing_run=quarantined_run,
            expected_processing_run_status=command.processing_run.status,
            expected_source_document_status=command.source_document.status,
        )
        return quarantined_run


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
    "QuarantineProcessingRunCommand",
    "QuarantineProcessingRunHandler",
]
