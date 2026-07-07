$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_specification.ps1"
$specificationPath = Join-Path $repoRoot "docs/specs/m013_durcissement_acceptation_v1.md"

function Invoke-M013SpecificationValidator {
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
    throw "Validateur de spécification M-013 absent: scripts/validate_m013_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specificationPath -PathType Leaf)) {
    throw "Spécification M-013 absente: docs/specs/m013_durcissement_acceptation_v1.md"
}

# Given le système complet a été mesuré par M-012 et les critères V1 sont publiés.
# When la spécification M-013 est publiée.
# Then chaque comportement de durcissement nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
$result = Invoke-M013SpecificationValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La spécification M-013 conforme doit être acceptée."
Assert-OutputContains -Output $result.Output -Expected "Spécification M-013 valide" -Message "Le validateur doit annoncer la spécification M-013 valide."

Write-Host "Test d'acceptation de spécification M-013: OK"
