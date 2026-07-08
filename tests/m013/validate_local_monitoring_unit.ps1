$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_monitoring.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_monitoring_unit_" + [System.Guid]::NewGuid().ToString("N"))

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.observability import (
    M013_LOCAL_LOG_RETENTION_HOURS,
    MonitoringSignal,
    MonitoringSignalPolicy,
    ResourceProfilePolicy,
    ResourceProfileMeasurement,
    build_m013_local_monitoring_profile,
    build_m013_resource_profile,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(collection, expected, message):
    if expected not in collection:
        raise AssertionError(f"{message} Valeur absente: {expected!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def signal(**overrides):
    payload = {
        "signal_id": "MON-M013-UNIT-001",
        "context": "platform",
        "component": "llm-gateway",
        "metric_name": "llm_gateway_latency_ms",
        "metric_family": "latence",
        "owner": "platform",
        "correlation_field": "trace_id",
        "retention_hours": M013_LOCAL_LOG_RETENTION_HOURS,
        "local_only": True,
        "external_export_enabled_by_default": False,
        "contains_full_prompt": False,
        "contains_full_evidence": False,
        "contains_full_response": False,
        "contains_secret": False,
        "contains_market_payload": False,
        "gap_status_visible": True,
        "spark_failure_visible": True,
        "backup_restore_visible": True,
        "security_boundary_visible": True,
        "alert_threshold": "p95 > seuil publié par benchmark M012-LLM-REAL-PATH",
        "threshold_source": "docs/evaluation/m012/llm_real_path_benchmark_report.md",
    }
    payload.update(overrides)
    return MonitoringSignal(**payload)


def measurement(**overrides):
    payload = {
        "measurement_id": "RES-M013-UNIT-001",
        "host": "docker-local",
        "resource_kind": "CPU",
        "metric_name": "docker_local_cpu_utilization_percent",
        "measured_value": 42.0,
        "unit": "percent",
        "benchmark_source": "docs/evaluation/m012/llm_real_path_benchmark_report.md",
        "capacity_decision": "accepté pour V1 locale sous charge benchmarkée",
        "explicit_setting": "cpu_quota=8",
    }
    payload.update(overrides)
    return ResourceProfileMeasurement(**payload)


# Given la V1 publie des signaux locaux pour tous les contextes et services critiques.
# When MonitoringSignalPolicy construit le profil local M-013.
# Then chaque signal porte propriétaire, corrélation, rétention courte, statut d'écart
# et garde-fous de non-divulgation.
monitoring_policy = MonitoringSignalPolicy(public_endpoint_enabled=False)
monitoring_profile = build_m013_local_monitoring_profile()
monitoring_policy.validate_profile(monitoring_profile)

for metric in (
    "v1_health_status",
    "v1_error_total",
    "v1_latency_ms",
    "job_queue_depth",
    "outbox_pending_total",
    "llm_gateway_latency_ms",
    "spark_inference_availability",
    "backup_restore_result",
    "v1_gap_status",
    "network_security_violation_total",
):
    assert_contains(monitoring_profile.metrics_by_name, metric, "Métrique V1 critique manquante.")

for context in ("SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV", "platform"):
    assert_contains(monitoring_profile.contexts, context, "Contexte V1 absent du monitoring local.")

assert_equal(monitoring_profile.local_only, True, "Le monitoring V1 doit rester local.")
assert_equal(monitoring_profile.external_export_enabled_by_default, False, "Aucun export externe par défaut.")
assert_equal(monitoring_profile.retention_hours, M013_LOCAL_LOG_RETENTION_HOURS, "La rétention courte doit être explicite.")

assert_raises("métrique absente", lambda: MonitoringSignalPolicy(public_endpoint_enabled=False).validate_profile(monitoring_profile.without_metric("v1_health_status")))
assert_raises("payload sensible interdit", lambda: signal(contains_full_prompt=True))
assert_raises("payload sensible interdit", lambda: signal(contains_full_evidence=True))
assert_raises("payload sensible interdit", lambda: signal(contains_secret=True))
assert_raises("rétention courte requise", lambda: signal(retention_hours=0))
assert_raises("corrélation requise", lambda: signal(correlation_field=""))
assert_raises("statut d'écart visible requis", lambda: signal(gap_status_visible=False))
assert_raises("panne Spark visible requise", lambda: signal(spark_failure_visible=False))
assert_raises("sauvegarde restauration visible requise", lambda: signal(backup_restore_visible=False))
assert_raises("seuil sourcé requis", lambda: signal(alert_threshold="p95 > 5s", threshold_source=""))
assert_raises("export externe par défaut interdit", lambda: signal(external_export_enabled_by_default=True))
assert_raises("endpoint public interdit", lambda: MonitoringSignalPolicy(public_endpoint_enabled=True))


# Given le profil de ressources fixe Gemma, vLLM et docker-local sur des mesures V1.
# When ResourceProfilePolicy valide le profil.
# Then CPU, GPU, mémoire, I/O, image vLLM, révision modèle, concurrence et longueur
# de contexte sont sourcés par benchmark plutôt que par défaut implicite.
resource_policy = ResourceProfilePolicy()
resource_profile = build_m013_resource_profile()
resource_policy.validate_profile(resource_profile)

for resource_kind in ("CPU", "GPU", "MEMORY", "IO", "STORAGE"):
    assert_contains(resource_profile.resource_kinds, resource_kind, "Mesure de ressource docker-local absente.")

assert_equal(resource_profile.docker_local_profiled, True, "Le profil docker-local doit être mesuré.")
assert_equal(resource_profile.vllm_image_digest.startswith("sha256:"), True, "Image vLLM non épinglée.")
assert_equal(resource_profile.model_revision, "gemma-m013-v1-benchmark-revision", "Révision modèle absente.")
assert_equal(resource_profile.concurrency.benchmark_source.endswith("llm_real_path_benchmark_report.md"), True, "Concurrence non sourcée.")
assert_equal(resource_profile.context_length.benchmark_source.endswith("llm_real_path_benchmark_report.md"), True, "Longueur de contexte non sourcée.")

assert_raises("mesure CPU/GPU/I/O absente", lambda: resource_policy.validate_profile(resource_profile.without_resource("GPU")))
assert_raises("image vLLM épinglée requise", lambda: resource_profile.with_vllm_image_digest("vllm-openai:latest"))
assert_raises("révision modèle requise", lambda: resource_profile.with_model_revision(""))
assert_raises("concurrence sourcée par benchmark requise", lambda: resource_profile.with_concurrency_source(""))
assert_raises("longueur de contexte sourcée par benchmark requise", lambda: resource_profile.with_context_length_source(""))
assert_raises("valeur par défaut interdite", lambda: resource_profile.with_context_length_default(True))
assert_raises("mesure CPU/GPU/I/O absente", lambda: measurement(measured_value=0.0))

print("Tests unitaires MonitoringSignalPolicy et ResourceProfilePolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_monitoring_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires MonitoringSignalPolicy M-013 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $monitoringPath = Join-Path $ProjectRoot "docs/governance/m013_local_monitoring.md"
    $resourceProfilePath = Join-Path $ProjectRoot "docs/governance/m013_resource_profile.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

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

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_local_monitoring.md") -Destination (Join-Path $projectRoot "docs/governance/m013_local_monitoring.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_resource_profile.md") -Destination (Join-Path $projectRoot "docs/governance/m013_resource_profile.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur monitoring local M-013 absent: scripts/validate_m013_monitoring.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-009 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Monitoring local M-013 valide" `
        -Message "La fixture valide doit annoncer le GREEN T-009."

    Assert-ValidatorFails `
        -Name "metrique-sante-absente" `
        -ExpectedMessage "Marqueur monitoring local absent: v1_health_status" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_local_monitoring.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("v1_health_status", "health_status_masque") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "secret-documente" `
        -ExpectedMessage "Payload sensible interdit dans le monitoring local M-013" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_local_monitoring.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nAuthorization: Bearer SECRET_INTERDIT_M013"
        }

    Assert-ValidatorFails `
        -Name "export-externe" `
        -ExpectedMessage "Export externe par défaut interdit" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_local_monitoring.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("Export externe par défaut: interdit", "Export externe par défaut: activé") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "image-vllm-non-epinglee" `
        -ExpectedMessage "Image vLLM épinglée requise" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_resource_profile.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "latest") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "traceabilite-absente" `
        -ExpectedMessage "Traçabilité T-009 absente: REQ-M013-009" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("REQ-M013-009", "REQ-M013-XXX") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur monitoring local M-013: OK"
