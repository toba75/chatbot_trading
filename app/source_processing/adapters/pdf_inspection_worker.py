"""Sous-processus pypdf sans état, tué par le parent à l'expiration du budget."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


_TABLE_ROW = re.compile(r"(?m)^\s*\S+(?:\s{2,}|\t)\S+(?:\s{2,}|\t)\S+")
_FORMULA = re.compile(r"(?:[=±×÷∑∫√≤≥]|\b(?:sin|cos|log|exp)\s*\()")


class InspectionRejected(RuntimeError):
    pass


def _limit_process(memory_bytes: int, elapsed_seconds: float) -> None:
    if os.name == "nt":
        return
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    cpu_seconds = max(1, int(elapsed_seconds) + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))


def _inspect_page(page_number: int, page: Any, budget: dict[str, Any], total: list[int]) -> dict[str, Any]:
    resources = page.get("/Resources")
    xobjects = None if resources is None else resources.get_object().get("/XObject")
    if xobjects is None:
        image_count = 0
    else:
        xobjects = xobjects.get_object()
        if len(xobjects) > budget["max_xobjects_per_page"]:
            raise InspectionRejected("PDF_PAGE_XOBJECT_BUDGET_EXCEEDED")
        image_count = 0
        for reference in xobjects.values():
            if reference.get_object().get("/Subtype") == "/Image":
                image_count += 1

    fragments: list[str] = []
    page_characters = 0

    def visit(text: str, *_: Any) -> None:
        nonlocal page_characters
        page_characters += len(text)
        total[0] += len(text)
        if page_characters > budget["max_text_characters_per_page"]:
            raise InspectionRejected("PDF_PAGE_TEXT_MEMORY_BUDGET_EXCEEDED")
        if total[0] > budget["max_total_text_characters"]:
            raise InspectionRejected("PDF_TEXT_MEMORY_BUDGET_EXCEEDED")
        fragments.append(text)

    page.extract_text(visitor_text=visit)
    text = "".join(fragments).strip()
    text_characters = len(text)
    has_text = text_characters > 0
    has_image = image_count > 0
    ratio = 0.0 if not has_text else sum(character.isalnum() for character in text) / text_characters
    has_table = bool(_TABLE_ROW.search(text))
    has_formula = bool(_FORMULA.search(text))
    mixed = has_text and has_image
    existing_ocr_state = "VALID" if mixed and text_characters >= 20 and ratio >= 0.55 else "BAD" if mixed else "NONE"
    native_text_state = "RELIABLE" if has_text and text_characters >= 20 and ratio >= 0.55 else "SUSPECT" if has_text else "ABSENT"
    image_state = "SCAN_CLEAN" if has_image and existing_ocr_state != "BAD" else "SCAN_DEGRADED" if has_image else "NONE"
    return {
        "corruption_state": "NONE",
        "existing_ocr_state": existing_ocr_state,
        "has_formula": has_formula,
        "has_table": has_table,
        "image_count": image_count,
        "image_state": image_state,
        "layout_complexity": "COMPLEX" if has_table or has_formula or image_count > 1 else "SIMPLE",
        "manifest_state": "PRESENT" if has_text or has_image else "EMPTY",
        "mixed_content_detected": mixed,
        "native_text_state": native_text_state,
        "page_number": page_number,
        "text_characters": text_characters,
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or set(request) != {"path", "budget"}:
            raise InspectionRejected("PDF_INSPECTOR_REQUEST_INVALID")
        path = Path(request["path"])
        budget = request["budget"]
        _limit_process(budget["max_process_memory_bytes"], budget["max_elapsed_seconds"])
        with path.open("rb") as stream:
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted:
                raise InspectionRejected("PDF_ENCRYPTED")
            page_count = len(reader.pages)
            if page_count < 1:
                raise InspectionRejected("PDF_PAGE_COUNT_INVALID")
            if page_count > budget["max_pages"]:
                raise InspectionRejected("PDF_PAGE_BUDGET_EXCEEDED")
            total = [0]
            pages = [_inspect_page(number, page, budget, total) for number, page in enumerate(reader.pages, 1)]
        print(json.dumps({"pages": pages}, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return 0
    except InspectionRejected as exc:
        print(json.dumps({"error_code": str(exc)}))
        return 2
    except PdfReadError:
        print(json.dumps({"error_code": "PDF_CORRUPTED"}))
        return 2
    except OSError:
        print(json.dumps({"error_code": "PDF_UNREADABLE"}))
        return 2
    except (KeyError, TypeError, ValueError):
        print(json.dumps({"error_code": "PDF_PAGE_INSPECTION_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
