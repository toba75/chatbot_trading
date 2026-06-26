"""Cas d'usage de mise en quarantaine d'une tentative documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import SourceDocument


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save(self, processing_run: DocumentProcessingRun) -> None:
        """Persiste la tentative mise en quarantaine."""


class SourceDocumentRepository(Protocol):
    """Port de dépôt des sources documentaires mises en quarantaine."""

    def save(self, source_document: SourceDocument) -> None:
        """Persiste la source mise en quarantaine."""


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
        source_document_repository: SourceDocumentRepository,
    ) -> None:
        if not callable(getattr(processing_run_repository, "save", None)):
            raise ValueError("processing_run_repository invalide")
        if not callable(getattr(source_document_repository, "save", None)):
            raise ValueError("source_document_repository invalide")
        self._processing_run_repository = processing_run_repository
        self._source_document_repository = source_document_repository

    def handle(self, command: QuarantineProcessingRunCommand) -> DocumentProcessingRun:
        if not isinstance(command, QuarantineProcessingRunCommand):
            raise ValueError("commande QuarantineProcessingRun invalide")

        quarantined_source = command.source_document.quarantine(reason=command.reason)
        quarantined_run = command.processing_run.quarantine(
            routing_policy_version=command.routing_policy_version,
            reason=command.reason,
        )
        self._source_document_repository.save(quarantined_source)
        self._processing_run_repository.save(quarantined_run)
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
    "SourceDocumentRepository",
]
