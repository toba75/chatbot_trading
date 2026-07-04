$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$specificationPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"
$validatorPath = Join-Path $repoRoot "scripts/validate_m010_traceability.ps1"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsModulePath = Join-Path $repoRoot "app/strategy_design/application/traceability_metrics.py"
$journalPath = Join-Path $repoRoot "docs/tasks/milestone_010/journal.md"

$expectedRequirementIds = @(
    "REQ-M010-001",
    "REQ-M010-002",
    "REQ-M010-003",
    "REQ-M010-004",
    "REQ-M010-005",
    "REQ-M010-006",
    "REQ-M010-007",
    "REQ-M010-008",
    "REQ-M010-009",
    "REQ-M010-010",
    "REQ-M010-011"
)

$expectedM010TestPaths = @(
    "tests/m010/validate_m010_precondition_acceptance.ps1",
    "tests/m010/validate_m010_precondition_unit.ps1",
    "tests/m010/validate_m010_specification_acceptance.ps1",
    "tests/m010/validate_m010_specification_unit.ps1",
    "tests/m010/validate_strategy_candidate_creation_acceptance.ps1",
    "tests/m010/validate_strategy_candidate_creation_unit.ps1",
    "tests/m010/validate_strategy_rule_origin_acceptance.ps1",
    "tests/m010/validate_strategy_rule_origin_unit.ps1",
    "tests/m010/validate_strategy_parameter_calibration_acceptance.ps1",
    "tests/m010/validate_strategy_parameter_calibration_unit.ps1",
    "tests/m010/validate_strategy_compatibility_acceptance.ps1",
    "tests/m010/validate_strategy_compatibility_unit.ps1",
    "tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1",
    "tests/m010/validate_strategy_candidate_diagnostics_unit.ps1",
    "tests/m010/validate_strategy_compilation_acceptance.ps1",
    "tests/m010/validate_strategy_compilation_unit.ps1",
    "tests/m010/validate_strategy_snapshot_acceptance.ps1",
    "tests/m010/validate_strategy_snapshot_unit.ps1",
    "tests/m010/validate_strategy_http_contract_acceptance.ps1",
    "tests/m010/validate_strategy_http_contract_unit.ps1",
    "tests/m010/validate_m010_traceability_acceptance.ps1",
    "tests/m010/validate_m010_traceability_unit.ps1"
)

$expectedMetricNames = @(
    "strategy_compilable_rate",
    "strategy_rejection_reason_top",
    "strategy_rule_origin_proportion",
    "strategy_parameter_without_calibration_plan_total",
    "strategy_compatibility_conflict_by_category",
    "strategy_versions_per_strategy"
)

function Assert-File {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message Chemin attendu: $Path"
    }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw "$Message Element attendu: $Expected"
    }
}

function Assert-NotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content.Contains($Forbidden)) {
        throw "$Message Element interdit: $Forbidden"
    }
}

function Invoke-M010TraceabilityValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Validateur M-010 RED. Sortie: $($output -join "`n")"
    }
}

Assert-File -Path $matrixPath -Message "Matrice de tracabilite absente."
Assert-File -Path $specificationPath -Message "Specification M-010 absente."
Assert-File -Path $validatorPath -Message "Validateur de tracabilite M-010 absent."
Assert-File -Path $traceabilityValidatorPath -Message "Validateur de tracabilite transverse absent."
Assert-File -Path $testGatePath -Message "Gate test absent."
Assert-File -Path $lintGatePath -Message "Gate lint absent."
Assert-File -Path $metricsModulePath -Message "Module de metriques SD M-010 absent."
Assert-File -Path $journalPath -Message "Journal M-010 absent."

# Given M-010 a livre creation, attribution, validation, compilation, snapshot et API strategie.
# When les gates transverses sont executees.
# Then chaque exigence M-010 est reliee a un test GREEN, les six metriques SD normatives sont publiees
# et les validateurs globaux restent GREEN sans payload sensible.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $specificationPath
$validatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $validatorPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath
$metricsModuleContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $metricsModulePath
$journalContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $journalPath

foreach ($requirementId in $expectedRequirementIds) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-010 absente de la matrice."
    Assert-Contains -Content $validatorContent -Expected $requirementId -Message "Exigence M-010 absente du validateur dedie."
}

foreach ($testPath in $expectedM010TestPaths) {
    Assert-Contains -Content $testGateContent -Expected $testPath -Message "Test M-010 non enrole dans scripts/test.ps1."
}

Assert-Contains -Content $lintGateContent -Expected "scripts/validate_m010_traceability.ps1" -Message "Validateur M-010 absent de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_traceability.ps1" -Message "Validateur transverse absent de scripts/lint.ps1."
Assert-Contains -Content $matrixContent -Expected "tests/m010/validate_m010_traceability_acceptance.ps1" -Message "Test d'acceptation T-011 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "tests/m010/validate_m010_traceability_unit.ps1" -Message "Test unitaire T-011 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/strategy_design/application/traceability_metrics.py" -Message "Module de metriques SD absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "concurrence optimiste" -Message "Concurrence optimiste absente de la matrice."
Assert-Contains -Content $matrixContent -Expected "StrategySnapshotCreated" -Message "Outbox StrategySnapshotCreated absente de la matrice."
Assert-Contains -Content $matrixContent -Expected "supersession de version" -Message "Supersession de version absente de la matrice."

foreach ($metricName in $expectedMetricNames) {
    Assert-Contains -Content $metricsModuleContent -Expected $metricName -Message "Metrique normative M-010 absente du module SD."
    Assert-Contains -Content $specificationContent -Expected $metricName -Message "Metrique normative M-010 absente de la specification."
    Assert-Contains -Content $validatorContent -Expected $metricName -Message "Metrique normative M-010 absente du validateur dedie."
}

foreach ($sensitivePayload in @(
    "PROMPT_COMPLET_INTERDIT_M010",
    "secret-token-m010",
    "texte source complet interdit m010",
    "payload documentaire complet interdit m010",
    "mutable_snapshot_payload_complet_interdit"
)) {
    Assert-NotContains -Content $metricsModuleContent -Forbidden $sensitivePayload -Message "Les metriques M-010 ne doivent pas exposer de payload sensible."
}

Assert-Contains -Content $journalContent -Expected "### T-011 -" -Message "Journal T-011 absent."
Assert-Contains -Content $journalContent -Expected "T-011 applique" -Message "Journal T-011 incomplet."
Assert-Contains -Content $journalContent -Expected "ADR: aucune nouvelle ADR" -Message "Le journal doit justifier l'absence de nouvelle ADR."
Assert-Contains -Content $journalContent -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_acceptance.ps1" -Message "Commande d'acceptation T-011 absente du journal."
Assert-Contains -Content $journalContent -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_traceability.ps1" -Message "Commande du validateur M-010 absente du journal."
Assert-Contains -Content $traceabilityValidatorContent -Expected "Assert-M009RequirementRows" -Message "Le validateur transverse doit rester actif pour les milestones amont."

Invoke-M010TraceabilityValidator

Write-Host "Test d'acceptation T-011 tracabilite, metriques et gates M-010: OK"
