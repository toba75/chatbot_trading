$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $PSScriptRoot "resolve_m013_fastapi_python.ps1")
$python = Resolve-M013FastApiPython -RepoRoot $repoRoot
$null = & docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) { throw "DOCKER_ENGINE_REQUIRED" }

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

function Wait-Postgres([string] $containerName) {
    $consecutiveReady = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $containerName pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $consecutiveReady++
            if ($consecutiveReady -ge 3) { return }
        } else {
            $consecutiveReady = 0
        }
        Start-Sleep -Milliseconds 500
    }
    throw "POSTGRES_DOCKER_NOT_READY"
}

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$container = "ostrading-m13-ka-$suffix"
$port = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$secret = Join-Path $temporaryRoot "postgres_password"
$image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
[System.IO.File]::WriteAllText($secret, "m13-ka-password", [System.Text.UTF8Encoding]::new($false))

try {
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-ka-password `
        --publish "127.0.0.1:${port}:5432" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    Wait-Postgres $container
    $env:PYTHONPATH = $repoRoot
    $env:PYTHONIOENCODING = "utf-8"
    $env:M13_KA_URL = "postgresql://app@127.0.0.1:$port/app"
    $env:M13_KA_SECRET = $secret
    $env:M13_KA_MIGRATIONS = Join-Path $repoRoot "deploy/postgres/migrations"
    @'
import hashlib
import os
from pathlib import Path

from app.contracts.source_references import SourceLocator
from app.knowledge_access.adapters.postgres_projection_read import PostgresKnowledgeProjectionRepository
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint, KnowledgeProjection, ProjectionProfile, ProjectionStatus
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner

factory = PsycopgConnectionFactory(connection_url=os.environ["M13_KA_URL"], password_path=Path(os.environ["M13_KA_SECRET"]), connect_timeout_seconds=5)
PostgresMigrationRunner(connection_factory=factory, migrations_path=Path(os.environ["M13_KA_MIGRATIONS"]), operation_timeout_seconds=30).run()
writer = PostgresKnowledgeProjectionRepository(connection_factory=factory, sample_storage_limit=3)
profile = ProjectionProfile("public-v1", "hierarchical-v1", "dense-v1", "sparse-v1", "hybrid-v1")

def projection(label, status):
    return KnowledgeProjection(f"PROJ-M013-{label}", f"DOC-M013-{label}", f"CVER-M013-{label}", profile, BuildFingerprint(hashlib.sha256(label.encode()).hexdigest()), status)

def sample(value, number):
    text = f"Extrait PostgreSQL {value.document_id} {number}"
    locator = SourceLocator("1.0", value.canonical_version_id, value.document_id, number, f"item-{number}", (0.0, 0.0, 1.0, 1.0), hashlib.sha256(f"item-{number}".encode()).hexdigest())
    return KnowledgeChunk.parent(chunk_id=f"KCHK-{hashlib.sha256(text.encode()).hexdigest()[:32].upper()}", canonical_version_id=value.canonical_version_id, document_id=value.document_id, profile_id="hierarchical", profile_version="1", text=text, source_locators=(locator,))

states = {
    "BUILDING": projection("BUILDING", ProjectionStatus.REQUESTED).start_build(),
    "SEARCHABLE": projection("SEARCHABLE", ProjectionStatus.REQUESTED).start_build().mark_built().start_indexing().mark_searchable(),
    "STALE": projection("STALE", ProjectionStatus.REQUESTED).start_build().mark_built().start_indexing().mark_searchable().mark_stale(),
    "FAILED": projection("FAILED", ProjectionStatus.REQUESTED).start_build().mark_failed(),
}
for name, value in states.items():
    chunks = () if name in ("BUILDING", "FAILED") else tuple(sample(value, number) for number in range(1, 4))
    writer.save_projection_outputs(projection=value, chunk_count=len(chunks), chunks=chunks, state_observed_at="2026-07-12T12:00:00Z")
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "KA_POSTGRES_WRITE_FAILED" }

    & docker restart $container *> $null
    if ($LASTEXITCODE -ne 0) { throw "KA_POSTGRES_RESTART_FAILED" }
    Wait-Postgres $container

    @'
import os
from pathlib import Path
from app.knowledge_access.adapters.postgres_projection_read import PostgresProjectionReadRepository
from app.platform.postgres import PsycopgConnectionFactory

factory = PsycopgConnectionFactory(connection_url=os.environ["M13_KA_URL"], password_path=Path(os.environ["M13_KA_SECRET"]), connect_timeout_seconds=5)
reader = PostgresProjectionReadRepository(connection_factory=factory)
for status in ("BUILDING", "SEARCHABLE", "STALE", "FAILED"):
    record = reader.current_projection_for_document_id(f"DOC-M013-{status}", sample_limit=2)
    assert record is not None and record.projection.status.value == status
    expected = 2 if status in ("SEARCHABLE", "STALE") else 0
    assert len(record.chunk_samples) == expected
    if expected:
        assert record.chunk_count == 3
        assert record.chunk_samples[0].source_locators[0].page_pdf == 1
print("postgres=réel; restart=oui; statuts=BUILDING,SEARCHABLE,STALE,FAILED; sample_limit=2")
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "KA_POSTGRES_RESTART_READ_FAILED" }
}
finally {
    Remove-Item Env:M13_KA_URL -ErrorAction SilentlyContinue
    Remove-Item Env:M13_KA_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:M13_KA_MIGRATIONS -ErrorAction SilentlyContinue
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live persistance KA PostgreSQL après redémarrage: OK"
