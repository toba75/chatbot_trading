"""Contrat de renumérotation publique des pages Granite (ADR-032)."""

from __future__ import annotations

import importlib


def test_granite_republie_la_page_locale_docling_dans_le_repere_source() -> None:
    # Given Granite convertit une unique page source 25 et Docling la renumérote localement 1.
    # When le worker Granite construit la réponse M-004.
    # Then la sortie porte la page publique 25 sans rechercher à tort la clé locale 25.
    worker = importlib.import_module("app.source_processing.adapters.docling_granite_worker")

    class _Page:
        size = type("_Size", (), {"width": 100.0, "height": 200.0})()

    class _Document:
        pages = {1: _Page()}

        @staticmethod
        def iterate_items(*, page_no):
            assert page_no == 1
            bbox = type("_Bbox", (), {"l": 10.0, "t": 20.0, "r": 90.0, "b": 180.0})()
            provenance = type("_Provenance", (), {"page_no": 1, "bbox": bbox})()
            item = type("_Item", (), {"text": "Texte Granite", "prov": [provenance]})()
            return ((item, 0),)

    assert worker._page_payload(
        document=_Document(),
        source_page_number=25,
        output_page_number=25,
    ) == {
        "page_number": 25,
        "items": [
            {
                "text": "Texte Granite",
                "bbox": [0.1, 0.1, 0.9, 0.9],
                "provenance": {"page_number": 25, "source": "granite_docling"},
            }
        ],
    }
