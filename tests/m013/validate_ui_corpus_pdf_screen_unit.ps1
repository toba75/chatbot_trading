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
    build_registration_payload,
    ensure_no_destructive_ui_fields,
    remove_from_active_selection,
    render_corpus_pdf_screen,
    render_pdf_viewer,
)


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_not_contains(text: str, forbidden: str, message: str) -> None:
    if forbidden in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


assert_raises(
    "document_id invalide",
    lambda: CorpusPdfDocument(
        document_id="BAD-0001",
        title="Rapport",
        source_status="SOURCE_REGISTERED",
        diagnostic_status="DIAGNOSTIC_REQUESTED",
        conversion_status="CANONICAL_ACCEPTED",
        canonical_version_id="CANON-0001",
        projection_status="SEARCHABLE",
        selected=True,
    ),
)
assert_raises(
    "statut source public invalide",
    lambda: CorpusPdfDocument(
        document_id="DOC-M013-UI-0001",
        title="Rapport",
        source_status="DELETE_REQUESTED",
        diagnostic_status="DIAGNOSTIC_REQUESTED",
        conversion_status="CANONICAL_ACCEPTED",
        canonical_version_id="CANON-0001",
        projection_status="SEARCHABLE",
        selected=True,
    ),
)
assert_raises(
    "titre requis",
    lambda: CorpusPdfDocument(
        document_id="DOC-M013-UI-0001",
        title="",
        source_status="SOURCE_REGISTERED",
        diagnostic_status="DIAGNOSTIC_REQUESTED",
        conversion_status="CANONICAL_ACCEPTED",
        canonical_version_id="CANON-0001",
        projection_status="SEARCHABLE",
        selected=True,
    ),
)

unsafe_document = CorpusPdfDocument(
    document_id="DOC-M013-UI-0001",
    title="<script>alert('x')</script>",
    source_status="SOURCE_REGISTERED",
    diagnostic_status="DIAGNOSTIC_REQUESTED",
    conversion_status="CANONICAL_ACCEPTED",
    canonical_version_id="CANON-M013-UI-0001",
    projection_status="SEARCHABLE",
    selected=True,
)
state = CorpusPdfScreenState(
    documents=(unsafe_document,),
    active_selected_document_ids=("DOC-M013-UI-0001",),
    read_model_status="READ_MODEL_READY",
)
html = render_corpus_pdf_screen(state)
assert_contains(html, "&lt;script&gt;", "Le titre documentaire doit être échappé.")
assert_not_contains(html, "<script>alert", "Le HTML ne doit pas injecter le titre brut.")
assert_contains(html, 'data-action="retirer_selection_active"', "L'action de retrait doit être non destructive.")
assert_not_contains(html.lower(), "delete", "Aucun contrôle delete ne doit être rendu.")
assert_not_contains(html.lower(), "supprimer", "Aucun contrôle supprimer ne doit être rendu.")
assert_not_contains(html.lower(), "purge", "Aucun contrôle purge ne doit être rendu.")

viewer = render_pdf_viewer(unsafe_document)
assert_contains(viewer, "PDF original", "Le visualiseur doit être explicite.")
assert_contains(viewer, "DOC-M013-UI-0001", "Le visualiseur doit afficher l'identifiant public.")
assert_not_contains(viewer, "original_storage_ref", "Le visualiseur ne doit pas exposer de stockage interne.")

payload = build_registration_payload(
    original_content=b"%PDF-1.7\n",
    title="Rapport",
    issuer="Emetteur",
    document_date="DATE_NON_RENSEIGNEE",
    document_type="rapport",
    language="fr",
)
assert_equal(payload["bibliographic_metadata"]["document_date"], "DATE_NON_RENSEIGNEE", "La date explicite non renseignée doit être conservée.")
assert_raises(
    "original_content requis",
    lambda: build_registration_payload(
        original_content=b"",
        title="Rapport",
        issuer="Emetteur",
        document_date="2024-01-01",
        document_type="rapport",
        language="fr",
    ),
)
assert_raises(
    "title requis",
    lambda: build_registration_payload(
        original_content=b"%PDF-1.7\n",
        title="",
        issuer="Emetteur",
        document_date="2024-01-01",
        document_type="rapport",
        language="fr",
    ),
)
assert_raises(
    "champ UI destructif interdit",
    lambda: ensure_no_destructive_ui_fields({"delete": True}),
)
assert_raises(
    "champ UI interne interdit",
    lambda: ensure_no_destructive_ui_fields({"original_storage_ref": "/var/lib/documents/a.pdf"}),
)
assert_raises(
    "document absent de la sélection active",
    lambda: remove_from_active_selection(
        selected_document_ids=("DOC-M013-UI-0002",),
        document_id="DOC-M013-UI-0001",
    ),
)

remaining = remove_from_active_selection(
    selected_document_ids=("DOC-M013-UI-0001", "DOC-M013-UI-0002"),
    document_id="DOC-M013-UI-0001",
)
assert_equal(remaining, ("DOC-M013-UI-0002",), "Le retrait doit préserver les autres documents sélectionnés.")

print("Tests unitaires T-024 premier écran corpus PDF UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_corpus_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires T-024 premier écran corpus PDF UI invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
