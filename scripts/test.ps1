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
$platformTopologyPath = Join-Path $repoRoot "app/platform/topology_registry.json"
$sparkFirewallPath = Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json"
$appRoot = Join-Path $repoRoot "app"
$contextRegistryPath = Join-Path $repoRoot "app/context_registry.json"

$validationCommands = @(
    @{ Path = "scripts/validate_m000_precondition_report.ps1"; Arguments = @("-Path", $preconditionReportPath) },
    @{ Path = "scripts/validate_adr_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_task_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_definition_of_done.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m001_specification.ps1"; Arguments = @("-Path", $m001SpecificationPath) },
    @{ Path = "scripts/validate_m002_specification.ps1"; Arguments = @("-Path", $m002SpecificationPath) },
    @{ Path = "scripts/validate_m003_specification.ps1"; Arguments = @("-Path", $m003SpecificationPath) },
    @{ Path = "scripts/validate_platform_topology.ps1"; Arguments = @("-Path", $platformTopologyPath) },
    @{ Path = "scripts/validate_local_compose.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_network_boundary.ps1"; Arguments = @("-SparkFirewallPath", $sparkFirewallPath) },
    @{ Path = "scripts/validate_architecture_boundaries.ps1"; Arguments = @("-AppRoot", $appRoot, "-ContextRegistryPath", $contextRegistryPath, "-SpecificationPath", $m001SpecificationPath) }
)

# Le self-test d'acceptation T-006 reste exécuté explicitement hors gate pour éviter une récursion.
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
    @{ Path = "tests/m003/validate_m003_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_unit.ps1"; Arguments = @() }
)

$expectedValidationPaths = @(
    "scripts/validate_m000_precondition_report.ps1",
    "scripts/validate_adr_system.ps1",
    "scripts/validate_task_system.ps1",
    "scripts/validate_traceability.ps1",
    "scripts/validate_definition_of_done.ps1",
    "scripts/validate_m001_specification.ps1",
    "scripts/validate_m002_specification.ps1",
    "scripts/validate_m003_specification.ps1",
    "scripts/validate_platform_topology.ps1",
    "scripts/validate_local_compose.ps1",
    "scripts/validate_network_boundary.ps1",
    "scripts/validate_architecture_boundaries.ps1"
)

$expectedTestPaths = @(
    "tests/governance/validate_m000_precondition_report_acceptance.ps1",
    "tests/governance/validate_m000_precondition_report_unit.ps1",
    "tests/governance/validate_adr_system_acceptance.ps1",
    "tests/governance/validate_adr_system_unit.ps1",
    "tests/governance/validate_task_system_acceptance.ps1",
    "tests/governance/validate_task_system_unit.ps1",
    "tests/governance/validate_traceability_acceptance.ps1",
    "tests/governance/validate_traceability_unit.ps1",
    "tests/governance/validate_definition_of_done_acceptance.ps1",
    "tests/governance/validate_definition_of_done_unit.ps1",
    "tests/governance/validate_m000_validation_commands_unit.ps1",
    "tests/m001/validate_m001_specification_acceptance.ps1",
    "tests/m001/validate_m001_specification_unit.ps1",
    "tests/m001/validate_context_modules_acceptance.ps1",
    "tests/m001/validate_context_registry_unit.ps1",
    "tests/m001/validate_contract_identity_acceptance.ps1",
    "tests/m001/validate_contract_identity_unit.ps1",
    "tests/m001/validate_source_contracts_acceptance.ps1",
    "tests/m001/validate_source_locator_unit.ps1",
    "tests/m001/validate_evidence_claim_contracts_acceptance.ps1",
    "tests/m001/validate_evidence_claim_contracts_unit.ps1",
    "tests/m001/validate_research_outcome_contract_acceptance.ps1",
    "tests/m001/validate_research_outcome_contract_unit.ps1",
    "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1",
    "tests/m001/validate_strategy_experiment_contracts_unit.ps1",
    "tests/m001/validate_event_envelope_acceptance.ps1",
    "tests/m001/validate_event_envelope_unit.ps1",
    "tests/m001/validate_architecture_boundaries_acceptance.ps1",
    "tests/m001/validate_architecture_boundaries_unit.ps1",
    "tests/m001/validate_m001_traceability_acceptance.ps1",
    "tests/m001/validate_m001_traceability_unit.ps1",
    "tests/m002/validate_m002_specification_acceptance.ps1",
    "tests/m002/validate_m002_specification_unit.ps1",
    "tests/m002/validate_platform_topology_acceptance.ps1",
    "tests/m002/validate_platform_topology_unit.ps1",
    "tests/m002/validate_local_compose_acceptance.ps1",
    "tests/m002/validate_local_compose_unit.ps1",
    "tests/m002/validate_network_boundary_acceptance.ps1",
    "tests/m002/validate_network_boundary_unit.ps1",
    "tests/m002/validate_llm_gateway_contract_acceptance.ps1",
    "tests/m002/validate_llm_gateway_contract_unit.ps1",
    "tests/m002/validate_llm_gateway_failures_acceptance.ps1",
    "tests/m002/validate_llm_gateway_failures_unit.ps1",
    "tests/m002/validate_outbox_acceptance.ps1",
    "tests/m002/validate_outbox_unit.ps1",
    "tests/m002/validate_job_runtime_acceptance.ps1",
    "tests/m002/validate_job_runtime_unit.ps1",
    "tests/m002/validate_gateway_observability_acceptance.ps1",
    "tests/m002/validate_gateway_observability_unit.ps1",
    "tests/m002/validate_m002_traceability_acceptance.ps1",
    "tests/m002/validate_m002_traceability_unit.ps1",
    "tests/m003/validate_m003_specification_acceptance.ps1",
    "tests/m003/validate_m003_specification_unit.ps1",
    "tests/m003/validate_source_registration_acceptance.ps1",
    "tests/m003/validate_source_registration_unit.ps1",
    "tests/m003/validate_page_manifest_acceptance.ps1",
    "tests/m003/validate_page_manifest_unit.ps1",
    "tests/m003/validate_page_diagnostics_acceptance.ps1",
    "tests/m003/validate_page_diagnostics_unit.ps1"
)

Invoke-M000ValidationGate `
    -GateName "test" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount 12 `
    -ExpectedTestCount 59 `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
