$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "UV_PROJECT_PYTHON_REQUIRED" }
$env:PYTHONPATH = $repoRoot
$env:PYTHONIOENCODING = "utf-8"

@'
from app.platform.job_runtime.relay import (
    ClaimedRelayMessage,
    JobOutboxRelay,
    RelayedJobMessage,
)


class CrashBeforeAckOutbox:
    def __init__(self, claim):
        self.claim = claim
        self.ack_attempts = 0
        self.acked_job_id = None

    def claim_next(self, *, owner_id, lease_seconds):
        assert owner_id == "RELAY-UNIT"
        assert lease_seconds == 5
        return self.claim

    def acknowledge(self, claim, *, platform_job_id):
        self.ack_attempts += 1
        if self.ack_attempts == 1:
            raise RuntimeError("CRASH_AFTER_PLATFORM_COMMIT")
        self.acked_job_id = platform_job_id


class IdempotentConsumer:
    def __init__(self):
        self.seen = {}

    def consume_relay_message(self, message):
        existing = self.seen.get(message.message_id)
        if existing is not None:
            assert existing == message.content_hash
            return "JOB-M002-000001"
        self.seen[message.message_id] = message.content_hash
        return "JOB-M002-000001"


message = RelayedJobMessage(
    message_id="OUTBOX-SP-0000000001",
    job_name="DIAGNOSE",
    priority="P1",
    input_hash="a" * 64,
    configuration_hash="b" * 64,
    code_version="unit",
    model_version="none",
    payload={"document_id": "DOC-M013-UNIT"},
    trace_id="TRACE-M13-RELAY-UNIT",
)
claim = ClaimedRelayMessage(message=message, owner_id="RELAY-UNIT")
outbox = CrashBeforeAckOutbox(claim)
consumer = IdempotentConsumer()
relay = JobOutboxRelay(outbox=outbox, consumer=consumer)

# Given le job plateforme est committé mais le processus tombe avant l'ACK SP.
try:
    relay.relay_pending(limit=1, owner_id="RELAY-UNIT", lease_seconds=5)
except RuntimeError as error:
    assert str(error) == "CRASH_AFTER_PLATFORM_COMMIT"
else:
    raise AssertionError("Le crash avant ACK doit rester visible.")

# When le même message est redélivré, Then le consommateur reste idempotent et l'ACK aboutit.
assert relay.relay_pending(limit=1, owner_id="RELAY-UNIT", lease_seconds=5) == 1
assert len(consumer.seen) == 1
assert outbox.acked_job_id == "JOB-M002-000001"
print("relay-unit=crash-redelivery-idempotent")
'@ | & $python -B -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$migrationPath = Join-Path $repoRoot "deploy\postgres\migrations\007_job_outbox_context_boundary.sql"
if (-not (Test-Path -LiteralPath $migrationPath -PathType Leaf)) {
    throw "Migration 007 de frontière outbox absente."
}
$migration = Get-Content -Raw -Encoding UTF8 $migrationPath
foreach ($marker in @(
    "DROP CONSTRAINT IF EXISTS job_outbox_platform_job_id_fkey",
    "DROP CONSTRAINT IF EXISTS document_conversion_requests_job_id_fkey",
    "relay_owner",
    "relay_lease_expires_at",
    "source_message_id",
    "source_message_hash"
)) {
    if (-not $migration.Contains($marker)) { throw "Garantie migration 007 absente: $marker" }
}

$platformQueue = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app\platform\job_runtime\postgres.py")
if ($platformQueue.Contains("source_processing.job_outbox")) {
    throw "Le consommateur platform ne doit pas accéder à l'outbox SP."
}
$spOutbox = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app\source_processing\adapters\postgres_job_outbox.py")
foreach ($marker in @("FOR UPDATE SKIP LOCKED", "claim_next", "acknowledge", "relay_lease_expires_at")) {
    if (-not $spOutbox.Contains($marker)) { throw "Protocole SP absent: $marker" }
}

Write-Host "Frontière transactionnelle outbox SP/platform: OK"
