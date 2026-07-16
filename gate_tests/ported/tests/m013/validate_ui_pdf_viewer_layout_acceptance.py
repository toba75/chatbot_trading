"""Acceptation du layout du visualiseur PDF UI."""

from app.platform.ui_corpus import CorpusPdfDocument, CorpusPdfScreenState, ui_get_response


def test_validate_ui_pdf_viewer_layout_acceptance() -> None:
    document = CorpusPdfDocument(
        document_id="DOC-M013-VIEWER-0001",
        title="Markets and Momentum",
        authors=("James F. Dalton",),
        publication_year=None,
        edition=None,
        metadata_status="EXTRACTED",
        source_status="REGISTERED",
        diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        conversion_action_available=False,
        selected=False,
    )
    state = CorpusPdfScreenState(
        documents=(document,),
        active_selected_document_ids=(),
        read_model_status="READ_MODEL_READY",
    )
    status, content_type, body = ui_get_response(
        path="/ui/documents/DOC-M013-VIEWER-0001/pdf",
        state=state,
    )
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert 'class="pdf-viewer-page"' in body
    assert 'class="pdf-viewer-frame"' in body
    assert "height: calc(100vh - 132px);" in body
    assert "min-height: 640px;" in body
    assert "width: 100%;" in body
    assert "border: 0;" in body
    assert 'type="application/pdf"' in body
