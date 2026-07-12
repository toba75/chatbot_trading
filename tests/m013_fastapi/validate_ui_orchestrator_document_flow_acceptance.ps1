$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.ui_corpus import render_corpus_pdf_screen, render_document_inspection  # noqa: E402
from app.platform.ui_document_api import UiDocumentApiClient, UrllibUiDocumentApiTransport  # noqa: E402


DOCUMENT_ID = "DOC-M013-FASTAPI-UI01"
PDF = b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"
requests: list[tuple[str, str]] = []


class OrchestratorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        requests.append(("GET", self.path))
        if self.path == "/v1/documents":
            self._json(200, {"documents": [{
                "document_id": DOCUMENT_ID,
                "title": "Rapport API",
                "document_status": "SOURCE_REGISTERED",
                "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
                "conversion_status": "CONVERSION_NOT_REQUESTED",
                "canonical_version_id": None,
            }]})
            return
        if self.path == f"/v1/documents/{DOCUMENT_ID}/projection":
            self._json(200, {"document_id": DOCUMENT_ID, "projection_status": "PROJECTION_NOT_REQUESTED"})
            return
        if self.path == f"/v1/documents/{DOCUMENT_ID}/diagnostic":
            self._json(409, {"error_code": "DIAGNOSTIC_NOT_REQUESTED", "document_id": DOCUMENT_ID})
            return
        if self.path == f"/v1/documents/{DOCUMENT_ID}/original":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(PDF)))
            self.end_headers()
            self.wfile.write(PDF)
            return
        self._json(404, {"error_code": "ENDPOINT_NOT_FOUND", "path": self.path})

    def do_POST(self) -> None:
        requests.append(("POST", self.path))
        if self.path == f"/v1/documents/{DOCUMENT_ID}/diagnose":
            self._json(202, {"document_id": DOCUMENT_ID, "diagnostic_status": "DIAGNOSTIC_REQUESTED"})
            return
        if self.path == "/v1/documents/DOC-M013-FASTAPI-FAIL/diagnose":
            self._json(503, {"error_code": "DOCUMENT_COMMAND_UNAVAILABLE", "document_id": "DOC-M013-FASTAPI-FAIL"})
            return
        self._json(404, {"error_code": "ENDPOINT_NOT_FOUND", "path": self.path})

    def _json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), OrchestratorHandler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    transport = UrllibUiDocumentApiTransport(
        orchestrator_origin=f"http://127.0.0.1:{server.server_port}",
        timeout_seconds=5,
    )
    client = UiDocumentApiClient(transport=transport)

    # Given l'API documentaire répond réellement en HTTP.
    # When l'UI ouvre le corpus, diagnostique, inspecte une étape et ouvre le PDF.
    # Then elle affiche exclusivement les réponses publiques de ces contrats.
    state = client.build_corpus_state(active_selected_document_ids=())
    body = render_corpus_pdf_screen(state)
    if "Rapport API" not in body or ">Diagnostiquer</button>" not in body:
        raise AssertionError(f"Le corpus HTTP réel n'est pas rendu: {body}")

    command = client.forward_document_command(
        path=f"/v1/documents/{DOCUMENT_ID}/diagnose",
        body=b"",
        content_type="application/octet-stream",
    )
    if command.status_code != 202 or command.payload["diagnostic_status"] != "DIAGNOSTIC_REQUESTED":
        raise AssertionError(f"Commande diagnostic non relayée: {command}")

    diagnostic = client.read_diagnostic(DOCUMENT_ID)
    inspection = render_document_inspection(title="Diagnostic", response=diagnostic)
    if "DIAGNOSTIC_NOT_REQUESTED" not in inspection or "original_storage_ref" in inspection:
        raise AssertionError(f"Erreur publique diagnostic invalide: {inspection}")

    pdf = client.read_original_pdf(DOCUMENT_ID)
    if pdf.status_code != 200 or pdf.content_type != "application/pdf" or pdf.body != PDF:
        raise AssertionError("Le visualiseur ne lit pas le PDF via le contrat original public.")

    unavailable = client.forward_document_command(
        path="/v1/documents/DOC-M013-FASTAPI-FAIL/diagnose",
        body=b"",
        content_type="application/octet-stream",
    )
    if unavailable.status_code != 503 or unavailable.payload != {
        "error_code": "DOCUMENT_COMMAND_UNAVAILABLE",
        "document_id": "DOC-M013-FASTAPI-FAIL",
    }:
        raise AssertionError(f"L'erreur publique a été masquée ou remplacée: {unavailable}")

    expected_requests = {
        ("GET", "/v1/documents"),
        ("GET", f"/v1/documents/{DOCUMENT_ID}/projection"),
        ("GET", f"/v1/documents/{DOCUMENT_ID}/diagnostic"),
        ("GET", f"/v1/documents/{DOCUMENT_ID}/original"),
        ("POST", f"/v1/documents/{DOCUMENT_ID}/diagnose"),
        ("POST", "/v1/documents/DOC-M013-FASTAPI-FAIL/diagnose"),
    }
    if set(requests) != expected_requests:
        raise AssertionError(f"Trajet HTTP UI/API incomplet: {requests}")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

print("Test d'acceptation parcours documentaire UI/orchestrateur: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_ui_flow_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation parcours documentaire UI/orchestrateur invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
