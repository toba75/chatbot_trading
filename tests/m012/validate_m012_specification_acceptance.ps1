$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m012_specification.ps1"
$specificationPath = Join-Path $repoRoot "docs/specs/m012_evaluation_pilote_calibration.md"

function Invoke-M012SpecificationValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath 2>&1
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-012 absent: scripts/validate_m012_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specificationPath -PathType Leaf)) {
    throw "Spécification M-012 absente: docs/specs/m012_evaluation_pilote_calibration.md"
}

# Given la mission M-012 est de mesurer le système sur corpus pilote avant acceptation V1.
# When la spécification d'évaluation pilote est publiée.
# Then chaque comportement M-012 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
$result = Invoke-M012SpecificationValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La spécification M-012 conforme doit être acceptée."
Assert-OutputContains -Output $result.Output -Expected "Spécification M-012 valide" -Message "Le validateur doit annoncer la spécification M-012 valide."

Write-Host "Test d'acceptation de spécification M-012: OK"
