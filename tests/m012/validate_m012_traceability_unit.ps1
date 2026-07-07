$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m012_traceability.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m012_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
$outsideRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_traceability_outside_" + [System.Guid]::NewGuid().ToString("N"))

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

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $gapReportPath = Join-Path $ProjectRoot "docs/governance/m012_v1_gap_report.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"
    $governanceTestPath = Join-Path $ProjectRoot "tests/governance/validate_m000_validation_commands_acceptance.ps1"
    $specificationPath = Join-Path $ProjectRoot "docs/specs/m012_evaluation_pilote_calibration.md"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -MatrixPath $matrixPath `
            -GapReportPath $gapReportPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath `
            -GovernanceTestPath $governanceTestPath `
            -SpecificationPath $specificationPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/evaluation") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/specs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "tests/governance") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m012_v1_gap_report.md") -Destination (Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/evaluation/m012") -Destination (Join-Path $projectRoot "docs/evaluation/m012") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs/m012_evaluation_pilote_calibration.md") -Destination (Join-Path $projectRoot "docs/specs/m012_evaluation_pilote_calibration.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "tests/governance/validate_m000_validation_commands_acceptance.ps1") -Destination (Join-Path $projectRoot "tests/governance/validate_m000_validation_commands_acceptance.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

function Remove-TreeWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $lastError = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force
            return
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 250
        }
    }
    throw $lastError
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de traçabilité M-012 absent: scripts/validate_m012_traceability.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide M-012 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Traçabilité M-012 valide" `
        -Message "La fixture valide doit annoncer le GREEN M-012."

    New-Item -ItemType Directory -Path $outsideRoot | Out-Null
    $outsideMatrixPath = Join-Path $outsideRoot "outside_matrix.md"
    Copy-Item -LiteralPath (Join-Path $validProjectRoot "docs/traceability/matrix.md") -Destination $outsideMatrixPath
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $outsideResult = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -MatrixPath $outsideMatrixPath `
            -GapReportPath (Join-Path $validProjectRoot "docs/governance/m012_v1_gap_report.md") `
            -TestGatePath (Join-Path $validProjectRoot "scripts/test.ps1") `
            -LintGatePath (Join-Path $validProjectRoot "scripts/lint.ps1") `
            -GovernanceTestPath (Join-Path $validProjectRoot "tests/governance/validate_m000_validation_commands_acceptance.ps1") `
            -SpecificationPath (Join-Path $validProjectRoot "docs/specs/m012_evaluation_pilote_calibration.md") 2>&1
        $outsideExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($outsideExitCode -eq 0) {
        throw "Un chemin absolu hors dépôt doit être refusé."
    }
    Assert-OutputContains `
        -Output ($outsideResult -join "`n") `
        -Expected "Chemin hors dépôt interdit (matrix)" `
        -Message "Le chemin hors dépôt doit être nommé."

    Assert-ValidatorFails `
        -Name "missing-requirement" `
        -ExpectedMessage "Exigence M-012 absente: REQ-M012-012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            $lines = Get-Content -Encoding UTF8 -LiteralPath $path
            $lines | Where-Object { -not $_.StartsWith("| REQ-M012-012 |") } | Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "missing-ra-metric" `
        -ExpectedMessage "Métrique V1 absente du rapport: answer_accuracy_score" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("answer_accuracy_score", "answer_exactitude_score_absente") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "gap-without-status" `
        -ExpectedMessage "Statut d'écart V1 invalide pour KA" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| KA | différé |", "| KA | ouvert |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "sensitive-payload" `
        -ExpectedMessage "Payload sensible M-012 exposé: PROMPT_COMPLET_INTERDIT_M012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "PROMPT_COMPLET_INTERDIT_M012"
        }

    Assert-ValidatorFails `
        -Name "sensitive-public-report" `
        -ExpectedMessage "Payload sensible M-012 exposé: PROMPT_COMPLET_INTERDIT_M012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m012/llm_real_path_benchmark_report.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "PROMPT_COMPLET_INTERDIT_M012"
        }

    Assert-ValidatorFails `
        -Name "test-gate-missing" `
        -ExpectedMessage "Gate test sans test M-012: tests/m012/validate_m012_traceability_acceptance.ps1" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "scripts/test.ps1"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace('$m012TraceabilityAcceptancePath = "tests/m012/validate_m012_traceability_acceptance.ps1"', '$m012TraceabilityAcceptancePath = "tests/m012/traceability_acceptance_absent.ps1"') |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "lint-gate-missing" `
        -ExpectedMessage "Gate lint sans validateur M-012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "scripts/lint.ps1"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("scripts/validate_m012_traceability.ps1", "scripts/validate_m012_traceability_absent.ps1") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "counter-drift" `
        -ExpectedMessage "Compteur test global M-012 incohérent" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "tests/governance/validate_m000_validation_commands_acceptance.ps1"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace('$expectedTestCount = 276', '$expectedTestCount = 275') |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    Remove-TreeWithRetry -Path $temporaryRoot
    Remove-TreeWithRetry -Path $outsideRoot
}

Write-Host "Tests unitaires T-012 traçabilité M-012: OK"
