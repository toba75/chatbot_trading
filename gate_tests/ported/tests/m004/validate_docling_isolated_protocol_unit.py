"""Contrat UTF-8 des processus Docling isolés (ADR-032)."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess

import pytest


def _response(source: str) -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0",
            "tool_version": "2.111.0",
            "pages": [
                {
                    "page_number": 1,
                    "items": [
                        {
                            "text": "Droit ©",
                            "bbox": [0.1, 0.1, 0.9, 0.9],
                            "provenance": {"page_number": 1, "source": source},
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _native_converter(tmp_path: Path):
    runtime = importlib.import_module("app.source_processing.adapters.docling_native_conversion")
    assets_root = tmp_path / "native-assets"
    model_path = assets_root / "models" / "layout.bin"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes("actif Docling scellé".encode("utf-8"))
    manifest_path = tmp_path / "native-assets.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "docling",
                "tool_version": "2.111.0",
                "assets": [
                    {
                        "relative_path": "models/layout.bin",
                        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "native-source.pdf"
    source_path.write_bytes(b"%PDF-1.7\nsource unicode native\n%%EOF\n")
    request = runtime.NativeDoclingConversionRequest(
        document_id="DOC-0000000000000001",
        processing_run_id="RUN-M004-UNICODE-NATIVE",
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        source_pdf_path=source_path,
        expected_page_numbers=(1,),
        routing_policy_version="routing-v1",
    )
    return runtime, runtime.IsolatedNativeDoclingConverter(
        asset_manifest_path=manifest_path,
        assets_root=assets_root,
        timeout_seconds=1.0,
    ), request, "DOCLING_STANDARD_UNAVAILABLE", "docling"


def _granite_converter(tmp_path: Path):
    runtime = importlib.import_module("app.source_processing.adapters.docling_granite_conversion")
    assets_root = tmp_path / "granite-assets"
    model_path = assets_root / "ibm-granite--granite-docling-258M" / "config.json"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b'{"model_type":"granite_docling"}')
    manifest_path = tmp_path / "granite-assets.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "granite_docling",
                "tool_version": "2.111.0",
                "model_repository": "ibm-granite/granite-docling-258M",
                "model_revision": runtime.GRANITE_DOCLING_MODEL_REVISION,
                "assets": [
                    {
                        "relative_path": "ibm-granite--granite-docling-258M/config.json",
                        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "granite-source.pdf"
    source_path.write_bytes(b"%PDF-1.7\nsource unicode granite\n%%EOF\n")
    request = runtime.GraniteDoclingConversionRequest(
        document_id="DOC-0000000000000001",
        processing_run_id="RUN-M004-UNICODE-GRANITE",
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        source_pdf_path=source_path,
        page_number=1,
        source_page_number=1,
        route_name="TARGETED_ENRICHMENT",
        routing_policy_version="routing-v1",
    )
    return runtime, runtime.IsolatedGraniteDoclingConverter(
        asset_manifest_path=manifest_path,
        assets_root=assets_root,
        timeout_seconds=1.0,
    ), request, "GRANITE_DOCLING_UNAVAILABLE", "granite_docling"


def _assert_parent_protocol(runtime, converter, request, error_code: str, source: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def valid_run(*args, **kwargs):
        assert isinstance(kwargs["input"], bytes)
        assert "text" not in kwargs
        assert "encoding" not in kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=_response(source),
            stderr=b"\xa9",
        )

    monkeypatch.setattr(runtime.subprocess, "run", valid_run)
    converted = converter.convert(request)
    assert converted.pages[0].items[0].text == "Droit ©"

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=b"\xa9",
            stderr=b"",
        ),
    )
    error_type = (
        runtime.DoclingNativeConversionError
        if error_code == "DOCLING_STANDARD_UNAVAILABLE"
        else runtime.GraniteDoclingConversionError
    )
    with pytest.raises(error_type, match=error_code):
        converter.convert(request)


def _assert_worker_protocol(module_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = importlib.import_module(module_name)
    raw_stdout = io.BytesIO()
    stdout = io.TextIOWrapper(raw_stdout, encoding="cp1252")
    monkeypatch.setattr(worker.sys, "stdin", io.StringIO("{}"))
    monkeypatch.setattr(worker.sys, "stdout", stdout)
    monkeypatch.setattr(
        worker,
        "_convert",
        lambda payload: {
            "schema_version": "1.0",
            "tool_version": "2.111.0",
            "pages": [{"page_number": 1, "items": [{"text": "Droit ©"}]}],
        },
    )
    assert worker.main() == 0
    stdout.flush()
    payload = json.loads(raw_stdout.getvalue().decode("utf-8"))
    assert payload["pages"][0]["items"][0]["text"] == "Droit ©"


def test_validate_docling_isolated_protocol_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given une page native ou TARGETED_ENRICHMENT contient © et l'hôte Windows utilise CP-1252.
    # When les processus Docling isolés publient leur réponse et que le parent la consomme.
    # Then le protocole est UTF-8, les flux invalides deviennent des erreurs stables et aucun état générique n'est requis.
    native = _native_converter(tmp_path / "native")
    _assert_parent_protocol(*native, monkeypatch=monkeypatch)
    _assert_worker_protocol("app.source_processing.adapters.docling_native_worker", monkeypatch)

    granite = _granite_converter(tmp_path / "granite")
    _assert_parent_protocol(*granite, monkeypatch=monkeypatch)
    _assert_worker_protocol("app.source_processing.adapters.docling_granite_worker", monkeypatch)
