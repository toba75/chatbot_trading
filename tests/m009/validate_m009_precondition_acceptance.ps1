$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m009_precondition.ps1"
$canonicalReportPath = Join-Path $repoRoot "docs/governance/m009_precondition_green.md"
$temporaryRoot = Join-Path $repoRoot ("docs/governance/.tmp_m009_precondition_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-M009PreconditionValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $previousRecursionGuard = $env:OST_M009_PRECONDITION_ACCEPTANCE_RUNNING
        $env:OST_M009_PRECONDITION_ACCEPTANCE_RUNNING = "1"
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ReportPath 2>&1
    }
    finally {
        if ($null -eq $previousRecursionGuard) {
            Remove-Item Env:\OST_M009_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
        }
        else {
            $env:OST_M009_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
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
    throw "Validateur de précondition M-009 absent: scripts/validate_m009_precondition.ps1"
}

if (-not (Test-Path -LiteralPath $canonicalReportPath -PathType Leaf)) {
    throw "Rapport de précondition M-009 absent: docs/governance/m009_precondition_green.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given M-008 est présent dans master avec sa spécification, ses tests et ses tâches.
    # When les gates de précondition M-009 sont exécutées sur une branche M-009.
    # Then M-009 ne peut commencer que si les validateurs amont acceptent le jalon aval et si test, lint, traçabilité, ADR et frontières d'architecture ont un verdict GREEN exploitable.
    $reportPath = Join-Path $temporaryRoot "m009_precondition_green.md"
    $result = Invoke-M009PreconditionValidator -ReportPath $reportPath

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La précondition M-009 doit être GREEN sur la base courante."
    Assert-OutputContains -Output $result.Output -Expected "Précondition M-009 GREEN" -Message "Le validateur doit annoncer le GREEN de précondition."

    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw "Rapport de précondition M-009 absent après exécution du validateur."
    }

    $generatedReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath
    $canonicalReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalReportPath

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Given M-008 est présent dans ``master``" `
        -Message "Le rapport doit reprendre le Given métier."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/test.ps1."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/lint.ps1."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "docs/tasks/milestone_008 dans master" `
        -Message "Le rapport doit vérifier la présence des tâches M-008 dans master."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "docs/specs/m008_conversation_produit.md dans master" `
        -Message "Le rapport doit vérifier la présence de la spécification M-008 dans master."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "tests/m008 dans master" `
        -Message "Le rapport doit vérifier la présence des tests M-008 dans master."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Branche M-009 autorisée" `
        -Message "Le rapport doit nommer la branche M-009 autorisée."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Validation GREEN: scripts/validate_traceability.ps1" `
        -Message "Le rapport doit conserver la preuve de traçabilité GREEN."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Validation GREEN: scripts/validate_adr_system.ps1" `
        -Message "Le rapport doit conserver la preuve ADR GREEN."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "Validation GREEN: scripts/validate_architecture_boundaries.ps1" `
        -Message "Le rapport doit conserver la preuve des frontières d'architecture GREEN."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "scripts/validate_m003_precondition.ps1 accepte M-009" `
        -Message "Le rapport doit prouver que la précondition M-003 accepte le jalon M-009."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "scripts/validate_m008_precondition.ps1 accepte M-009" `
        -Message "Le rapport doit prouver que la précondition M-008 accepte le jalon M-009."

    Assert-OutputContains `
        -Output $generatedReport `
        -Expected "validate_m009_precondition_unit.ps1" `
        -Message "Le rapport doit prouver que le test unitaire de précondition M-009 est enrôlé."

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

Write-Host "Test d'acceptation de précondition M-009: OK"
