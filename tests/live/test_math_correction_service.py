from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
from docling_core.types.doc import DoclingDocument

from pdf_math_audit.contract import CAPABILITY_PROFILE, CONTRACT_VERSION


ROOT = Path(__file__).parents[2]
PDF = ROOT / "experiments/math_pipeline_comparison/source-pages-7-10.pdf"
DOCUMENT = ROOT / "experiments/math_pipeline_comparison/docling-subset-document.json"
LIVE = os.environ.get("MATH_AUDIT_LIVE") == "1"


def _multipart() -> tuple[bytes, str]:
    boundary = f"codex-{uuid.uuid4().hex}"
    parts = []

    def field(
        name: str,
        value: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> None:
        disposition = f'form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        headers = [f"Content-Disposition: {disposition}"]
        if content_type:
            headers.append(f"Content-Type: {content_type}")
        parts.append(
            f"--{boundary}\r\n".encode()
            + "\r\n".join(headers).encode()
            + b"\r\n\r\n"
            + value
            + b"\r\n"
        )

    pdf = PDF.read_bytes()
    document = DOCUMENT.read_bytes()
    field("source_pdf", pdf, filename="source.pdf", content_type="application/pdf")
    field(
        "docling_document",
        document,
        filename="document.json",
        content_type="application/json",
    )
    field("source_sha256", hashlib.sha256(pdf).hexdigest().encode())
    field("docling_document_sha256", hashlib.sha256(document).hexdigest().encode())
    field("contract_version", CONTRACT_VERSION.encode())
    field("capability_profile", CAPABILITY_PROFILE.encode())
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), boundary


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="MATH_AUDIT_LIVE=1 requis")
def test_service_produit_et_prouve_un_docling_document_derive() -> None:
    body, boundary = _multipart()
    endpoint = os.environ.get("MATH_AUDIT_LIVE_URL", "http://127.0.0.1:8000")
    request = Request(
        f"{endpoint}/v1/qualifications",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlopen(request, timeout=120) as response:
        events = [json.loads(line) for line in response]

    artifacts: dict[str, bytearray] = {}
    for event in events:
        if event["type"] == "artifact":
            artifacts.setdefault(event["name"], bytearray()).extend(
                base64.b64decode(event["content_base64"])
            )
    metadata = events[-1]["artifacts"]
    assert events[-1]["type"] == "result"
    for name, content in artifacts.items():
        assert metadata[name]["bytes"] == len(content)
        assert metadata[name]["sha256"] == hashlib.sha256(content).hexdigest()

    report = json.loads(artifacts["report"])
    assert report["correction"]["status"] == "corrected"
    assert report["correction"]["accepted"] == 1
    assert set(artifacts) == {
        "evidence",
        "corrections",
        "correction_evidence",
        "derived_docling_document",
        "derived_html",
        "derived_markdown",
        "native_page_html",
        "report",
    }
    assert b"id='page-1'" in artifacts["native_page_html"]
    native = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    derived = DoclingDocument.model_validate_json(artifacts["derived_docling_document"])
    assert native.texts[8].text != derived.texts[8].text
    assert native.texts[8].orig == derived.texts[8].orig
    assert (
        hashlib.sha256(DOCUMENT.read_bytes()).hexdigest()
        == report["contract"]["docling_document_sha256"]
    )
