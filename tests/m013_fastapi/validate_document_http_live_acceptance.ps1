$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pyproject = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "pyproject.toml")
if (-not $pyproject.Contains('api = "app.platform.orchestrator_command:main"')) {
    throw "Commande uv run api absente."
}

$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "DOCKER_ENGINE_REQUIRED"
}
$uv = Get-Command uv -ErrorAction Stop
$apiPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $apiPython -PathType Leaf)) {
    throw "UV_PROJECT_PYTHON_REQUIRED"
}
& $uv.Source run --project $repoRoot --no-sync api --help *> $null
if ($LASTEXITCODE -ne 0) {
    throw "UV_RUN_API_COMMAND_INVALID"
}

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$containerName = "ostrading-m13-fastapi-$suffix"
$postgresPort = Get-FreeTcpPort
$apiPort = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ostrading-m13-fastapi-$suffix"
$configPath = Join-Path $temporaryRoot "application.yaml"
$secretPath = Join-Path $temporaryRoot "config\secrets\local\postgres_password"
$corpusRoot = Join-Path $temporaryRoot "data\corpus"
$stdoutPath = Join-Path $temporaryRoot "api.stdout.log"
$stderrPath = Join-Path $temporaryRoot "api.stderr.log"
$apiProcess = $null

New-Item -ItemType Directory -Path $temporaryRoot, $corpusRoot, (Split-Path -Parent $secretPath) -Force | Out-Null
[System.IO.File]::WriteAllText($secretPath, "m13-fastapi-live-password", [System.Text.UTF8Encoding]::new($false))

$config = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config\application.example.yaml")
$config = $config.Replace("postgresql+psycopg://app@postgres/app", "postgresql+psycopg://app@127.0.0.1:$postgresPort/app")
$config = $config.Replace("  api:`r`n    bind_host: 0.0.0.0`r`n    port: 8080", "  api:`r`n    bind_host: 127.0.0.1`r`n    port: $apiPort")
$config = $config.Replace("  api:`n    bind_host: 0.0.0.0`n    port: 8080", "  api:`n    bind_host: 127.0.0.1`n    port: $apiPort")
[System.IO.File]::WriteAllText($configPath, $config, [System.Text.UTF8Encoding]::new($false))

try {
    $image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
    $containerId = & docker run --detach --name $containerName `
        --env POSTGRES_DB=app `
        --env POSTGRES_USER=app `
        --env POSTGRES_PASSWORD=m13-fastapi-live-password `
        --publish "127.0.0.1:${postgresPort}:5432" `
        $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerId)) {
        throw "POSTGRES_DOCKER_START_FAILED"
    }

    $ready = $false
    $consecutiveReady = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $containerName pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $consecutiveReady += 1
            if ($consecutiveReady -eq 3) { $ready = $true; break }
        } else {
            $consecutiveReady = 0
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "POSTGRES_DOCKER_NOT_READY" }

    Get-ChildItem (Join-Path $repoRoot "deploy\postgres\migrations") -Filter "*.sql" -File |
        Sort-Object Name |
        ForEach-Object {
            Get-Content -Raw -Encoding UTF8 $_.FullName |
                & docker exec -i $containerName psql -v ON_ERROR_STOP=1 -U app -d app *> $null
            if ($LASTEXITCODE -ne 0) { throw "POSTGRES_MIGRATION_FAILED $($_.Name)" }
        }

    $apiProcess = Start-Process -FilePath $apiPython `
        -ArgumentList @("-B", "-m", "app.platform.orchestrator_command", "--config", $configPath) `
        -WorkingDirectory $temporaryRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    $origin = "http://127.0.0.1:$apiPort"
    $healthy = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($apiProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "$origin/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $healthy = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $healthy) {
        $stderr = if (Test-Path $stderrPath) { Get-Content -Raw -Encoding UTF8 $stderrPath } else { "" }
        throw "ORCHESTRATOR_API_NOT_HEALTHY $stderr"
    }

    $env:M13_FASTAPI_LIVE_ORIGIN = $origin
    $env:M13_FASTAPI_LIVE_ROOT = $temporaryRoot
    $scenario = @'
import hashlib
import json
import os
import urllib.request
import uuid
from pathlib import Path

from pypdf import PdfWriter

origin = os.environ["M13_FASTAPI_LIVE_ORIGIN"]
root = Path(os.environ["M13_FASTAPI_LIVE_ROOT"])
pdf_path = root / "preuve-reelle.pdf"
writer = PdfWriter()
writer.add_blank_page(width=595, height=842)
writer.add_metadata({"/Title": "Preuve live M13-FastAPI", "/Author": "OSTrading"})
writer.add_attachment("preuve-plus-un-mio.bin", b"x" * (1024 * 1024 + 4096))
with pdf_path.open("wb") as stream:
    writer.write(stream)
pdf_bytes = pdf_path.read_bytes()
assert len(pdf_bytes) > 1024 * 1024, len(pdf_bytes)

def request(path, *, method="GET", data=None, headers=None):
    req = urllib.request.Request(origin + path, method=method, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, dict(response.headers), response.read()

for path in ("/health", "/ready", "/openapi.json"):
    status, headers, body = request(path, headers={"X-Trace-Id": f"TRACE-M13-{path[1:].replace('/', '-') }"})
    assert status == 200, (path, status, body)
    normalized_headers = {name.lower(): value for name, value in headers.items()}
    assert normalized_headers["x-trace-id"].startswith("TRACE-M13-")

openapi = json.loads(request("/openapi.json")[2])
for internal in ("original_storage_ref", "processing_run_id", "job_id", "qdrant_collection", "postgres_password_path"):
    assert internal not in json.dumps(openapi), internal

boundary = "----OSTrading" + uuid.uuid4().hex
parts = []
def field(name, value):
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
field("title", "Preuve réelle M13-FastAPI")
field("authors", "OSTrading")
field("publication_year", "2026")
field("edition", "1")
parts.append(
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"original_content\"; filename=\"preuve-reelle.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
    + pdf_bytes
    + b"\r\n"
)
parts.append(f"--{boundary}--\r\n".encode())
payload = b"".join(parts)
status, headers, body = request(
    "/v1/documents",
    method="POST",
    data=payload,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Trace-Id": "TRACE-M13-PDF-REGISTER"},
)
assert status == 201, (status, body)
registered = json.loads(body)
document_id = registered["document_id"]
assert set(registered) == {"document_id", "document_status"}

status, _, body = request("/v1/documents", headers={"X-Trace-Id": "TRACE-M13-PDF-LIST"})
assert status == 200
corpus = json.loads(body)
assert any(item["document_id"] == document_id for item in corpus["documents"])

status, _, original = request(f"/v1/documents/{document_id}/original", headers={"X-Trace-Id": "TRACE-M13-PDF-ORIGINAL"})
assert status == 200
assert hashlib.sha256(original).hexdigest() == hashlib.sha256(pdf_bytes).hexdigest()

status, _, body = request(f"/v1/documents/{document_id}/diagnose", method="POST", data=b"", headers={"X-Trace-Id": "TRACE-M13-PDF-DIAGNOSE"})
assert status == 202, (status, body)
status, _, body = request(f"/v1/documents/{document_id}/diagnostic", headers={"X-Trace-Id": "TRACE-M13-PDF-DIAGNOSTIC"})
assert status == 200, (status, body)
diagnostic = json.loads(body)
assert diagnostic["document_id"] == document_id
assert len(diagnostic["pages"]) == 1

status, _, body = request(f"/v1/documents/{document_id}/projection", headers={"X-Trace-Id": "TRACE-M13-PDF-PROJECTION"})
assert status == 200, (status, body)
assert json.loads(body) == {"document_id": document_id, "projection_status": "PROJECTION_NOT_REQUESTED"}

print(json.dumps({"document_id": document_id, "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(), "postgres": "docker", "transport": "uvicorn-http"}, sort_keys=True))
'@
    $scenario | & $apiPython -B -
    if ($LASTEXITCODE -ne 0) { throw "DOCUMENT_HTTP_LIVE_SCENARIO_FAILED" }

    Start-Sleep -Milliseconds 200
    $requestLogs = @(
        Get-Content -Encoding UTF8 $stdoutPath |
            ForEach-Object {
                try { $_ | ConvertFrom-Json }
                catch { $null }
            } |
            Where-Object { $_.event_type -eq "orchestrator_http_request" }
    )
    if ($requestLogs.Count -lt 10) {
        throw "ORCHESTRATOR_TRACE_LOGS_MISSING"
    }
    foreach ($requestLog in $requestLogs) {
        if ([string]::IsNullOrWhiteSpace($requestLog.trace_id)) {
            throw "ORCHESTRATOR_TRACE_ID_MISSING"
        }
        if ($requestLog.configuration_hash -notmatch '^[a-f0-9]{64}$') {
            throw "ORCHESTRATOR_CONFIGURATION_HASH_MISSING"
        }
        if ($requestLog.status_code -lt 200 -or $requestLog.status_code -gt 599) {
            throw "ORCHESTRATOR_TRACE_STATUS_INVALID"
        }
    }
    $rawLogs = Get-Content -Raw -Encoding UTF8 $stdoutPath
    foreach ($sensitiveMarker in @("Preuve réelle M13-FastAPI", "OSTrading", "bc6cfa26")) {
        if ($rawLogs.Contains($sensitiveMarker)) {
            throw "ORCHESTRATOR_SENSITIVE_PAYLOAD_LOGGED"
        }
    }
}
finally {
    Remove-Item Env:M13_FASTAPI_LIVE_ORIGIN -ErrorAction SilentlyContinue
    Remove-Item Env:M13_FASTAPI_LIVE_ROOT -ErrorAction SilentlyContinue
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
        $apiProcess.WaitForExit()
    }
    & docker rm --force $containerName *> $null
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Test d'acceptation HTTP live PDF/PostgreSQL/Uvicorn: OK"
