"""Acceptation du corpus PDF avec extraction bibliographique post-projection."""

from __future__ import annotations

from app.platform.ui_corpus import CorpusPdfDocument, CorpusPdfScreenState, ui_get_response


def test_validate_ui_corpus_pdf_screen_acceptance() -> None:
    searchable = CorpusPdfDocument(
        document_id="DOC-M013-UI-0001",
        title="Rapport annuel 2024",
        authors=("Alice Exemple",),
        publication_year=2024,
        edition=None,
        metadata_status="EXTRACTED",
        source_status="REGISTERED",
        diagnostic_status="ROUTE_PLANNED",
        conversion_status="CANONICAL_ACCEPTED",
        canonical_version_id="CANON-M013-UI-0001",
        projection_status="SEARCHABLE",
        conversion_action_available=False,
        selected=True,
    )
    pending = CorpusPdfDocument(
        document_id="DOC-M013-UI-0002",
        title=None,
        authors=None,
        publication_year=None,
        edition=None,
        metadata_status="PENDING",
        source_status="REGISTERED",
        diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        conversion_action_available=False,
        selected=False,
    )
    state = CorpusPdfScreenState(
        documents=(searchable, pending),
        active_selected_document_ids=(searchable.document_id,),
        read_model_status="READ_MODEL_READY",
    )

    status, content_type, body = ui_get_response(path="/", state=state)

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Le PDF seul est admis" in body
    assert "Alice Exemple" in body
    assert "Métadonnées : PENDING (extraction après projection)" in body
    assert 'name="title"' not in body
    assert 'name="authors"' not in body
    assert 'action="/v1/documents/DOC-M013-UI-0002/diagnose"' in body
    assert 'data-selectable="false"' in body
