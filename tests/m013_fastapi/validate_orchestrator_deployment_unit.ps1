$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonPreflight = Join-Path $repoRoot "scripts\require_python.ps1"
. $pythonPreflight
$python = Get-RequiredPythonExecutable
$env:PYTHONPATH = $repoRoot
$env:PYTHONIOENCODING = "utf-8"

$test = @'
import sys
from pathlib import Path

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_runtime import build_orchestrator_composition_root


repo_root = Path(sys.argv[1])
configuration = load_application_configuration(
    repo_root / "config" / "application.example.yaml",
    {},
)
root = build_orchestrator_composition_root(configuration)
application = create_orchestrator_app(
    configuration=configuration,
    composition_root_factory=build_orchestrator_composition_root,
)

assert root.configuration is configuration
assert len(root.dependencies) == 1
assert root.dependencies[0].readiness().name == "postgres"
application.include_router(root.document_command_router)

paths = tuple(route.path for route in application.routes)
required_paths = (
    "/health",
    "/ready",
    "/openapi.json",
    "/v1/documents",
    "/v1/documents/{document_id}/diagnose",
    "/v1/documents/{document_id}/diagnostic",
    "/v1/documents/{document_id}/conversion",
    "/v1/documents/{document_id}/original",
    "/v1/documents/{document_id}/projection",
)
for required_path in required_paths:
    assert required_path in paths, required_path
assert paths.count("/v1/documents") == 2
assert application.title == "OSTrading orchestrator-api"
assert application.docs_url is None
assert application.redoc_url is None

openapi_text = str(application.openapi())
for internal_name in (
    "original_storage_ref",
    "processing_run_id",
    "job_id",
    "qdrant_collection",
    "postgres_password_path",
):
    assert internal_name not in openapi_text, internal_name

print("Tests unitaires déploiement orchestrator-api: OK")
'@

$test | & $python -B - $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Tests unitaires déploiement orchestrator-api RED."
}
