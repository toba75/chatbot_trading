$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$env:M013_REVIEW3_UI_REPO = $repoRoot

@'
from __future__ import annotations

import os
from pathlib import Path

from app.platform.configuration import load_application_configuration
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import POSTGRES_MIGRATIONS_PATH, PostgresMigrationRunner
from app.source_processing.adapters.postgres_document_persistence import CorpusQuotaExceededError, PostgresCorpusQuotaRepository

repo = Path(os.environ["M013_REVIEW3_UI_REPO"])
configuration = load_application_configuration(repo / "config/application.example.yaml", environment_snapshot={})
factory = PsycopgConnectionFactory(
    connection_url=configuration.services.postgres.url,
    password_path=Path(configuration.security.secrets.postgres_password_path),
    connect_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
)
PostgresMigrationRunner(
    connection_factory=factory,
    migrations_path=POSTGRES_MIGRATIONS_PATH,
    operation_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
).run()
repository = PostgresCorpusQuotaRepository(connection_factory=factory)
repository.reset_for_acceptance_test()

# Given deux réservations concurrentes visent un quota agrégé,
# When leur somme dépasse la capacité,
# Then PostgreSQL sérialise le compteur et refuse la seconde sans dépassement.
assert repository.reserve(fingerprint="a" * 64, content_length=700, quota_bytes=1_000) is True
try:
    repository.reserve(fingerprint="b" * 64, content_length=400, quota_bytes=1_000)
except CorpusQuotaExceededError as exc:
    assert exc.error_code == "CORPUS_QUOTA_EXCEEDED"
else:
    raise AssertionError("quota agrégé dépassé")
assert repository.current_usage_bytes() == 700
assert repository.reserve(fingerprint="a" * 64, content_length=700, quota_bytes=1_000) is False
repository.reset_for_acceptance_test()
print("review3-ui-quota-live=serialized")
'@ | & $pythonExecutable -B -
$exitCode = $LASTEXITCODE
Remove-Item Env:M013_REVIEW3_UI_REPO -ErrorAction SilentlyContinue
if ($exitCode -ne 0) { throw "M013_REVIEW3_UI_SECURITY_LIVE_RED" }

Write-Host "Quota PostgreSQL de revue 3: OK"
