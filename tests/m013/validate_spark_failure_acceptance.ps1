$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_spark_failures.ps1"
$drillPath = Join-Path $repoRoot "docs/governance/m013_spark_failure_drill.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013SparkFailureValidator {
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur pannes Spark M-013 absent: scripts/validate_m013_spark_failures.ps1"
}

if (-not (Test-Path -LiteralPath $drillPath -PathType Leaf)) {
    throw "Exercice pannes Spark M-013 absent: docs/governance/m013_spark_failure_drill.md"
}

# Given une commande V1 requiert Gemma via llm-gateway.
# When le Spark est indisponible, lent ou coupe la génération.
# Then LLM_UNAVAILABLE ou un diagnostic explicite est publié sans réponse factuelle, fallback, snapshot, benchmark promu ni double outbox.
$result = Invoke-M013SparkFailureValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Les pannes Spark M-013 conformes doivent être acceptées."
Assert-OutputContains -Output $result.Output -Expected "Pannes Spark M-013 valides" -Message "Le validateur doit annoncer les pannes Spark M-013 valides."
Assert-OutputContains -Output $result.Output -Expected "LLM_UNAVAILABLE" -Message "Le validateur doit prouver le statut public d'indisponibilité."
Assert-OutputContains -Output $result.Output -Expected "circuit breaker ouvrable et refermable" -Message "Le validateur doit prouver le circuit breaker."
Assert-OutputContains -Output $result.Output -Expected "fonctions locales hors Gemma disponibles" -Message "Le validateur doit prouver les fonctions locales hors Gemma."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-006" -Message "La matrice doit tracer T-006."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_spark_failures.ps1" -Message "La matrice doit tracer le validateur T-006."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_spark_failure_drill.md" -Message "La matrice doit tracer l'exercice T-006."

Write-Host "Test d'acceptation T-006 pannes Spark M-013: OK"
