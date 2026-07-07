param(
    [Parameter(Mandatory = $false)]
    [string] $DrillPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultDrillPath = "docs/governance/m013_spark_failure_drill.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredStatusMarkers = @(
    "LLM_UNAVAILABLE",
    "LLM_FIRST_TOKEN_TIMEOUT",
    "LLM_TLS_CERTIFICATE_INVALID",
    "LLM_AUTHENTICATION_FAILED",
    "LLM_PARTIAL_OUTPUT",
    "LLM_CIRCUIT_OPEN",
    "LLM_RECOVERED"
)

$requiredDrillMarkers = @(
    "# Exercice pannes Spark M-013",
    "M013-SparkFailureDrill-1.0",
    "SparkFailurePolicy",
    'Given une commande V1 requiert Gemma via `llm-gateway`',
    "When le Spark est indisponible",
    'Then `LLM_UNAVAILABLE`',
    "factuelle",
    "snapshot",
    "aucun benchmark LLM promu",
    "aucun provider alternatif",
    "retry born",
    "premier token interdit",
    "circuit breaker ouvrable et refermable",
    "fonctions locales hors Gemma disponibles",
    "aucun prompt complet",
    "aucun double outbox",
    "ADR-008",
    "ADR-009",
    "DDD-ADR-006",
    "CTRL-M013-SPARK-001",
    "CTRL-M013-SPARK-002",
    "CTRL-M013-SPARK-003",
    "CTRL-M013-SPARK-004",
    "CTRL-M013-SPARK-005",
    "CTRL-M013-SPARK-006",
    "CTRL-M013-SPARK-007",
    "CTRL-M013-SPARK-008",
    "CTRL-M013-SPARK-009",
    "CTRL-M013-SPARK-010",
    "CTRL-M013-SPARK-011"
)

$forbiddenDrillPatterns = @(
    "fallback distant de secours",
    "fallback silencieux autorisé",
    "provider alternatif appelé",
    "provider alternatif autorisé",
    "snapshot stratégie créé",
    "benchmark LLM promu automatiquement",
    "réponse factuelle publiée sans génération complète",
    "PROMPT_COMPLET_INTERDIT_M013",
    "SECRET_INTERDIT_M013",
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "Authorization: Bearer"
)

function Assert-M013Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-M013Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-M013Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Resolve-M013RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    Assert-M013Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"

    return $resolvedPath
}

function Invoke-M013SparkFailureDomainCheck {
    . (Join-Path $repoRoot "scripts/require_python.ps1")
    $pythonExecutable = Get-RequiredPythonExecutable
    $pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.llm_gateway.spark_failure_drill import (
    SPARK_FAILURE_DRILL_POLICY_VERSION,
    SparkFailureDrillPolicy,
    build_m013_spark_failure_drill,
)

drill = build_m013_spark_failure_drill()
SparkFailureDrillPolicy(policy_version=SPARK_FAILURE_DRILL_POLICY_VERSION).validate_drill(drill)
print(f"{len(drill.cases)} cas de panne Spark validés")
'@
    $pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_spark_failure_validator_" + [System.Guid]::NewGuid().ToString("N") + ".py")
    Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $pythonScriptPath -Force
    }

    if ($exitCode -ne 0) {
        throw "Politique de panne Spark M-013 invalide: $($output -join "`n")"
    }
}

function Assert-M013DrillReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $DrillContent
    )

    foreach ($pattern in $forbiddenDrillPatterns) {
        if ($DrillContent -match [regex]::Escape($pattern)) {
            throw "Fallback Spark interdit: $pattern"
        }
    }

    foreach ($status in $requiredStatusMarkers) {
        Assert-M013Contains `
            -Content $DrillContent `
            -Expected $status `
            -Message "statut public panne Spark absent: $status"
    }

    foreach ($marker in $requiredDrillMarkers) {
        Assert-M013Contains -Content $DrillContent -Expected $marker -Message "Marqueur drill pannes Spark absent: $marker"
    }
}

function Assert-M013Traceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($marker in @(
        "REQ-M013-006",
        "docs/tasks/milestone_013/0006_eprouver_pannes_spark_sans_fallback.md",
        "tests/m013/validate_spark_failure_acceptance.ps1",
        "tests/m013/validate_spark_failure_unit.ps1",
        "scripts/validate_m013_spark_failures.ps1",
        "docs/governance/m013_spark_failure_drill.md",
        "app/platform/llm_gateway/spark_failure_drill.py",
        "ADR-008",
        "ADR-009",
        "DDD-ADR-006"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-006 absente: $marker"
    }

    foreach ($marker in @(
        "scripts/validate_m013_spark_failures.ps1",
        "tests/m013/validate_spark_failure_acceptance.ps1",
        "tests/m013/validate_spark_failure_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans pannes Spark M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_spark_failures.ps1" `
        -Message "Gate lint sans validateur pannes Spark M-013."
}

$resolvedDrillPath = Resolve-M013RequiredPath -Path $DrillPath -DefaultRelativePath $defaultDrillPath -Label "drill pannes Spark"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

Invoke-M013SparkFailureDomainCheck

$drillContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedDrillPath).TrimStart([char] 0xFEFF)
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)

Assert-M013DrillReport -DrillContent $drillContent
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Pannes Spark M-013 valides: LLM_UNAVAILABLE, circuit breaker ouvrable et refermable, fonctions locales hors Gemma disponibles."
