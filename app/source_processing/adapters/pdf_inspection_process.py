"""Frontière d'inspection PDF dans un processus jetable borné."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 1_000
MAX_PDF_INSPECTION_SECONDS = 90.0
MAX_PAGE_TEXT_CHARACTERS = 250_000
MAX_TOTAL_TEXT_CHARACTERS = 5_000_000
MAX_PAGE_XOBJECTS = 256
MAX_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024


class PdfInspectionProcessError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if not isinstance(error_code, str) or error_code.strip() == "":
            raise ValueError("error_code inspection PDF invalide")
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True, slots=True)
class PdfInspectionBudget:
    max_pdf_bytes: int
    max_pages: int
    max_elapsed_seconds: float
    max_text_characters_per_page: int
    max_total_text_characters: int
    max_xobjects_per_page: int
    max_process_memory_bytes: int

    def __post_init__(self) -> None:
        for field_name in (
            "max_pdf_bytes",
            "max_pages",
            "max_text_characters_per_page",
            "max_total_text_characters",
            "max_xobjects_per_page",
            "max_process_memory_bytes",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} invalide")
        if isinstance(self.max_elapsed_seconds, bool) or not isinstance(
            self.max_elapsed_seconds, int | float
        ) or self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds invalide")
        if self.max_total_text_characters < self.max_text_characters_per_page:
            raise ValueError("budget texte total inférieur au budget par page")

    def to_payload(self) -> dict[str, int | float]:
        return {field_name: getattr(self, field_name) for field_name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class InspectedPdfPage:
    page_number: int
    manifest_state: str
    text_characters: int
    image_count: int
    native_text_state: str
    image_state: str
    existing_ocr_state: str
    layout_complexity: str
    corruption_state: str
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool

    @classmethod
    def from_payload(cls, payload: Any) -> "InspectedPdfPage":
        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise PdfInspectionProcessError("PDF_INSPECTOR_RESPONSE_INVALID")
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class PdfInspectionReport:
    pages: tuple[InspectedPdfPage, ...]

    def __post_init__(self) -> None:
        if len(self.pages) < 1:
            raise ValueError("pages inspection PDF absentes")


def run_disposable_process(
    *, command: tuple[str, ...], request_payload: str, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    if not isinstance(command, tuple) or len(command) < 1:
        raise ValueError("commande inspecteur invalide")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        stdout, stderr = process.communicate(request_payload, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise PdfInspectionProcessError("PDF_TIME_BUDGET_EXCEEDED") from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class IsolatedPdfInspector:
    """Lance pypdf hors du processus API/worker et tue tout dépassement."""

    def __init__(self, *, budget: PdfInspectionBudget) -> None:
        if not isinstance(budget, PdfInspectionBudget):
            raise ValueError("budget PDF invalide")
        self._budget = budget

    def inspect_content(self, original_content: bytes) -> PdfInspectionReport:
        if not isinstance(original_content, bytes) or len(original_content) < 1:
            raise PdfInspectionProcessError("PDF_EMPTY")
        if len(original_content) > self._budget.max_pdf_bytes:
            raise PdfInspectionProcessError("PDF_SIZE_BUDGET_EXCEEDED")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as stream:
            path = Path(stream.name)
            stream.write(original_content)
        try:
            return self.inspect_path(path)
        finally:
            path.unlink(missing_ok=True)

    def inspect_path(self, path: Path) -> PdfInspectionReport:
        if not isinstance(path, Path):
            raise ValueError("chemin PDF invalide")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise PdfInspectionProcessError("PDF_UNREADABLE") from exc
        if size < 1:
            raise PdfInspectionProcessError("PDF_EMPTY")
        if size > self._budget.max_pdf_bytes:
            raise PdfInspectionProcessError("PDF_SIZE_BUDGET_EXCEEDED")
        request = json.dumps(
            {"path": str(path.resolve()), "budget": self._budget.to_payload()},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        completed = run_disposable_process(
            command=(sys.executable, "-B", "-m", "app.source_processing.adapters.pdf_inspection_worker"),
            request_payload=request,
            timeout_seconds=float(self._budget.max_elapsed_seconds),
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise PdfInspectionProcessError("PDF_INSPECTOR_RESPONSE_INVALID") from exc
        if completed.returncode != 0:
            error_code = payload.get("error_code") if isinstance(payload, dict) else None
            if not isinstance(error_code, str):
                raise PdfInspectionProcessError("PDF_INSPECTOR_RESPONSE_INVALID")
            raise PdfInspectionProcessError(error_code)
        if not isinstance(payload, dict) or set(payload) != {"pages"} or not isinstance(payload["pages"], list):
            raise PdfInspectionProcessError("PDF_INSPECTOR_RESPONSE_INVALID")
        return PdfInspectionReport(tuple(InspectedPdfPage.from_payload(page) for page in payload["pages"]))


def build_m13_isolated_pdf_inspector() -> IsolatedPdfInspector:
    """Construit l'unique politique de budgets partagée par upload et diagnostic."""

    return IsolatedPdfInspector(
        budget=PdfInspectionBudget(
            max_pdf_bytes=MAX_PDF_BYTES,
            max_pages=MAX_PDF_PAGES,
            max_elapsed_seconds=MAX_PDF_INSPECTION_SECONDS,
            max_text_characters_per_page=MAX_PAGE_TEXT_CHARACTERS,
            max_total_text_characters=MAX_TOTAL_TEXT_CHARACTERS,
            max_xobjects_per_page=MAX_PAGE_XOBJECTS,
            max_process_memory_bytes=MAX_PROCESS_MEMORY_BYTES,
        )
    )


__all__ = [
    "InspectedPdfPage",
    "IsolatedPdfInspector",
    "PdfInspectionBudget",
    "PdfInspectionProcessError",
    "PdfInspectionReport",
    "run_disposable_process",
    "build_m13_isolated_pdf_inspector",
]
