param(
    [Parameter(Mandatory = $false)]
    [string] $MonitoringPath,

    [Parameter(Mandatory = $false)]
    [string] $ResourceProfilePath,

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

$defaultMonitoringPath = "docs/governance/m013_local_monitoring.md"
$defaultResourceProfilePath = "docs/governance/m013_resource_profile.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredMetrics = @(
    "v1_health_status",
    "v1_error_total",
    "v1_latency_ms",
    "job_queue_depth",
    "outbox_pending_total",
    "llm_gateway_latency_ms",
    "spark_inference_availability",
    "backup_restore_result",
    "v1_gap_status",
    "network_security_violation_total"
)

$requiredMonitoringMarkers = @(
    "# Monitoring local d'exploitation M-013",
    "M013-LocalMonitoringProfile-1.0",
    "LocalMonitoringProfile",
    "MonitoringSignalPolicy",
    "Given la V1 traite documents",
    "When le monitoring local",
    "Then les signaux indiquent santé",
    "Export externe par défaut: interdit",
    "Endpoint public: interdit",
    "Rétention courte des logs: 72 heures",
    "Corrélation:",
    "Aucun payload sensible",
    "Aucun prompt complet",
    "Aucune preuve complète",
    "Aucune réponse complète",
    "Aucun secret",
    "Aucune donnée de marché complète",
    "restore_test_result",
    "circuit breaker",
    "retry avant premier token",
    "v1_gap_status",
    "network_security_violation_total"
)

$requiredResourceMarkers = @(
    "# Profil de ressources V1 M-013",
    "M013-ResourceProfile-1.0",
    "ResourceProfilePolicy",
    "Profil CPU/GPU/I/O docker-local",
    "DGX Spark",
    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gemma-m013-v1-benchmark-revision",
    "Concurrence sourcée par benchmark",
    "Longueur de contexte sourcée par benchmark",
    "docs/evaluation/m012/llm_real_path_benchmark_report.md",
    "CPU",
    "GPU",
    "MEMORY",
    "IO",
    "STORAGE",
    "Aucune capacité hôte n'est acceptée sans mesure",
    "défaut implicite"
)

$forbiddenPatterns = @(
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "POSTGRES_PASSWORD\s*=",
    "QDRANT_API_KEY\s*=",
    "GEMMA_API_KEY\s*=",
    "VLLM_API_KEY\s*=",
    "Authorization:\s*Bearer",
    "SECRET_INTERDIT_M013",
    "PROMPT_COMPLET",
    "PREUVE_COMPLETE",
    "REPONSE_COMPLETE"
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

function Invoke-M013MonitoringDomainCheck {
    . (Join-Path $repoRoot "scripts/require_python.ps1")
    $pythonExecutable = Get-RequiredPythonExecutable
    $pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.observability import (
    MonitoringSignalPolicy,
    ResourceProfilePolicy,
    build_m013_local_monitoring_profile,
    build_m013_resource_profile,
)

monitoring_profile = build_m013_local_monitoring_profile()
resource_profile = build_m013_resource_profile()
MonitoringSignalPolicy(public_endpoint_enabled=False).validate_profile(monitoring_profile)
ResourceProfilePolicy().validate_profile(resource_profile)
print(f"{len(monitoring_profile.metrics_by_name)} métriques contrôlées, {len(resource_profile.measurements)} mesures ressources")
'@
    $pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_monitoring_validator_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Politique monitoring local M-013 invalide: $($output -join "`n")"
    }
}

function Assert-M013MonitoringDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MonitoringContent
    )

    foreach ($pattern in $forbiddenPatterns) {
        if ([regex]::IsMatch($MonitoringContent, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Payload sensible interdit dans le monitoring local M-013: $pattern"
        }
    }

    if ($MonitoringContent.Contains("Export externe par défaut: activé")) {
        throw "Export externe par défaut interdit"
    }

    foreach ($marker in $requiredMonitoringMarkers) {
        Assert-M013Contains -Content $MonitoringContent -Expected $marker -Message "Marqueur monitoring local absent: $marker"
    }

    foreach ($metric in $requiredMetrics) {
        Assert-M013Contains -Content $MonitoringContent -Expected $metric -Message "Marqueur monitoring local absent: $metric"
    }
}

function Assert-M013ResourceProfileDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ResourceProfileContent
    )

    foreach ($pattern in $forbiddenPatterns) {
        if ([regex]::IsMatch($ResourceProfileContent, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Payload sensible interdit dans le profil ressources M-013: $pattern"
        }
    }

    if (-not [regex]::IsMatch($ResourceProfileContent, "sha256:[0-9a-f]{64}")) {
        throw "Image vLLM épinglée requise"
    }

    foreach ($marker in $requiredResourceMarkers) {
        Assert-M013Contains -Content $ResourceProfileContent -Expected $marker -Message "Marqueur profil ressources absent: $marker"
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
        "REQ-M013-009",
        "docs/tasks/milestone_013/0009_publier_monitoring_local_exploitation.md",
        "tests/m013/validate_local_monitoring_acceptance.ps1",
        "tests/m013/validate_local_monitoring_unit.ps1",
        "scripts/validate_m013_monitoring.ps1",
        "docs/governance/m013_local_monitoring.md",
        "docs/governance/m013_resource_profile.md",
        "app/platform/observability/__init__.py",
        "ADR-008",
        "ADR-009",
        "ADR-010"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-009 absente: $marker"
    }

    foreach ($marker in @(
        "scripts/validate_m013_monitoring.ps1",
        "tests/m013/validate_local_monitoring_acceptance.ps1",
        "tests/m013/validate_local_monitoring_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans monitoring local M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_monitoring.ps1" `
        -Message "Gate lint sans validateur monitoring local M-013."
}

$resolvedMonitoringPath = Resolve-M013RequiredPath -Path $MonitoringPath -DefaultRelativePath $defaultMonitoringPath -Label "monitoring local"
$resolvedResourceProfilePath = Resolve-M013RequiredPath -Path $ResourceProfilePath -DefaultRelativePath $defaultResourceProfilePath -Label "profil ressources"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

Invoke-M013MonitoringDomainCheck

$monitoringContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMonitoringPath).TrimStart([char] 0xFEFF)
$resourceProfileContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedResourceProfilePath).TrimStart([char] 0xFEFF)
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)

Assert-M013MonitoringDocument -MonitoringContent $monitoringContent
Assert-M013ResourceProfileDocument -ResourceProfileContent $resourceProfileContent
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Monitoring local M-013 valide: $($requiredMetrics.Count) métriques V1 critiques, aucun payload sensible, rétention courte, corrélation, aucun export externe, profil CPU/GPU/I/O docker-local, vLLM épinglée, modèle révisionné, concurrence sourcée par benchmark, longueur de contexte sourcée par benchmark."
