$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "UV_PROJECT_PYTHON_REQUIRED" }
$env:PYTHONPATH = $repoRoot
$env:PYTHONIOENCODING = "utf-8"
$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) { throw "DOCKER_ENGINE_REQUIRED" }

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$container = "ostrading-m13-migration-$suffix"
$volume = "ostrading-m13-prevolume-$suffix"
$port = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$secret = Join-Path $temporaryRoot "postgres_password"
$migrations007 = Join-Path $temporaryRoot "migrations-007"
$image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
New-Item -ItemType Directory -Path $migrations007 -Force | Out-Null
Get-ChildItem (Join-Path $repoRoot "deploy/postgres/migrations") -Filter "*.sql" |
    Where-Object { $_.Name -match '^00[1-7]_' } |
    Copy-Item -Destination $migrations007
[System.IO.File]::WriteAllText($secret, "m13-migration-password", [System.Text.UTF8Encoding]::new($false))

function Start-Postgres {
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-migration-password `
        --publish "127.0.0.1:${port}:5432" --volume "${volume}:/var/lib/postgresql/data" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    $consecutiveReady = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $consecutiveReady += 1
            if ($consecutiveReady -eq 3) { return }
        } else {
            $consecutiveReady = 0
        }
        Start-Sleep -Milliseconds 500
    }
    throw "POSTGRES_DOCKER_NOT_READY"
}

try {
    # Given un volume pré-M13 ne contient que la première migration et aucun ledger.
    Start-Postgres
    Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy/postgres/migrations/001_document_persistence.sql") |
        & docker exec -i $container psql -v ON_ERROR_STOP=1 -U app -d app *> $null
    if ($LASTEXITCODE -ne 0) { throw "PRE_M13_SCHEMA_CREATION_FAILED" }
    & docker rm --force $container *> $null

    # When le même volume redémarre avec le runner M13-FastAPI.
    Start-Postgres
    $env:M13_MIGRATION_URL = "postgresql://app@127.0.0.1:$port/app"
    $env:M13_MIGRATION_SECRET = $secret
    $env:M13_MIGRATION_PATH = Join-Path $repoRoot "deploy/postgres/migrations"
    $env:M13_MIGRATION_PATH_007 = $migrations007
    @'
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psycopg

from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner

factory = PsycopgConnectionFactory(
    connection_url=os.environ["M13_MIGRATION_URL"],
    password_path=Path(os.environ["M13_MIGRATION_SECRET"]),
    connect_timeout_seconds=5,
)
runner007 = PostgresMigrationRunner(
    connection_factory=factory,
    migrations_path=Path(os.environ["M13_MIGRATION_PATH_007"]),
    operation_timeout_seconds=30,
)
with ThreadPoolExecutor(max_workers=2) as executor:
    list(executor.map(lambda _: runner007.run(), range(2)))
assert runner007.required_schema_version == 7
assert runner007.is_required_schema_ready()

runner = PostgresMigrationRunner(
    connection_factory=factory,
    migrations_path=Path(os.environ["M13_MIGRATION_PATH"]),
    operation_timeout_seconds=30,
)
with ThreadPoolExecutor(max_workers=2) as executor:
    list(executor.map(lambda _: runner.run(), range(2)))
runner.run()
assert runner.is_required_schema_ready()
with factory.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, filename FROM platform.schema_migrations ORDER BY version", ())
        assert cursor.fetchall() == [
            (1, "001_document_persistence.sql"),
            (2, "002_knowledge_projection_read_models.sql"),
            (3, "003_document_worker_runtime.sql"),
            (4, "004_knowledge_projection_chunk_samples.sql"),
            (5, "005_source_processing_read_performance.sql"),
            (6, "006_worker_resilience_and_ka_version.sql"),
            (7, "007_job_outbox_context_boundary.sql"),
            (8, "008_claim_fencing_and_projection_replay.sql"),
        ]
        cursor.execute("SELECT to_regclass('knowledge_access.knowledge_projections')", ())
        assert cursor.fetchone() == ("knowledge_access.knowledge_projections",)
print("upgrade-volume-007=schema-008; ledger=idempotent; lock=advisory")
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "POSTGRES_MIGRATION_UPGRADE_FAILED" }
}
finally {
    Remove-Item Env:M13_MIGRATION_URL -ErrorAction SilentlyContinue
    Remove-Item Env:M13_MIGRATION_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:M13_MIGRATION_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:M13_MIGRATION_PATH_007 -ErrorAction SilentlyContinue
    & docker rm --force $container *> $null
    & docker volume rm $volume *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live upgrade PostgreSQL sur volume pré-M13: OK"
