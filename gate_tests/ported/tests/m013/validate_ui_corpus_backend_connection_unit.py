from __future__ import annotations

from pathlib import Path
import sys


def test_validate_ui_corpus_backend_connection_unit() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '\nimport sys\n\nrepo_root = sys.argv[1]\nif repo_root not in sys.path:\n    sys.path.insert(0, repo_root)\n\nfrom app.platform.ui_corpus import (  # noqa: E402\n    build_unavailable_corpus_pdf_state,\n    render_corpus_pdf_screen,\n)\nfrom app.platform.ui_document_api import ORCHESTRATOR_API_UNAVAILABLE  # noqa: E402\n\n\ndef assert_equal(actual: object, expected: object, message: str) -> None:\n    if actual != expected:\n        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")\n\n\ndef assert_contains(text: str, expected: str, message: str) -> None:\n    if expected not in text:\n        raise AssertionError(f"{message} Texte obtenu: {text!r}")\n\n\n# Given l\'appel HTTP réel à l\'orchestrateur échoue.\n# When l\'UI construit son état indisponible depuis cette erreur observée.\n# Then elle bloque les actions et rend le code public sans inventer d\'état métier.\nstate = build_unavailable_corpus_pdf_state(\n    public_error={"error_code": ORCHESTRATOR_API_UNAVAILABLE},\n)\nassert_equal(state.read_model_status, "READ_MODEL_UNAVAILABLE", "L\'indisponibilité réelle doit être visible.")\nassert_equal(state.documents, (), "Aucun document ne doit être inventé.")\nhtml = render_corpus_pdf_screen(state)\nassert_contains(html, ORCHESTRATOR_API_UNAVAILABLE, "Le code public doit être rendu.")\nassert_contains(html, "<fieldset disabled", "Les commandes doivent être bloquées sur erreur réelle.")\n\nprint("Tests unitaires frontière UI vers API orchestratrice: OK")'
        namespace = {'__name__': __name__, '__file__': str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), 'exec'), namespace)
    finally:
        sys.argv = original_argv
