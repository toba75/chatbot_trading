$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import tempfile

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.ui_corpus import (  # noqa: E402
    build_corpus_pdf_state_from_corpus_root,
    ui_get_pdf_content_response,
    ui_get_response,
)
from app.platform.configuration import load_application_configuration  # noqa: E402
from app.platform.local_runtime import _local_post_response  # noqa: E402


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_not_contains(text: str, forbidden: str, message: str) -> None:
    if forbidden in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def runtime_configuration_for(corpus_root: Path):
    template_path = Path(repo_root) / "config" / "application.yaml"
    config_text = template_path.read_text(encoding="utf-8")
    corpus_root_text = corpus_root.as_posix()
    config_text = config_text.replace(
        "  corpus_root: data/corpus",
        f'  corpus_root: "{corpus_root_text}"',
    )
    config_path = corpus_root.parent / "application.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    return load_application_configuration(config_path=config_path, environment_snapshot={})


with tempfile.TemporaryDirectory() as temporary_root:
    corpus_root = Path(temporary_root) / "corpus"
    corpus_root.mkdir()
    pdf_content = b"%PDF-1.7\nbackend fixture\n%%EOF\n"
    pdf_path = corpus_root / "Alpha Strategy.pdf"
    pdf_path.write_bytes(pdf_content)
    (corpus_root / "notes.txt").write_text("hors corpus", encoding="utf-8")

    expected_document_id = "DOC-" + sha256(pdf_content).hexdigest()[:16].upper()

    # Given le backend local possede un corpus PDF configure.
    # When l'UI construit son read-model depuis ce corpus.
    # Then le premier ecran affiche le PDF reel sans exposer le chemin de stockage.
    state = build_corpus_pdf_state_from_corpus_root(corpus_root=corpus_root)
    assert_equal(state.read_model_status, "READ_MODEL_READY", "Le read-model corpus doit etre branche.")
    assert_equal(len(state.documents), 1, "Seuls les fichiers PDF du corpus doivent etre affiches.")
    assert_equal(state.documents[0].document_id, expected_document_id, "Le document_id doit venir du contenu PDF.")
    assert_equal(state.documents[0].projection_status, "PROJECTION_NOT_REQUESTED", "Un PDF brut ne doit pas devenir SEARCHABLE.")
    assert_equal(state.documents[0].selected, False, "Un PDF non indexe ne doit pas etre selectionne.")

    status_code, content_type, body = ui_get_response(path="/", state=state)
    assert_equal(status_code, 200, "L'ecran corpus doit etre servi.")
    assert_equal(content_type, "text/html; charset=utf-8", "L'ecran corpus doit rester HTML.")
    assert_contains(body, "Alpha Strategy", "Le PDF du corpus doit apparaitre dans l'UI.")
    assert_contains(body, expected_document_id, "L'identite publique doit etre visible.")
    assert_contains(body, "SOURCE_REGISTERED", "Le statut source issu du corpus doit etre visible.")
    assert_contains(body, "PROJECTION_NOT_REQUESTED", "Le statut projection non interrogeable doit etre visible.")
    assert_contains(body, 'data-selectable="false"', "Le PDF brut ne doit pas etre selectionnable.")
    assert_not_contains(body, str(corpus_root), "Le chemin interne du corpus ne doit pas fuiter.")
    assert_not_contains(body, "original_storage_ref", "La reference de stockage SP ne doit pas fuiter.")
    assert_not_contains(body.lower(), "qdrant", "Le stockage KA ne doit pas fuiter.")

    viewer_status, viewer_content_type, viewer_body = ui_get_response(
        path=f"/ui/documents/{expected_document_id}/pdf",
        state=state,
    )
    assert_equal(viewer_status, 200, "Le visualiseur public doit etre servi.")
    assert_equal(viewer_content_type, "text/html; charset=utf-8", "Le visualiseur doit etre HTML.")
    assert_contains(viewer_body, f"/ui/documents/{expected_document_id}/pdf/content", "Le visualiseur doit pointer vers le contenu controle.")
    assert_not_contains(viewer_body, str(corpus_root), "Le visualiseur ne doit pas divulguer le chemin local.")

    content_status, content_type, response_body = ui_get_pdf_content_response(
        path=f"/ui/documents/{expected_document_id}/pdf/content",
        corpus_root=corpus_root,
    )
    assert_equal(content_status, 200, "Le contenu PDF doit etre servi depuis le backend local.")
    assert_equal(content_type, "application/pdf", "Le contenu original doit garder son type PDF.")
    assert_equal(response_body, pdf_content, "Le contenu servi doit etre le PDF original.")

    # Given l'utilisateur clique sur Diagnostiquer depuis l'UI locale.
    # When le formulaire POST /v1/documents/{document_id}/diagnose arrive sur le service ui.
    # Then le runtime local reconnait la commande documentaire et publie un statut public explicite.
    runtime_configuration = runtime_configuration_for(corpus_root)
    diagnosis_status, diagnosis_body = _local_post_response(
        service_id="ui",
        path=f"/v1/documents/{expected_document_id}/diagnose",
        body={},
        application_configuration=runtime_configuration,
    )
    assert_equal(diagnosis_status, 202, "Le clic Diagnostiquer ne doit pas retourner ENDPOINT_NOT_FOUND.")
    assert_equal(
        diagnosis_body,
        {"document_id": expected_document_id, "diagnostic_status": "DIAGNOSTIC_REQUESTED"},
        "La reponse diagnostic doit rester minimale et publique.",
    )

    repeated_status, repeated_body = _local_post_response(
        service_id="ui",
        path=f"/v1/documents/{expected_document_id}/diagnose",
        body={},
        application_configuration=runtime_configuration,
    )
    assert_equal(repeated_status, 409, "Un second clic ne doit pas relancer silencieusement le diagnostic.")
    assert_equal(
        repeated_body,
        {"error_code": "DIAGNOSTIC_ALREADY_REQUESTED", "document_id": expected_document_id},
        "La repetition doit produire une erreur publique stable.",
    )

print("Test d'acceptation connexion backend UI corpus PDF: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_backend_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Test d'acceptation connexion backend UI corpus PDF invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
