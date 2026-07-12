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
$container = "ostrading-m13-relay-$suffix"
$port = Get-FreeTcpPort
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) $container
$secret = Join-Path $temporaryRoot "postgres_password"
$migrations006 = Join-Path $temporaryRoot "migrations-006"
$image = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
New-Item -ItemType Directory -Path $migrations006 -Force | Out-Null
[System.IO.File]::WriteAllText($secret, "m13-relay-password", [System.Text.UTF8Encoding]::new($false))
Get-ChildItem (Join-Path $repoRoot "deploy\postgres\migrations") -Filter "00[1-6]_*.sql" |
    Copy-Item -Destination $migrations006

try {
    $id = & docker run --detach --name $container `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env POSTGRES_PASSWORD=m13-relay-password `
        --publish "127.0.0.1:${port}:5432" $image
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "POSTGRES_DOCKER_START_FAILED" }
    $consecutiveReady = 0
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        & docker exec $container pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $consecutiveReady++
            if ($consecutiveReady -ge 3) { break }
        } else { $consecutiveReady = 0 }
        Start-Sleep -Milliseconds 500
    }
    if ($consecutiveReady -lt 3) { throw "POSTGRES_DOCKER_NOT_READY" }

    $env:M13_RELAY_URL = "postgresql://app@127.0.0.1:$port/app"
    $env:M13_RELAY_SECRET = $secret
    $env:M13_RELAY_MIGRATIONS_006 = $migrations006
    $env:M13_RELAY_MIGRATIONS = Join-Path $repoRoot "deploy\postgres\migrations"
    @'
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.platform.job_runtime import JOB_RUNTIME_CATALOG
from app.platform.job_runtime.postgres import JobRelayMessageConflictError, PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay, RelayedJobMessage
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox


base_factory = PsycopgConnectionFactory(
    connection_url=os.environ["M13_RELAY_URL"],
    password_path=Path(os.environ["M13_RELAY_SECRET"]),
    connect_timeout_seconds=5,
)
runner006 = PostgresMigrationRunner(
    connection_factory=base_factory,
    migrations_path=Path(os.environ["M13_RELAY_MIGRATIONS_006"]),
    operation_timeout_seconds=10,
)
runner006.run()
assert runner006.required_schema_version == 6
runner007 = PostgresMigrationRunner(
    connection_factory=base_factory,
    migrations_path=Path(os.environ["M13_RELAY_MIGRATIONS"]),
    operation_timeout_seconds=10,
)
runner007.run()
runner007.run()
assert runner007.required_schema_version == 7
assert runner007.is_required_schema_ready()


class TrackingFactory:
    def __init__(self, factory):
        self.factory = factory
        self.connection_count = 0

    def connect(self):
        self.connection_count += 1
        return self.factory.connect()


tracking = TrackingFactory(base_factory)
outbox = PostgresJobOutbox(connection_factory=tracking)
queue = PostgresJobQueue(connection_factory=tracking, catalog=JOB_RUNTIME_CATALOG)


def insert_message(index):
    with base_factory.connect() as connection:
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO source_processing.job_outbox (
                    job_name, priority, input_hash, configuration_hash,
                    code_version, model_version, payload, trace_id, status
                ) VALUES ('DIAGNOSE', 'P1', %s, %s, 'live', 'none', %s::jsonb, %s, 'pending')
                RETURNING outbox_id
                """,
                (f"{index:064x}", "b" * 64, f'{{"document_id":"DOC-M013-RELAY-{index}"}}', f"TRACE-M13-RELAY-{index}"),
            )
            return cursor.fetchone()[0]


# Deux relais concurrents ne peuvent pas réclamer deux fois le même message.
first_message_id = insert_message(1)
def relay_once(owner):
    relay = JobOutboxRelay(outbox=outbox, consumer=queue)
    return relay.relay_pending(limit=1, owner_id=owner, lease_seconds=2)

with ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(relay_once, ("RELAY-A", "RELAY-B")))
assert sum(results) == 1, results

# Crash après commit platform, avant ACK SP : la lease expirée redélivre sans doublon.
second_message_id = insert_message(2)
claimed = outbox.claim_next(owner_id="RELAY-CRASH", lease_seconds=1)
assert claimed is not None and claimed.message.message_id == second_message_id
platform_job_id = queue.consume_relay_message(claimed.message)
time.sleep(1.2)
recovered = JobOutboxRelay(outbox=outbox, consumer=queue).relay_pending(
    limit=1,
    owner_id="RELAY-RECOVERY",
    lease_seconds=2,
)
assert recovered == 1

# Le même identifiant avec un contenu divergent est refusé explicitement.
divergent = RelayedJobMessage(
    message_id=claimed.message.message_id,
    job_name=claimed.message.job_name,
    priority=claimed.message.priority,
    input_hash=claimed.message.input_hash,
    configuration_hash=claimed.message.configuration_hash,
    code_version=claimed.message.code_version,
    model_version=claimed.message.model_version,
    payload={"document_id": "DOC-DIVERGENT"},
    trace_id=claimed.message.trace_id,
)
try:
    queue.consume_relay_message(divergent)
except JobRelayMessageConflictError as error:
    assert str(error) == "JOB_RELAY_MESSAGE_CONFLICT"
else:
    raise AssertionError("Conflit de message divergent absent.")

with base_factory.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM platform.technical_jobs", ())
        assert cursor.fetchone() == (2,)
        cursor.execute("SELECT COUNT(*) FROM source_processing.job_outbox WHERE status = 'relayed'", ())
        assert cursor.fetchone() == (2,)
        cursor.execute(
            """
            SELECT COUNT(*)
              FROM pg_constraint c
              JOIN pg_class t ON t.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = t.relnamespace
              JOIN pg_class rt ON rt.oid = c.confrelid
              JOIN pg_namespace rn ON rn.oid = rt.relnamespace
             WHERE c.contype = 'f'
               AND n.nspname = 'source_processing'
               AND t.relname = 'job_outbox'
               AND rn.nspname = 'platform'
            """,
            (),
        )
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT version FROM platform.schema_migrations ORDER BY version", ())
        assert cursor.fetchall() == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]

# Claim SP, commit platform et ACK SP ouvrent chacun leur transaction locale.
assert tracking.connection_count >= 8, tracking.connection_count
print(
    "relay-live=concurrent-claim; crash-redelivery=idempotent; "
    "cross-schema-fk=absent; schema=007; transactions=separate"
)
'@ | & $python -B -
    if ($LASTEXITCODE -ne 0) { throw "JOB_OUTBOX_BOUNDARY_LIVE_FAILED" }
}
finally {
    foreach ($name in @("M13_RELAY_URL", "M13_RELAY_SECRET", "M13_RELAY_MIGRATIONS_006", "M13_RELAY_MIGRATIONS")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    & docker rm --force $container *> $null
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Test live frontière outbox SP/platform: OK"
