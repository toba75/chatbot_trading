$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = $repoRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "UV_PROJECT_PYTHON_REQUIRED" }

$scenario = @'
from datetime import timedelta

from app.platform.job_runtime.postgres import PostgresJobQueue
from app.source_processing.application.document_worker import DocumentDiagnosticWorker
from app.source_processing.adapters.postgres_document_persistence import (
    ProcessingRunVersionConflictError,
)

for method_name in (
    "relay_pending_outbox",
    "claim_next",
    "renew_lease",
    "mark_succeeded",
    "mark_failed",
):
    assert callable(getattr(PostgresJobQueue, method_name, None)), method_name

assert callable(getattr(DocumentDiagnosticWorker, "execute", None))
assert issubclass(ProcessingRunVersionConflictError, RuntimeError)
assert str(ProcessingRunVersionConflictError()) == "PROCESSING_RUN_VERSION_CONFLICT"

print("Contrats worker, outbox, lease et version optimiste: OK")
'@

$scenario | & $python -B -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$migration = Join-Path $repoRoot "deploy\postgres\migrations\003_document_worker_runtime.sql"
if (-not (Test-Path -LiteralPath $migration -PathType Leaf)) {
    throw "Migration worker ADR-022 absente."
}
$sql = Get-Content -Raw -Encoding UTF8 $migration
foreach ($marker in @(
    "source_processing.job_outbox",
    "trace_id",
    "aggregate_version",
    "lease_owner",
    "lease_expires_at",
    "relay_attempts"
)) {
    if (-not $sql.Contains($marker)) { throw "Garantie SQL ADR-022 absente: $marker" }
}

$queue = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app\platform\job_runtime\postgres.py")
foreach ($marker in @("FOR UPDATE SKIP LOCKED", "lease_owner", "lease_expires_at")) {
    if (-not $queue.Contains($marker)) { throw "Garantie de claim absente: $marker" }
}

$persistence = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app\source_processing\adapters\postgres_document_persistence.py")
if ($persistence.Contains("submit_in_transaction(")) {
    throw "Écriture intercontextes directe SP vers platform encore présente."
}
foreach ($marker in @("job_outbox", "PROCESSING_RUN_VERSION_CONFLICT", "REPEATABLE READ READ ONLY")) {
    if (-not $persistence.Contains($marker)) { throw "Garantie SP absente: $marker" }
}

$runtime = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app\platform\local_runtime.py")
if ($runtime.Contains("threading.Event().wait()")) {
    throw "worker-documents attend encore sans consommer la file."
}
foreach ($marker in @("DocumentDiagnosticWorker", "claim_next", "relay_pending_outbox")) {
    if (-not $runtime.Contains($marker)) { throw "Raccordement worker absent: $marker" }
}

Write-Host "Test d'acceptation worker/cohérence des données ADR-022: OK"
