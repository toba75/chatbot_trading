"""Invariants unitaires du runtime Docling natif réellement isolé (ADR-032)."""

from __future__ import annotations

import hashlib
import io
import importlib
import json
from pathlib import Path
import subprocess

import pytest

from app.source_processing.application.publish_canonical_source import StoreCanonicalArtifactRequest
from app.source_processing.domain.canonical_source import CanonicalArtifactKind


def _runtime_module():
    # Given la branche ne possède encore aucun runtime Docling natif.
    # When cette tranche est commencée.
    # Then l'absence de l'adaptateur est un RED explicite, jamais un faux convertisseur.
    try:
        return importlib.import_module("app.source_processing.adapters.docling_native_conversion")
    except ModuleNotFoundError as error:
        pytest.fail("DOCLING_NATIVE_RUNTIME_ABSENT: l'adaptateur Docling natif isolé est requis.")
        raise AssertionError("pytest.fail doit interrompre le test") from error


def _manifest_payload(*, sha256: str, relative_path: str = "models/layout.bin") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "tool": "docling",
        "tool_version": "2.111.0",
        "assets": [{"relative_path": relative_path, "sha256": sha256}],
    }


def _store_request(*, content: bytes) -> StoreCanonicalArtifactRequest:
    digest = hashlib.sha256(content).hexdigest()
    return StoreCanonicalArtifactRequest(
        canonical_source_id="CSRC-0000000000000001",
        canonical_version_id="CVER-M004-T003-UNIT-0001",
        artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
        expected_artifact_ref=(
            "artifact:source_processing.canonical_sources/"
            "CSRC-0000000000000001/CVER-M004-T003-UNIT-0001/docling.json"
        ),
        artifact_sha256=digest,
        content_bytes=content,
    )


def _manifest_refuses_missing_or_divergent_assets(tmp_path: Path) -> None:
    runtime = _runtime_module()
    assets_root = tmp_path / "assets"
    assets_root.mkdir(parents=True)
    manifest_path = tmp_path / "native-assets.json"

    manifest_path.write_text(json.dumps(_manifest_payload(sha256="a" * 64)), encoding="utf-8")
    with pytest.raises(runtime.DoclingAssetManifestError, match="CONVERSION_ASSET_MANIFEST_INVALID"):
        runtime.DoclingAssetManifest.load(manifest_path=manifest_path, assets_root=assets_root)

    model_path = assets_root / "models" / "layout.bin"
    model_path.parent.mkdir()
    model_path.write_bytes("actif Docling versionné".encode("utf-8"))
    manifest_path.write_text(
        json.dumps(_manifest_payload(sha256=hashlib.sha256(model_path.read_bytes()).hexdigest())),
        encoding="utf-8",
    )
    manifest = runtime.DoclingAssetManifest.load(manifest_path=manifest_path, assets_root=assets_root)
    assert manifest.tool_version == "2.111.0"

    model_path.write_bytes("actif altéré".encode("utf-8"))
    with pytest.raises(runtime.DoclingAssetManifestError, match="CONVERSION_ASSET_MANIFEST_INVALID"):
        runtime.DoclingAssetManifest.load(manifest_path=manifest_path, assets_root=assets_root)


def _artifact_store_is_hashed_and_immutable(tmp_path: Path) -> None:
    runtime = _runtime_module()
    canonical_root = tmp_path / "canonical"
    store = runtime.CanonicalArtifactFileStore(root=canonical_root)
    assert canonical_root.is_dir()
    request = _store_request(content=b'{"schema_version":"1.0","producer":"Docling"}')

    stored = store.store_docling_json(request)
    assert stored.artifact_ref == request.expected_artifact_ref
    assert stored.artifact_sha256 == request.artifact_sha256
    assert store.store_docling_json(request) == stored

    artifact_path = tmp_path / "canonical" / "CSRC-0000000000000001" / "CVER-M004-T003-UNIT-0001" / "docling.json"
    artifact_path.write_bytes('{"contenu":"altéré"}'.encode("utf-8"))
    with pytest.raises(runtime.CanonicalArtifactStoreError, match="CANONICAL_ARTIFACT_IMMUTABILITY_VIOLATION"):
        store.store_docling_json(request)


def _runner_refuses_page_omission_and_missing_provenance() -> None:
    runtime = _runtime_module()
    request = runtime.NativeDoclingConversionRequest(
        document_id="DOC-0000000000000001",
        processing_run_id="RUN-M004-T003-UNIT",
        source_sha256="a" * 64,
        source_pdf_path=Path("C:/native/document.pdf"),
        expected_page_numbers=(1, 2),
        routing_policy_version="routing-v1",
    )

    with pytest.raises(runtime.DoclingNativeConversionError, match="DOCLING_PAGE_MANIFEST_MISMATCH"):
        runtime.NativeDoclingConversionResponse.from_payload(
            request=request,
            payload={"schema_version": "1.0", "tool_version": "2.111.0", "pages": [{"page_number": 1, "items": [{"text": "Texte", "bbox": [0, 0, 1, 1]}]}]},
        )

    with pytest.raises(runtime.DoclingNativeConversionError, match="DOCLING_PROVENANCE_MISSING"):
        runtime.NativeDoclingConversionResponse.from_payload(
            request=request,
            payload={
                "schema_version": "1.0",
                "tool_version": "2.111.0",
                "pages": [
                    {"page_number": 1, "items": [{"text": "Texte", "bbox": [0, 0, 1, 1], "provenance": None}]},
                    {"page_number": 2, "items": [{"text": "Texte", "bbox": [0, 0, 1, 1], "provenance": None}]},
                ],
            },
        )


def _isolated_native_converter(tmp_path: Path):
    runtime = _runtime_module()
    assets_root = tmp_path / "assets"
    model_path = assets_root / "models" / "layout.bin"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"actif Docling scellé")
    manifest_path = tmp_path / "native-assets.json"
    manifest_path.write_text(
        json.dumps(
            _manifest_payload(
                sha256=hashlib.sha256(model_path.read_bytes()).hexdigest()
            )
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7\nsource unicode\n%%EOF\n")
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
    ), request


def test_native_isolated_protocol_uses_utf8_bytes_and_names_invalid_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given une page native contient le caractère Unicode © dans sa sortie Docling.
    # When le parent reçoit la réponse du processus isolé.
    # Then le protocole transporte des octets UTF-8 et un flux invalide devient DOCLING_STANDARD_UNAVAILABLE.
    runtime, converter, request = _isolated_native_converter(tmp_path)
    response = json.dumps(
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
                            "provenance": {"page_number": 1, "source": "docling"},
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    def valid_run(*args, **kwargs):
        assert isinstance(kwargs["input"], bytes)
        assert "text" not in kwargs
        assert "encoding" not in kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=response, stderr=b"\xa9")

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
    with pytest.raises(runtime.DoclingNativeConversionError, match="DOCLING_STANDARD_UNAVAILABLE"):
        converter.convert(request)


def test_native_worker_emits_utf8_even_when_the_host_stream_is_cp1252(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given le processus Docling tourne sous un hôte Windows dont stdout est CP-1252.
    # When il publie une réponse contenant ©.
    # Then le protocole borné reste UTF-8 et le parent peut le décoder sans ambiguïté.
    worker = importlib.import_module("app.source_processing.adapters.docling_native_worker")
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
    assert "Droit ©" in json.loads(raw_stdout.getvalue().decode("utf-8"))["pages"][0]["items"][0]["text"]


def test_validate_native_docling_conversion_unit(tmp_path: Path) -> None:
    """Given le protocole Docling natif, when ses invariants sont évalués, then aucun état incomplet ne passe."""
    _manifest_refuses_missing_or_divergent_assets(tmp_path / "manifest")
    _artifact_store_is_hashed_and_immutable(tmp_path / "store")
    _runner_refuses_page_omission_and_missing_provenance()
