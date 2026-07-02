$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m009_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m009_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidM009SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m009_recherche_approfondie_multi_sources.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-009 absente pour le fixture unitaire: docs/specs/m009_recherche_approfondie_multi_sources.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M009SpecificationValidator {
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
    throw "Validateur de spécification M-009 absent: scripts/validate_m009_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM009SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M009SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-009 conforme doit être acceptée."

    $missingMissionSpecPath = New-TemporarySpec `
        -Name "missing-mission-ra" `
        -Content ($validContent.Replace("## Mission RA approfondie", "## Mission incomplète"))
    $missingMissionResult = Invoke-M009SpecificationValidator -SpecPath $missingMissionSpecPath
    Assert-ExitCode -Actual $missingMissionResult.ExitCode -Expected 1 -Message "Une mission RA approfondie absente doit être refusée."
    Assert-OutputContains -Output $missingMissionResult.Output -Expected "Section obligatoire absente: ## Mission RA approfondie" -Message "La mission absente doit être nommée."

    $missingModeSpecPath = New-TemporarySpec `
        -Name "missing-deep-mode" `
        -Content ($validContent.Replace("RECHERCHE_APPROFONDIE", "RECHERCHE_DOCUMENTAIRE_SIMPLE"))
    $missingModeResult = Invoke-M009SpecificationValidator -SpecPath $missingModeSpecPath
    Assert-ExitCode -Actual $missingModeResult.ExitCode -Expected 1 -Message "Le mode approfondi doit être obligatoire."
    Assert-OutputContains -Output $missingModeResult.Output -Expected "RECHERCHE_APPROFONDIE" -Message "Le mode absent doit être nommé."

    $missingCoverageSpecPath = New-TemporarySpec `
        -Name "missing-coverage-obligation" `
        -Content ($validContent.Replace("CoverageObligation", "CoverageTarget"))
    $missingCoverageResult = Invoke-M009SpecificationValidator -SpecPath $missingCoverageSpecPath
    Assert-ExitCode -Actual $missingCoverageResult.ExitCode -Expected 1 -Message "Les obligations de couverture doivent être obligatoires."
    Assert-OutputContains -Output $missingCoverageResult.Output -Expected "CoverageObligation" -Message "L'obligation absente doit être nommée."

    $missingEgDependencySpecPath = New-TemporarySpec `
        -Name "missing-eg-dependency" `
        -Content ($validContent.Replace("VerifiedClaimCatalog", "ClaimCatalogInterne"))
    $missingEgDependencyResult = Invoke-M009SpecificationValidator -SpecPath $missingEgDependencySpecPath
    Assert-ExitCode -Actual $missingEgDependencyResult.ExitCode -Expected 1 -Message "La dépendance EG publiée doit être obligatoire."
    Assert-OutputContains -Output $missingEgDependencyResult.Output -Expected "VerifiedClaimCatalog" -Message "La dépendance EG absente doit être nommée."

    $missingEndpointSpecPath = New-TemporarySpec `
        -Name "missing-endpoint" `
        -Content ($validContent.Replace("POST /v1/research/deep", "POST /v1/research"))
    $missingEndpointResult = Invoke-M009SpecificationValidator -SpecPath $missingEndpointSpecPath
    Assert-ExitCode -Actual $missingEndpointResult.ExitCode -Expected 1 -Message "L'endpoint de recherche approfondie doit être obligatoire."
    Assert-OutputContains -Output $missingEndpointResult.Output -Expected "POST /v1/research/deep" -Message "L'endpoint absent doit être nommé."

    $missingPublicErrorSpecPath = New-TemporarySpec `
        -Name "missing-public-error" `
        -Content ($validContent.Replace("DEEP_RESEARCH_MANDATE_REQUIRED", "DEEP_RESEARCH_CONTEXT_OPTIONAL"))
    $missingPublicErrorResult = Invoke-M009SpecificationValidator -SpecPath $missingPublicErrorSpecPath
    Assert-ExitCode -Actual $missingPublicErrorResult.ExitCode -Expected 1 -Message "Les erreurs publiques M-009 doivent être obligatoires."
    Assert-OutputContains -Output $missingPublicErrorResult.Output -Expected "DEEP_RESEARCH_MANDATE_REQUIRED" -Message "L'erreur publique absente doit être nommée."

    $missingMetricSpecPath = New-TemporarySpec `
        -Name "missing-metric" `
        -Content ($validContent.Replace("deep_research_coverage_obligation_met_total", "deep_research_coverage_total"))
    $missingMetricResult = Invoke-M009SpecificationValidator -SpecPath $missingMetricSpecPath
    Assert-ExitCode -Actual $missingMetricResult.ExitCode -Expected 1 -Message "Les métriques de couverture doivent être obligatoires."
    Assert-OutputContains -Output $missingMetricResult.Output -Expected "deep_research_coverage_obligation_met_total" -Message "La métrique absente doit être nommée."

    $frequencyConsensusSpecPath = New-TemporarySpec `
        -Name "frequency-consensus" `
        -Content ($validContent + "`nLa fréquence de citation devient consensus lorsque trois documents répètent la même conclusion.`n")
    $frequencyConsensusResult = Invoke-M009SpecificationValidator -SpecPath $frequencyConsensusSpecPath
    Assert-ExitCode -Actual $frequencyConsensusResult.ExitCode -Expected 1 -Message "La confusion fréquence/consensus doit être refusée."
    Assert-OutputContains -Output $frequencyConsensusResult.Output -Expected "Confusion fréquence/consensus interdite" -Message "La confusion fréquence/consensus doit être nommée."

    $missingExclusionSpecPath = New-TemporarySpec `
        -Name "missing-exclusion" `
        -Content ($validContent.Replace("M-009 ne livre pas la stratégie candidate attribuée M-010 ni l'expérience reproductible M-011.", "M-009 prépare les stratégies et expériences aval."))
    $missingExclusionResult = Invoke-M009SpecificationValidator -SpecPath $missingExclusionSpecPath
    Assert-ExitCode -Actual $missingExclusionResult.ExitCode -Expected 1 -Message "Les exclusions M-010/M-011 doivent être obligatoires."
    Assert-OutputContains -Output $missingExclusionResult.Output -Expected "M-009 ne livre pas la stratégie candidate attribuée M-010" -Message "Les exclusions absentes doivent être nommées."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-008", "DDD-ADR-008-RETIREE"))
    $missingAdrResult = Invoke-M009SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-008" -Message "L'ADR absente doit être nommée."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-009: OK"
