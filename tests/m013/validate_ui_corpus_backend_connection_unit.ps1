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

from app.platform.ui_corpus import (  # noqa: E402
    build_unavailable_corpus_pdf_state,
    render_corpus_pdf_screen,
)
from app.platform.ui_document_api import ORCHESTRATOR_API_UNAVAILABLE  # noqa: E402


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


# Given l'appel HTTP réel à l'orchestrateur échoue.
# When l'UI construit son état indisponible depuis cette erreur observée.
# Then elle bloque les actions et rend le code public sans inventer d'état métier.
state = build_unavailable_corpus_pdf_state(
    public_error={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
)
assert_equal(state.read_model_status, "READ_MODEL_UNAVAILABLE", "L'indisponibilité réelle doit être visible.")
assert_equal(state.documents, (), "Aucun document ne doit être inventé.")
html = render_corpus_pdf_screen(state)
assert_contains(html, ORCHESTRATOR_API_UNAVAILABLE, "Le code public doit être rendu.")
assert_contains(html, "<fieldset disabled", "Les commandes doivent être bloquées sur erreur réelle.")

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
