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
    [ordered] @{
        Id = "REQ-M010-001"
        Source = "docs/tasks/milestone_010/0001_verifier_precondition_green.md"
        Test = "tests/m010/validate_m010_precondition_acceptance.ps1"
        Command = "scripts/validate_m010_precondition.ps1"
        Code = "scripts/validate_m010_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-002"
        Source = "docs/tasks/milestone_010/0002_publier_specification_strategie_candidate.md"
        Test = "tests/m010/validate_m010_specification_acceptance.ps1"
        Command = "scripts/validate_m010_specification.ps1"
        Code = "docs/specs/m010_strategie_candidate_attribuee.md"
        Adr = "ADR-010; DDD-ADR-009; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-003"
        Source = "docs/tasks/milestone_010/0003_ouvrir_strategie_candidate_depuis_resultat_verifie.md"
        Test = "tests/m010/validate_strategy_candidate_creation_acceptance.ps1"
        Command = "tests/m010/validate_strategy_candidate_creation_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/create_strategy_candidate.py; app/strategy_design/adapters/in_memory_strategy_candidate_repository.py"
        Adr = "ADR-010; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-004"
        Source = "docs/tasks/milestone_010/0004_attribuer_origines_regles_strategie.md"
        Test = "tests/m010/validate_strategy_rule_origin_acceptance.ps1"
        Command = "tests/m010/validate_strategy_rule_origin_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/manage_strategy_rules.py"
        Adr = "ADR-010; DDD-ADR-005; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-005"
        Source = "docs/tasks/milestone_010/0005_controler_parametres_calibration.md"
        Test = "tests/m010/validate_strategy_parameter_calibration_acceptance.ps1"
        Command = "tests/m010/validate_strategy_parameter_calibration_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/manage_strategy_parameters.py"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-006"
        Source = "docs/tasks/milestone_010/0006_analyser_compatibilite_strategie.md"
        Test = "tests/m010/validate_strategy_compatibility_acceptance.ps1"
        Command = "tests/m010/validate_strategy_compatibility_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py"
        Adr = "ADR-010; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-007"
        Source = "docs/tasks/milestone_010/0007_valider_strategie_candidate_diagnostics.md"
        Test = "tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1"
        Command = "tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/validate_strategy_candidate.py"
        Adr = "ADR-010; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-008"
        Source = "docs/tasks/milestone_010/0008_compiler_strategie_candidate_deterministe.md"
        Test = "tests/m010/validate_strategy_compilation_acceptance.ps1"
        Command = "tests/m010/validate_strategy_compilation_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/compile_strategy_candidate.py; app/strategy_design/adapters/deterministic_strategy_compiler_backend.py"
        Adr = "ADR-010; DDD-ADR-009"
    },
    [ordered] @{
        Id = "REQ-M010-009"
        Source = "docs/tasks/milestone_010/0009_creer_snapshot_strategie_immuable.md"
        Test = "tests/m010/validate_strategy_snapshot_acceptance.ps1"
        Command = "tests/m010/validate_strategy_snapshot_acceptance.ps1"
        Code = "app/strategy_design/domain/strategy_candidate.py; app/strategy_design/application/create_strategy_snapshot.py; app/strategy_design/adapters/in_memory_strategy_snapshot_store.py"
        Adr = "DDD-ADR-009; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-010"
        Source = "docs/tasks/milestone_010/0010_exposer_endpoints_strategies.md"
        Test = "tests/m010/validate_strategy_http_contract_acceptance.ps1"
        Command = "tests/m010/validate_strategy_http_contract_acceptance.ps1"
        Code = "app/strategy_design/adapters/strategy_http.py"
        Adr = "ADR-010; DDD-ADR-009; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M010-011"
        Source = "docs/tasks/milestone_010/0011_relier_m010_metriques_tracabilite_gates.md"
        Test = "tests/m010/validate_m010_traceability_acceptance.ps1"
        Command = "tests/m010/validate_m010_traceability_acceptance.ps1"
        Code = "app/strategy_design/application/traceability_metrics.py; scripts/validate_m010_traceability.ps1; docs/tasks/milestone_010/journal.md"
        Adr = "ADR-010; DDD-ADR-009; DDD-ADR-010"
    }
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

$forbiddenSensitivePayloads = @(
    "PROMPT_COMPLET_INTERDIT_M010",
    "secret-token-m010",
    "texte source complet interdit m010",
    "payload documentaire complet interdit m010",
    "mutable_snapshot_payload_complet_interdit"
)

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $candidatePath = $Path
    if ([string]::IsNullOrWhiteSpace($candidatePath)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif (-not [System.IO.Path]::IsPathRooted($candidatePath)) {
        $candidatePath = Join-Path $repoRoot $candidatePath
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    Assert-Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors depot interdit ($Label): $resolvedPath"
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"
    return $resolvedPath
}

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Normalize-MatrixPathCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    return @($Value.Split(";") | ForEach-Object {
        $path = $_.Trim().Replace("\", "/")
        if ($path.StartsWith("./")) {
            $path = $path.Substring(2)
        }
        $path
    } | Where-Object { $_ -ne "" }) -join "; "
}

function Get-CommandScript {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command
    )

    $pattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+\.?[\\/][^\s;|&]+)?\s*$"
    Assert-Condition `
        -Condition ($Command -match $pattern) `
        -Message "Commande M-010 invalide: $Command"
    $scriptPath = $Matches["script"].Replace("\", "/")
    if ($scriptPath.StartsWith("./")) {
        return $scriptPath.Substring(2)
    }
    return $scriptPath
}

function ConvertTo-M010RequirementMap {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent
    )

    $requirementsById = @{}
    foreach ($line in ($MatrixContent -split "`r?`n")) {
        if (-not $line.StartsWith("| REQ-M010-")) {
            continue
        }

        $cells = Split-MarkdownRow -Line $line
        Assert-Condition `
            -Condition ($cells.Count -eq 8) `
            -Message "Ligne M-010 incomplete: $line"

        $requirementId = $cells[0]
        $requirementsById[$requirementId] = [ordered] @{
            Source = Normalize-MatrixPathCell -Value $cells[1]
            Test = Normalize-MatrixPathCell -Value $cells[3]
            Command = Get-CommandScript -Command $cells[4]
            Code = Normalize-MatrixPathCell -Value $cells[5]
            Adr = $cells[6]
        }
    }

    return $requirementsById
}

function Assert-M010RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $RequirementsById
    )

    foreach ($expected in $expectedRequirements) {
        $requirementId = $expected["Id"]
        Assert-Condition `
            -Condition ($RequirementsById.ContainsKey($requirementId)) `
            -Message "Exigence M-010 absente: $requirementId"

        $requirement = $RequirementsById[$requirementId]
        foreach ($cellName in @("Source", "Test", "Command", "Code", "Adr")) {
            $expectedValue = $expected[$cellName]
            $actualValue = $requirement[$cellName]
            if ($actualValue -ne $expectedValue) {
                if ($cellName -eq "Test") {
                    throw "Test M-010 invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
                }
                if ($cellName -eq "Command") {
                    throw "Commande M-010 invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
                }
                if ($cellName -eq "Adr") {
                    throw "ADR M-010 invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
                }
                throw "$cellName M-010 invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
            }
        }
    }
}

function Get-NormativeMetricNames {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MetricsModuleContent
    )

    $tupleMatch = [regex]::Match(
        $MetricsModuleContent,
        "_NORMATIVE_METRIC_NAMES\s*=\s*\((?<body>[\s\S]*?)\)"
    )
    Assert-Condition `
        -Condition $tupleMatch.Success `
        -Message "Compteur normatif M-010 incoherent: tuple absent"

    return @([regex]::Matches($tupleMatch.Groups["body"].Value, '"(?<name>strategy_[a-z_]+)"') | ForEach-Object {
        $_.Groups["name"].Value
    })
}

$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"
$resolvedSpecificationPath = Resolve-RequiredPath -Path $SpecificationPath -DefaultRelativePath "docs/specs/m010_strategie_candidate_attribuee.md" -Label "specification"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "test gate"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "lint gate"
$resolvedMetricsModulePath = Resolve-RequiredPath -Path $MetricsModulePath -DefaultRelativePath "app/strategy_design/application/traceability_metrics.py" -Label "metrics module"

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSpecificationPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath
$metricsModuleContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMetricsModulePath

Assert-M010RequirementRows -RequirementsById (ConvertTo-M010RequirementMap -MatrixContent $matrixContent)

foreach ($testPath in $expectedM010TestPaths) {
    Assert-Condition `
        -Condition ($testGateContent.Contains($testPath)) `
        -Message "Gate test sans test M-010: $testPath"
}

$actualM010TestPaths = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "tests/m010") -Filter "*.ps1" -File | ForEach-Object {
    "tests/m010/$($_.Name)"
})
foreach ($testPath in $actualM010TestPaths) {
    Assert-Condition `
        -Condition ($testGateContent.Contains($testPath)) `
        -Message "Test M-010 hors scripts/test.ps1: $testPath"
}

Assert-Condition `
    -Condition ($lintGateContent.Contains("scripts/validate_m010_traceability.ps1")) `
    -Message "Gate lint sans validateur M-010"

$declaredMetricNames = Get-NormativeMetricNames -MetricsModuleContent $metricsModuleContent
foreach ($metricName in $expectedMetricNames) {
    Assert-Condition `
        -Condition ($declaredMetricNames -contains $metricName) `
        -Message "Metrique M-010 absente: $metricName"
    Assert-Condition `
        -Condition ($specificationContent.Contains($metricName)) `
        -Message "Metrique M-010 absente de la specification: $metricName"
}
Assert-Condition `
    -Condition (($declaredMetricNames.Count -eq 6) -and (($declaredMetricNames | Select-Object -Unique).Count -eq 6)) `
    -Message "Compteur normatif M-010 incoherent"

foreach ($sensitivePayload in $forbiddenSensitivePayloads) {
    Assert-Condition `
        -Condition (-not $metricsModuleContent.Contains($sensitivePayload)) `
        -Message "Payload sensible M-010 expose: $sensitivePayload"
}

Assert-Condition `
    -Condition ($matrixContent.Contains("concurrence optimiste")) `
    -Message "Concurrence optimiste M-010 absente"
Assert-Condition `
    -Condition ($matrixContent.Contains("StrategySnapshotCreated")) `
    -Message "Outbox StrategySnapshotCreated M-010 absente"
Assert-Condition `
    -Condition ($matrixContent.Contains("supersession de version")) `
    -Message "Supersession de version M-010 absente"

Write-Host "Tracabilite M-010 valide: $($expectedRequirements.Count) exigence(s), $($expectedMetricNames.Count) metrique(s)."
