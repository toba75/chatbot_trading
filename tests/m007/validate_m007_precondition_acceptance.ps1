$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m007_precondition.ps1"
$temporaryRoot = Join-Path $repoRoot ("docs/governance/.tmp_m007_precondition_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-M007PreconditionValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $previousRecursionGuard = $env:OST_M007_PRECONDITION_ACCEPTANCE_RUNNING
        $env:OST_M007_PRECONDITION_ACCEPTANCE_RUNNING = "1"
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ReportPath 2>&1
    }
    finally {
        if ($null -eq $previousRecursionGuard) {
            Remove-Item Env:\OST_M007_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
        }
        else {
            $env:OST_M007_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
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
    throw "Validateur de précondition M-007 absent: scripts/validate_m007_precondition.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given M-006 est présent dans master.
    # When les gates de précondition M-007 sont exécutées.
    # Then M-007 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-006 sont GREEN ou si le blocage exact est isolé.
    $reportPath = Join-Path $temporaryRoot "m007_precondition_green.md"
    $result = Invoke-M007PreconditionValidator -ReportPath $reportPath

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La précondition M-007 doit être GREEN sur la base courante."
    Assert-OutputContains -Output $result.Output -Expected "Précondition M-007 GREEN" -Message "Le validateur doit annoncer le GREEN de précondition."

    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw "Rapport de précondition M-007 absent après exécution du validateur."
    }

    $reportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Given M-006 est présent dans ``master``" `
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
        -Expected "docs/tasks/milestone_006 dans master" `
        -Message "Le rapport doit vérifier la présence de M-006 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "docs/specs/m006_claims_verifiables.md dans master" `
        -Message "Le rapport doit vérifier la présence de la spécification M-006 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "tests/m006 dans master" `
        -Message "Le rapport doit vérifier la présence des preuves de tests M-006 dans master."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "Branche M-007 autorisée" `
        -Message "Le rapport doit nommer la branche M-007 autorisée."

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
        -Expected "M-007 s'appuie sur les claims vérifiables M-006 publiés dans master." `
        -Message "Le rapport doit expliciter l'appui sur les claims vérifiables publiés."

    Assert-OutputContains `
        -Output $reportContent `
        -Expected "validate_m007_precondition_unit.ps1" `
        -Message "Le rapport doit prouver que le test unitaire de précondition M-007 est enrôlé."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot -PathType Container) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Test d'acceptation de précondition M-007: OK"
