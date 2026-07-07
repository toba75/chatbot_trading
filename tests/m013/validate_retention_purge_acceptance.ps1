$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_retention.ps1"
$policyPath = Join-Path $repoRoot "docs/governance/m013_retention_policy.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$adrPath = Join-Path $repoRoot "docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md"
$adrIndexPath = Join-Path $repoRoot "docs/adr/index.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013RetentionValidator {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur rétention purge M-013 absent: scripts/validate_m013_retention.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -PolicyPath $policyPath `
            -MatrixPath $matrixPath `
            -AdrPath $adrPath `
            -AdrIndexPath $adrIndexPath `
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

# Given la V1 conserve originaux, versions canoniques, claims, réponses,
# conversations, stratégies, expériences, benchmarks, projections et décisions.
# When la politique de rétention et une purge administrative sont décidées.
# Then chaque catégorie possède une durée, une opération autorisée, une
# justification, un audit, une compatibilité de lecture et un garde-fou empêchant
# la suppression silencieuse des versions défavorables ou supersédées.
$result = Invoke-M013RetentionValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La politique V1 de rétention et purge administrative doit être acceptée."
Assert-OutputContains -Output $result.Output -Expected "Rétention purge M-013 valide" -Message "Le validateur doit annoncer le GREEN T-008."
Assert-OutputContains -Output $result.Output -Expected "catégories durables" -Message "Le validateur doit compter les catégories durables."
Assert-OutputContains -Output $result.Output -Expected "aucune purge ordinaire" -Message "Le validateur doit refuser la purge ordinaire."
Assert-OutputContains -Output $result.Output -Expected "conversation sans cascade" -Message "Le validateur doit prouver l'isolation CV."
Assert-OutputContains -Output $result.Output -Expected "projection régénérable reconstruite" -Message "Le validateur doit prouver la reconstruction des projections."
Assert-OutputContains -Output $result.Output -Expected "DDD-ADR-012" -Message "Le validateur doit référencer l'ADR T-008."

Write-Host "Test d'acceptation T-008 rétention purge M-013: OK"
