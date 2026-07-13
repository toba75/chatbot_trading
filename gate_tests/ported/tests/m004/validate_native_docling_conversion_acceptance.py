"""Parcours d'acceptation d'un PDF natif réellement converti par Docling."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def _runtime_module():
    try:
        return importlib.import_module("app.source_processing.adapters.docling_native_conversion")
    except ModuleNotFoundError as error:
        pytest.fail("DOCLING_NATIVE_RUNTIME_ABSENT: le parcours réel Docling n'est pas câblé.")
        raise AssertionError("pytest.fail doit interrompre le test") from error


def _write_native_pdf(path: Path) -> None:
    """Produit un vrai PDF avec couche texte native, sans fixture synthétique Docling."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 16 Tf 72 720 Td (Conversion native Docling reelle) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(contents)
    with path.open("wb") as stream:
        writer.write(stream)


def test_native_pdf_is_converted_in_a_uv_isolated_offline_process(tmp_path: Path) -> None:
    # Given un PDF natif réel et les actifs Docling préchargés, hachés et scellés.
    # When le runner isolé du worker M-004 convertit le PDF NATIVE_STANDARD.
    # Then toutes les pages, leur provenance et la version Docling produite sont restituées.
    runtime = _runtime_module()
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    manifest_path = repository_root / "config" / "docling-assets.native.json"
    assets_root = repository_root / "data" / "docling_assets" / "native"
    assert manifest_path.is_file(), "CONVERSION_ASSET_MANIFEST_INVALID: manifeste Docling natif absent."
    assert assets_root.is_dir(), "CONVERSION_ASSET_MANIFEST_INVALID: actifs Docling natifs absents."

    source_pdf = tmp_path / "native.pdf"
    _write_native_pdf(source_pdf)
    request = runtime.NativeDoclingConversionRequest(
        document_id="DOC-0000000000000001",
        processing_run_id="RUN-M004-T003-ACCEPTANCE",
        source_sha256=hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        source_pdf_path=source_pdf,
        expected_page_numbers=(1,),
        routing_policy_version="routing-v1",
    )
    converter = runtime.IsolatedNativeDoclingConverter(
        asset_manifest_path=manifest_path,
        assets_root=assets_root,
        timeout_seconds=120.0,
    )

    response = converter.convert(request)
    assert response.tool_version == "2.111.0"
    assert tuple(page.page_number for page in response.pages) == (1,)
    assert all(item.provenance for page in response.pages for item in page.items)
