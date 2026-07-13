$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) { throw "DOCKER_ENGINE_REQUIRED" }
$head = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') { throw "GIT_HEAD_REQUIRED" }

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ost-m013-compose-$suffix"
$exportRoot = Join-Path $temporaryRoot "source"
$archivePath = Join-Path $temporaryRoot "head.tar"
$project = "ostm13$suffix"
$edgePort = Get-FreeTcpPort
$composePath = Join-Path $exportRoot "deploy/local-compose/compose.yaml"
$secretPath = Join-Path $exportRoot "deploy/local-compose/secrets/postgres_password"
$pythonCommand = @(Get-Command python -CommandType Application -ErrorAction SilentlyContinue)[0]
if ($null -eq $pythonCommand) { throw "PYTHON_TEST_DRIVER_REQUIRED" }
$python = $pythonCommand.Source

$previousRevision = $env:OSTRADING_IMAGE_REVISION
$previousSchema = $env:OSTRADING_POSTGRES_SCHEMA_VERSION
$previousEdgePort = $env:OST_EDGE_HTTPS_PORT
$previousCaddyAdmin = $env:CADDY_ADMIN

New-Item -ItemType Directory -Path $exportRoot -Force | Out-Null
try {
    & git -C $repoRoot archive --format=tar --output=$archivePath HEAD
    if ($LASTEXITCODE -ne 0) { throw "GIT_HEAD_EXPORT_FAILED" }
    & tar -xf $archivePath -C $exportRoot
    if ($LASTEXITCODE -ne 0) { throw "GIT_HEAD_EXTRACT_FAILED" }
    $exportedHead = (& git -C $repoRoot rev-parse HEAD).Trim()
    if ($exportedHead -ne $head) { throw "GIT_HEAD_EXPORT_MISMATCH" }

    New-Item -ItemType Directory -Path (Split-Path -Parent $secretPath) -Force | Out-Null
    [System.IO.File]::WriteAllText($secretPath, "m013-compose-live-password", [System.Text.UTF8Encoding]::new($false))
    $env:OSTRADING_IMAGE_REVISION = $head
    $env:OSTRADING_POSTGRES_SCHEMA_VERSION = "008"
    $env:OST_EDGE_HTTPS_PORT = [string] $edgePort
    $env:CADDY_ADMIN = "localhost:2019"

    & docker compose --project-name $project -f $composePath config --quiet
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_CONFIG_INVALID" }
    & docker compose --project-name $project -f $composePath build orchestrator-api worker-documents llm-gateway ui
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_FINAL_BUILD_FAILED" }

    $apiImage = "ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-008-$head"
    $workerImage = "ostrading/worker-documents:0.1.0-m013-fastapi-schema-008-$head"
    foreach ($image in @($apiImage, $workerImage)) {
        $inspection = (& docker image inspect $image | ConvertFrom-Json)[0]
        if ($inspection.Config.User -ne "ostrading") { throw "IMAGE_NON_ROOT_REQUIRED:$image" }
        if ($inspection.Config.Labels.'org.opencontainers.image.revision' -ne $head) { throw "IMAGE_REVISION_MISMATCH:$image" }
        if ($inspection.Config.Labels.'org.ostrading.postgres-schema-version' -ne "008") { throw "IMAGE_SCHEMA_MISMATCH:$image" }
    }
    $apiInspection = (& docker image inspect $apiImage | ConvertFrom-Json)[0]
    if (($apiInspection.Config.Entrypoint -join ' ') -ne 'api') { throw "API_ENTRYPOINT_MISMATCH" }
    $workerInspection = (& docker image inspect $workerImage | ConvertFrom-Json)[0]
    if (($workerInspection.Config.Entrypoint -join ' ') -ne 'python -m app.source_processing.adapters.worker_runtime') { throw "WORKER_ENTRYPOINT_MISMATCH" }

    & docker compose --project-name $project -f $composePath up --detach --scale worker-documents=2 postgres qdrant llm-gateway orchestrator-api worker-documents ui edge-gateway
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_FINAL_UP_FAILED" }

    $ready = $false
    for ($attempt = 0; $attempt -lt 180; $attempt++) {
        $status = & curl.exe --insecure --silent --output NUL --write-out "%{http_code}" "https://localhost:$edgePort/api/ready"
        if ($LASTEXITCODE -eq 0 -and $status -eq "200") { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        & docker compose --project-name $project -f $composePath ps
        & docker compose --project-name $project -f $composePath logs --no-color --tail=200
        throw "COMPOSE_FINAL_NOT_READY"
    }

    $workerContainers = @(& docker compose --project-name $project -f $composePath ps --quiet worker-documents | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($workerContainers.Count -ne 2) { throw "WORKER_CONCURRENCY_MISMATCH:$($workerContainers.Count)" }
    foreach ($container in $workerContainers) {
        $running = (& docker inspect --format '{{.State.Running}}' $container).Trim()
        if ($running -ne "true") { throw "WORKER_REPLICA_NOT_RUNNING:$container" }
    }

    $env:M013_COMPOSE_ORIGIN = "https://localhost:$edgePort/api"
    $env:M013_COMPOSE_PROJECT = $project
    $env:M013_COMPOSE_FILE = $composePath
    @'
import json
import os
import ssl
import time
import urllib.request
import uuid
from pathlib import Path

from pypdf import PdfWriter

origin = os.environ["M013_COMPOSE_ORIGIN"]
context = ssl._create_unverified_context()

def request(path, *, method="GET", data=None, headers=None):
    req = urllib.request.Request(origin + path, method=method, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        return response.status, dict(response.headers), response.read()

for path in ("/health", "/ready", "/openapi.json"):
    status, _, body = request(path)
    assert status == 200, (path, status, body)

ready = json.loads(request("/ready")[2])
assert ready["status"] == "ready", ready
assert {item["name"] for item in ready["dependencies"]} == {"postgres", "llm-gateway"}, ready

openapi = json.loads(request("/openapi.json")[2])
assert "/v1/documents" in openapi["paths"]
assert "multipart/form-data" in openapi["paths"]["/v1/documents"]["post"]["requestBody"]["content"]

pdf_path = Path(os.environ["TEMP"]) / f"m013-compose-{uuid.uuid4().hex}.pdf"
writer = PdfWriter()
writer.add_blank_page(width=595, height=842)
writer.add_metadata({"/Title": "Preuve Compose M13", "/Author": "OSTrading"})
with pdf_path.open("wb") as stream:
    writer.write(stream)
pdf_bytes = pdf_path.read_bytes()
pdf_path.unlink()

boundary = "----OSTrading" + uuid.uuid4().hex
parts = []
def field(name, value):
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
field("title", "Preuve Compose M13")
field("authors", "OSTrading")
field("publication_year", "2026")
field("edition", "1")
parts.append(
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"original_content\"; filename=\"preuve.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
    + pdf_bytes + b"\r\n"
)
parts.append(f"--{boundary}--\r\n".encode())
status, _, body = request(
    "/v1/documents",
    method="POST",
    data=b"".join(parts),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
assert status == 201, (status, body)
document_id = json.loads(body)["document_id"]
status, _, body = request(f"/v1/documents/{document_id}/diagnose", method="POST", data=b"")
assert status == 202, (status, body)

completed = None
for _ in range(120):
    status, _, body = request(f"/v1/documents/{document_id}/diagnostic")
    assert status == 200, (status, body)
    completed = json.loads(body)
    if completed["diagnostic_status"] in {"COMPLETED", "FAILED"}:
        break
    time.sleep(0.5)
assert completed["diagnostic_status"] == "COMPLETED", completed
print(json.dumps({"document_id": document_id, "diagnostic_status": completed["diagnostic_status"]}, sort_keys=True))
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_REAL_PDF_SCENARIO_FAILED" }

    $ledgerVersion = (& docker compose --project-name $project -f $composePath exec -T postgres psql -At -U ostrading -d ostrading -c "SELECT max(version) FROM platform.schema_migrations").Trim()
    if ($LASTEXITCODE -ne 0 -or $ledgerVersion -ne "8") { throw "POSTGRES_LEDGER_SCHEMA_008_REQUIRED:$ledgerVersion" }
}
finally {
    Remove-Item Env:M013_COMPOSE_ORIGIN -ErrorAction SilentlyContinue
    Remove-Item Env:M013_COMPOSE_PROJECT -ErrorAction SilentlyContinue
    Remove-Item Env:M013_COMPOSE_FILE -ErrorAction SilentlyContinue
    $cleanupErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose --project-name $project -f $composePath down --volumes --remove-orphans *> $null
    }
    finally {
        $ErrorActionPreference = $cleanupErrorActionPreference
    }
    if ($null -eq $previousRevision) { Remove-Item Env:OSTRADING_IMAGE_REVISION -ErrorAction SilentlyContinue } else { $env:OSTRADING_IMAGE_REVISION = $previousRevision }
    if ($null -eq $previousSchema) { Remove-Item Env:OSTRADING_POSTGRES_SCHEMA_VERSION -ErrorAction SilentlyContinue } else { $env:OSTRADING_POSTGRES_SCHEMA_VERSION = $previousSchema }
    if ($null -eq $previousEdgePort) { Remove-Item Env:OST_EDGE_HTTPS_PORT -ErrorAction SilentlyContinue } else { $env:OST_EDGE_HTTPS_PORT = $previousEdgePort }
    if ($null -eq $previousCaddyAdmin) { Remove-Item Env:CADDY_ADMIN -ErrorAction SilentlyContinue } else { $env:CADDY_ADMIN = $previousCaddyAdmin }
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Test live de l'artefact Compose final exporté depuis HEAD: OK"
