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
    "tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.ps1",
    "tests/m013_fastapi/validate_ui_document_api_client_unit.ps1",
    "tests/m013_fastapi/validate_runtime_operations_acceptance.ps1",
    "tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_acceptance.ps1",
    "tests/m013_fastapi/validate_document_http_live_acceptance.ps1",
    "tests/m013_fastapi/validate_ka_projection_persistence_live.ps1",
    "tests/m013_fastapi/validate_orchestrator_deployment_unit.ps1",
    "tests/m013_fastapi/validate_m013_fastapi_traceability_unit.ps1",
    "tests/m013_fastapi/validate_review_governance_performance_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_safety_acceptance.ps1",
    "tests/m013_fastapi/validate_review3_safety_live.ps1"
)) {
    Assert-Contains $gate $testPath "Test T-011 absent de la gate M13-FastAPI."
}
Assert-Contains $testGate "scripts/validate_m013_fastapi.ps1" "Gate M13-FastAPI absente de scripts/test.ps1."
Assert-Contains $lintGate "scripts/validate_m013_fastapi.ps1" "Gate M13-FastAPI absente de scripts/lint.ps1."
foreach ($marker in @(
    "REQ-M013-FASTAPI-001",
    "REQ-M013-FASTAPI-002",
    "REQ-M013-FASTAPI-003",
    "REQ-M013-FASTAPI-004",
    "REQ-M013-FASTAPI-005",
    "REQ-M013-FASTAPI-006",
    "REQ-M013-FASTAPI-007",
    "REQ-M013-FASTAPI-008",
    "REQ-M013-FASTAPI-009",
    "REQ-M013-FASTAPI-010",
    "REQ-M013-FASTAPI-011",
    "docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md",
    "scripts/validate_m013_fastapi.ps1",
    "ADR-019",
    "ADR-020",
    "ADR-021",
    "ADR-024",
    "ADR-025"
)) {
    Assert-Contains $traceability $marker "Traçabilité T-011 incomplète."
}
foreach ($marker in @("## T-011", "Commit RED", "Commit GREEN", "ADR-019", "ADR-020")) {
    Assert-Contains $journal $marker "Journal T-011 incomplet."
}

Write-Host "Tests unitaires traçabilité M13-FastAPI: OK"
