from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
import pytest
from docling_core.types.doc import DoclingDocument

from docling_serve_mps.service import verify_model_assets, verify_runtime

ROOT = Path(__file__).resolve().parents[3]
PDF = ROOT / "reference/ostrading-environment-qualification-5-pages.pdf"
PDF_SHA256 = "8b67cc7428a569f15bc256247a5b8aa04b32311e7ad05da82cf6e4c75e64cb7b"
ENDPOINT = os.environ.get("DOCLING_SERVE_URL", "http://127.0.0.1:5001")
LIVE = os.environ.get("DOCLING_SERVE_MPS_LIVE") == "1"


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="DOCLING_SERVE_MPS_LIVE=1 requis")
def test_existing_file_api_converts_the_reference_pdf_on_mlx() -> None:
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == PDF_SHA256
    assert verify_model_assets(ROOT) == "e9939db25d2f296c8678d0491c4609a8c596c50a"
    runtime = verify_runtime(ROOT)
    assert runtime["torch_device"] == "mps:0"
    assert runtime["vlm_engine"] == "mlx"

    with httpx.Client(base_url=ENDPOINT, timeout=86_700) as client:
        assert client.get("/health").json() == {"status": "ok"}
        versions = client.get("/version").json()
        assert versions["docling-serve"] == "1.28.0"
        assert versions["docling"] == "2.115.0"
        assert versions["docling-core"] == "2.87.1"

        response = client.post(
            "/v1/convert/file",
            files={"files": (PDF.name, PDF.read_bytes(), "application/pdf")},
            data={
                "from_formats": "pdf",
                "to_formats": ["json", "doctags", "html", "md"],
                "pipeline": "vlm",
                "vlm_pipeline_preset": "default",
                "document_timeout": "86400",
                "abort_on_error": "true",
                "include_images": "false",
                "include_page_images": "true",
                "images_scale": "2.0",
                "image_export_mode": "embedded",
            },
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["errors"] == []
    document_payload = payload["document"]
    assert all(
        document_payload[name]
        for name in ("json_content", "doctags_content", "html_content", "md_content")
    )
    document = DoclingDocument.model_validate(document_payload["json_content"])
    assert list(document.pages) == [1, 2, 3, 4, 5]
    assert document.validate_tree(document.body, raise_on_error=True)
