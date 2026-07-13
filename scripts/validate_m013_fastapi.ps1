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

$lockHeader = Get-Content -Encoding UTF8 (Join-Path $repoRoot "uv.lock") -TotalCount 5 | Out-String
$pythonVersionMatch = [regex]::Match($lockHeader, 'requires-python\s*=\s*"==(?<version>\d+\.\d+\.\d+)"')
if (-not $pythonVersionMatch.Success) {
    throw "M013_FASTAPI_LOCKED_PYTHON_VERSION_REQUIRED: uv.lock doit verrouiller une version Python exacte."
}
$lockedPythonVersion = $pythonVersionMatch.Groups["version"].Value
$temporaryEnvironment = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("m013-fastapi-gate-" + [guid]::NewGuid().ToString("N"))
$previousPath = $env:PATH
$previousVirtualEnvironment = [System.Environment]::GetEnvironmentVariable("VIRTUAL_ENV", "Process")
$previousUvProjectEnvironment = [System.Environment]::GetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", "Process")
$previousM013Python = [System.Environment]::GetEnvironmentVariable("M013_FASTAPI_PYTHON", "Process")
$locationPushed = $false
Write-Host "M013_FASTAPI_TEMP_ENVIRONMENT: $temporaryEnvironment"

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
    "tests/m013_fastapi/validate_api_ui_iteration2_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_safety_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_deployment_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_api_architecture_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_ui_security_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_maintenance_acceptance.ps1"
)
$liveTests = @(
    "tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1",
    "tests/m013_fastapi/validate_document_http_live_acceptance.ps1",
    "tests/m013_fastapi/validate_document_worker_live.ps1",
    "tests/m013_fastapi/validate_job_outbox_boundary_live.ps1",
    "tests/m013_fastapi/validate_ka_projection_persistence_live.ps1",
    "tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_safety_live.ps1",
    "tests/m013_fastapi/validate_review3_deployment_live.ps1",
    "tests/m013_fastapi/validate_review3_ui_security_live.ps1"
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
try {
    Push-Location $repoRoot
    $locationPushed = $true
    & $uvCommand.Source venv --no-project --python $lockedPythonVersion $temporaryEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "M013_FASTAPI_UV_VENV_FAILED: uv n'a pas créé l'environnement Python $lockedPythonVersion isolé."
    }
    $lockedPythonDirectory = Join-Path $temporaryEnvironment "Scripts"
    $lockedPython = Join-Path $lockedPythonDirectory "python.exe"
    if (-not (Test-Path -LiteralPath $lockedPython -PathType Leaf)) {
        throw "M013_FASTAPI_LOCKED_PYTHON_REQUIRED: python.exe absent de l'environnement uv isolé."
    }
    $env:VIRTUAL_ENV = $temporaryEnvironment
    $env:UV_PROJECT_ENVIRONMENT = $temporaryEnvironment
    $env:M013_FASTAPI_PYTHON = $lockedPython
    $env:PATH = "$lockedPythonDirectory;$previousPath"
    & $uvCommand.Source sync --frozen --no-dev --active --no-install-project --python $lockedPython
    if ($LASTEXITCODE -ne 0) {
        throw "M013_FASTAPI_UV_SYNC_FAILED: uv sync --frozen --no-dev --active --no-install-project a échoué dans l'environnement isolé."
    }
    $resolvedVersion = (& $lockedPython -c "import platform; print(platform.python_version())").Trim()
    if ($LASTEXITCODE -ne 0 -or $resolvedVersion -ne $lockedPythonVersion) {
        throw "M013_FASTAPI_LOCKED_PYTHON_REQUIRED: version attendue=$lockedPythonVersion; obtenue=$resolvedVersion."
    }

    foreach ($test in $tests) {
        $testPath = Join-Path $repoRoot $test
        Write-Host "Validation $Mode requise: $test"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $testPath
        if ($LASTEXITCODE -ne 0) {
            throw "Validation M13-FastAPI $Mode RED: $test"
        }
        Write-Host "Validation GREEN: $test"
    }
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
    $env:PATH = $previousPath
    foreach ($variable in @(
        @{ Name = "VIRTUAL_ENV"; Value = $previousVirtualEnvironment },
        @{ Name = "UV_PROJECT_ENVIRONMENT"; Value = $previousUvProjectEnvironment },
        @{ Name = "M013_FASTAPI_PYTHON"; Value = $previousM013Python }
    )) {
        if ($null -eq $variable.Value) {
            Remove-Item -Path "Env:$($variable.Name)" -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -Path "Env:$($variable.Name)" -Value $variable.Value
        }
    }
    if (Test-Path -LiteralPath $temporaryEnvironment) {
        Remove-Item -LiteralPath $temporaryEnvironment -Recurse -Force
    }
}

Write-Host "Gate M13-FastAPI $Mode GREEN: $($tests.Count) preuve(s), catalogue exhaustif contrôlé."
