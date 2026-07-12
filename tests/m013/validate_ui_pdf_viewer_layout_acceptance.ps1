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
    CorpusPdfDocument,
    CorpusPdfScreenState,
    ui_get_response,
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


document = CorpusPdfDocument(
    document_id="DOC-M013-VIEWER-0001",
    title="_OceanofPDF.com_Markets_and_Momentum_-_James_F_Dalton",
    source_status="REGISTERED",
    diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",
    conversion_status="CONVERSION_NOT_REQUESTED",
    canonical_version_id=None,
    projection_status="PROJECTION_NOT_REQUESTED",
    selected=False,
)
state = CorpusPdfScreenState(
    documents=(document,),
    active_selected_document_ids=(),
    read_model_status="READ_MODEL_READY",
)

# Given un utilisateur ouvre le visualiseur PDF depuis le corpus.
# When le PDF est rendu dans la page locale.
# Then le cadre de visualisation occupe l'espace utile de la fenetre au lieu de rester a la taille iframe par defaut.
status_code, content_type, body = ui_get_response(
    path="/ui/documents/DOC-M013-VIEWER-0001/pdf",
    state=state,
)
assert_equal(status_code, 200, "Le visualiseur PDF doit etre servi.")
assert_equal(content_type, "text/html; charset=utf-8", "Le visualiseur doit etre HTML.")
assert_contains(body, 'class="pdf-viewer-page"', "La page doit porter le layout du visualiseur.")
assert_contains(body, 'class="pdf-viewer-frame"', "L'iframe PDF doit porter une classe de layout stable.")
assert_contains(body, "height: calc(100vh - 132px);", "L'iframe doit utiliser la hauteur disponible.")
assert_contains(body, "min-height: 640px;", "L'iframe doit rester lisible sur grand ecran.")
assert_contains(body, "width: 100%;", "L'iframe doit utiliser toute la largeur disponible.")
assert_contains(body, "border: 0;", "Le cadre navigateur ne doit pas reduire la surface utile.")
assert_contains(body, 'type="application/pdf"', "Le visualiseur doit declarer le type PDF.")
assert_not_contains(body, "<iframe title=\"PDF original\" src=\"/ui/documents/DOC-M013-VIEWER-0001/pdf/content\"></iframe>", "Le rendu ne doit plus utiliser l'iframe sans dimension.")

print("Test d'acceptation layout visualiseur PDF UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_pdf_viewer_layout_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation layout visualiseur PDF UI invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
