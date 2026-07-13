from __future__ import annotations

from pathlib import Path
import sys


def test_validate_ui_pdf_viewer_layout_unit() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '\nimport sys\n\nrepo_root = sys.argv[1]\nif repo_root not in sys.path:\n    sys.path.insert(0, repo_root)\n\nfrom app.platform.ui_corpus import CorpusPdfDocument, render_pdf_viewer  # noqa: E402\n\n\ndef assert_contains(text: str, expected: str, message: str) -> None:\n    if expected not in text:\n        raise AssertionError(f"{message} Texte obtenu: {text!r}")\n\n\ndef assert_not_contains(text: str, forbidden: str, message: str) -> None:\n    if forbidden in text:\n        raise AssertionError(f"{message} Texte obtenu: {text!r}")\n\n\ndocument = CorpusPdfDocument(\n    document_id="DOC-M013-VIEWER-0002",\n    title="<script>titre hostile</script>",\n    source_status="REGISTERED",\n    diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",\n    conversion_status="CONVERSION_NOT_REQUESTED",\n    canonical_version_id=None,\n    projection_status="PROJECTION_NOT_REQUESTED",\n    selected=False,\n)\n\nviewer = render_pdf_viewer(document)\nassert_contains(viewer, "&lt;script&gt;", "Le titre doit rester echappe dans le visualiseur.")\nassert_not_contains(viewer, "<script>titre hostile</script>", "Le titre brut ne doit pas etre injecte.")\nassert_contains(viewer, "html, body { height: 100%; margin: 0;", "La page doit neutraliser les marges navigateur.")\nassert_contains(viewer, "body.pdf-viewer-page", "Le layout doit etre borne au visualiseur PDF.")\nassert_contains(viewer, ".pdf-viewer-header", "Le header doit avoir une zone propre.")\nassert_contains(viewer, ".pdf-viewer-main { flex: 1; min-height: 0;", "La zone PDF doit pouvoir prendre l\'espace restant.")\nassert_contains(viewer, ".pdf-viewer-frame", "L\'iframe doit etre dimensionnee par CSS.")\nassert_contains(viewer, "height: calc(100vh - 132px);", "La hauteur ne doit pas rester implicite.")\nassert_contains(viewer, "min-height: 640px;", "Le PDF doit rester visible sans micro-frame.")\nassert_contains(viewer, "word-break: break-word;", "Les longs titres PDF ne doivent pas casser le layout.")\nassert_contains(viewer, \'class="pdf-viewer-frame"\', "L\'iframe doit recevoir la classe de visualisation.")\nassert_contains(viewer, \'type="application/pdf"\', "Le type PDF doit etre explicite.")\nassert_not_contains(viewer, "original_storage_ref", "Le visualiseur ne doit pas divulguer le stockage interne.")\nassert_not_contains(viewer, "C:\\\\", "Le visualiseur ne doit pas divulguer de chemin Windows.")\n\nprint("Tests unitaires layout visualiseur PDF UI: OK")'
        namespace = {'__name__': __name__, '__file__': str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), 'exec'), namespace)
    finally:
        sys.argv = original_argv
