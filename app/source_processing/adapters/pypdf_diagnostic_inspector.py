"""Adaptateur pypdf d'inspection documentaire réelle et strictement bornée."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.source_processing.application.document_worker import WorkerProcessingError
from app.source_processing.application.record_page_diagnostics import PageDiagnosticInput
from app.source_processing.domain.document_processing_run import PageDiagnosticSignals


_TABLE_ROW = re.compile(r"(?m)^\s*\S+(?:\s{2,}|\t)\S+(?:\s{2,}|\t)\S+")
_FORMULA = re.compile(r"(?:[=±×÷∑∫√≤≥]|\b(?:sin|cos|log|exp)\s*\()")


class PdfInspectionError(WorkerProcessingError):
    """Erreur stable d'un original refusé par l'inspection bornée."""

    def __init__(self, error_code: str, *, retryable: bool = False) -> None:
        super().__init__(error_code, retryable=retryable)


@dataclass(frozen=True, slots=True)
class PdfInspectionBudget:
    """Budgets de sécurité appliqués avant et pendant toute inspection PDF."""

    max_pdf_bytes: int
    max_pages: int
    max_elapsed_seconds: float
    max_text_characters_per_page: int
    max_total_text_characters: int
    max_xobjects_per_page: int

    def __post_init__(self) -> None:
        for field_name in (
            "max_pdf_bytes",
            "max_pages",
            "max_text_characters_per_page",
            "max_total_text_characters",
            "max_xobjects_per_page",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} invalide")
        if (
            isinstance(self.max_elapsed_seconds, bool)
            or not isinstance(self.max_elapsed_seconds, (int, float))
            or self.max_elapsed_seconds <= 0
        ):
            raise ValueError("max_elapsed_seconds invalide")
        if self.max_total_text_characters < self.max_text_characters_per_page:
            raise ValueError("budget texte total inférieur au budget par page")


class PdfDiagnosticInspector:
    """Mesure texte, images, OCR, tableaux et formules sans décoder les images."""

    def __init__(self, *, original_source_store: Any, budget: PdfInspectionBudget) -> None:
        if not callable(getattr(original_source_store, "storage_ref", None)):
            raise ValueError("original_source_store sans storage_ref")
        if not callable(getattr(original_source_store, "resolve_internal_path", None)):
            raise ValueError("original_source_store sans résolution")
        if not isinstance(budget, PdfInspectionBudget):
            raise ValueError("budget PDF invalide")
        self._original_source_store = original_source_store
        self._budget = budget

    def inspect(self, original_storage_ref: str) -> tuple[PageDiagnosticInput, ...]:
        storage_ref = self._original_source_store.storage_ref(original_storage_ref)
        path = self._original_source_store.resolve_internal_path(storage_ref)
        if not isinstance(path, Path):
            raise PdfInspectionError("PDF_STORAGE_PATH_INVALID")
        started = time.perf_counter()
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise PdfInspectionError("PDF_UNREADABLE") from exc
        if size < 1:
            raise PdfInspectionError("PDF_EMPTY")
        if size > self._budget.max_pdf_bytes:
            raise PdfInspectionError("PDF_SIZE_BUDGET_EXCEEDED")
        try:
            with path.open("rb") as stream:
                reader = PdfReader(stream, strict=True)
                self._ensure_elapsed(started)
                if reader.is_encrypted:
                    raise PdfInspectionError("PDF_ENCRYPTED")
                page_count = len(reader.pages)
                if page_count < 1:
                    raise PdfInspectionError("PDF_PAGE_COUNT_INVALID")
                if page_count > self._budget.max_pages:
                    raise PdfInspectionError("PDF_PAGE_BUDGET_EXCEEDED")
                diagnostics: list[PageDiagnosticInput] = []
                total_text_characters = 0
                for page_number, page in enumerate(reader.pages, start=1):
                    self._ensure_elapsed(started)
                    diagnostic, text_characters = self._inspect_page(page_number, page)
                    total_text_characters += text_characters
                    if total_text_characters > self._budget.max_total_text_characters:
                        raise PdfInspectionError("PDF_TEXT_MEMORY_BUDGET_EXCEEDED")
                    diagnostics.append(diagnostic)
                self._ensure_elapsed(started)
                return tuple(diagnostics)
        except PdfInspectionError:
            raise
        except PdfReadError as exc:
            raise PdfInspectionError("PDF_CORRUPTED") from exc
        except OSError as exc:
            raise PdfInspectionError("PDF_UNREADABLE") from exc

    def _inspect_page(self, page_number: int, page: Any) -> tuple[PageDiagnosticInput, int]:
        try:
            extracted_text = page.extract_text() or ""
            image_count = _image_xobject_count(page)
        except PdfInspectionError:
            raise
        except (KeyError, TypeError, ValueError, PdfReadError) as exc:
            raise PdfInspectionError("PDF_PAGE_INSPECTION_FAILED") from exc
        text = extracted_text.strip()
        text_characters = len(text)
        if text_characters > self._budget.max_text_characters_per_page:
            raise PdfInspectionError("PDF_PAGE_TEXT_MEMORY_BUDGET_EXCEEDED")
        if image_count > self._budget.max_xobjects_per_page:
            raise PdfInspectionError("PDF_PAGE_XOBJECT_BUDGET_EXCEEDED")

        has_text = text_characters > 0
        has_image = image_count > 0
        alphanumeric_count = sum(character.isalnum() for character in text)
        alphanumeric_ratio = 0.0 if text_characters == 0 else alphanumeric_count / text_characters
        has_table = bool(_TABLE_ROW.search(text))
        has_formula = bool(_FORMULA.search(text))
        mixed = has_text and has_image
        existing_ocr_state = (
            "VALID"
            if mixed and text_characters >= 20 and alphanumeric_ratio >= 0.55
            else "BAD"
            if mixed
            else "NONE"
        )
        native_text_state = (
            "RELIABLE"
            if has_text and text_characters >= 20 and alphanumeric_ratio >= 0.55
            else "SUSPECT"
            if has_text
            else "ABSENT"
        )
        corruption_state = "CORRUPT" if not has_text and not has_image else "NONE"
        image_state = "SCAN_CLEAN" if has_image and existing_ocr_state != "BAD" else (
            "SCAN_DEGRADED" if has_image else "NONE"
        )
        layout_complexity = "COMPLEX" if has_table or has_formula or image_count > 1 else "SIMPLE"
        justification = (
            "Inspection pypdf bornée: "
            f"texte={text_characters}; images={image_count}; "
            f"ocr={existing_ocr_state}; tableau={str(has_table).lower()}; "
            f"formule={str(has_formula).lower()}."
        )
        return (
            PageDiagnosticInput(
                page_number=page_number,
                signals=PageDiagnosticSignals(
                    native_text_state=native_text_state,
                    image_state=image_state,
                    existing_ocr_state=existing_ocr_state,
                    layout_complexity=layout_complexity,
                    corruption_state=corruption_state,
                    mixed_content_detected=mixed,
                    has_table=has_table,
                    has_formula=has_formula,
                ),
                diagnostic_version="pypdf-bounded-v2",
                justification=justification,
            ),
            text_characters,
        )

    def _ensure_elapsed(self, started: float) -> None:
        if time.perf_counter() - started > self._budget.max_elapsed_seconds:
            raise PdfInspectionError("PDF_TIME_BUDGET_EXCEEDED")


def _image_xobject_count(page: Any) -> int:
    resources = page.get("/Resources")
    if resources is None:
        return 0
    resources = resources.get_object()
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return 0
    xobjects = xobjects.get_object()
    count = 0
    for reference in xobjects.values():
        candidate = reference.get_object()
        if candidate.get("/Subtype") == "/Image":
            count += 1
    return count


__all__ = ["PdfDiagnosticInspector", "PdfInspectionBudget", "PdfInspectionError"]
