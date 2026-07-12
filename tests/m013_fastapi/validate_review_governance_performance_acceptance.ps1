$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

function Assert-Contains {
    param([string] $Content, [string] $Expected, [string] $Message)
    if (-not $Content.Contains($Expected)) {
        throw "$Message Valeur attendue: $Expected"
    }
}

# Given M13-FastAPI comporte des preuves statiques et des preuves live Docker distinctes.
# When la gate canonique et les gates globales sont inspectées.
# Then leur mode est explicite, exhaustif et aucun lint statique ne dépend de Docker.
$gate = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts/validate_m013_fastapi.ps1")
$lint = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts/lint.ps1")
$test = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts/test.ps1")
foreach ($marker in @(
    '[ValidateSet("Static", "Live")]',
    '[string] $Mode',
    'M013_FASTAPI_GATE_INCOMPLETE',
    'M013_FASTAPI_LIVE_MODE_REQUIRED'
)) {
    Assert-Contains $gate $marker "Séparation ou exhaustivité de gate absente."
}
Assert-Contains $lint '"-Mode", "Static"' "lint doit appeler uniquement la gate statique."
Assert-Contains $test '"-Mode", "Live"' "test doit appeler la gate live complète."

$testPaths = Get-ChildItem (Join-Path $repoRoot "tests/m013_fastapi") -Filter "validate_*.ps1" -File |
    ForEach-Object { "tests/m013_fastapi/$($_.Name)" }
foreach ($testPath in $testPaths) {
    Assert-Contains $gate $testPath "Validation M13-FastAPI non enrôlée: $testPath"
}

$matrix = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs/traceability/matrix.md")
$validator = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts/validate_traceability.ps1")
$journal = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs/tasks/milestone_013-fastapi/journal.md")
foreach ($task in 1..11) {
    $requirement = "REQ-M013-FASTAPI-{0:D3}" -f $task
    Assert-Contains $matrix $requirement "Exigence absente de la matrice."
    Assert-Contains $validator $requirement "Exigence absente du validateur."
    Assert-Contains $journal $requirement "Exigence absente du journal."
}

$pythonCode = @'
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.platform.orchestrator_runtime import build_orchestrator_composition_root
from app.source_processing.adapters.postgres_document_persistence import PostgresDocumentPersistence


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="review", status="ready")


async def scenario(repo_root: Path) -> None:
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=__import__("fastapi").APIRouter(),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    schema = application.openapi()
    registration = schema["paths"]["/v1/documents"]["post"]
    multipart = registration["requestBody"]["content"]["multipart/form-data"]["schema"]
    required = set(multipart["required"])
    assert required == {"original_content", "title", "authors", "publication_year", "edition"}
    assert multipart["properties"]["original_content"]["format"] == "binary"
    assert set(registration["responses"]) >= {"201", "400", "409", "422", "500"}
    for status in ("201", "400", "409", "422", "500"):
        response = registration["responses"][status]
        assert "application/json" in response["content"], (status, response)
        assert "$ref" in response["content"]["application/json"]["schema"], (status, response)
    original = schema["paths"]["/v1/documents/{document_id}/original"]["get"]
    assert "application/pdf" in original["responses"]["200"]["content"]
    diagnose = schema["paths"]["/v1/documents/{document_id}/diagnose"]["post"]
    assert set(diagnose["responses"]) >= {"202", "400", "404", "409", "422", "500"}

    router_source = (repo_root / "app/platform/orchestrator_contract_routers.py").read_text(encoding="utf-8")
    assert "local_runtime._" not in router_source
    assert "build_public_contract_router" in inspect.getsource(build_orchestrator_composition_root)

    build_source = inspect.getsource(build_orchestrator_composition_root)
    assert build_source.count("PsycopgConnectionFactory(") == 1
    assert "connection_factory=connection_factory" in build_source

    persistence_source = inspect.getsource(PostgresDocumentPersistence.list_document_snapshots)
    assert "limit" in persistence_source and "after_document_id" in persistence_source
    assert "ANY(%s)" in persistence_source
    assert persistence_source.count("cursor.execute(") <= 8

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.platform.local_runtime",
            "serve-http",
            "orchestrator-api",
            "8080",
            "--config",
            str(repo_root / "config" / "application.example.yaml"),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode != 0
    assert "ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN" in process.stderr


asyncio.run(scenario(Path(sys.argv[1])))

worker_source = (Path(sys.argv[1]) / "app/source_processing/adapters/worker_runtime.py").read_text(encoding="utf-8")
for marker in (
    "bind_trace_id(claimed.trace_id)",
    '"success_count"',
    '"error_count"',
    '"duration_ms"',
    '"processed_volume"',
    '"tracing_enabled"',
):
    assert marker in worker_source, marker

migration = (Path(sys.argv[1]) / "deploy/postgres/migrations/005_source_processing_read_performance.sql").read_text(encoding="utf-8")
assert "source_documents_editorial_duplicate_idx" in migration
assert "work_title, work_authors" in migration

persistence_all = (Path(sys.argv[1]) / "app/source_processing/adapters/postgres_document_persistence.py").read_text(encoding="utf-8")
for marker in ("jsonb_to_recordset", "page_manifest_entries", "page_decisions", "page_routes"):
    assert marker in persistence_all, marker

print("Revue gouvernance, OpenAPI, runtime, performance et observabilité: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_review_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force -ErrorAction SilentlyContinue
}
if ($exitCode -ne 0) {
    throw ($output -join "`n")
}
Write-Host "Test d'acceptation correctifs de revue M13-FastAPI: OK"
