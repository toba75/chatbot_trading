$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "UV_PROJECT_PYTHON_REQUIRED" }
$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) { throw "DOCKER_ENGINE_REQUIRED" }

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$container = "ostrading-m13-ui-$suffix"
$allocatedPorts = [System.Collections.Generic.HashSet[int]]::new()
do { $postgresPort = Get-FreeTcpPort } until ($allocatedPorts.Add($postgresPort))
do { $apiPort = Get-FreeTcpPort } until ($allocatedPorts.Add($apiPort))
do { $uiPort = Get-FreeTcpPort } until ($allocatedPorts.Add($uiPort))
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$configPath = Join-Path $temporaryRoot "config\application.yaml"
$secretPath = Join-Path $temporaryRoot "config\secrets\local\postgres_password"
$apiStdoutPath = Join-Path $temporaryRoot "api.stdout.log"
$apiStderrPath = Join-Path $temporaryRoot "api.stderr.log"
$uiStdoutPath = Join-Path $temporaryRoot "ui.stdout.log"
$uiStderrPath = Join-Path $temporaryRoot "ui.stderr.log"
$uiLauncherPath = Join-Path $temporaryRoot "serve_ui.py"
$apiProcess = $null
$uiProcess = $null
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $repoRoot

New-Item -ItemType Directory -Path $temporaryRoot, (Split-Path -Parent $configPath), (Split-Path -Parent $secretPath), (Join-Path $temporaryRoot "data\corpus") -Force | Out-Null
[System.IO.File]::WriteAllText($secretPath, "m13-ui-live-password", [System.Text.UTF8Encoding]::new($false))
$config = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config\application.example.yaml")
$config = $config.Replace("postgresql+psycopg://app@postgres/app", "postgresql+psycopg://app@127.0.0.1:$postgresPort/app")
$config = $config.Replace("  api:`r`n    bind_host: 0.0.0.0`r`n    port: 8080", "  api:`r`n    bind_host: 127.0.0.1`r`n    port: $apiPort")
$config = $config.Replace("  api:`n    bind_host: 0.0.0.0`n    port: 8080", "  api:`n    bind_host: 127.0.0.1`n    port: $apiPort")
[System.IO.File]::WriteAllText($configPath, $config, [System.Text.UTF8Encoding]::new($false))
$uiLauncher = @'
from __future__ import annotations

import sys

from app.platform.local_runtime import serve_http_service

serve_http_service(service_id="ui", port=int(sys.argv[1]), config_path=sys.argv[2])
'@
[System.IO.File]::WriteAllText($uiLauncherPath, $uiLauncher, [System.Text.UTF8Encoding]::new($false))

try {
    # Given PostgreSQL, la factory FastAPI de production et le worker documentaire sont disponibles.
    $image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-ui-live-password `
        --publish "127.0.0.1:${postgresPort}:5432" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    $ready = $false
    $consecutiveReady = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $consecutiveReady++
            if ($consecutiveReady -ge 3) { $ready = $true; break }
        } else { $consecutiveReady = 0 }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "POSTGRES_DOCKER_NOT_READY" }

    $apiProcess = Start-Process -FilePath $python `
        -ArgumentList @("-B", "-m", "app.platform.orchestrator_command", "--config", $configPath) `
        -WorkingDirectory $temporaryRoot -RedirectStandardOutput $apiStdoutPath `
        -RedirectStandardError $apiStderrPath -WindowStyle Hidden -PassThru
    $apiOrigin = "http://127.0.0.1:$apiPort"
    $apiReady = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($apiProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "$apiOrigin/ready" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $apiReady = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $apiReady) {
        $stderr = if (Test-Path $apiStderrPath) { Get-Content -Raw -Encoding UTF8 $apiStderrPath } else { "" }
        throw "ORCHESTRATOR_API_NOT_READY $stderr"
    }

    # When le vrai serveur UI local_runtime démarre lui aussi sur un port éphémère.
    $uiProcess = Start-Process -FilePath $python `
        -ArgumentList @("-B", $uiLauncherPath, "$uiPort", $configPath) `
        -WorkingDirectory $temporaryRoot -RedirectStandardOutput $uiStdoutPath `
        -RedirectStandardError $uiStderrPath -WindowStyle Hidden -PassThru
    $uiOrigin = "http://127.0.0.1:$uiPort"
    $uiReady = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($uiProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "$uiOrigin/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $uiReady = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $uiReady) {
        $stderr = if (Test-Path $uiStderrPath) { Get-Content -Raw -Encoding UTF8 $uiStderrPath } else { "" }
        throw "UI_REAL_SERVER_NOT_READY $stderr"
    }

    $env:M13_UI_LIVE_ORIGIN = $uiOrigin
    $env:M13_UI_LIVE_API_LOG = $apiStdoutPath
    $env:M13_UI_LIVE_CONFIG = $configPath
    $env:M13_UI_LIVE_PYTHON = $python
    $env:M13_UI_LIVE_ROOT = $temporaryRoot
    $env:M13_UI_LIVE_REPO = $repoRoot
    $scenario = @'
from __future__ import annotations

import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid

from pypdf import PdfWriter


origin = os.environ["M13_UI_LIVE_ORIGIN"]
api_log = Path(os.environ["M13_UI_LIVE_API_LOG"])
config_path = os.environ["M13_UI_LIVE_CONFIG"]
python = os.environ["M13_UI_LIVE_PYTHON"]
runtime_root = os.environ["M13_UI_LIVE_ROOT"]
repo = os.environ["M13_UI_LIVE_REPO"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, *, method="GET", data=None, headers=None, follow_redirects=True):
    req = urllib.request.Request(origin + path, method=method, data=data, headers=headers or {})
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def multipart(pdf_bytes, *, include_title=True):
    boundary = "----OSTUi" + uuid.uuid4().hex
    parts = []
    fields = [("authors", "OSTrading"), ("publication_year", "2026"), ("edition", "1")]
    if include_title:
        fields.insert(0, ("title", "Preuve UI réelle"))
    for name, value in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="original_content"; filename="preuve-ui.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
        + pdf_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def api_request_paths():
    paths = []
    if not api_log.is_file():
        return paths
    for line in api_log.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") == "orchestrator_http_request":
            paths.append(event["path"])
    return paths


stream = io.BytesIO()
writer = PdfWriter()
writer.add_blank_page(width=595, height=842)
writer.add_metadata({"/Title": "Preuve UI réelle", "/Author": "OSTrading"})
writer.write(stream)
pdf = stream.getvalue()

# Then un navigateur charge un PDF réel via l'UI, observe POST-Redirect-GET et ne reçoit aucun JSON brut.
payload, content_type = multipart(pdf)
status, headers, body = request(
    "/v1/documents", method="POST", data=payload,
    headers={"Content-Type": content_type}, follow_redirects=False,
)
assert status == 303, (status, body)
assert headers.get("Location") == "/ui/corpus-pdf"
assert body == b""

status, _, corpus_body = request(headers["Location"])
assert status == 200
corpus = corpus_body.decode("utf-8")
document_match = re.search(r'data-document-id="(DOC-[A-F0-9]+)"', corpus)
assert document_match is not None, corpus
document_id = document_match.group(1)
for marker in ('<html lang="fr">', '@media (max-width: 720px)', 'aria-labelledby="ajout-pdf"', 'class="table-scroll"'):
    assert marker in corpus, marker
assert 'data-selectable="false"' in corpus
assert "CONVERSION_NOT_REQUESTED" in corpus
assert "PROJECTION_NOT_REQUESTED" in corpus
assert "/index" not in corpus

# Le diagnostic passe par le même serveur UI, puis un vrai worker consomme le job PostgreSQL.
status, headers, body = request(
    f"/v1/documents/{document_id}/diagnose", method="POST", data=b"",
    headers={"Content-Type": "application/octet-stream"}, follow_redirects=False,
)
assert status == 303, (status, body)
worker_environment = dict(os.environ)
worker_environment["PYTHONPATH"] = repo
worker = subprocess.run(
    [
        python, "-B", "-m", "app.source_processing.adapters.worker_runtime",
        "--config", config_path, "--max-jobs", "1", "--worker-id", "UI-LIVE-WORKER",
        "--lease-seconds", "5", "--poll-seconds", "0.1",
    ],
    cwd=runtime_root,
    env=worker_environment,
    capture_output=True,
    text=True,
    timeout=30,
)
assert worker.returncode == 0, (worker.stdout, worker.stderr)

status, _, diagnostic_body = request(f"/ui/documents/{document_id}/diagnostic")
diagnostic = diagnostic_body.decode("utf-8")
assert status == 200
for marker in ("DIAGNOSED", "Page 1", "Signaux page", "Justification de route"):
    assert marker in diagnostic, (marker, diagnostic)

status, _, original = request(f"/ui/documents/{document_id}/pdf/content")
assert status == 200
assert original == pdf

# La conversion M-004 et l'indexation absentes restent explicitement bloquées sans fallback.
status, _, conversion_body = request(f"/ui/documents/{document_id}/conversion")
conversion = html.unescape(conversion_body.decode("utf-8"))
assert status == 200
assert "QA_REJECTED" in conversion
assert "PAGE_AUTHORITY_MISSING" in conversion
status, _, index_body = request(
    f"/v1/documents/{document_id}/index", method="POST", data=b"",
    headers={"Content-Type": "application/octet-stream"}, follow_redirects=False,
)
index_error = index_body.decode("utf-8")
assert status == 503, (status, index_error)
assert 'role="alert"' in index_error
assert "SERVICE_NOT_CONFIGURED" in index_error

# Les erreurs conservent leur statut HTTP et une page française actionnable.
invalid_payload, invalid_content_type = multipart(pdf, include_title=False)
status, _, invalid_body = request(
    "/v1/documents", method="POST", data=invalid_payload,
    headers={"Content-Type": invalid_content_type}, follow_redirects=False,
)
invalid_page = invalid_body.decode("utf-8")
assert status == 422, (status, invalid_page)
assert 'role="alert"' in invalid_page
assert "RÃ©essayer depuis le corpus" in invalid_page
status, _, missing_body = request("/ui/documents/DOC-0000000000000000/diagnostic")
assert status == 404
assert 'role="alert"' in missing_body.decode("utf-8")

# Une lecture de corpus produit un unique appel paginé; aucun fan-out projection 1+N n'est toléré.
before = len(api_request_paths())
status, _, _ = request("/ui/corpus-pdf")
assert status == 200
deadline = time.monotonic() + 3
while len(api_request_paths()) <= before and time.monotonic() < deadline:
    time.sleep(0.05)
delta = api_request_paths()[before:]
assert delta == ["/v1/documents"], delta

print(json.dumps({
    "api_factory": "production",
    "document_id": document_id,
    "postgres": "docker",
    "ui_server": "ThreadingHTTPServer",
    "worker": "documentaire-réel",
}, ensure_ascii=False, sort_keys=True))
'@
    $scenario | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "UI_REAL_SERVER_LIVE_SCENARIO_FAILED" }
}
finally {
    foreach ($name in @("M13_UI_LIVE_ORIGIN", "M13_UI_LIVE_API_LOG", "M13_UI_LIVE_CONFIG", "M13_UI_LIVE_PYTHON", "M13_UI_LIVE_ROOT", "M13_UI_LIVE_REPO")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    $env:PYTHONPATH = $previousPythonPath
    foreach ($process in @($uiProcess, $apiProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live UI réelle/PostgreSQL/FastAPI/worker/ThreadingHTTPServer: OK"
