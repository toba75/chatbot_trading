param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("Static", "Live")]
    [string] $Mode
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Mode)) {
    throw "M013_FASTAPI_LIVE_MODE_REQUIRED: utiliser -Mode Static ou -Mode Live."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue
if ($null -eq $uvCommand) {
    throw "M013_FASTAPI_UV_REQUIRED: uv est requis pour matérialiser l'interpréteur verrouillé."
}

& $uvCommand.Source sync --frozen --no-dev --no-install-project
if ($LASTEXITCODE -ne 0) {
    throw "M013_FASTAPI_UV_SYNC_FAILED: uv sync --frozen --no-dev --no-install-project a échoué."
}

$lockedPythonDirectory = Join-Path $repoRoot ".venv\Scripts"
$lockedPython = Join-Path $lockedPythonDirectory "python.exe"
if (-not (Test-Path -LiteralPath $lockedPython -PathType Leaf)) {
    throw "M013_FASTAPI_LOCKED_PYTHON_REQUIRED: .venv\Scripts\python.exe absent après uv sync --frozen --no-dev --no-install-project."
}
$env:PATH = "$lockedPythonDirectory;$env:PATH"
$resolvedPython = @(Get-Command python -CommandType Application -ErrorAction Stop)[0].Source
if ((Resolve-Path -LiteralPath $resolvedPython).Path -ne (Resolve-Path -LiteralPath $lockedPython).Path) {
    throw "M013_FASTAPI_LOCKED_PYTHON_REQUIRED: la gate n'utilise pas l'interpréteur de uv.lock."
}

$staticTests = @(
    "tests/m013_fastapi/validate_precondition_acceptance.ps1",
    "tests/m013_fastapi/validate_precondition_unit.ps1",
    "tests/m013_fastapi/validate_fastapi_specification_acceptance.ps1",
    "tests/m013_fastapi/validate_fastapi_architecture_policy_unit.ps1",
    "tests/m013_fastapi/validate_orchestrator_asgi_health_acceptance.ps1",
    "tests/m013_fastapi/validate_orchestrator_app_factory_unit.ps1",
    "tests/m013_fastapi/validate_existing_api_contract_parity_acceptance.ps1",
    "tests/m013_fastapi/validate_existing_api_routers_unit.ps1",
    "tests/m013_fastapi/validate_document_persistence_restart_acceptance.ps1",
    "tests/m013_fastapi/validate_document_persistence_unit.ps1",
    "tests/m013_fastapi/validate_document_commands_http_acceptance.ps1",
    "tests/m013_fastapi/validate_document_command_router_unit.ps1",
    "tests/m013_fastapi/validate_document_read_models_acceptance.ps1",
    "tests/m013_fastapi/validate_document_queries_unit.ps1",
    "tests/m013_fastapi/validate_original_pdf_retrieval_acceptance.ps1",
    "tests/m013_fastapi/validate_original_pdf_stream_unit.ps1",
    "tests/m013_fastapi/validate_projection_read_model_acceptance.ps1",
    "tests/m013_fastapi/validate_projection_queries_unit.ps1",
    "tests/m013_fastapi/validate_ui_document_api_client_unit.ps1",
    "tests/m013_fastapi/validate_ui_product_contracts_unit.ps1",
    "tests/m013_fastapi/validate_runtime_operations_acceptance.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_acceptance.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_unit.ps1",
    "tests/m013_fastapi/validate_document_worker_runtime_acceptance.ps1",
    "tests/m013_fastapi/validate_job_outbox_boundary_acceptance.ps1",
    "tests/m013_fastapi/validate_worker_data_resilience_acceptance.ps1",
    "tests/m013_fastapi/validate_ka_projection_persistence_unit.ps1",
    "tests/m013_fastapi/validate_m013_fastapi_traceability_unit.ps1",
    "tests/m013_fastapi/validate_review_governance_performance_acceptance.ps1",
    "tests/m013_fastapi/validate_reproducible_operations_acceptance.ps1",
    "tests/m013_fastapi/validate_api_ui_iteration2_acceptance.ps1"
)
$liveTests = @(
    "tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1",
    "tests/m013_fastapi/validate_document_http_live_acceptance.ps1",
    "tests/m013_fastapi/validate_document_worker_live.ps1",
    "tests/m013_fastapi/validate_job_outbox_boundary_live.ps1",
    "tests/m013_fastapi/validate_ka_projection_persistence_live.ps1",
    "tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.ps1"
)

$declaredTests = @($staticTests + $liveTests | Sort-Object -Unique)
$discoveredTests = @(
    Get-ChildItem (Join-Path $repoRoot "tests/m013_fastapi") -Filter "validate_*.ps1" -File |
        ForEach-Object { "tests/m013_fastapi/$($_.Name)" } |
        Sort-Object -Unique
)
$missing = @($discoveredTests | Where-Object { $_ -notin $declaredTests })
$unknown = @($declaredTests | Where-Object { $_ -notin $discoveredTests })
if ($missing.Count -ne 0 -or $unknown.Count -ne 0) {
    throw "M013_FASTAPI_GATE_INCOMPLETE: missing=$($missing -join ','); unknown=$($unknown -join ',')"
}

$tests = if ($Mode -eq "Static") { $staticTests } else { @($staticTests + $liveTests) }
foreach ($test in $tests) {
    $testPath = Join-Path $repoRoot $test
    Write-Host "Validation $Mode requise: $test"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $testPath
    if ($LASTEXITCODE -ne 0) {
        throw "Validation M13-FastAPI $Mode RED: $test"
    }
    Write-Host "Validation GREEN: $test"
}

Write-Host "Gate M13-FastAPI $Mode GREEN: $($tests.Count) preuve(s), catalogue exhaustif contrôlé."
