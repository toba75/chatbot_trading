$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_backup_restore.ps1"
$drillPath = Join-Path $repoRoot "docs/governance/m013_backup_restore_drill.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013BackupRestoreValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -DrillPath $drillPath `
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

# Given une instance V1 contient corpus, versions canoniques, claims, réponses,
# conversations, stratégies, expériences, décisions et écarts V1.
# When une sauvegarde chiffrée est restaurée dans un environnement local isolé.
# Then les identifiants stables, artefacts immuables, résultats négatifs et décisions
# restent vérifiables sans secret en clair ni stockage métier sur Spark.
$result = Invoke-M013BackupRestoreValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La restauration M-013 conforme doit être acceptée."
Assert-OutputContains -Output $result.Output -Expected "Sauvegarde restauration M-013 valide" -Message "Le validateur doit annoncer le GREEN T-007."
Assert-OutputContains -Output $result.Output -Expected "restore_test_result" -Message "Le validateur doit prouver le résultat de restauration."
Assert-OutputContains -Output $result.Output -Expected "aucun secret en Git" -Message "Le validateur doit prouver l'absence de secret versionné."
Assert-OutputContains -Output $result.Output -Expected "aucune donnée métier sur Spark" -Message "Le validateur doit prouver le Spark sans état métier."
Assert-OutputContains -Output $result.Output -Expected "projections régénérables non autorité" -Message "Le validateur doit prouver le statut des projections."
Assert-OutputContains -Output $result.Output -Expected "résultats négatifs et supersédés conservés" -Message "Le validateur doit prouver la conservation des résultats défavorables."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-007" -Message "La matrice doit tracer T-007."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_backup_restore.ps1" -Message "La matrice doit tracer le validateur T-007."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_backup_restore_drill.md" -Message "La matrice doit tracer le drill T-007."

Write-Host "Test d'acceptation T-007 sauvegarde restauration M-013: OK"
