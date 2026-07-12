$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.document_public_statuses import (
    PublicConversionStatus,
    PublicDiagnosticStatus,
    PublicSourceStatus,
)
from app.platform.configuration import load_application_configuration
from app.platform.local_runtime import build_ui_orchestrator_origin
from app.platform.ui_corpus import render_corpus_pdf_screen, render_document_inspection
from app.platform.ui_document_api import (
    UiDocumentApiClient,
    UiDocumentApiResponse,
    UiDocumentJsonResponse,
)


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)

    def request(self, *, method, path, body, content_type):
        del method, path, body, content_type
        return self.responses.pop(0)


def response(payload, status=200):
    return UiDocumentApiResponse(
        status_code=status,
        content_type="application/json",
        body=json.dumps(payload).encode("utf-8"),
    )


def assert_rejected(payload, expected_fragment):
    client = UiDocumentApiClient(transport=QueueTransport([response(payload)]))
    try:
        client.read_diagnostic("DOC-M013-UI-CONTRACT")
    except ValueError as exc:
        assert expected_fragment in str(exc), str(exc)
        return
    raise AssertionError(f"Diagnostic invalide accepté: {expected_fragment}")


# Given SP expose ses statuts réels.
# When le client UI les parse.
# Then une définition partagée unique interdit les anciens statuts simulés.
assert {status.value for status in PublicSourceStatus} == {"REGISTERED", "QUARANTINED"}
assert {status.value for status in PublicDiagnosticStatus} == {
    "DIAGNOSTIC_NOT_REQUESTED",
    "MANIFEST_CREATED",
    "DIAGNOSED",
    "ROUTE_PLANNED",
    "MANUAL_REVIEW",
    "QUARANTINED",
    "REJECTED",
    "FAILED",
}
assert {status.value for status in PublicConversionStatus} == {
    "CONVERSION_NOT_REQUESTED",
    "CONVERSION_REQUESTED",
    "QA_REJECTED",
    "CANONICAL_ACCEPTED",
}

document_id = "DOC-M013-UI-CONTRACT"
valid_diagnostic = {
    "document_id": document_id,
    "diagnostic_status": "ROUTE_PLANNED",
    "source_page_count": 2,
    "diagnosed_page_count": 2,
    "manual_review_reason": None,
    "manifest": [
        {"page_number": 1, "manifest_status": "PRESENT"},
        {"page_number": 2, "manifest_status": "PRESENT"},
    ],
    "pages": [
        {
            "page_number": number,
            "manifest_status": "PRESENT",
            "diagnostic": {
                "page_state": "NATIVE_OK", "native_text_state": "RELIABLE",
                "image_state": "NONE", "existing_ocr_state": "NONE",
                "layout_complexity": "SIMPLE", "corruption_state": "NONE",
                "mixed_content_detected": False, "has_table": False,
                "has_formula": False, "diagnostic_version": "diag-v1",
                "justification": f"Signaux réels page {number}.",
            },
            "route": {
                "route_name": "NATIVE_STANDARD", "decision_mode": "AUTO",
                "confidence_score": 0.99, "preprocessing_action": "NONE",
                "routing_policy_version": "routing-v1",
                "justification": f"Route réelle page {number}.",
            },
        }
        for number in (1, 2)
    ],
}
client = UiDocumentApiClient(transport=QueueTransport([response(valid_diagnostic)]))
assert client.read_diagnostic(document_id).status_code == 200

wrong_document = dict(valid_diagnostic, document_id="DOC-OTHER")
assert_rejected(wrong_document, "autre document")
duplicate_pages = dict(valid_diagnostic, pages=[valid_diagnostic["pages"][0], valid_diagnostic["pages"][0]])
assert_rejected(duplicate_pages, "pages")
incomplete_manifest = dict(valid_diagnostic, manifest=valid_diagnostic["manifest"][:1])
assert_rejected(incomplete_manifest, "manifeste")
incoherent_count = dict(valid_diagnostic, diagnosed_page_count=1)
assert_rejected(incoherent_count, "comptage")

# La nullabilité de la conversion est gouvernée par le statut public.
for invalid_conversion in (
    {
        "document_id": document_id,
        "conversion_status": "QA_REJECTED",
        "qa_rejection_error_code": None,
        "canonical_version_id": None,
    },
    {
        "document_id": document_id,
        "conversion_status": "CANONICAL_ACCEPTED",
        "qa_rejection_error_code": None,
        "canonical_version_id": None,
    },
):
    conversion_client = UiDocumentApiClient(transport=QueueTransport([response(invalid_conversion)]))
    try:
        conversion_client.read_conversion(document_id)
    except ValueError:
        pass
    else:
        raise AssertionError("Nullabilité conversion incohérente acceptée")

configuration = load_application_configuration(
    Path(sys.argv[1]) / "config" / "application.example.yaml",
    {},
)
assert build_ui_orchestrator_origin(configuration, execution_context="host") == "http://127.0.0.1:8080"
assert build_ui_orchestrator_origin(configuration, execution_context="compose") == "http://orchestrator-api:8080"
try:
    build_ui_orchestrator_origin(configuration, execution_context="invented")
except ValueError as exc:
    assert "contexte" in str(exc)
else:
    raise AssertionError("Contexte d'exécution UI inconnu accepté")

inspection = render_document_inspection(
    title="Diagnostic",
    response=UiDocumentJsonResponse(status_code=200, payload=valid_diagnostic),
)
assert '<section aria-labelledby="resume-diagnostic">' in inspection
assert "Page 1" in inspection and "Page 2" in inspection
error_inspection = render_document_inspection(
    title="Diagnostic",
    response=UiDocumentJsonResponse(
        status_code=503,
        payload={"error_code": "ORCHESTRATOR_API_UNAVAILABLE"},
    ),
)
assert 'role="alert"' in error_inspection
assert "essayer" in error_inspection

print("Validation unitaire des contrats produit UI/SP: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_product_contracts_" + [guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($exitCode -ne 0) { throw ($output -join "`n") }
    Write-Host ($output -join "`n")
}
finally {
    $ErrorActionPreference = "Stop"
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
