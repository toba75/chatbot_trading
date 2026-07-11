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
    remove_from_active_selection,
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


searchable_document = CorpusPdfDocument(
    document_id="DOC-M013-UI-0001",
    title="Rapport annuel 2024",
    source_status="SOURCE_REGISTERED",
    diagnostic_status="DIAGNOSTIC_REQUESTED",
    conversion_status="CANONICAL_ACCEPTED",
    canonical_version_id="CANON-M013-UI-0001",
    projection_status="SEARCHABLE",
    selected=True,
)
blocked_document = CorpusPdfDocument(
    document_id="DOC-M013-UI-0002",
    title="Document en quarantaine",
    source_status="SOURCE_QUARANTINED",
    diagnostic_status="MANUAL_REVIEW",
    conversion_status="SOURCE_NOT_CANONICAL",
    canonical_version_id=None,
    projection_status="PROJECTION_NOT_FOUND",
    selected=False,
)
state = CorpusPdfScreenState(
    documents=(searchable_document, blocked_document),
    active_selected_document_ids=("DOC-M013-UI-0001",),
    read_model_status="READ_MODEL_READY",
)

# Given un utilisateur ouvre l'interface locale du chatbot.
# When il consulte le premier écran du corpus PDF.
# Then l'écran liste les PDF, leurs statuts publics, l'ajout documentaire,
# le retrait non destructif de la sélection active et la visualisation lecture seule.
status_code, content_type, body = ui_get_response(path="/", state=state)
assert_equal(status_code, 200, "L'écran corpus PDF doit être servi.")
assert_equal(content_type, "text/html; charset=utf-8", "Le premier écran doit être HTML.")
assert_contains(body, "Corpus PDF", "Le titre de l'écran corpus doit être visible.")
assert_contains(body, "Rapport annuel 2024", "Le PDF interrogeable doit être listé.")
assert_contains(body, "Document en quarantaine", "Le PDF bloqué doit rester visible.")
assert_contains(body, "SOURCE_QUARANTINED", "Le statut bloquant ne doit pas être masqué.")
assert_contains(body, "SEARCHABLE", "Le statut de projection interrogeable doit être visible.")
assert_contains(body, "POST /v1/documents", "L'ajout doit passer par le contrat public SP.")
assert_contains(body, "Retirer de la sélection active", "L'action non destructive doit remplacer la suppression.")
assert_contains(body, "/ui/documents/DOC-M013-UI-0001/pdf", "Le visualiseur PDF doit être ouvrable.")
assert_contains(body, 'data-selectable="false"', "Un document non SEARCHABLE ne doit pas être sélectionnable.")
assert_not_contains(body, "original_storage_ref", "Le chemin interne SP ne doit pas fuiter.")
assert_not_contains(body.lower(), "qdrant", "La collection technique KA ne doit pas fuiter.")
assert_not_contains(body.lower(), "postgres", "Le stockage interne ne doit pas fuiter.")
assert_not_contains(body.lower(), "supprimer", "Le premier écran ne doit pas proposer une suppression.")
assert_not_contains(body.lower(), "delete", "Le premier écran ne doit pas proposer une suppression technique.")
assert_not_contains(body.lower(), "purge", "Le premier écran ne doit pas proposer une purge.")

# Given un utilisateur renseigne explicitement les métadonnées du PDF.
# When l'UI construit la commande d'ajout documentaire.
# Then le payload contient original_content et bibliographic_metadata sans valeur inventée.
payload = build_registration_payload(
    original_content=b"%PDF-1.7\nfixture minimale",
    title="Rapport annuel 2024",
    issuer="OSTrading",
    document_date="2024-12-31",
    document_type="rapport_annuel",
    language="fr",
)
assert_contains(str(payload.keys()), "original_content", "Le contenu original doit être transmis.")
metadata = payload["bibliographic_metadata"]
assert_equal(metadata["title"], "Rapport annuel 2024", "Le titre doit venir du formulaire.")
assert_equal(metadata["issuer"], "OSTrading", "L'émetteur doit venir du formulaire.")
assert_equal(metadata["document_date"], "2024-12-31", "La date documentaire doit venir du formulaire.")
assert_equal(metadata["document_type"], "rapport_annuel", "Le type documentaire doit venir du formulaire.")
assert_equal(metadata["language"], "fr", "La langue doit venir du formulaire.")

# Given un PDF est sélectionné pour une conversation.
# When l'utilisateur le retire depuis le premier écran.
# Then seule la sélection active change; le document demeure dans le corpus affichable.
remaining_selection = remove_from_active_selection(
    selected_document_ids=("DOC-M013-UI-0001", "DOC-M013-UI-0003"),
    document_id="DOC-M013-UI-0001",
)
assert_equal(remaining_selection, ("DOC-M013-UI-0003",), "Le retrait doit seulement modifier la sélection active.")

# Given un utilisateur ouvre un PDF depuis la liste.
# When le visualiseur local est rendu.
# Then il affiche un cadre de visualisation sans divulguer le stockage interne.
viewer_status, viewer_content_type, viewer_body = ui_get_response(
    path="/ui/documents/DOC-M013-UI-0001/pdf",
    state=state,
)
assert_equal(viewer_status, 200, "Le visualiseur PDF doit être servi.")
assert_equal(viewer_content_type, "text/html; charset=utf-8", "Le visualiseur doit être HTML.")
assert_contains(viewer_body, "PDF original", "Le visualiseur doit nommer le PDF original.")
assert_contains(viewer_body, "DOC-M013-UI-0001", "Le visualiseur doit conserver l'identité publique.")
assert_not_contains(viewer_body, "original_storage_ref", "Le visualiseur ne doit pas divulguer le stockage SP.")
assert_not_contains(viewer_body, "C:\\", "Le visualiseur ne doit pas divulguer de chemin Windows.")

print("Test d'acceptation T-024 premier écran corpus PDF UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_corpus_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-024 premier écran corpus PDF UI invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
