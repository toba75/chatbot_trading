"""Sous-processus Granite-Docling hors ligne pour une page explicitement routée."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from app.source_processing.adapters.docling_granite_conversion import (
    GRANITE_DOCLING_MODEL_REPOSITORY,
    GRANITE_DOCLING_MODEL_REVISION,
)


_GRANITE_ROUTE_NAMES = frozenset(
    {
        "SCAN_GRANITE",
        "BAD_OCR_TO_GRANITE",
        "MIXED_PAGEWISE",
        "TARGETED_ENRICHMENT",
        "PREPROCESS_GRANITE",
    }
)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        response = _convert(payload)
    except Exception:
        print(json.dumps({"error_code": "GRANITE_DOCLING_UNAVAILABLE"}), flush=True)
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
        "page_number",
        "source_page_number",
        "route_name",
        "routing_policy_version",
        "assets_root",
        "model_repository",
        "model_revision",
    }:
        raise ValueError("payload invalide")
    if (
        payload["schema_version"] != "1.0"
        or payload["route_name"] not in _GRANITE_ROUTE_NAMES
        or payload["model_repository"] != GRANITE_DOCLING_MODEL_REPOSITORY
        or payload["model_revision"] != GRANITE_DOCLING_MODEL_REVISION
    ):
        raise ValueError("contrat Granite invalide")
    source_pdf_path = Path(_required_text(payload, "source_pdf_path"))
    assets_root = Path(_required_text(payload, "assets_root"))
    page_number = payload.get("page_number")
    source_page_number = payload.get("source_page_number")
    if (
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
        or isinstance(source_page_number, bool)
        or not isinstance(source_page_number, int)
        or source_page_number < 1
    ):
        raise ValueError("numéro de page Granite invalide")
    if not source_pdf_path.is_file() or not assets_root.is_dir():
        raise ValueError("entrée Granite absente")
    if hashlib.sha256(source_pdf_path.read_bytes()).hexdigest() != _required_text(payload, "source_sha256"):
        raise ValueError("hash source divergent")

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline

    vlm_options = VlmConvertOptions.from_preset("granite_docling")
    model_spec = vlm_options.model_spec.model_copy(
        update={"revision": GRANITE_DOCLING_MODEL_REVISION}
    )
    vlm_options = vlm_options.model_copy(
        update={"model_spec": model_spec, "force_backend_text": False}
    )
    pipeline_options = VlmPipelineOptions(
        artifacts_path=assets_root,
        document_timeout=110.0,
        enable_remote_services=False,
        allow_external_plugins=False,
        generate_page_images=True,
        force_backend_text=False,
        vlm_options=vlm_options,
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=pipeline_options,
            )
        },
    )
    result = converter.convert(
        source_pdf_path,
        page_range=(source_page_number, source_page_number),
        max_num_pages=1_000,
    )
    return {
        "schema_version": "1.0",
        "tool_version": "2.111.0",
        "pages": [
            _page_payload(
                document=result.document,
                source_page_number=source_page_number,
                output_page_number=page_number,
            )
        ],
    }


def _page_payload(
    *,
    document: Any,
    source_page_number: int,
    output_page_number: int,
) -> dict[str, object]:
    page = document.pages.get(source_page_number)
    if page is None:
        raise ValueError("page Granite absente")
    page_size = page.size
    width = float(page_size.width)
    height = float(page_size.height)
    if width <= 0 or height <= 0:
        raise ValueError("taille page invalide")
    items: list[dict[str, object]] = []
    for item, _ in document.iterate_items(page_no=source_page_number):
        text = getattr(item, "text", None)
        provenances = getattr(item, "prov", None)
        if not isinstance(text, str) or text.strip() == "" or not isinstance(provenances, list) or len(provenances) == 0:
            continue
        provenance = next((candidate for candidate in provenances if getattr(candidate, "page_no", None) == source_page_number), None)
        if provenance is None:
            continue
        box = provenance.bbox
        left, top, right, bottom = float(box.l), float(box.t), float(box.r), float(box.b)
        normalized = [
            min(left, right) / width,
            min(top, bottom) / height,
            max(left, right) / width,
            max(top, bottom) / height,
        ]
        if normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
            continue
        items.append(
            {
                "text": text.strip(),
                "bbox": normalized,
                "provenance": {"page_number": output_page_number, "source": "granite_docling"},
            }
        )
    if len(items) == 0:
        raise ValueError("provenance Granite absente")
    return {"page_number": output_page_number, "items": items}


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
