param(
    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $SpecificationPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath,

    [Parameter(Mandatory = $false)]
    [string] $MetricsModulePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$expectedRequirements = @(
    @{ Id = "REQ-M011-001"; Test = "tests/m011/validate_m011_precondition_acceptance.ps1"; Command = "scripts/validate_m011_precondition.ps1"; Code = "scripts/validate_m011_precondition.ps1" },
    @{ Id = "REQ-M011-002"; Test = "tests/m011/validate_m011_specification_acceptance.ps1"; Command = "scripts/validate_m011_specification.ps1"; Code = "docs/specs/m011_experience_reproductible.md" },
    @{ Id = "REQ-M011-003"; Test = "tests/m011/validate_experiment_planning_acceptance.ps1"; Command = "tests/m011/validate_experiment_planning_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py; app/experimentation/application/experiment_workflow.py; app/experimentation/adapters/in_memory_experiment_repository.py" },
    @{ Id = "REQ-M011-004"; Test = "tests/m011/validate_data_snapshot_freeze_acceptance.ps1"; Command = "tests/m011/validate_data_snapshot_freeze_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py" },
    @{ Id = "REQ-M011-005"; Test = "tests/m011/validate_cost_environment_freeze_acceptance.ps1"; Command = "tests/m011/validate_cost_environment_freeze_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py" },
    @{ Id = "REQ-M011-006"; Test = "tests/m011/validate_experiment_start_lock_acceptance.ps1"; Command = "tests/m011/validate_experiment_start_lock_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py; app/experimentation/application/experiment_workflow.py" },
    @{ Id = "REQ-M011-007"; Test = "tests/m011/validate_deterministic_backtest_acceptance.ps1"; Command = "tests/m011/validate_deterministic_backtest_acceptance.ps1"; Code = "app/experimentation/adapters/deterministic_backtest_engine.py" },
    @{ Id = "REQ-M011-008"; Test = "tests/m011/validate_experiment_result_acceptance.ps1"; Command = "tests/m011/validate_experiment_result_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py; app/experimentation/adapters/in_memory_experiment_repository.py" },
    @{ Id = "REQ-M011-009"; Test = "tests/m011/validate_experiment_retention_acceptance.ps1"; Command = "tests/m011/validate_experiment_retention_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py; app/experimentation/adapters/in_memory_experiment_repository.py" },
    @{ Id = "REQ-M011-010"; Test = "tests/m011/validate_experiment_reproducibility_acceptance.ps1"; Command = "tests/m011/validate_experiment_reproducibility_acceptance.ps1"; Code = "app/experimentation/domain/experiment.py; app/experimentation/application/experiment_workflow.py" },
    @{ Id = "REQ-M011-011"; Test = "tests/m011/validate_experiment_http_contract_acceptance.ps1"; Command = "tests/m011/validate_experiment_http_contract_acceptance.ps1"; Code = "app/experimentation/adapters/experiment_http.py" },
    @{ Id = "REQ-M011-012"; Test = "tests/m011/validate_m011_traceability_acceptance.ps1"; Command = "scripts/validate_m011_traceability.ps1"; Code = "app/experimentation/application/traceability_metrics.py; scripts/validate_m011_traceability.ps1; docs/tasks/milestone_011/journal.md" }
)

$expectedM011TestPaths = @(
    "tests/m011/validate_m011_precondition_acceptance.ps1",
    "tests/m011/validate_m011_precondition_unit.ps1",
    "tests/m011/validate_m011_specification_acceptance.ps1",
    "tests/m011/validate_m011_specification_unit.ps1",
    "tests/m011/validate_experiment_planning_acceptance.ps1",
    "tests/m011/validate_experiment_planning_unit.ps1",
    "tests/m011/validate_data_snapshot_freeze_acceptance.ps1",
    "tests/m011/validate_data_snapshot_freeze_unit.ps1",
    "tests/m011/validate_cost_environment_freeze_acceptance.ps1",
    "tests/m011/validate_cost_environment_freeze_unit.ps1",
    "tests/m011/validate_experiment_start_lock_acceptance.ps1",
    "tests/m011/validate_experiment_start_lock_unit.ps1",
    "tests/m011/validate_deterministic_backtest_acceptance.ps1",
    "tests/m011/validate_deterministic_backtest_unit.ps1",
    "tests/m011/validate_experiment_result_acceptance.ps1",
    "tests/m011/validate_experiment_result_unit.ps1",
    "tests/m011/validate_experiment_retention_acceptance.ps1",
    "tests/m011/validate_experiment_retention_unit.ps1",
    "tests/m011/validate_experiment_reproducibility_acceptance.ps1",
    "tests/m011/validate_experiment_reproducibility_unit.ps1",
    "tests/m011/validate_experiment_http_contract_acceptance.ps1",
    "tests/m011/validate_experiment_http_contract_unit.ps1",
    "tests/m011/validate_m011_traceability_acceptance.ps1",
    "tests/m011/validate_m011_traceability_unit.ps1"
)

$expectedMetricNames = @(
    "experiment_reproducible_rate",
    "experiment_failure_rate_by_cause",
    "negative_experiment_retention_ratio",
    "experiment_without_complete_cost_model_total",
    "coherent_repeat_count",
    "invalidated_result_ratio"
)

$forbiddenSensitivePayloads = @(
    "PROMPT_COMPLET_INTERDIT_M011",
    "secret-token-m011",
    "donnees_marche_completes_interdites_m011",
    "raw_engine_payload_interdit_m011"
)

function Resolve-RequiredPath {
    param([string] $Path, [string] $DefaultRelativePath, [string] $Label)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }
    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors depot interdit ($Label): $resolvedPath"
    }
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        throw "Fichier requis absent ($Label): $resolvedPath"
    }
    return $resolvedPath
}

function Split-MarkdownRow {
    param([string] $Line)
    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Normalize-MatrixPathCell {
    param([string] $Value)
    return @($Value.Split(";") | ForEach-Object {
        $path = $_.Trim().Replace("\", "/")
        if ($path.StartsWith("./")) { $path = $path.Substring(2) }
        $path
    } | Where-Object { $_ -ne "" }) -join "; "
}

function Get-CommandScript {
    param([string] $Command)
    $pattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+\.?[\\/][^\s;|&]+)?\s*$"
    if (-not ($Command -match $pattern)) {
        throw "Commande M-011 invalide: $Command"
    }
    $scriptPath = $Matches["script"].Replace("\", "/")
    if ($scriptPath.StartsWith("./")) { return $scriptPath.Substring(2) }
    return $scriptPath
}

function ConvertTo-M011RequirementMap {
    param([string] $MatrixContent)
    $requirementsById = @{}
    foreach ($line in ($MatrixContent -split "`r?`n")) {
        if (-not $line.StartsWith("| REQ-M011-")) { continue }
        $cells = Split-MarkdownRow -Line $line
        if ($cells.Count -ne 8) { throw "Ligne M-011 incomplete: $line" }
        $requirementsById[$cells[0]] = @{
            Test = Normalize-MatrixPathCell -Value $cells[3]
            Command = Get-CommandScript -Command $cells[4]
            Code = Normalize-MatrixPathCell -Value $cells[5]
        }
    }
    return $requirementsById
}

function Get-NormativeMetricNames {
    param([string] $MetricsModuleContent)
    $tupleMatch = [regex]::Match($MetricsModuleContent, "_NORMATIVE_METRIC_NAMES\s*=\s*\((?<body>[\s\S]*?)\)")
    if (-not $tupleMatch.Success) { throw "Compteur normatif M-011 incoherent: tuple absent" }
    return @([regex]::Matches($tupleMatch.Groups["body"].Value, '"(?<name>[a-z_]+)"') | ForEach-Object {
        $_.Groups["name"].Value
    })
}

$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"
$resolvedSpecificationPath = Resolve-RequiredPath -Path $SpecificationPath -DefaultRelativePath "docs/specs/m011_experience_reproductible.md" -Label "specification"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "test gate"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "lint gate"
$resolvedMetricsModulePath = Resolve-RequiredPath -Path $MetricsModulePath -DefaultRelativePath "app/experimentation/application/traceability_metrics.py" -Label "metrics module"

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSpecificationPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath
$metricsModuleContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMetricsModulePath

$requirementsById = ConvertTo-M011RequirementMap -MatrixContent $matrixContent
foreach ($expected in $expectedRequirements) {
    $requirementId = $expected["Id"]
    if (-not $requirementsById.ContainsKey($requirementId)) {
        throw "Exigence M-011 absente: $requirementId"
    }
    foreach ($cellName in @("Test", "Command", "Code")) {
        if ($requirementsById[$requirementId][$cellName] -ne $expected[$cellName]) {
            throw "$cellName M-011 invalide pour ${requirementId}. Attendu: $($expected[$cellName]). Obtenu: $($requirementsById[$requirementId][$cellName])"
        }
    }
}

foreach ($testPath in $expectedM011TestPaths) {
    if (-not $testGateContent.Contains($testPath)) {
        throw "Gate test sans test M-011: $testPath"
    }
}
if (-not $lintGateContent.Contains("scripts/validate_m011_traceability.ps1")) {
    throw "Gate lint sans validateur M-011"
}

$declaredMetricNames = Get-NormativeMetricNames -MetricsModuleContent $metricsModuleContent
foreach ($metricName in $expectedMetricNames) {
    if ($declaredMetricNames -notcontains $metricName) {
        throw "Metrique M-011 absente: $metricName"
    }
    if (-not $specificationContent.Contains($metricName)) {
        throw "Metrique M-011 absente de la specification: $metricName"
    }
}
if (($declaredMetricNames.Count -ne 6) -or (($declaredMetricNames | Select-Object -Unique).Count -ne 6)) {
    throw "Compteur normatif M-011 incoherent"
}

foreach ($sensitivePayload in $forbiddenSensitivePayloads) {
    if ($metricsModuleContent.Contains($sensitivePayload)) {
        throw "Payload sensible M-011 expose: $sensitivePayload"
    }
}

foreach ($marker in @(
    "registre append-only des experiences",
    "ExperimentRepository",
    "ExperimentResultRepository",
    "ExperimentArtifactStore",
    "RepeatExperiment",
    "CompareExperiments",
    "ExperimentComparisonCompleted",
    "ExperimentScheduled",
    "ExperimentCancelled",
    "correction par nouvelle experience liee",
    "minimum_backtest_control_count",
    "POST /v1/strategies/{id}/backtest",
    "GET /v1/experiments/{id}"
)) {
    if (-not $matrixContent.Contains($marker)) {
        throw "Marqueur M-011 absent: $marker"
    }
}

Write-Host "Tracabilite M-011 valide: $($expectedRequirements.Count) exigence(s), $($expectedMetricNames.Count) metrique(s)."
