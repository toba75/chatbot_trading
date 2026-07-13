$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$env:M013_REVIEW3_UI_REPO = $repoRoot

@'
from __future__ import annotations

from pathlib import Path
import os

from app.platform.local_authorization import LocalMutationAuthorizer
from app.platform.ui_corpus import CorpusPdfDocument, CorpusPdfScreenState, render_corpus_pdf_screen, render_document_inspection, render_pdf_viewer
from app.source_processing.adapters.postgres_document_persistence import CorpusQuotaExceededError, DocumentCorpusStatusRow

repo = Path(os.environ["M013_REVIEW3_UI_REPO"])


# Given le corpus contient plus de cent documents,
# When le navigateur ouvre une page,
# Then une seule page bornée est chargée et la navigation reste explicite.
document = CorpusPdfDocument(
    document_id="DOC-M013-UI-SECURITY-0001",
    title="Rapport borné",
    source_status="REGISTERED",
    diagnostic_status="FAILED",
    conversion_status="CONVERSION_NOT_REQUESTED",
    canonical_version_id=None,
    projection_status="PROJECTION_NOT_REQUESTED",
    manual_review_reason=None,
    failure_error_code="PDF_CORRUPTED",
    selected=False,
)
state = CorpusPdfScreenState(
    documents=(document,),
    active_selected_document_ids=(),
    read_model_status="READ_MODEL_READY",
    current_cursor="DOC-M013-UI-SECURITY-0000",
    next_cursor="DOC-M013-UI-SECURITY-0100",
)
body = render_corpus_pdf_screen(state)
for marker in (
    'name="cursor"',
    "Page suivante",
    "Retour au début",
    "PDF_CORRUPTED",
    "50 Mio maximum",
    'name="title" maxlength="512"',
    '<meta name="viewport"',
):
    assert marker in body, marker
viewer = render_pdf_viewer(document)
assert '<meta name="viewport"' in viewer
assert "Télécharger le PDF original" in viewer


# Given conversion/indexation M-004 n'est pas livrée,
# When l'UI reçoit le contrat d'indisponibilité,
# Then elle ne conseille jamais de réessayer un composant absent.
response = type("Response", (), {"status_code": 409, "payload": {"error_code": "CONVERSION_NOT_REQUESTED"}})()
error_page = render_document_inspection(title="Conversion", response=response)
assert "fonctionnalité non livrée" in error_page
assert "réessayez" not in error_page.casefold()
assert '<meta name="viewport"' in error_page


# Given une mutation locale persistante,
# When le token backend est absent ou trop court,
# Then l'autorisation refuse explicitement sans protéger les lectures.
secret = b"s" * 32
authorizer = LocalMutationAuthorizer(secret=secret)
assert authorizer.authorize(method="GET", path="/health", authorization_header=None) is None
assert authorizer.authorize(method="GET", path="/v1/documents", authorization_header=None) is None
assert authorizer.authorize(method="POST", path="/v1/documents", authorization_header=None) == (401, "LOCAL_API_TOKEN_REQUIRED")
assert authorizer.authorize(method="POST", path="/v1/documents", authorization_header="Bearer mauvais") == (403, "LOCAL_API_TOKEN_INVALID")
assert authorizer.authorize(method="POST", path="/v1/documents", authorization_header=f"Bearer {secret.decode()}") is None
try:
    LocalMutationAuthorizer(secret=b"court")
except ValueError as exc:
    assert str(exc) == "LOCAL_API_TOKEN_TOO_SHORT"
else:
    raise AssertionError("token local court accepté")


# Le read-model léger ne transporte aucun manifeste, page ou route.
row = DocumentCorpusStatusRow(
    document_id="DOC-M013-UI-SECURITY-0001",
    title="Rapport borné",
    document_status="REGISTERED",
    diagnostic_status="FAILED",
    conversion_status="CONVERSION_NOT_REQUESTED",
    canonical_version_id=None,
    manual_review_reason=None,
    failure_error_code="PDF_CORRUPTED",
)
assert not hasattr(row, "manifest") and not hasattr(row, "pages") and not hasattr(row, "routes")
assert issubclass(CorpusQuotaExceededError, RuntimeError)

ui_client = (repo / "app/platform/ui_document_api.py").read_text(encoding="utf-8")
ui_runtime = (repo / "app/platform/local_runtime.py").read_text(encoding="utf-8")
api_router = (repo / "app/source_processing/adapters/http.py").read_text(encoding="utf-8")
persistence = (repo / "app/source_processing/adapters/postgres_document_persistence.py").read_text(encoding="utf-8")
for forbidden in ("upload.read(max_pdf_bytes + 1)", "response.read()"):
    assert forbidden not in api_router + ui_client, forbidden
for marker in (
    "UiDocumentApiStreamResponse",
    "request_stream",
    "BoundedThreadingHTTPServer",
    "UI_TRANSFER_CAPACITY_EXHAUSTED",
    "_validate_same_origin_request",
    "socket_timeout_seconds",
):
    assert marker in ui_client + ui_runtime, marker
for marker in ("list_document_status_rows", "corpus_quota", "FOR UPDATE", "CORPUS_QUOTA_EXCEEDED"):
    assert marker in persistence, marker

migration = repo / "deploy/postgres/migrations/009_corpus_quota.sql"
assert migration.is_file()
sql = migration.read_text(encoding="utf-8")
for marker in ("corpus_quota", "corpus_original_reservations", "CHECK", "PRIMARY KEY"):
    assert marker in sql, marker

print("review3-ui-security=pagination; streaming; auth; quota; accessibilité")
'@ | & $pythonExecutable -B -
$exitCode = $LASTEXITCODE
Remove-Item Env:M013_REVIEW3_UI_REPO -ErrorAction SilentlyContinue
if ($exitCode -ne 0) { throw "M013_REVIEW3_UI_SECURITY_ACCEPTANCE_RED" }

Write-Host "UI, sécurité et quota de revue 3: OK"
