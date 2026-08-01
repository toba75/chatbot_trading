from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from docling_core.types.doc import DoclingDocument
from pypdf import PdfReader

from qualification.math_audit.runtime import runtime_proof


def request_payload(filename: str, content: bytes) -> dict[str, object]:
    return {
        "sources": [
            {
                "kind": "file",
                "filename": filename,
                "base64_string": base64.b64encode(content).decode("ascii"),
            }
        ],
        "options": {
            "from_formats": ["pdf"],
            "to_formats": ["json"],
            "pipeline": "vlm",
            "vlm_pipeline_preset": "default",
            "document_timeout": 86400,
            "abort_on_error": True,
            "include_images": False,
            "include_page_images": False,
            "images_scale": 2.0,
            "image_export_mode": "placeholder",
        },
        "target": {"kind": "inbody"},
    }


def _get_json(url: str, timeout: int) -> dict[str, object]:
    with urlopen(url, timeout=timeout) as response:
        return json.load(response)


def _post_json(url: str, payload: dict[str, object], timeout: int) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _json_bytes(value: object) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require_pages(document: DoclingDocument, expected_pages: int) -> None:
    expected = list(range(1, expected_pages + 1))
    actual = sorted(document.pages)
    if actual != expected:
        raise RuntimeError(f"Pages Docling inattendues : {actual} != {expected}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(
    endpoint: str,
    pdf_path: Path,
    output_dir: Path,
    runtime: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    document_path = output_dir / "docling-document.json"
    response_path = output_dir / "docling-response.json"
    provenance_path = output_dir / "candidate-provenance.json"
    existing = [path for path in (document_path, response_path, provenance_path) if path.exists()]
    if existing:
        raise FileExistsError(f"Capture déjà présente : {', '.join(map(str, existing))}")

    endpoint = endpoint.rstrip("/")
    health = _get_json(f"{endpoint}/health", 10)
    if health != {"status": "ok"}:
        raise RuntimeError(f"Santé Docling inattendue : {health}")
    versions = _get_json(f"{endpoint}/version", 10)
    pdf_bytes = pdf_path.read_bytes()
    payload = _post_json(
        f"{endpoint}/v1/convert/source",
        request_payload(pdf_path.name, pdf_bytes),
        86700,
    )
    if payload.get("status") != "success" or payload.get("errors"):
        raise RuntimeError(
            f"Conversion Docling invalide : {payload.get('status')}, {payload.get('errors')}"
        )
    document_bytes = _json_bytes(payload["document"]["json_content"])
    document = DoclingDocument.model_validate_json(document_bytes)
    _require_pages(document, len(PdfReader(pdf_path).pages))

    response_bytes = _json_bytes(payload)
    document_path.write_bytes(document_bytes)
    response_path.write_bytes(response_bytes)
    provenance = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "endpoint": endpoint,
        "versions": versions,
        "runtime_proof": runtime,
        "processing_time": payload["processing_time"],
        "source_pdf": pdf_path.name,
        "source_pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "docling_document": document_path.name,
        "docling_document_sha256": hashlib.sha256(document_bytes).hexdigest(),
        "raw_response": response_path.name,
        "raw_response_sha256": hashlib.sha256(response_bytes).hexdigest(),
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture un DoclingDocument réel.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--compose-file", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    args = parser.parse_args()
    proof = runtime_proof(
        args.endpoint,
        args.compose_file,
        args.env_file,
        args.service,
        args.model_manifest,
    )
    capture(args.endpoint, args.pdf, args.output_dir, proof)


if __name__ == "__main__":
    main()
