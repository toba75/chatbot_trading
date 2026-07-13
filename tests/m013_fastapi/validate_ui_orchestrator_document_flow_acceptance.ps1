$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$python = Get-RequiredPythonExecutable
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
do { $gatewayPort = Get-FreeTcpPort } until ($allocatedPorts.Add($gatewayPort))
do { $apiPort = Get-FreeTcpPort } until ($allocatedPorts.Add($apiPort))
do { $uiPort = Get-FreeTcpPort } until ($allocatedPorts.Add($uiPort))
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$configPath = Join-Path $temporaryRoot "config\application.yaml"
$secretPath = Join-Path $temporaryRoot "config\secrets\local\postgres_password"
$localTokenPath = Join-Path $temporaryRoot "config\secrets\local\local_api_token"
$localToken = "m013-ui-live-$([Guid]::NewGuid().ToString('N'))"
$apiStdoutPath = Join-Path $temporaryRoot "api.stdout.log"
$apiStderrPath = Join-Path $temporaryRoot "api.stderr.log"
$gatewayStdoutPath = Join-Path $temporaryRoot "gateway.stdout.log"
$gatewayStderrPath = Join-Path $temporaryRoot "gateway.stderr.log"
$uiStdoutPath = Join-Path $temporaryRoot "ui.stdout.log"
$uiStderrPath = Join-Path $temporaryRoot "ui.stderr.log"
$uiLauncherPath = Join-Path $temporaryRoot "serve_ui.py"
$apiProcess = $null
$gatewayProcess = $null
$uiProcess = $null
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $repoRoot

New-Item -ItemType Directory -Path $temporaryRoot, (Split-Path -Parent $configPath), (Split-Path -Parent $secretPath), (Join-Path $temporaryRoot "data\corpus") -Force | Out-Null
[System.IO.File]::WriteAllText($secretPath, "m13-ui-live-password", [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($localTokenPath, $localToken, [System.Text.UTF8Encoding]::new($false))
$config = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config\application.example.yaml")
$config = $config.Replace("postgresql+psycopg://app@postgres/app", "postgresql+psycopg://app@127.0.0.1:$postgresPort/app")
$config = $config.Replace("url: http://llm-gateway:8090", "url: http://127.0.0.1:$gatewayPort")
$config = $config.Replace("    port: 8090", "    port: $gatewayPort")
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

    $gatewayProcess = Start-Process -FilePath $python `
        -ArgumentList @("-B", "-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "$gatewayPort", "--config", $configPath) `
        -WorkingDirectory $temporaryRoot -RedirectStandardOutput $gatewayStdoutPath `
        -RedirectStandardError $gatewayStderrPath -WindowStyle Hidden -PassThru
    $gatewayReady = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($gatewayProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$gatewayPort/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $gatewayReady = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $gatewayReady) {
        $stderr = if (Test-Path $gatewayStderrPath) { Get-Content -Raw -Encoding UTF8 $gatewayStderrPath } else { "" }
        throw "LLM_GATEWAY_NOT_READY $stderr"
    }

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
    $env:M13_UI_LIVE_API_ORIGIN = $apiOrigin
    $env:M13_UI_LIVE_TOKEN = $localToken
    $env:M13_UI_LIVE_API_LOG = $apiStdoutPath
    $env:M13_UI_LIVE_UI_LOG = $uiStdoutPath
    $env:M13_UI_LIVE_CONFIG = $configPath
    $env:M13_UI_LIVE_PYTHON = $python
    $env:M13_UI_LIVE_ROOT = $temporaryRoot
    $env:M13_UI_LIVE_REPO = $repoRoot
    $scenario = @'
from __future__ import annotations

import html
import http.client
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

from pypdf import PdfWriter
from app.platform.orchestrator_asgi import MAX_REQUEST_BODY_BYTES


origin = os.environ["M13_UI_LIVE_ORIGIN"]
api_origin = os.environ["M13_UI_LIVE_API_ORIGIN"]
local_token = os.environ["M13_UI_LIVE_TOKEN"]
api_log = Path(os.environ["M13_UI_LIVE_API_LOG"])
ui_log = Path(os.environ["M13_UI_LIVE_UI_LOG"])
config_path = os.environ["M13_UI_LIVE_CONFIG"]
python = os.environ["M13_UI_LIVE_PYTHON"]
runtime_root = os.environ["M13_UI_LIVE_ROOT"]
repo = os.environ["M13_UI_LIVE_REPO"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_request(base_origin, path, *, method="GET", data=None, headers=None, follow_redirects=True):
    req = urllib.request.Request(base_origin + path, method=method, data=data, headers=headers or {})
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def request(path, *, method="GET", data=None, headers=None, follow_redirects=True, same_origin=True):
    request_headers = dict(headers or {})
    if method == "POST" and same_origin:
        request_headers["Origin"] = origin
        request_headers["Sec-Fetch-Site"] = "same-origin"
    return http_request(
        origin,
        path,
        method=method,
        data=data,
        headers=request_headers,
        follow_redirects=follow_redirects,
    )


def api_request(path, *, method="GET", data=None, headers=None):
    return http_request(api_origin, path, method=method, data=data, headers=headers)


def oversized_ui_request():
    parsed = urlsplit(origin)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.putrequest("POST", "/v1/documents")
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-Length", str(MAX_REQUEST_BODY_BYTES + 1))
        connection.putheader("Origin", origin)
        connection.putheader("Sec-Fetch-Site", "same-origin")
        connection.endheaders()
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def open_slow_upload():
    parsed = urlsplit(origin)
    connection = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
    headers = (
        "POST /v1/documents HTTP/1.1\r\n"
        f"Host: {parsed.netloc}\r\n"
        f"Origin: {origin}\r\n"
        "Sec-Fetch-Site: same-origin\r\n"
        "Content-Type: application/octet-stream\r\n"
        "Content-Length: 1024\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    connection.sendall(headers + b"x")
    return connection


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

# Les lectures API restent publiques; les mutations directes exigent le secret backend.
assert api_request("/health")[0] == 200
api_openapi = api_request("/openapi.json")
assert api_openapi[0] == 200
assert local_token not in api_openapi[2].decode("utf-8")
assert api_request("/v1/documents", method="POST", data=b"")[0] == 401
assert api_request(
    "/v1/documents",
    method="POST",
    data=b"",
    headers={"Authorization": "Bearer mauvais"},
)[0] == 403

# Then un navigateur charge un PDF réel via l'UI, observe POST-Redirect-GET et ne reçoit aucun JSON brut.
payload, content_type = multipart(pdf)
status, headers, body = request(
    "/v1/documents", method="POST", data=payload,
    headers={"Content-Type": content_type}, follow_redirects=False,
)
assert status == 303, (status, body)
location = headers.get("Location")
assert location is not None and location.startswith("/ui/corpus-pdf?"), location
assert body == b""

status, _, corpus_body = request(location)
assert status == 200
corpus = corpus_body.decode("utf-8")
document_match = re.search(r'data-document-id="(DOC-[A-F0-9]+)"', corpus)
assert document_match is not None, corpus
document_id = document_match.group(1)
assert f"document_id={document_id}" in location
assert "duplicate=false" in location
assert document_id in corpus and "enregistr" in corpus.casefold()
assert local_token not in corpus
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
assert status == 409, (status, conversion)
assert 'role="alert"' in conversion
assert "CONVERSION_NOT_REQUESTED" in conversion
status, _, index_body = request(
    f"/v1/documents/{document_id}/index", method="POST", data=b"",
    headers={"Content-Type": "application/octet-stream"}, follow_redirects=False,
)
index_error = index_body.decode("utf-8")
assert status == 404, (status, index_error)
assert 'role="alert"' in index_error
assert "UI_DOCUMENT_COMMAND_FORBIDDEN" in index_error

# Les erreurs conservent leur statut HTTP et une page française actionnable.
invalid_payload, invalid_content_type = multipart(pdf, include_title=False)
status, _, invalid_body = request(
    "/v1/documents", method="POST", data=invalid_payload,
    headers={"Content-Type": invalid_content_type}, follow_redirects=False,
)
invalid_page = invalid_body.decode("utf-8")
assert status == 400, (status, invalid_page)
assert 'role="alert"' in invalid_page
assert 'href="/ui/corpus-pdf"' in invalid_page
status, _, missing_body = request("/ui/documents/DOC-0000000000000000/diagnostic")
assert status == 404
assert 'role="alert"' in missing_body.decode("utf-8")

# Une lecture de corpus produit un unique appel paginé; aucun fan-out projection 1+N n'est toléré.
# Les mutations navigateur sans origine fiable sont refusées avant tout transfert.
csrf_status, _, csrf_body = request(
    "/v1/documents",
    method="POST",
    data=b"",
    headers={"Content-Type": "application/octet-stream"},
    follow_redirects=False,
    same_origin=False,
)
assert csrf_status == 403
assert "UI_ORIGIN_FORBIDDEN" in csrf_body.decode("utf-8")
bad_origin_status, _, _ = request(
    "/v1/documents",
    method="POST",
    data=b"",
    headers={"Content-Type": "application/octet-stream", "Origin": "http://example.invalid"},
    follow_redirects=False,
    same_origin=False,
)
assert bad_origin_status == 403

# La limite 50 Mio est refusée sans lire le corps et reste accessible en français.
oversized_status, oversized_body = oversized_ui_request()
oversized_page = oversized_body.decode("utf-8")
assert oversized_status == 413
assert "HTTP_REQUEST_TOO_LARGE" in oversized_page and 'role="alert"' in oversized_page

# Quatre transferts lents occupent la capacité bornée; le suivant reçoit 503.
slow_connections = [open_slow_upload() for _ in range(4)]
try:
    capacity_status = None
    capacity_body = b""
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        capacity_status, _, capacity_body = request("/health")
        if capacity_status == 503:
            break
        time.sleep(0.05)
    assert capacity_status == 503, capacity_status
    assert "UI_TRANSFER_CAPACITY_EXHAUSTED" in capacity_body.decode("utf-8")
finally:
    for connection in slow_connections:
        connection.close()

deadline = time.monotonic() + 3
while time.monotonic() < deadline:
    if request("/health")[0] == 200:
        break
    time.sleep(0.05)
else:
    raise AssertionError("capacité UI non libérée")

before = len(api_request_paths())
status, _, _ = request("/ui/corpus-pdf")
assert status == 200
deadline = time.monotonic() + 3
while len(api_request_paths()) <= before and time.monotonic() < deadline:
    time.sleep(0.05)
delta = api_request_paths()[before:]
assert delta == ["/v1/documents"], delta

for runtime_log in (api_log, ui_log):
    if runtime_log.is_file():
        assert local_token not in runtime_log.read_text(encoding="utf-8")

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
    foreach ($name in @("M13_UI_LIVE_ORIGIN", "M13_UI_LIVE_API_ORIGIN", "M13_UI_LIVE_TOKEN", "M13_UI_LIVE_API_LOG", "M13_UI_LIVE_UI_LOG", "M13_UI_LIVE_CONFIG", "M13_UI_LIVE_PYTHON", "M13_UI_LIVE_ROOT", "M13_UI_LIVE_REPO")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    $env:PYTHONPATH = $previousPythonPath
    foreach ($process in @($uiProcess, $apiProcess, $gatewayProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live UI réelle/PostgreSQL/FastAPI/worker/ThreadingHTTPServer: OK"
