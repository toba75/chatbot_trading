"""Tests unitaires du layout du visualiseur PDF UI."""

from app.platform.ui_corpus import CorpusPdfDocument, render_pdf_viewer


def test_validate_ui_pdf_viewer_layout_unit() -> None:
    document = CorpusPdfDocument(
        document_id="DOC-M013-VIEWER-0002",
        title="<script>titre hostile</script>",
        authors=("Auteur",),
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
    viewer = render_pdf_viewer(document)
    assert "&lt;script&gt;" in viewer
    assert "<script>titre hostile</script>" not in viewer
    assert "html, body { height: 100%; margin: 0;" in viewer
    assert "body.pdf-viewer-page" in viewer
    assert ".pdf-viewer-header" in viewer
    assert ".pdf-viewer-main { flex: 1; min-height: 0;" in viewer
    assert ".pdf-viewer-frame" in viewer
    assert "height: calc(100vh - 132px);" in viewer
    assert "min-height: 640px;" in viewer
    assert "word-break: break-word;" in viewer
    assert 'class="pdf-viewer-frame"' in viewer
    assert 'type="application/pdf"' in viewer
    assert "original_storage_ref" not in viewer
    assert "C:\\" not in viewer
