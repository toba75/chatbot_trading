param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m011_experience_reproductible.md"

$requiredSections = @(
    "# M-011",
    "## Statut",
    "## Mission EX",
    "## Contexte DDD",
    "## Langage ubiquitaire EX",
    "## Ports et adaptateurs EX",
    "## API publique EX",
    "### Champs publics interdits",
    "## Comportements",
    "## Commandes de validation",
    "## Exclusions M-011"
)

$requiredTerms = @(
    "Experiment",
    "DataSnapshotRef",
    "CostModelSnapshot",
    "ExecutionEnvironment",
    "FrozenInputs",
    "ExperimentRepository",
    "ExperimentResultRepository",
    "ExperimentArtifactStore",
    "DeterministicBacktestEngineAdapter",
    "RepeatExperiment",
    "CompareExperiments",
    "ExperimentComparisonCompleted",
    "ExperimentScheduled",
    "ExperimentCancelled",
    "strategy_parameter_hash",
    "POST /v1/strategies/{id}/backtest",
    "GET /v1/experiments/{id}"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_precondition_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_planning_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_data_snapshot_freeze_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_cost_environment_freeze_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_start_lock_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_deterministic_backtest_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_result_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_retention_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_reproducibility_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_http_contract_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_traceability_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredAdrIds = @("ADR-010", "DDD-ADR-001", "DDD-ADR-008", "DDD-ADR-009", "DDD-ADR-010")
$requiredMetrics = @(
    "experiment_reproducible_rate",
    "experiment_failure_rate_by_cause",
    "negative_experiment_retention_ratio",
    "experiment_without_complete_cost_model_total",
    "coherent_repeat_count",
    "invalidated_result_ratio"
)

function Resolve-M011SpecificationPath {
    param([string] $InputPath)
    if ([string]::IsNullOrWhiteSpace($InputPath)) {
        $candidatePath = Join-Path $repoRoot $defaultSpecificationPath
    }
    elseif ([System.IO.Path]::IsPathRooted($InputPath)) {
        $candidatePath = $InputPath
    }
    else {
        $candidatePath = Join-Path $repoRoot $InputPath
    }
    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedCandidatePath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedCandidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors dépôt interdit (spécification M-011): $resolvedCandidatePath"
    }
    return $resolvedCandidatePath
}

function Assert-Contains {
    param([string] $Content, [string] $Expected, [string] $Message)
    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

$resolvedPath = Resolve-M011SpecificationPath -InputPath $Path
if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
    throw "Spécification M-011 absente: $resolvedPath"
}

$content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedPath).TrimStart([char] 0xFEFF)
$lines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedPath)
if ($lines.Count -gt 0) {
    $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
}

foreach ($section in $requiredSections) {
    if (-not $content.Contains($section)) {
        throw "Section obligatoire absente: $section"
    }
}
foreach ($term in $requiredTerms) {
    Assert-Contains -Content $content -Expected $term -Message "Terme M-011 absent: $term"
}
foreach ($command in $requiredCommands) {
    Assert-Contains -Content $content -Expected $command -Message "Commande de validation M-011 absente: $command"
}
foreach ($adrId in $requiredAdrIds) {
    Assert-Contains -Content $content -Expected $adrId -Message "ADR M-011 absente: $adrId"
}
foreach ($metric in $requiredMetrics) {
    Assert-Contains -Content $content -Expected $metric -Message "Métrique M-011 absente: $metric"
}

Write-Host "Specification M-011 valide: 12 comportement(s), 6 metrique(s), 6 etat(s) controles."
