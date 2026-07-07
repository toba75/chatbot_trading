$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_v1_gap_decisions.ps1"
$decisionsPath = Join-Path $repoRoot "docs/governance/m013_v1_gap_decisions.md"
$sourceGapReportPath = Join-Path $repoRoot "docs/governance/m012_v1_gap_report.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"

function Invoke-M013V1GapDecisionValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -DecisionsPath $decisionsPath `
            -SourceGapReportPath $sourceGapReportPath `
            -MatrixPath $matrixPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
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
    throw "Validateur de décisions d'écarts V1 M-013 absent: scripts/validate_m013_v1_gap_decisions.ps1"
}

if (-not (Test-Path -LiteralPath $decisionsPath -PathType Leaf)) {
    throw "Rapport de décisions d'écarts V1 M-013 absent: docs/governance/m013_v1_gap_decisions.md"
}

# Given le rapport M-012 contient des écarts V1 satisfaits, différés et bloquants.
# When M-013 publie les décisions d'écarts V1.
# Then chaque écart conserve son benchmark source, reçoit une décision explicite et bloque l'acceptation V1 si son statut reste bloquant.
$result = Invoke-M013V1GapDecisionValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Les décisions d'écarts V1 M-013 conformes doivent être acceptées."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "Décisions d'écarts V1 M-013 valides" `
    -Message "Le validateur doit annoncer le rapport de décisions valide."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "8 écart(s)" `
    -Message "Le validateur doit couvrir SP, KA, EG, RA, CV, SD, LLM et EX."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "5 écart(s) non accepté(s)" `
    -Message "Le validateur doit exposer la liste des écarts non acceptés."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "acceptation V1 refusée" `
    -Message "Un écart bloquant doit refuser l'acceptation V1."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains `
    -Output $matrixContent `
    -Expected "REQ-M013-003" `
    -Message "La matrice doit tracer T-003."
Assert-OutputContains `
    -Output $matrixContent `
    -Expected "scripts/validate_m013_v1_gap_decisions.ps1" `
    -Message "La matrice doit tracer le validateur T-003."

Write-Host "Test d'acceptation T-003 décisions d'écarts V1 M-013: OK"
