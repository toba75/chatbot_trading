$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_precondition.ps1"
$canonicalReportPath = Join-Path $repoRoot "docs/governance/m013_precondition_green.md"
$temporaryRoot = Join-Path $repoRoot ("docs/governance/.tmp_m013_precondition_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-M013PreconditionValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $previousRecursionGuard = $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING
        $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING = "1"
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ReportPath 2>&1
    }
    finally {
        if ($null -eq $previousRecursionGuard) {
            Remove-Item Env:\OST_M013_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
        }
        else {
            $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
        }
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de précondition M-013 absent: scripts/validate_m013_precondition.ps1"
}

if (-not (Test-Path -LiteralPath $canonicalReportPath -PathType Leaf)) {
    throw "Rapport de précondition M-013 absent: docs/governance/m013_precondition_green.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given M-012 est présent dans master avec ses tâches, sa spécification, ses validateurs, ses tests, son contexte EV et son rapport d'écarts V1.
    # When les gates de précondition M-013 sont exécutées sur une branche M-013 créée depuis master.
    # Then M-013 ne peut commencer que si la présence M-012, les écarts V1, la branche de travail et les gates amont ont un verdict explicite.
    $reportPath = Join-Path $temporaryRoot "m013_precondition_green.md"
    $result = Invoke-M013PreconditionValidator -ReportPath $reportPath

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La précondition M-013 doit être GREEN sur la base courante."
    Assert-OutputContains -Output $result.Output -Expected "Précondition M-013 GREEN" -Message "Le validateur doit annoncer le GREEN de précondition."

    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw "Rapport de précondition M-013 absent après exécution du validateur."
    }

    $generatedReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath
    $canonicalReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalReportPath

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Given M-012 est présent dans ``master``" `
        -Message "Le rapport doit reprendre le Given métier."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/test.ps1."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/lint.ps1."

    foreach ($expectedMarker in @(
        "docs/tasks/milestone_012 dans master",
        "docs/specs/m012_evaluation_pilote_calibration.md dans master",
        "scripts/validate_m012_precondition.ps1 dans master",
        "scripts/validate_m012_specification.ps1 dans master",
        "scripts/validate_m012_traceability.ps1 dans master",
        "tests/m012 dans master",
        "app/evaluation dans master",
        "docs/governance/m012_v1_gap_report.md dans master",
        "docs/traceability/matrix.md dans master"
    )) {
        Assert-OutputContains `
            -Output $generatedReport `
            -Expected $expectedMarker `
            -Message "Le rapport doit vérifier la preuve M-012: $expectedMarker"
    }

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Branche M-013 autorisée" `
        -Message "Le rapport doit nommer la branche M-013 autorisée."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "scripts/validate_m003_precondition.ps1 accepte M-013" `
        -Message "Le rapport doit prouver que la précondition M-003 accepte le jalon M-013."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "scripts/validate_m012_precondition.ps1 accepte M-013" `
        -Message "Le rapport doit prouver que la précondition M-012 accepte le jalon M-013."

    foreach ($expectedGapMarker in @(
        "Écart V1 SP statuté",
        "Écart V1 KA statuté",
        "Écart V1 EG statuté",
        "Écart V1 RA statuté",
        "Écart V1 CV statuté",
        "Écart V1 SD statuté",
        "Écart V1 LLM statuté",
        "Écart V1 EX statuté",
        "Test scientifique RED conservé"
    )) {
        Assert-OutputContains `
            -Output $generatedReport `
            -Expected $expectedGapMarker `
            -Message "Le rapport doit conserver le statut V1: $expectedGapMarker"
    }

    foreach ($expectedEvidence in @(
        "Validation GREEN: scripts/validate_traceability.ps1",
        "Validation GREEN: scripts/validate_m012_traceability.ps1",
        "Validation GREEN: scripts/validate_adr_system.ps1",
        "validate_m013_precondition_unit.ps1"
    )) {
        Assert-OutputContains `
            -Output $generatedReport `
            -Expected $expectedEvidence `
            -Message "Le rapport doit conserver la preuve de gate: $expectedEvidence"
    }

    Assert-OutputContains `
        -Output $canonicalReport `
        -Expected "Statut: ``GREEN``" `
        -Message "Le rapport canonique doit matérialiser un statut GREEN."

    Assert-OutputContains `
        -Output $canonicalReport `
        -Expected "Sorties des gates" `
        -Message "Le rapport canonique doit conserver les sorties de commandes."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot -PathType Container) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Test d'acceptation de précondition M-013: OK"
