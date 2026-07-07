$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_security.ps1"
$auditPath = Join-Path $repoRoot "docs/governance/m013_security_audit.md"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"

function Invoke-M013NetworkSecurityValidator {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -AuditPath $auditPath `
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
    throw "Validateur sécurité réseau M-013 absent: scripts/validate_m013_security.ps1"
}

if (-not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
    throw "Rapport d'audit sécurité réseau M-013 absent: docs/governance/m013_security_audit.md"
}

# Given la topologie V1 cible sépare docker-local et spark-inference.
# When l'audit réseau M-013 inspecte Compose, configuration gateway et règles Spark.
# Then aucun service interne n'est exposé publiquement, le point d'entrée utilisateur reste lié à 127.0.0.1 par défaut, le navigateur ne peut pas joindre le Spark et seul llm-gateway possède l'egress autorisé.
$result = Invoke-M013NetworkSecurityValidator
Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "L'audit sécurité réseau M-013 conforme doit être accepté."
Assert-OutputContains -Output $result.Output -Expected "Audit sécurité réseau M-013 valide" -Message "Le validateur doit annoncer l'audit M-013 valide."
Assert-OutputContains -Output $result.Output -Expected "127.0.0.1" -Message "Le validateur doit prouver le binding loopback du point d'entrée utilisateur."
Assert-OutputContains -Output $result.Output -Expected "llm-gateway -> spark-inference" -Message "Le validateur doit prouver le chemin Spark autorisé unique."

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
Assert-OutputContains -Output $matrixContent -Expected "REQ-M013-005" -Message "La matrice doit tracer T-005."
Assert-OutputContains -Output $matrixContent -Expected "scripts/validate_m013_security.ps1" -Message "La matrice doit tracer le validateur T-005."
Assert-OutputContains -Output $matrixContent -Expected "docs/governance/m013_security_audit.md" -Message "La matrice doit tracer le rapport d'audit T-005."

Write-Host "Test d'acceptation T-005 sécurité réseau M-013: OK"
