$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gatePath = Join-Path $PSScriptRoot "m000_validation_gate.ps1"

if (-not (Test-Path -LiteralPath $gatePath -PathType Leaf)) {
    throw "Agrégateur de validation absent: scripts/m000_validation_gate.ps1"
}

. $gatePath

$preconditionReportPath = Join-Path $repoRoot "docs/governance/m000_precondition_green_initiale.md"

$validationCommands = @(
    @{ Path = "scripts/validate_m000_precondition_report.ps1"; Arguments = @("-Path", $preconditionReportPath) },
    @{ Path = "scripts/validate_adr_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_task_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_definition_of_done.ps1"; Arguments = @() }
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
    @{ Path = "tests/governance/validate_m000_validation_commands_unit.ps1"; Arguments = @() }
)

$expectedValidationPaths = @(
    "scripts/validate_m000_precondition_report.ps1",
    "scripts/validate_adr_system.ps1",
    "scripts/validate_task_system.ps1",
    "scripts/validate_traceability.ps1",
    "scripts/validate_definition_of_done.ps1"
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
    "tests/governance/validate_m000_validation_commands_unit.ps1"
)

Invoke-M000ValidationGate `
    -GateName "test" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount 5 `
    -ExpectedTestCount 11 `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
