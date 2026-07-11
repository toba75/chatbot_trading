$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.local_runtime import _local_post_response  # noqa: E402
from app.platform.ui_corpus import (  # noqa: E402
    build_unconnected_corpus_pdf_state,
    render_corpus_pdf_screen,
    ui_unavailable_pdf_content_response,
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_not_contains(text: str, forbidden: str, message: str) -> None:
    if forbidden in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_raises(expected_fragment: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


# Given les contrats documentaires de l'API orchestratrice ne sont pas câblés.
# When l'UI construit le premier écran.
# Then les fonctions documentaires restent explicitement non opérationnelles.
state = build_unconnected_corpus_pdf_state()
assert_equal(state.read_model_status, "READ_MODEL_NOT_CONNECTED", "Le read-model doit déclarer l'absence de câblage API.")
assert_equal(state.documents, (), "Aucun document ne doit être inventé depuis un stockage direct.")

html = render_corpus_pdf_screen(state)
assert_contains(html, "ORCHESTRATOR_API_CONTRACT_NOT_WIRED", "Le blocage API doit être visible.")
assert_contains(html, "Fonction UI non ", "L'indisponibilité doit être explicite.")
assert_contains(html, "<fieldset disabled", "Le formulaire d'ajout doit être désactivé.")
assert_not_contains(html, ">Diagnostiquer</button>", "Aucune commande de diagnostic ne doit être simulée.")

diagnosis_path = "/v1/documents/DOC-FFFFFFFFFFFFFFFF/diagnose"
status_code, body = _local_post_response(
    service_id="ui",
    path=diagnosis_path,
    body={},
)
assert_equal(status_code, 503, "Une commande UI non câblée doit être refusée.")
assert_equal(
    body,
    {
        "error_code": "UI_FUNCTION_NOT_OPERATIONAL",
        "reason": "ORCHESTRATOR_API_CONTRACT_NOT_WIRED",
        "endpoint": diagnosis_path,
    },
    "Le refus doit nommer le contrat API non câblé sans fabriquer de statut métier.",
)

registration_status, registration_body = _local_post_response(
    service_id="ui",
    path="/v1/documents",
    body={"multipart_body": "non interprété par l'UI"},
)
assert_equal(registration_status, 503, "L'ajout PDF non câblé doit être refusé avant interprétation métier.")
assert_equal(registration_body["reason"], "ORCHESTRATOR_API_CONTRACT_NOT_WIRED", "L'ajout doit exposer le même blocage API.")

content_status, content_type, content_body = ui_unavailable_pdf_content_response(
    path="/ui/documents/DOC-FFFFFFFFFFFFFFFF/pdf/content",
)
assert_equal(content_status, 503, "Le contenu PDF ne doit pas être lu directement.")
assert_equal(content_type, "text/plain; charset=utf-8", "Le blocage PDF doit rester public.")
assert_contains(content_body.decode("utf-8"), "ORCHESTRATOR_API_CONTRACT_NOT_WIRED", "Le contenu doit expliquer le blocage API.")

assert_raises(
    "chemin contenu PDF invalide",
    lambda: ui_unavailable_pdf_content_response(path="/ui/documents/DOC-FFFFFFFFFFFFFFFF/pdf"),
)

print("Tests unitaires frontière UI vers API orchestratrice: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_backend_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires frontière UI vers API orchestratrice invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
