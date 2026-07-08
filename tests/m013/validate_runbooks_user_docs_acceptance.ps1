$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_runbooks.ps1"
$runbookRoot = Join-Path $repoRoot "docs/runbooks"
$userGuidePath = Join-Path $repoRoot "docs/user/v1_guide_utilisateur.md"
$documentationIndexPath = Join-Path $repoRoot "docs/governance/m013_documentation_index.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013RunbookValidator {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur runbooks documentation utilisateur M-013 absent: scripts/validate_m013_runbooks.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -RunbookRoot $runbookRoot `
            -UserGuidePath $userGuidePath `
            -DocumentationIndexPath $documentationIndexPath `
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

# Given la V1 possède des gates, sauvegardes, restauration testée, audit réseau,
# pannes Spark explicites, rétention, monitoring et décisions d'écarts.
# When l'utilisateur suit les runbooks locaux et la documentation utilisateur V1.
# Then chaque action critique nomme une commande vérifiée, un résultat attendu,
# une erreur explicite, une preuve conservée et ne publie aucun fallback silencieux,
# service interne, secret, commande destructive sans précondition ou promesse de rentabilité.
$result = Invoke-M013RunbookValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Les runbooks et la documentation utilisateur V1 doivent être acceptés."
Assert-OutputContains -Output $result.Output -Expected "Runbooks documentation utilisateur M-013 valides" -Message "Le validateur doit annoncer le GREEN T-010."
Assert-OutputContains -Output $result.Output -Expected "8 runbook(s)" -Message "Le validateur doit compter les runbooks critiques."
Assert-OutputContains -Output $result.Output -Expected "documentation utilisateur V1" -Message "Le validateur doit contrôler la documentation utilisateur V1."
Assert-OutputContains -Output $result.Output -Expected "aucun secret" -Message "Le validateur doit prouver l'absence de secret."
Assert-OutputContains -Output $result.Output -Expected "aucune promesse financière" -Message "Le validateur doit refuser les promesses de rentabilité."
Assert-OutputContains -Output $result.Output -Expected "commandes vérifiées" -Message "Le validateur doit prouver les commandes vérifiées."
Assert-OutputContains -Output $result.Output -Expected "écarts V1 non acceptés visibles" -Message "Le validateur doit prouver les limites V1."
Assert-OutputContains -Output $result.Output -Expected "aucun service interne publié" -Message "Le validateur doit refuser l'exposition Spark ou stockage interne."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-010" -Message "La matrice doit tracer T-010."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_runbooks.ps1" -Message "La matrice doit tracer le validateur T-010."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_documentation_index.md" -Message "La matrice doit tracer l'index documentaire T-010."
Assert-OutputContains -Output $matrixContent -Expected "docs/user/v1_guide_utilisateur.md" -Message "La matrice doit tracer la documentation utilisateur V1."

Write-Host "Test d'acceptation T-010 runbooks documentation utilisateur M-013: OK"
