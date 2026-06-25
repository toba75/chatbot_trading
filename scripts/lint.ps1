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
    "scripts/validate_architecture_boundaries.ps1"
)

$expectedTestPaths = @()

Invoke-M000ValidationGate `
    -GateName "lint" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount 8 `
    -ExpectedTestCount 0 `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
