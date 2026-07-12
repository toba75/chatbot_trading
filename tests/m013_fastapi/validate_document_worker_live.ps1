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
$container = "ostrading-m13-worker-$suffix"
$postgresPort = Get-FreeTcpPort
$apiPort = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$configPath = Join-Path $temporaryRoot "application.yaml"
$secretPath = Join-Path $temporaryRoot "config\secrets\local\postgres_password"
$stdoutPath = Join-Path $temporaryRoot "api.stdout.log"
$stderrPath = Join-Path $temporaryRoot "api.stderr.log"
$apiProcess = $null

New-Item -ItemType Directory -Path $temporaryRoot, (Split-Path -Parent $secretPath), (Join-Path $temporaryRoot "data\corpus") -Force | Out-Null
[System.IO.File]::WriteAllText($secretPath, "m13-worker-live-password", [System.Text.UTF8Encoding]::new($false))
$config = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config\application.example.yaml")
$config = $config.Replace("postgresql+psycopg://app@postgres/app", "postgresql+psycopg://app@127.0.0.1:$postgresPort/app")
$config = $config.Replace("  api:`r`n    bind_host: 0.0.0.0`r`n    port: 8080", "  api:`r`n    bind_host: 127.0.0.1`r`n    port: $apiPort")
$config = $config.Replace("  api:`n    bind_host: 0.0.0.0`n    port: 8080", "  api:`n    bind_host: 127.0.0.1`n    port: $apiPort")
[System.IO.File]::WriteAllText($configPath, $config, [System.Text.UTF8Encoding]::new($false))

try {
    $image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-worker-live-password `
        --publish "127.0.0.1:${postgresPort}:5432" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "POSTGRES_DOCKER_NOT_READY" }

    $apiProcess = Start-Process -FilePath $python `
        -ArgumentList @("-B", "-m", "app.platform.orchestrator_command", "--config", $configPath) `
        -WorkingDirectory $temporaryRoot -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru
    $origin = "http://127.0.0.1:$apiPort"
    $healthy = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($apiProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "$origin/ready" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $healthy = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $healthy) {
        $stderr = if (Test-Path $stderrPath) { Get-Content -Raw -Encoding UTF8 $stderrPath } else { "" }
        throw "ORCHESTRATOR_API_NOT_READY $stderr"
    }

    $env:M13_WORKER_LIVE_ORIGIN = $origin
    $env:M13_WORKER_LIVE_CONFIG = $configPath
    $env:M13_WORKER_LIVE_ROOT = $temporaryRoot
    $env:M13_WORKER_LIVE_PYTHON = $python
    $env:M13_WORKER_LIVE_REPO = $repoRoot
    @'
import io
import json
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

import psycopg
from pypdf import PdfWriter

from app.platform.configuration import load_application_configuration
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.source_processing.adapters.postgres_document_persistence import (
    ProcessingRunVersionConflictError,
    build_document_persistence,
)
from app.source_processing.domain.source_document import DocumentId
from app.source_processing.domain.document_processing_run import RoutingPolicyVersion

origin = os.environ["M13_WORKER_LIVE_ORIGIN"]
config_path = Path(os.environ["M13_WORKER_LIVE_CONFIG"])
python = os.environ["M13_WORKER_LIVE_PYTHON"]
repo = os.environ["M13_WORKER_LIVE_REPO"]
runtime_root = os.environ["M13_WORKER_LIVE_ROOT"]
worker_environment = dict(os.environ)
worker_environment["PYTHONPATH"] = repo


def request(path, *, method="GET", data=None, headers=None):
    req = urllib.request.Request(origin + path, method=method, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.status, json.loads(response.read())


def register_and_diagnose(index):
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_metadata({"/Title": f"Worker live {index}", "/Subject": uuid.uuid4().hex})
    writer.write(stream)
    pdf = stream.getvalue()
    boundary = "----OSTWorker" + uuid.uuid4().hex
    parts = []
    for name, value in (("title", f"Worker live {index}"), ("authors", "OSTrading"), ("publication_year", "2026"), ("edition", "1")):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"original_content\"; filename=\"worker-{index}.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
        + pdf + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    trace_id = f"TRACE-M13-WORKER-{index}"
    status, registered = request(
        "/v1/documents", method="POST", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Trace-Id": trace_id},
    )
    assert status == 201
    document_id = registered["document_id"]
    status, _ = request(f"/v1/documents/{document_id}/diagnose", method="POST", data=b"", headers={"X-Trace-Id": trace_id})
    assert status == 202
    return document_id, trace_id


documents = [register_and_diagnose(index) for index in range(1, 4)]
os.chdir(runtime_root)
configuration = load_application_configuration(config_path, environment_snapshot={})
adapters = build_document_persistence(configuration)
assert isinstance(adapters.job_queue, PostgresJobQueue)

# Deux processus réclament deux jobs concurrents; SKIP LOCKED interdit un double claim actif.
commands = [
    [python, "-B", "-m", "app.source_processing.adapters.worker_runtime", "--config", str(config_path), "--max-jobs", "1", "--worker-id", owner, "--lease-seconds", "5", "--poll-seconds", "0.1"]
    for owner in ("LIVE-WORKER-A", "LIVE-WORKER-B")
]
processes = [subprocess.Popen(command, cwd=runtime_root, env=worker_environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
for process in processes:
    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 0, (stdout, stderr)

# Le troisième job est réclamé par un processus qui s'arrête avant résultat; une lease expirée permet la reprise.
claimed = adapters.job_queue.claim_next(owner_id="LIVE-CRASHED", lease_seconds=1, job_names=("DIAGNOSE",))
assert claimed is not None
time.sleep(1.2)
recovery = subprocess.run(
    [python, "-B", "-m", "app.source_processing.adapters.worker_runtime", "--config", str(config_path), "--max-jobs", "1", "--worker-id", "LIVE-RECOVERY", "--lease-seconds", "5", "--poll-seconds", "0.1"],
    cwd=runtime_root, env=worker_environment, capture_output=True, text=True, timeout=30,
)
assert recovery.returncode == 0, (recovery.stdout, recovery.stderr)

for document_id, _ in documents:
    status, diagnostic = request(f"/v1/documents/{document_id}/diagnostic", headers={"X-Trace-Id": "TRACE-M13-WORKER-READ"})
    assert status == 200
    assert diagnostic["diagnostic_status"] == "DIAGNOSED", diagnostic
    assert diagnostic["diagnosed_page_count"] == diagnostic["source_page_count"] == 1

with adapters.job_queue._connection_factory.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT status, trace_id, payload ? 'trace_id', lease_owner, lease_expires_at FROM platform.technical_jobs ORDER BY sequence", ())
        rows = cursor.fetchall()
        assert len(rows) == 3
        assert all(row[0] == "succeeded" for row in rows), rows
        assert {row[1] for row in rows} == {trace_id for _, trace_id in documents}
        assert all(row[2] is False for row in rows)
        assert all(row[3] is None and row[4] is None for row in rows)

# Deux writers issus du même snapshot ne peuvent pas écraser les enfants silencieusement.
document_id = DocumentId.from_value(documents[0][0])
first = adapters.processing_run_repository.find_by_document_id(document_id)
second = adapters.processing_run_repository.find_by_document_id(document_id)
assert first.aggregate_version == second.aggregate_version
first_update = first.quarantine(RoutingPolicyVersion.from_value("route-live-v1"), "Conflit optimiste live.")
second_update = second.quarantine(RoutingPolicyVersion.from_value("route-live-v1"), "Writer obsolète live.")
adapters.processing_run_repository.save(first_update)
try:
    adapters.processing_run_repository.save(second_update)
except ProcessingRunVersionConflictError:
    pass
else:
    raise AssertionError("PROCESSING_RUN_VERSION_CONFLICT absent")

# PostgreSQL réel confirme qu'un interleaving sous REPEATABLE READ conserve le même snapshot.
factory = adapters.job_queue._connection_factory
with factory.connect() as reader, factory.connect() as writer:
    with reader.transaction():
        with reader.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", ())
            cursor.execute("SELECT aggregate_version FROM source_processing.document_processing_runs WHERE document_id = %s", (document_id.value,))
            before = cursor.fetchone()[0]
        with writer.transaction():
            with writer.cursor() as cursor:
                cursor.execute("UPDATE source_processing.document_processing_runs SET aggregate_version = aggregate_version + 1 WHERE document_id = %s", (document_id.value,))
        with reader.cursor() as cursor:
            cursor.execute("SELECT aggregate_version FROM source_processing.document_processing_runs WHERE document_id = %s", (document_id.value,))
            assert cursor.fetchone()[0] == before

print(json.dumps({"jobs": 3, "workers": 2, "crash_recovery": True, "optimistic_conflict": True, "snapshot": "repeatable-read"}, sort_keys=True))
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "DOCUMENT_WORKER_LIVE_SCENARIO_FAILED" }
}
finally {
    foreach ($name in @("M13_WORKER_LIVE_ORIGIN", "M13_WORKER_LIVE_CONFIG", "M13_WORKER_LIVE_ROOT", "M13_WORKER_LIVE_PYTHON", "M13_WORKER_LIVE_REPO")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
        $apiProcess.WaitForExit()
    }
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live API/PostgreSQL/worker concurrent/crash-reprise ADR-022: OK"
