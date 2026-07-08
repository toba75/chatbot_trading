$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_monitoring.ps1"
$monitoringPath = Join-Path $repoRoot "docs/governance/m013_local_monitoring.md"
$resourceProfilePath = Join-Path $repoRoot "docs/governance/m013_resource_profile.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013MonitoringValidator {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur monitoring local M-013 absent: scripts/validate_m013_monitoring.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -MonitoringPath $monitoringPath `
            -ResourceProfilePath $resourceProfilePath `
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

# Given la V1 traite documents, conversations, recherches, stratégies,
# expériences et sauvegardes avec Gemma sur Spark et les services techniques
# sur docker-local.
# When le monitoring local et le profil de ressources sont consultés après une
# exécution, une panne ou un benchmark de capacité.
# Then les signaux indiquent santé, erreurs, latence, jobs, outbox, gateway,
# Spark, sauvegarde, restauration, écarts, sécurité, capacité et réglages sans
# exposer de payload sensible ni masquer une non-acceptation V1.
$result = Invoke-M013MonitoringValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Le monitoring local M-013 conforme doit être accepté."
Assert-OutputContains -Output $result.Output -Expected "Monitoring local M-013 valide" -Message "Le validateur doit annoncer le GREEN T-009."
Assert-OutputContains -Output $result.Output -Expected "métriques V1 critiques" -Message "Le validateur doit compter les métriques V1 critiques."
Assert-OutputContains -Output $result.Output -Expected "aucun payload sensible" -Message "Le validateur doit prouver l'absence de prompt, preuve, secret ou payload complet."
Assert-OutputContains -Output $result.Output -Expected "rétention courte" -Message "Le validateur doit prouver la rétention courte des logs."
Assert-OutputContains -Output $result.Output -Expected "corrélation" -Message "Le validateur doit prouver la corrélation des signaux."
Assert-OutputContains -Output $result.Output -Expected "aucun export externe" -Message "Le validateur doit refuser l'export externe par défaut."
Assert-OutputContains -Output $result.Output -Expected "profil CPU/GPU/I/O docker-local" -Message "Le validateur doit prouver le profil de ressources local."
Assert-OutputContains -Output $result.Output -Expected "vLLM épinglée" -Message "Le validateur doit prouver l'image vLLM épinglée."
Assert-OutputContains -Output $result.Output -Expected "modèle révisionné" -Message "Le validateur doit prouver la révision du modèle."
Assert-OutputContains -Output $result.Output -Expected "concurrence sourcée par benchmark" -Message "Le validateur doit prouver la concurrence sourcée."
Assert-OutputContains -Output $result.Output -Expected "longueur de contexte sourcée par benchmark" -Message "Le validateur doit prouver la longueur de contexte sourcée."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-009" -Message "La matrice doit tracer T-009."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_monitoring.ps1" -Message "La matrice doit tracer le validateur T-009."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_local_monitoring.md" -Message "La matrice doit tracer le profil de monitoring T-009."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_resource_profile.md" -Message "La matrice doit tracer le profil de ressources T-009."

Write-Host "Test d'acceptation T-009 monitoring local M-013: OK"
