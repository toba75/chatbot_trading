$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
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
$container = "ostrading-m13-review3-$suffix"
$port = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$secret = Join-Path $temporaryRoot "postgres_password"
$image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
[System.IO.File]::WriteAllText($secret, "m13-review3-password", [System.Text.UTF8Encoding]::new($false))

try {
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-review3-password `
        --publish "127.0.0.1:${port}:5432" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    $ready = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) { $ready++ } else { $ready = 0 }
        if ($ready -ge 3) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($ready -lt 3) { throw "POSTGRES_DOCKER_NOT_READY" }

    $env:PYTHONPATH = $repoRoot
    $env:PYTHONIOENCODING = "utf-8"
    $env:M013_REVIEW3_URL = "postgresql://app@127.0.0.1:$port/app"
    $env:M013_REVIEW3_SECRET = $secret
    $env:M013_REVIEW3_MIGRATIONS = Join-Path $repoRoot "deploy/postgres/migrations"
    @'
from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from pathlib import Path

from app.contracts.source_references import CanonicalSourceRef, SourceLocator
from app.contracts.technical_jobs import JobIdempotenceKey, JobPriority, JobRequest
from app.knowledge_access.adapters.postgres_projection_read import (
    KnowledgeProjectionReplayConflictError,
    PostgresKnowledgeProjectionRepository,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import KnowledgeProjection, ProjectionProfile
from app.platform.job_runtime import JOB_RUNTIME_CATALOG
from app.platform.job_runtime.postgres import JobLeaseConflictError, PostgresJobQueue
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.source_processing.adapters.postgres_job_outbox import JobOutboxLeaseConflictError, PostgresJobOutbox


factory = PsycopgConnectionFactory(
    connection_url=os.environ["M013_REVIEW3_URL"],
    password_path=Path(os.environ["M013_REVIEW3_SECRET"]),
    connect_timeout_seconds=5,
)
runner = PostgresMigrationRunner(
    connection_factory=factory,
    migrations_path=Path(os.environ["M013_REVIEW3_MIGRATIONS"]),
    operation_timeout_seconds=30,
)
runner.run()
assert runner.required_schema_version == 9


def wait_until(predicate, *, timeout=4.0):
    deadline = time.monotonic() + timeout
    event = threading.Event()
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        event.wait(0.05)
    raise AssertionError("deadline PostgreSQL dépassée")


queue = PostgresJobQueue(connection_factory=factory, catalog=JOB_RUNTIME_CATALOG)
request = JobRequest(
    job_name="DIAGNOSE",
    priority=JobPriority.P1,
    idempotence_key=JobIdempotenceKey("DIAGNOSE", "a" * 64, "b" * 64, "review3", "pypdf-review3"),
    payload={"document_id": "DOC-M013-REVIEW3-LIVE"},
)
trace_token = bind_trace_id("TRACE-M013-REVIEW3-LIVE")
try:
    submitted = queue.submit(request, recalculate=False)
finally:
    reset_trace_id(trace_token)
first = queue.claim_next(
    owner_id=f"WORKER-A:{uuid.uuid4()}", lease_seconds=1, job_names=("DIAGNOSE",)
)
assert first is not None and first.claim_generation == first.execution_attempts == 1
assert queue.claim_next(owner_id=f"WORKER-B:{uuid.uuid4()}", lease_seconds=1, job_names=("DIAGNOSE",)) is None

# Le heartbeat maintient le claim au-delà de sa durée initiale; aucun second claim n'entre.
renewed = first
for _ in range(4):
    threading.Event().wait(0.35)
    renewed = queue.renew_lease(
        job_id=first.job.job_id,
        owner_id=first.lease_owner,
        claim_generation=first.claim_generation,
        claim_token=first.claim_token,
        lease_seconds=1,
    )
assert renewed.claim_token == first.claim_token
assert queue.claim_next(owner_id=f"WORKER-C:{uuid.uuid4()}", lease_seconds=1, job_names=("DIAGNOSE",)) is None

# Après arrêt du heartbeat, le reclaim change génération et token; l'ancien writer est fenced.
second = wait_until(
    lambda: queue.claim_next(
        owner_id=f"WORKER-RECOVERY:{uuid.uuid4()}", lease_seconds=3, job_names=("DIAGNOSE",)
    )
)
assert second.claim_generation == 2 and second.execution_attempts == 2
assert second.claim_token != first.claim_token and second.lease_owner != first.lease_owner
try:
    queue.mark_failed(
        job_id=first.job.job_id,
        owner_id=first.lease_owner,
        claim_generation=first.claim_generation,
        claim_token=first.claim_token,
        failure_reason="STALE_WRITER",
    )
except JobLeaseConflictError:
    pass
else:
    raise AssertionError("ancien worker non fenced")
queue.mark_succeeded(
    job_id=second.job.job_id,
    owner_id=second.lease_owner,
    claim_generation=second.claim_generation,
    claim_token=second.claim_token,
    result={"document_id": "DOC-M013-REVIEW3-LIVE"},
)


# Une panne opérationnelle est relâchée deux fois puis devient terminale à la troisième tentative.
retry_request = JobRequest(
    job_name="DIAGNOSE",
    priority=JobPriority.P1,
    idempotence_key=JobIdempotenceKey("DIAGNOSE", "1" * 64, "2" * 64, "review3", "pypdf-review3"),
    payload={"document_id": "DOC-M013-REVIEW3-RETRY"},
)
trace_token = bind_trace_id("TRACE-M013-REVIEW3-RETRY")
try:
    queue.submit(retry_request, recalculate=False)
finally:
    reset_trace_id(trace_token)
for expected_attempt in (1, 2):
    retry_claim = queue.claim_next(
        owner_id=f"WORKER-RETRY-{expected_attempt}:{uuid.uuid4()}",
        lease_seconds=3,
        job_names=("DIAGNOSE",),
    )
    assert retry_claim.execution_attempts == expected_attempt
    queue.schedule_retry(
        job_id=retry_claim.job.job_id,
        owner_id=retry_claim.lease_owner,
        claim_generation=retry_claim.claim_generation,
        claim_token=retry_claim.claim_token,
        max_attempts=3,
    )
retry_claim = queue.claim_next(
    owner_id=f"WORKER-RETRY-3:{uuid.uuid4()}", lease_seconds=3, job_names=("DIAGNOSE",)
)
assert retry_claim.execution_attempts == 3
try:
    queue.schedule_retry(
        job_id=retry_claim.job.job_id,
        owner_id=retry_claim.lease_owner,
        claim_generation=retry_claim.claim_generation,
        claim_token=retry_claim.claim_token,
        max_attempts=3,
    )
except JobLeaseConflictError:
    pass
else:
    raise AssertionError("quatrième tentative autorisée")
queue.mark_failed(
    job_id=retry_claim.job.job_id,
    owner_id=retry_claim.lease_owner,
    claim_generation=retry_claim.claim_generation,
    claim_token=retry_claim.claim_token,
    failure_reason="POSTGRES_TRANSIENT_FAILURE",
)

# Une erreur d'intégrité permanente ne repasse jamais pending.
integrity_request = JobRequest(
    job_name="DIAGNOSE",
    priority=JobPriority.P1,
    idempotence_key=JobIdempotenceKey("DIAGNOSE", "3" * 64, "4" * 64, "review3", "pypdf-review3"),
    payload={"document_id": "DOC-M013-REVIEW3-INTEGRITY"},
)
trace_token = bind_trace_id("TRACE-M013-REVIEW3-INTEGRITY")
try:
    queue.submit(integrity_request, recalculate=False)
finally:
    reset_trace_id(trace_token)
integrity_claim = queue.claim_next(
    owner_id=f"WORKER-INTEGRITY:{uuid.uuid4()}", lease_seconds=3, job_names=("DIAGNOSE",)
)
queue.mark_failed(
    job_id=integrity_claim.job.job_id,
    owner_id=integrity_claim.lease_owner,
    claim_generation=integrity_claim.claim_generation,
    claim_token=integrity_claim.claim_token,
    failure_reason="POSTGRES_INTEGRITY_FAILURE",
)
with factory.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, execution_attempts FROM platform.technical_jobs WHERE job_id = %s",
            (integrity_claim.job.job_id,),
        )
        assert cursor.fetchone() == ("failed", 1)


# Le même fencing s'applique à l'ACK de l'outbox SP.
with factory.connect() as connection:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO source_processing.job_outbox (
                job_name, priority, input_hash, configuration_hash,
                code_version, model_version, payload, trace_id, status
            ) VALUES ('DIAGNOSE', 'P1', %s, %s, 'review3', 'pypdf-review3', %s::jsonb, 'TRACE-REVIEW3', 'pending')
            """,
            ("c" * 64, "d" * 64, '{"document_id":"DOC-M013-REVIEW3-OUTBOX"}'),
        )
outbox = PostgresJobOutbox(connection_factory=factory)
relay_first = outbox.claim_next(owner_id=f"RELAY-A:{uuid.uuid4()}", lease_seconds=1)
assert relay_first is not None
relay_second = wait_until(lambda: outbox.claim_next(owner_id=f"RELAY-B:{uuid.uuid4()}", lease_seconds=3))
assert relay_second.claim_generation == 2 and relay_second.claim_token != relay_first.claim_token
try:
    outbox.acknowledge(relay_first, platform_job_id="JOB-M002-999998")
except JobOutboxLeaseConflictError:
    pass
else:
    raise AssertionError("ancien ACK outbox non fenced")
outbox.acknowledge(relay_second, platform_job_id="JOB-M002-999999")


# Un replay KA strict est idempotent si et seulement si l'empreinte complète est identique.
profile = ProjectionProfile("public-v1", "hierarchical-v1", "dense-v1", "sparse-v1", "hybrid-v1")
projection = KnowledgeProjection.request(
    canonical_ref=CanonicalSourceRef(
        "1.0", "CSRC-M013-REVIEW3-LIVE", "DOC-M013-REVIEW3-KA-LIVE", "CVER-M013-REVIEW3-LIVE",
        "e" * 64, "f" * 64, 1, "2026-07-13T00:00:00Z", "qa-v1"
    ),
    projection_profile=profile,
).start_build().mark_built().start_indexing().mark_searchable()
locator = SourceLocator(
    "1.0", projection.canonical_version_id, projection.document_id, 1, "item-1",
    (0.0, 0.0, 1.0, 1.0), hashlib.sha256(b"item-1").hexdigest()
)
sample = KnowledgeChunk.parent(
    chunk_id=f"KCHK-{hashlib.sha256(b'review3').hexdigest()[:32].upper()}",
    canonical_version_id=projection.canonical_version_id,
    document_id=projection.document_id,
    profile_id="hierarchical",
    profile_version="1",
    text="Sortie KA review3",
    source_locators=(locator,),
)
ka = PostgresKnowledgeProjectionRepository(connection_factory=factory, sample_storage_limit=2)
arguments = dict(
    projection=projection, chunk_count=1, chunks=(sample,), state_observed_at="2026-07-13T00:00:00Z"
)
ka.save_projection_outputs(**arguments)
ka.save_projection_outputs(**arguments)
try:
    ka.save_projection_outputs(**{**arguments, "state_observed_at": "2026-07-13T00:00:01Z"})
except KnowledgeProjectionReplayConflictError:
    pass
else:
    raise AssertionError("replay KA divergent accepté")

with factory.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version FROM platform.schema_migrations ORDER BY version", ())
        assert cursor.fetchall() == [(number,) for number in range(1, 10)]

print("schema=009; lease=renewed; reclaim=fenced; replicas=unique; retries=3; integrity=permanent; outbox=fenced; ka=replay-strict")
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "M013_REVIEW3_SAFETY_LIVE_RED" }
}
finally {
    Remove-Item Env:M013_REVIEW3_URL -ErrorAction SilentlyContinue
    Remove-Item Env:M013_REVIEW3_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:M013_REVIEW3_MIGRATIONS -ErrorAction SilentlyContinue
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Sûreté review3 live PostgreSQL: OK"
