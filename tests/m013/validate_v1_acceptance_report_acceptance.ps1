$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_acceptance.ps1"
$reportPath = Join-Path $repoRoot "docs/governance/m013_v1_acceptance_report.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013AcceptanceValidator {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur rapport d'acceptation V1 M-013 absent: scripts/validate_m013_acceptance.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -ReportPath $reportPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
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

# Given M-013 a livré décisions d'écarts, régression, audit sécurité, drill Spark,
# sauvegarde/restauration, rétention, monitoring, runbooks et anti-patterns.
# When la gate finale V1 agrège les preuves.
# Then le rapport d'acceptation publie un verdict par critère, refuse l'acceptation
# en présence d'un bloquant et liste les écarts non acceptés avec commandes de preuve.
$result = Invoke-M013AcceptanceValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Le rapport d'acceptation V1 M-013 conforme doit être validé."
Assert-OutputContains -Output $result.Output -Expected "Rapport d'acceptation V1 M-013 valide" -Message "Le validateur doit annoncer le GREEN T-012."
Assert-OutputContains -Output $result.Output -Expected "8 critère(s)" -Message "Le validateur doit compter tous les critères V1."
Assert-OutputContains -Output $result.Output -Expected "5 écart(s) non accepté(s)" -Message "Le validateur doit exposer la liste des écarts non acceptés."
Assert-OutputContains -Output $result.Output -Expected "2 écart(s) bloquant(s)" -Message "Le validateur doit compter les bloquants SD et LLM."
Assert-OutputContains -Output $result.Output -Expected "verdict V1 non acceptée" -Message "Un écart bloquant doit refuser le verdict acceptée."

$reportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath
Assert-OutputContains -Output $reportContent -Expected "Given M-013 a livré décisions d'écarts" -Message "Le rapport doit porter le scénario BDD T-012."
Assert-OutputContains -Output $reportContent -Expected "Verdict V1: non acceptée" -Message "Le rapport doit publier le verdict honnête."
Assert-OutputContains -Output $reportContent -Expected "Définition de terminé" -Message "Le rapport doit relier la définition de terminé."
Assert-OutputContains -Output $reportContent -Expected "Gates finales" -Message "Le rapport doit lister les gates finales."
Assert-OutputContains -Output $reportContent -Expected "ADR: non requise" -Message "Le rapport doit documenter l'absence de nouvelle ADR."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-012" -Message "La matrice doit tracer T-012."
Assert-OutputContains -Output $matrixContent -Expected "tests/m013/validate_v1_acceptance_report_acceptance.ps1" -Message "La matrice doit tracer le test d'acceptation T-012."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_acceptance.ps1" -Message "La matrice doit tracer le validateur T-012."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_v1_acceptance_report.md" -Message "La matrice doit tracer le rapport d'acceptation."

Write-Host "Test d'acceptation T-012 rapport d'acceptation V1 M-013: OK"
