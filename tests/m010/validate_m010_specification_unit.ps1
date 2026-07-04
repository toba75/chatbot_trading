$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m010_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m010_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidM010SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-010 absente pour le fixture unitaire: docs/specs/m010_strategie_candidate_attribuee.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M010SpecificationValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $SpecPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function New-TemporarySpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $specPath = Join-Path $temporaryRoot "$Name.md"
    $Content | Set-Content -Encoding UTF8 -LiteralPath $specPath
    return $specPath
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-010 absent: scripts/validate_m010_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM010SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M010SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-010 conforme doit être acceptée."

    $missingMissionSpecPath = New-TemporarySpec `
        -Name "missing-mission-sd" `
        -Content ($validContent.Replace("## Mission SD", "## Mission incomplète"))
    $missingMissionResult = Invoke-M010SpecificationValidator -SpecPath $missingMissionSpecPath
    Assert-ExitCode -Actual $missingMissionResult.ExitCode -Expected 1 -Message "Une mission SD absente doit être refusée."
    Assert-OutputContains -Output $missingMissionResult.Output -Expected "Section obligatoire absente: ## Mission SD" -Message "La mission absente doit être nommée."

    $missingAggregateSpecPath = New-TemporarySpec `
        -Name "missing-strategy-candidate" `
        -Content ($validContent.Replace("StrategyCandidate", "CandidateSansContrat"))
    $missingAggregateResult = Invoke-M010SpecificationValidator -SpecPath $missingAggregateSpecPath
    Assert-ExitCode -Actual $missingAggregateResult.ExitCode -Expected 1 -Message "L'agrégat StrategyCandidate doit être obligatoire."
    Assert-OutputContains -Output $missingAggregateResult.Output -Expected "StrategyCandidate" -Message "L'agrégat absent doit être nommé."

    $missingOriginsSpecPath = New-TemporarySpec `
        -Name "missing-origins" `
        -Content ($validContent.Replace("PARAMETER_TO_CALIBRATE", "PARAMETER_OPTIONAL"))
    $missingOriginsResult = Invoke-M010SpecificationValidator -SpecPath $missingOriginsSpecPath
    Assert-ExitCode -Actual $missingOriginsResult.ExitCode -Expected 1 -Message "Les origines autorisées doivent être obligatoires."
    Assert-OutputContains -Output $missingOriginsResult.Output -Expected "PARAMETER_TO_CALIBRATE" -Message "L'origine absente doit être nommée."

    $missingCalibrationSpecPath = New-TemporarySpec `
        -Name "missing-calibration-protocol" `
        -Content ($validContent.Replace("ParameterCalibrationPolicy", "ParameterTuningPolicy"))
    $missingCalibrationResult = Invoke-M010SpecificationValidator -SpecPath $missingCalibrationSpecPath
    Assert-ExitCode -Actual $missingCalibrationResult.ExitCode -Expected 1 -Message "Le protocole de calibration doit être obligatoire."
    Assert-OutputContains -Output $missingCalibrationResult.Output -Expected "ParameterCalibrationPolicy" -Message "La politique absente doit être nommée."

    $missingCompatibilitySpecPath = New-TemporarySpec `
        -Name "missing-compatibility" `
        -Content ($validContent.Replace("StrategyCompatibilityPolicy", "StrategyConsistencyPolicy"))
    $missingCompatibilityResult = Invoke-M010SpecificationValidator -SpecPath $missingCompatibilitySpecPath
    Assert-ExitCode -Actual $missingCompatibilityResult.ExitCode -Expected 1 -Message "La compatibilité de stratégie doit être obligatoire."
    Assert-OutputContains -Output $missingCompatibilityResult.Output -Expected "StrategyCompatibilityPolicy" -Message "La compatibilité absente doit être nommée."

    $missingSnapshotSpecPath = New-TemporarySpec `
        -Name "missing-snapshot" `
        -Content ($validContent.Replace("StrategySnapshot", "StrategyExport"))
    $missingSnapshotResult = Invoke-M010SpecificationValidator -SpecPath $missingSnapshotSpecPath
    Assert-ExitCode -Actual $missingSnapshotResult.ExitCode -Expected 1 -Message "Le snapshot immuable doit être obligatoire."
    Assert-OutputContains -Output $missingSnapshotResult.Output -Expected "StrategySnapshot" -Message "Le snapshot absent doit être nommé."

    $missingEndpointSpecPath = New-TemporarySpec `
        -Name "missing-endpoint" `
        -Content ($validContent.Replace("POST /v1/strategies/compile", "POST /v1/strategies"))
    $missingEndpointResult = Invoke-M010SpecificationValidator -SpecPath $missingEndpointSpecPath
    Assert-ExitCode -Actual $missingEndpointResult.ExitCode -Expected 1 -Message "L'endpoint de compilation doit être obligatoire."
    Assert-OutputContains -Output $missingEndpointResult.Output -Expected "POST /v1/strategies/compile" -Message "L'endpoint absent doit être nommé."

    $missingPublicErrorSpecPath = New-TemporarySpec `
        -Name "missing-public-error" `
        -Content ($validContent.Replace("RULE_ORIGIN_REQUIRED", "RULE_ORIGIN_OPTIONAL"))
    $missingPublicErrorResult = Invoke-M010SpecificationValidator -SpecPath $missingPublicErrorSpecPath
    Assert-ExitCode -Actual $missingPublicErrorResult.ExitCode -Expected 1 -Message "Les erreurs publiques M-010 doivent être obligatoires."
    Assert-OutputContains -Output $missingPublicErrorResult.Output -Expected "RULE_ORIGIN_REQUIRED" -Message "L'erreur publique absente doit être nommée."

    $missingMetricSpecPath = New-TemporarySpec `
        -Name "missing-metric" `
        -Content ($validContent.Replace("strategy_candidate_compilation_rejected_total", "strategy_candidate_rejected_total"))
    $missingMetricResult = Invoke-M010SpecificationValidator -SpecPath $missingMetricSpecPath
    Assert-ExitCode -Actual $missingMetricResult.ExitCode -Expected 1 -Message "Les métriques de compilation refusée doivent être obligatoires."
    Assert-OutputContains -Output $missingMetricResult.Output -Expected "strategy_candidate_compilation_rejected_total" -Message "La métrique absente doit être nommée."

    $missingBacktestExclusionSpecPath = New-TemporarySpec `
        -Name "missing-backtest-exclusion" `
        -Content ($validContent.Replace("M-010 ne lance aucun backtest et ne produit aucun résultat d'expérience M-011.", "M-010 prépare la future exécution expérimentale."))
    $missingBacktestExclusionResult = Invoke-M010SpecificationValidator -SpecPath $missingBacktestExclusionSpecPath
    Assert-ExitCode -Actual $missingBacktestExclusionResult.ExitCode -Expected 1 -Message "L'exclusion du backtest M-011 doit être obligatoire."
    Assert-OutputContains -Output $missingBacktestExclusionResult.Output -Expected "M-010 ne lance aucun backtest" -Message "L'exclusion absente doit être nommée."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-009", "DDD-ADR-009-RETIREE"))
    $missingAdrResult = Invoke-M010SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-009" -Message "L'ADR absente doit être nommée."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-010: OK"
