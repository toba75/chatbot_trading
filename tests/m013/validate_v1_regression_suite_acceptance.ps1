$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_regression.ps1"
$suitePath = Join-Path $repoRoot "docs/evaluation/m013/v1_regression_suite.json"
$decisionsPath = Join-Path $repoRoot "docs/governance/m013_v1_gap_decisions.md"
$sourceGapReportPath = Join-Path $repoRoot "docs/governance/m012_v1_gap_report.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013RegressionValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -SuitePath $suitePath `
            -DecisionsPath $decisionsPath `
            -SourceGapReportPath $sourceGapReportPath `
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de régression V1 M-013 absent: scripts/validate_m013_regression.ps1"
}

if (-not (Test-Path -LiteralPath $suitePath -PathType Leaf)) {
    throw "Fixture de suite de régression V1 M-013 absente: docs/evaluation/m013/v1_regression_suite.json"
}

# Given un corpus personnel de test et les contextes M-001 à M-012 livrés.
# When la suite de régression V1 rejoue les parcours de bout en bout.
# Then chaque critère V1 possède un verdict GREEN ou un écart non accepté relié au rapport V1.
$result = Invoke-M013RegressionValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "La suite de régression V1 conforme doit être acceptée."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "Suite de régression V1 M-013 valide" `
    -Message "Le validateur doit annoncer la suite de régression valide."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "8 critère(s)" `
    -Message "Le validateur doit couvrir tous les critères V1 issus de M-012."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "10 parcours V1" `
    -Message "Le validateur doit couvrir les principaux parcours produit V1."
Assert-OutputContains `
    -Output $result.Output `
    -Expected "5 écart(s) non accepté(s)" `
    -Message "Le validateur doit conserver les écarts non acceptés visibles."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains `
    -Output $matrixContent `
    -Expected "REQ-M013-004" `
    -Message "La matrice doit tracer T-004."
Assert-OutputContains `
    -Output $matrixContent `
    -Expected "tests/m013/validate_v1_regression_suite_acceptance.ps1" `
    -Message "La matrice doit tracer le test d'acceptation T-004."
Assert-OutputContains `
    -Output $matrixContent `
    -Expected "scripts/validate_m013_regression.ps1" `
    -Message "La matrice doit tracer le validateur T-004."
Write-Host "Test d'acceptation T-004 suite de régression V1 M-013: OK"
