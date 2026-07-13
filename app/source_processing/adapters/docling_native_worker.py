"""Sous-processus Docling standard : entrée/sortie JSON bornées et hors ligne."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        response = _convert(payload)
    except Exception:
        print(json.dumps({"error_code": "DOCLING_STANDARD_UNAVAILABLE"}), flush=True)
        return 1
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


def _convert(payload: Any) -> dict[str, object]:
    if not isinstance(payload, Mapping) or set(payload) != {
        "schema_version",
        "document_id",
        "processing_run_id",
        "source_sha256",
        "source_pdf_path",
        "expected_page_numbers",
        "routing_policy_version",
        "assets_root",
    }:
        raise ValueError("payload invalide")
    source_pdf_path = Path(_required_text(payload, "source_pdf_path"))
    assets_root = Path(_required_text(payload, "assets_root"))
    if not source_pdf_path.is_file() or not assets_root.is_dir():
        raise ValueError("entrée Docling absente")
    if hashlib.sha256(source_pdf_path.read_bytes()).hexdigest() != _required_text(payload, "source_sha256"):
        raise ValueError("hash source divergent")
    expected_pages = _page_numbers(payload.get("expected_page_numbers"))

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions(
        artifacts_path=assets_root,
        do_ocr=False,
        do_table_structure=False,
        force_backend_text=True,
        document_timeout=110.0,
        enable_remote_services=False,
        allow_external_plugins=False,
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)},
    )
    result = converter.convert(
        source_pdf_path,
        page_range=(expected_pages[0], expected_pages[-1]),
        max_num_pages=1_000,
    )
    document = result.document
    pages = [_page_payload(document=document, page_number=page_number) for page_number in expected_pages]
    return {"schema_version": "1.0", "tool_version": "2.111.0", "pages": pages}


def _page_payload(*, document: Any, page_number: int) -> dict[str, object]:
    page = document.pages.get(page_number)
    if page is None:
        raise ValueError("page absente")
    page_size = page.size
    width = float(page_size.width)
    height = float(page_size.height)
    if width <= 0 or height <= 0:
        raise ValueError("taille page invalide")
    items: list[dict[str, object]] = []
    for item, _ in document.iterate_items(page_no=page_number):
        text = getattr(item, "text", None)
        provenances = getattr(item, "prov", None)
        if not isinstance(text, str) or text.strip() == "" or not isinstance(provenances, list) or len(provenances) == 0:
            continue
        provenance = next((candidate for candidate in provenances if getattr(candidate, "page_no", None) == page_number), None)
        if provenance is None:
            continue
        box = provenance.bbox
        left, top, right, bottom = float(box.l), float(box.t), float(box.r), float(box.b)
        normalized = [min(left, right) / width, min(top, bottom) / height, max(left, right) / width, max(top, bottom) / height]
        if normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
            continue
        items.append(
            {
                "text": text.strip(),
                "bbox": normalized,
                "provenance": {"page_number": page_number, "source": "docling"},
            }
        )
    if len(items) == 0:
        raise ValueError("provenance absente")
    return {"page_number": page_number, "items": items}


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _page_numbers(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) == 0:
        raise ValueError("pages invalides")
    pages = tuple(value)
    if any(isinstance(page, bool) or not isinstance(page, int) or page < 1 for page in pages):
        raise ValueError("pages invalides")
    if pages != tuple(sorted(set(pages))):
        raise ValueError("pages invalides")
    return pages


if __name__ == "__main__":
    raise SystemExit(main())
