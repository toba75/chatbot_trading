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
$m007SpecificationPath = Join-Path $repoRoot "docs/specs/m007_reponse_documentaire_verifiee.md"
$m008SpecificationPath = Join-Path $repoRoot "docs/specs/m008_conversation_produit.md"
$m009SpecificationPath = Join-Path $repoRoot "docs/specs/m009_recherche_approfondie_multi_sources.md"
$m010SpecificationPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"
$m011SpecificationPath = Join-Path $repoRoot "docs/specs/m011_experience_reproductible.md"
$m012SpecificationPath = Join-Path $repoRoot "docs/specs/m012_evaluation_pilote_calibration.md"
$m013SpecificationPath = Join-Path $repoRoot "docs/specs/m013_durcissement_acceptation_v1.md"
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
    @{ Path = "scripts/validate_m004_specification.ps1"; Arguments = @("-Path", $m004SpecificationPath) },
    @{ Path = "scripts/validate_m005_specification.ps1"; Arguments = @("-Path", $m005SpecificationPath) },
    @{ Path = "scripts/validate_m006_specification.ps1"; Arguments = @("-Path", $m006SpecificationPath) },
    @{ Path = "scripts/validate_m007_specification.ps1"; Arguments = @("-Path", $m007SpecificationPath) },
    @{ Path = "scripts/validate_m008_specification.ps1"; Arguments = @("-Path", $m008SpecificationPath) },
    @{ Path = "scripts/validate_m009_specification.ps1"; Arguments = @("-Path", $m009SpecificationPath) },
    @{ Path = "scripts/validate_m010_specification.ps1"; Arguments = @("-Path", $m010SpecificationPath) },
    @{ Path = "scripts/validate_m010_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m011_specification.ps1"; Arguments = @("-Path", $m011SpecificationPath) },
    @{ Path = "scripts/validate_m011_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m012_specification.ps1"; Arguments = @("-Path", $m012SpecificationPath) },
    @{ Path = "scripts/validate_m012_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m013_specification.ps1"; Arguments = @("-Path", $m013SpecificationPath) },
    @{ Path = "scripts/validate_m013_v1_gap_decisions.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m013_regression.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m013_security.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_platform_topology.ps1"; Arguments = @("-Path", $platformTopologyPath) },
    @{ Path = "scripts/validate_local_compose.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_network_boundary.ps1"; Arguments = @("-SparkFirewallPath", $sparkFirewallPath) },
    @{ Path = "scripts/validate_architecture_boundaries.ps1"; Arguments = @("-AppRoot", $appRoot, "-ContextRegistryPath", $contextRegistryPath, "-SpecificationPath", $m001SpecificationPath) }
)

$testCommands = @()

$expectedValidationPaths = @(
    "scripts/validate_m000_precondition_report.ps1",
    "scripts/validate_adr_system.ps1",
    "scripts/validate_task_system.ps1",
    "scripts/validate_traceability.ps1",
    "scripts/validate_definition_of_done.ps1",
    "scripts/validate_m001_specification.ps1",
    "scripts/validate_m002_specification.ps1",
    "scripts/validate_m003_specification.ps1",
    "scripts/validate_m004_specification.ps1",
    "scripts/validate_m005_specification.ps1",
    "scripts/validate_m006_specification.ps1",
    "scripts/validate_m007_specification.ps1",
    "scripts/validate_m008_specification.ps1",
    "scripts/validate_m009_specification.ps1",
    "scripts/validate_m010_specification.ps1",
    "scripts/validate_m010_traceability.ps1",
    "scripts/validate_m011_specification.ps1",
    "scripts/validate_m011_traceability.ps1",
    "scripts/validate_m012_specification.ps1",
    "scripts/validate_m012_traceability.ps1",
    "scripts/validate_m013_specification.ps1",
    "scripts/validate_m013_v1_gap_decisions.ps1",
    "scripts/validate_m013_regression.ps1",
    "scripts/validate_m013_security.ps1",
    "scripts/validate_platform_topology.ps1",
    "scripts/validate_local_compose.ps1",
    "scripts/validate_network_boundary.ps1",
    "scripts/validate_architecture_boundaries.ps1"
)

$expectedTestPaths = @()

Invoke-M000ValidationGate `
    -GateName "lint" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount 28 `
    -ExpectedTestCount 0 `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
