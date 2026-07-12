$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Assert-Contains {
    param([string] $Content, [string] $Expected, [string] $Message)
    if (-not $Content.Contains($Expected)) {
        throw "$Message Valeur attendue: $Expected"
    }
}

$gatePath = Join-Path $repoRoot "scripts\validate_m013_fastapi.ps1"
if (-not (Test-Path -LiteralPath $gatePath -PathType Leaf)) {
    throw "Gate canonique M13-FastAPI absente."
}
$gate = Get-Content -Raw -Encoding UTF8 $gatePath
$testGate = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts\test.ps1")
$lintGate = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts\lint.ps1")
$traceability = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs\traceability\matrix.md")
$journal = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs\tasks\milestone_013-fastapi\journal.md")

foreach ($testPath in @(
    "tests/m013_fastapi/validate_document_command_router_unit.ps1",
    "tests/m013_fastapi/validate_original_pdf_stream_unit.ps1",
    "tests/m013_fastapi/validate_runtime_operations_acceptance.ps1",
    "tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_acceptance.ps1",
    "tests/m013_fastapi/validate_document_http_live_acceptance.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_unit.ps1",
    "tests/m013_fastapi/validate_m013_fastapi_traceability_unit.ps1"
)) {
    Assert-Contains $gate $testPath "Test T-011 absent de la gate M13-FastAPI."
}
Assert-Contains $testGate "scripts/validate_m013_fastapi.ps1" "Gate M13-FastAPI absente de scripts/test.ps1."
Assert-Contains $lintGate "scripts/validate_m013_fastapi.ps1" "Gate M13-FastAPI absente de scripts/lint.ps1."
foreach ($marker in @(
    "REQ-M013-FASTAPI-011",
    "docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md",
    "scripts/validate_m013_fastapi.ps1",
    "ADR-019",
    "ADR-020"
)) {
    Assert-Contains $traceability $marker "Traçabilité T-011 incomplète."
}
foreach ($marker in @("## T-011", "Commit RED", "Commit GREEN", "ADR-019", "ADR-020")) {
    Assert-Contains $journal $marker "Journal T-011 incomplet."
}

Write-Host "Tests unitaires traçabilité M13-FastAPI: OK"
