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

from app.platform.ui_corpus import CorpusPdfDocument, render_pdf_viewer  # noqa: E402


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_not_contains(text: str, forbidden: str, message: str) -> None:
    if forbidden in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


document = CorpusPdfDocument(
    document_id="DOC-M013-VIEWER-0002",
    title="<script>titre hostile</script>",
    source_status="SOURCE_REGISTERED",
    diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",
    conversion_status="CONVERSION_NOT_REQUESTED",
    canonical_version_id=None,
    projection_status="PROJECTION_NOT_REQUESTED",
    selected=False,
)

viewer = render_pdf_viewer(document)
assert_contains(viewer, "&lt;script&gt;", "Le titre doit rester echappe dans le visualiseur.")
assert_not_contains(viewer, "<script>titre hostile</script>", "Le titre brut ne doit pas etre injecte.")
assert_contains(viewer, "html, body { height: 100%; margin: 0;", "La page doit neutraliser les marges navigateur.")
assert_contains(viewer, "body.pdf-viewer-page", "Le layout doit etre borne au visualiseur PDF.")
assert_contains(viewer, ".pdf-viewer-header", "Le header doit avoir une zone propre.")
assert_contains(viewer, ".pdf-viewer-main { flex: 1; min-height: 0;", "La zone PDF doit pouvoir prendre l'espace restant.")
assert_contains(viewer, ".pdf-viewer-frame", "L'iframe doit etre dimensionnee par CSS.")
assert_contains(viewer, "height: calc(100vh - 132px);", "La hauteur ne doit pas rester implicite.")
assert_contains(viewer, "min-height: 640px;", "Le PDF doit rester visible sans micro-frame.")
assert_contains(viewer, "word-break: break-word;", "Les longs titres PDF ne doivent pas casser le layout.")
assert_contains(viewer, 'class="pdf-viewer-frame"', "L'iframe doit recevoir la classe de visualisation.")
assert_contains(viewer, 'type="application/pdf"', "Le type PDF doit etre explicite.")
assert_not_contains(viewer, "original_storage_ref", "Le visualiseur ne doit pas divulguer le stockage interne.")
assert_not_contains(viewer, "C:\\", "Le visualiseur ne doit pas divulguer de chemin Windows.")

print("Tests unitaires layout visualiseur PDF UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_pdf_viewer_layout_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires layout visualiseur PDF UI invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
