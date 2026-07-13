$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) { throw "DOCKER_ENGINE_REQUIRED" }

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$container = "ostrading-m13-ui-security-$suffix"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$secretPath = Join-Path $temporaryRoot "postgres_password"
$port = Get-FreeTcpPort
$image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
[System.IO.File]::WriteAllText(
    $secretPath,
    "m013-review3-ui-security-password",
    [System.Text.UTF8Encoding]::new($false)
)

try {
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app `
        --env POSTGRES_USER=app `
        --env POSTGRES_PASSWORD=m013-review3-ui-security-password `
        --publish "127.0.0.1:${port}:5432" `
        $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) {
        throw "POSTGRES_DOCKER_START_FAILED"
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "POSTGRES_DOCKER_NOT_READY" }

    $env:M013_REVIEW3_UI_URL = "postgresql://app@127.0.0.1:$port/app"
    $env:M013_REVIEW3_UI_SECRET = $secretPath
    $env:M013_REVIEW3_UI_MIGRATIONS = Join-Path $repoRoot "deploy/postgres/migrations"
    @'
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import threading

from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner
from app.source_processing.adapters.postgres_document_persistence import (
    CorpusQuotaExceededError,
    PostgresCorpusQuotaRepository,
)

factory = PsycopgConnectionFactory(
    connection_url=os.environ["M013_REVIEW3_UI_URL"],
    password_path=Path(os.environ["M013_REVIEW3_UI_SECRET"]),
    connect_timeout_seconds=5,
)
runner = PostgresMigrationRunner(
    connection_factory=factory,
    migrations_path=Path(os.environ["M013_REVIEW3_UI_MIGRATIONS"]),
    operation_timeout_seconds=30,
)
runner.run()
assert runner.required_schema_version == 9
repository = PostgresCorpusQuotaRepository(connection_factory=factory)
repository.reset_for_acceptance_test()
barrier = threading.Barrier(2)


def reserve_concurrently(fingerprint):
    barrier.wait(timeout=10)
    try:
        return repository.reserve(
            fingerprint=fingerprint,
            content_length=600,
            quota_bytes=1_000,
        )
    except CorpusQuotaExceededError as exc:
        return exc.error_code


try:
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve_concurrently, ("a" * 64, "b" * 64)))
    assert sorted(str(result) for result in results) == ["CORPUS_QUOTA_EXCEEDED", "True"]
    assert repository.current_usage_bytes() == 600
    accepted_fingerprint = "a" * 64 if results[0] is True else "b" * 64
    assert repository.reserve(
        fingerprint=accepted_fingerprint,
        content_length=600,
        quota_bytes=1_000,
    ) is False
finally:
    repository.reset_for_acceptance_test()
print("review3-ui-quota-live=serialized; schema=009")
'@ | & $pythonExecutable -B -
    if ($LASTEXITCODE -ne 0) { throw "M013_REVIEW3_UI_SECURITY_LIVE_RED" }
}
finally {
    foreach ($name in @("M013_REVIEW3_UI_URL", "M013_REVIEW3_UI_SECRET", "M013_REVIEW3_UI_MIGRATIONS")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Quota PostgreSQL concurrent de revue 3: OK"
