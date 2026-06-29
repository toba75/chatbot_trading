$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gatePath = Join-Path $PSScriptRoot "m000_validation_gate.ps1"

if (-not (Test-Path -LiteralPath $gatePath -PathType Leaf)) {
    throw "Agrégateur de validation absent: scripts/m000_validation_gate.ps1"
}

. $gatePath

$preconditionReportPath = Join-Path $repoRoot "docs/governance/m000_precondition_green_initiale.md"
$m001SpecificationPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"
$m002SpecificationPath = Join-Path $repoRoot "docs/specs/m002_plateforme_locale_sure.md"
$m003SpecificationPath = Join-Path $repoRoot "docs/specs/m003_source_enregistree_diagnostiquee_routee.md"
$m004SpecificationPath = Join-Path $repoRoot "docs/specs/m004_version_canonique_publiee.md"
$m005SpecificationPath = Join-Path $repoRoot "docs/specs/m005_projection_connaissance_recherchable.md"
$m006SpecificationPath = Join-Path $repoRoot "docs/specs/m006_claims_verifiables.md"
$platformTopologyPath = Join-Path $repoRoot "app/platform/topology_registry.json"
$sparkFirewallPath = Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json"
$appRoot = Join-Path $repoRoot "app"
$contextRegistryPath = Join-Path $repoRoot "app/context_registry.json"
$m003PreconditionAcceptancePath = "tests/m003/validate_m003_precondition_acceptance.ps1"
$m004PreconditionAcceptancePath = "tests/m004/validate_m004_precondition_acceptance.ps1"
$m005PreconditionAcceptancePath = "tests/m005/validate_m005_precondition_acceptance.ps1"
$m005PreconditionUnitPath = "tests/m005/validate_m005_precondition_unit.ps1"
$m006PreconditionAcceptancePath = "tests/m006/validate_m006_precondition_acceptance.ps1"
$m006PreconditionUnitPath = "tests/m006/validate_m006_precondition_unit.ps1"

$validationCommands = @(
    @{ Path = "scripts/validate_m000_precondition_report.ps1"; Arguments = @("-Path", $preconditionReportPath) },
    @{ Path = "scripts/validate_adr_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_task_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_definition_of_done.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m001_specification.ps1"; Arguments = @("-Path", $m001SpecificationPath) },
    @{ Path = "scripts/validate_m002_specification.ps1"; Arguments = @("-Path", $m002SpecificationPath) },
    @{ Path = "scripts/validate_m003_specification.ps1"; Arguments = @("-Path", $m003SpecificationPath) },
    @{ Path = "scripts/validate_m004_specification.ps1"; Arguments = @("-Path", $m004SpecificationPath) },
    @{ Path = "scripts/validate_m005_specification.ps1"; Arguments = @("-Path", $m005SpecificationPath) },
    @{ Path = "scripts/validate_m006_specification.ps1"; Arguments = @("-Path", $m006SpecificationPath) },
    @{ Path = "scripts/validate_platform_topology.ps1"; Arguments = @("-Path", $platformTopologyPath) },
    @{ Path = "scripts/validate_local_compose.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_network_boundary.ps1"; Arguments = @("-SparkFirewallPath", $sparkFirewallPath) },
    @{ Path = "scripts/validate_architecture_boundaries.ps1"; Arguments = @("-AppRoot", $appRoot, "-ContextRegistryPath", $contextRegistryPath, "-SpecificationPath", $m001SpecificationPath) }
)

# Les tests M-003 ciblés restent exécutés explicitement hors gate pour éviter une récursion.
$testCommands = @(
    @{ Path = "tests/governance/validate_m000_precondition_report_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_m000_precondition_report_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_adr_system_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_adr_system_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_task_system_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_task_system_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_definition_of_done_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_definition_of_done_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_m000_validation_commands_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_context_modules_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_context_registry_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_contract_identity_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_contract_identity_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_source_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_source_locator_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_evidence_claim_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_evidence_claim_contracts_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_research_outcome_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_research_outcome_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_strategy_experiment_contracts_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_event_envelope_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_event_envelope_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_architecture_boundaries_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_architecture_boundaries_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_platform_topology_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_platform_topology_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_local_compose_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_local_compose_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_network_boundary_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_network_boundary_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_failures_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_failures_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_outbox_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_outbox_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_job_runtime_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_job_runtime_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_gateway_observability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_gateway_observability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_route_plan_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_route_plan_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_review_quarantine_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_review_quarantine_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_commands_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_commands_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_http_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_audit_signals_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_page_conversion_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_page_conversion_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_text_authority_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_text_authority_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_quality_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_quality_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_source_locator_resolution_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_source_locator_resolution_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_event_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_event_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_document_conversion_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_document_conversion_command_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_index_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hierarchical_chunking_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hierarchical_chunking_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_metadata_filters_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_metadata_filters_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_encoding_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_encoding_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_qdrant_projection_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_qdrant_projection_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_events_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hybrid_search_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hybrid_search_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_trace_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_command_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_extraction_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_extraction_unit.ps1"; Arguments = @() }
)

function Get-GateCommandPaths {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Commands
    )

    return @($Commands | ForEach-Object { $_.Path })
}

$excludedPreconditionTestPaths = @()
if ($env:OST_M003_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-005 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-003 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m005PreconditionUnitPath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath
    )
}
elseif ($env:OST_M004_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-005 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-004 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m005PreconditionUnitPath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath
    )
}
elseif ($env:OST_M005_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-005 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-005 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-005 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath
    )
}
elseif ($env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: exécution imbriquée du validateur de précondition."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath
    )
}

if ($excludedPreconditionTestPaths.Count -gt 0) {
    $testCommands = @(
        $testCommands | Where-Object { $excludedPreconditionTestPaths -notcontains $_.Path }
    )
}

$expectedValidationPaths = Get-GateCommandPaths -Commands $validationCommands
$expectedTestPaths = Get-GateCommandPaths -Commands $testCommands
$expectedValidationCount = $expectedValidationPaths.Count
$expectedTestCount = $expectedTestPaths.Count
Invoke-M000ValidationGate `
    -GateName "test" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount $expectedValidationCount `
    -ExpectedTestCount $expectedTestCount `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
