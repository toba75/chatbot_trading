$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_antipatterns.ps1"
$reviewPath = Join-Path $repoRoot "docs/governance/m013_antipattern_review.md"
$specificationPath = Join-Path $repoRoot "docs/specs/m013_durcissement_acceptation_v1.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013AntipatternValidator {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur anti-patterns V1 M-013 absent: scripts/validate_m013_antipatterns.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -ReviewPath $reviewPath `
            -SpecificationPath $specificationPath `
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

# Given la spécification V1 liste les anti-patterns interdits et les questions ouvertes contrôlées.
# When la validation M-013 des anti-patterns s'exécute.
# Then chaque interdiction possède un contrôle automatisé ou une revue documentée datée avec preuve et périmètre,
# toute violation bloque l'acceptation V1, et aucune question ouverte n'est résolue sans ADR.
$result = Invoke-M013AntipatternValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Les anti-patterns interdits V1 doivent bloquer toute acceptation non contrôlée."
Assert-OutputContains -Output $result.Output -Expected "Anti-patterns V1 M-013 valides" -Message "Le validateur doit annoncer le GREEN T-011."
Assert-OutputContains -Output $result.Output -Expected "17 anti-pattern(s)" -Message "Le validateur doit compter les anti-patterns V1 obligatoires."
Assert-OutputContains -Output $result.Output -Expected "14 question(s) ouverte(s) contrôlée(s)" -Message "Le validateur doit contrôler les questions ouvertes de la section 23."
Assert-OutputContains -Output $result.Output -Expected "9 contrôle(s) relié(s)" -Message "Le validateur doit relier les contrôles transverses existants."
Assert-OutputContains -Output $result.Output -Expected "aucune violation active" -Message "Le validateur doit refuser les violations actives."

$reviewContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $reviewPath
Assert-OutputContains -Output $reviewContent -Expected "Given la spécification V1 liste les anti-patterns interdits" -Message "La revue doit porter le scénario BDD T-011."
Assert-OutputContains -Output $reviewContent -Expected "Date de revue: 2026-07-08" -Message "La revue doit être datée."
Assert-OutputContains -Output $reviewContent -Expected "Périmètre revu:" -Message "La revue doit nommer son périmètre."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_network_boundary.ps1" -Message "La revue doit relier la frontière réseau."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_architecture_boundaries.ps1" -Message "La revue doit relier les frontières d'architecture."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_traceability.ps1" -Message "La revue doit relier la traçabilité."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_adr_system.ps1" -Message "La revue doit relier le système ADR."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_m013_security.ps1" -Message "La revue doit relier l'audit sécurité."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_m013_backup_restore.ps1" -Message "La revue doit relier sauvegarde et restauration."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_m013_retention.ps1" -Message "La revue doit relier la rétention."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_m013_monitoring.ps1" -Message "La revue doit relier le monitoring."
Assert-OutputContains -Output $reviewContent -Expected "scripts/validate_m013_runbooks.ps1" -Message "La revue doit relier les runbooks."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-011" -Message "La matrice doit tracer T-011."
Assert-OutputContains -Output $matrixContent -Expected "tests/m013/validate_v1_antipatterns_acceptance.ps1" -Message "La matrice doit tracer le test d'acceptation T-011."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_antipatterns.ps1" -Message "La matrice doit tracer le validateur T-011."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_antipattern_review.md" -Message "La matrice doit tracer la revue T-011."

Write-Host "Test d'acceptation T-011 anti-patterns V1 M-013: OK"

