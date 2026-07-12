$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$tests = @(
    "tests/m013_fastapi/validate_orchestrator_deployment_acceptance.ps1",
    "tests/m013_fastapi/validate_document_http_live_acceptance.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_unit.ps1",
    "tests/m013_fastapi/validate_m013_fastapi_traceability_unit.ps1"
)

foreach ($test in $tests) {
    $testPath = Join-Path $repoRoot $test
    if (-not (Test-Path -LiteralPath $testPath -PathType Leaf)) {
        throw "Test M13-FastAPI absent: $test"
    }
    Write-Host "Validation requise: $test"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $testPath
    if ($LASTEXITCODE -ne 0) {
        throw "Validation M13-FastAPI RED: $test"
    }
    Write-Host "Validation GREEN: $test"
}

Write-Host "Gate M13-FastAPI GREEN: 4 preuve(s), Docker/PostgreSQL/PDF/Uvicorn inclus."
