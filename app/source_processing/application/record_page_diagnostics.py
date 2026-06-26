"""Cas d'usage d'enregistrement des diagnostics page par page."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDiagnosticPolicy,
    PageDiagnosticSignals,
    PageNumber,
)


class ProcessingRunRepository(Protocol):
    """Port de dépôt des tentatives de traitement documentaire."""

    def save(self, processing_run: DocumentProcessingRun) -> None:
        """Persiste la tentative diagnostiquée sans route implicite."""


@dataclass(frozen=True)
class PageDiagnosticInput:
    """Entrée applicative d'un diagnostic technique inspecté pour une page."""

    page_number: int
    signals: PageDiagnosticSignals
    diagnostic_version: str
    justification: str

    def __post_init__(self) -> None:
        PageNumber.from_value(self.page_number)
        if not isinstance(self.signals, PageDiagnosticSignals):
            raise ValueError("signaux diagnostiques invalides")
        DiagnosticVersion.from_value(self.diagnostic_version)
        _ensure_justification(self.justification)


@dataclass(frozen=True)
class RecordPageDiagnosticsCommand:
    """Commande applicative d'enregistrement des diagnostics de pages."""

    processing_run: DocumentProcessingRun
    diagnostics: tuple[PageDiagnosticInput, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        object.__setattr__(
            self,
            "diagnostics",
            _ensure_page_diagnostic_inputs(self.diagnostics),
        )


class RecordPageDiagnosticsHandler:
    """Handler applicatif de la commande RecordPageDiagnostics."""

    def __init__(self, processing_run_repository: ProcessingRunRepository) -> None:
        if not callable(getattr(processing_run_repository, "save", None)):
            raise ValueError("processing_run_repository invalide")
        self._processing_run_repository = processing_run_repository

    def handle(self, command: RecordPageDiagnosticsCommand) -> DocumentProcessingRun:
        if not isinstance(command, RecordPageDiagnosticsCommand):
            raise ValueError("commande RecordPageDiagnostics invalide")

        diagnostic_policy = PageDiagnosticPolicy()
        page_decisions = tuple(
            _page_decision_from_input(diagnostic_policy, page_diagnostic_input)
            for page_diagnostic_input in command.diagnostics
        )
        diagnosed_run = command.processing_run.record_page_diagnostics(page_decisions)
        self._processing_run_repository.save(diagnosed_run)
        return diagnosed_run


def _page_decision_from_input(
    diagnostic_policy: PageDiagnosticPolicy,
    page_diagnostic_input: PageDiagnosticInput,
) -> PageDecision:
    if not isinstance(page_diagnostic_input, PageDiagnosticInput):
        raise ValueError("diagnostic de page invalide")
    return diagnostic_policy.classify(
        page_number=PageNumber.from_value(page_diagnostic_input.page_number),
        signals=page_diagnostic_input.signals,
        diagnostic_version=DiagnosticVersion.from_value(
            page_diagnostic_input.diagnostic_version
        ),
        justification=page_diagnostic_input.justification,
    )


def _ensure_page_diagnostic_inputs(
    value: Sequence[PageDiagnosticInput],
) -> tuple[PageDiagnosticInput, ...]:
    if value is None:
        raise ValueError("diagnostics de pages absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("diagnostics de pages invalides")
    diagnostics = tuple(value)
    if len(diagnostics) == 0:
        raise ValueError("diagnostics de pages vides")
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, PageDiagnosticInput):
            raise ValueError("diagnostic de page invalide")
    return diagnostics


def _ensure_justification(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("justification de diagnostic invalide")
    if value.strip() == "":
        raise ValueError("justification de diagnostic invalide")
    if value != value.strip():
        raise ValueError("justification de diagnostic invalide")
    return value


__all__ = [
    "PageDiagnosticInput",
    "ProcessingRunRepository",
    "RecordPageDiagnosticsCommand",
    "RecordPageDiagnosticsHandler",
]
