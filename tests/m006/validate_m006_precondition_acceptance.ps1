$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m006_precondition.ps1"
$temporaryRoot = Join-Path $repoRoot ("docs/governance/.tmp_m006_precondition_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-M006PreconditionValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $previousRecursionGuard = $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING
        $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING = "1"
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ReportPath 2>&1
    }
    finally {
        if ($null -eq $previousRecursionGuard) {
            Remove-Item Env:\OST_M006_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
        }
        else {
            $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
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
    throw "Validateur de précondition M-006 absent: scripts/validate_m006_precondition.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given M-004 et M-005 sont présents dans master.
    # When les gates de précondition M-006 sont exécutées.
    # Then M-006 ne peut commencer que si les validations et preuves M-005 sont GREEN ou si le blocage exact est isolé.
    $reportPath = Join-Path $temporaryRoot "m006_precondition_green.md"
    $result = Invoke-M006PreconditionValidator -ReportPath $reportPath

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La précondition M-006 doit être GREEN sur la base courante."
    Assert-OutputContains -Output $result.Output -Expected "Précondition M-006 GREEN" -Message "Le validateur doit annoncer le GREEN de précondition."

    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw "Rapport de précondition M-006 absent après exécution du validateur."
    }

    $reportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Given M-004 et M-005" `
        -Message "Le rapport doit reprendre le Given métier."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/test.ps1."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1" `
        -Message "Le rapport doit consigner l'exécution de scripts/lint.ps1."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "docs/tasks/milestone_004 dans master" `
        -Message "Le rapport doit vérifier la présence de M-004 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "docs/tasks/milestone_005 dans master" `
        -Message "Le rapport doit vérifier la présence de M-005 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "docs/specs/m005_projection_connaissance_recherchable.md dans master" `
        -Message "Le rapport doit vérifier la présence de la spécification M-005 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "tests/m005 dans master" `
        -Message "Le rapport doit vérifier la présence des preuves de tests M-005 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "docs/governance/m005_precondition_green.md dans master" `
        -Message "Le rapport doit vérifier la preuve de précondition M-005 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Branche M-006 autorisée" `
        -Message "Le rapport doit nommer la branche M-006 autorisée."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Validation GREEN: scripts/validate_traceability.ps1" `
        -Message "Le rapport doit conserver la preuve de traçabilité GREEN."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Validation GREEN: scripts/validate_adr_system.ps1" `
        -Message "Le rapport doit conserver la preuve ADR GREEN."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Validation GREEN: scripts/validate_architecture_boundaries.ps1" `
        -Message "Le rapport doit conserver la preuve des frontières d'architecture GREEN."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "M-006 s'appuie sur les preuves amont M-004 et M-005 publiées dans master." `
        -Message "Le rapport doit expliciter l'appui sur les preuves amont publiées."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "validate_m006_precondition_unit.ps1" `
        -Message "Le rapport doit prouver que le test unitaire de précondition M-006 est enrôlé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de précondition M-006: OK"
