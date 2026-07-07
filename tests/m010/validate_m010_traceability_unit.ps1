$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m010_traceability.ps1"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$specificationPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsModulePath = Join-Path $repoRoot "app/strategy_design/application/traceability_metrics.py"

function Assert-File {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message Chemin attendu: $Path"
    }
}

function Invoke-M010TraceabilityValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixPath,

        [Parameter(Mandatory = $true)]
        [string] $SpecificationPath,

        [Parameter(Mandatory = $true)]
        [string] $TestGatePath,

        [Parameter(Mandatory = $true)]
        [string] $LintGatePath,

        [Parameter(Mandatory = $true)]
        [string] $MetricsModulePath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath `
            -MatrixPath $MatrixPath `
            -SpecificationPath $SpecificationPath `
            -TestGatePath $TestGatePath `
            -LintGatePath $LintGatePath `
            -MetricsModulePath $MetricsModulePath `
            2>&1
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

function Copy-CanonicalFixture {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TemporaryRoot
    )

    New-Item -ItemType Directory -Path $TemporaryRoot -Force | Out-Null

    $fixture = [ordered] @{
        Matrix = Join-Path $TemporaryRoot "matrix.md"
        Specification = Join-Path $TemporaryRoot "specification.md"
        TestGate = Join-Path $TemporaryRoot "test.ps1"
        LintGate = Join-Path $TemporaryRoot "lint.ps1"
        MetricsModule = Join-Path $TemporaryRoot "traceability_metrics.py"
    }

    Copy-Item -LiteralPath $matrixPath -Destination $fixture.Matrix
    Copy-Item -LiteralPath $specificationPath -Destination $fixture.Specification
    Copy-Item -LiteralPath $testGatePath -Destination $fixture.TestGate
    Copy-Item -LiteralPath $lintGatePath -Destination $fixture.LintGate
    Copy-Item -LiteralPath $metricsModulePath -Destination $fixture.MetricsModule

    return [pscustomobject] $fixture
}

function Set-Text {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $Content
}

function Remove-M010TemporaryRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return
    }

    $lastError = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds (200 * $attempt)
        }
    }

    throw "Nettoyage temporaire M-010 impossible apres 5 tentatives: $Path. Derniere erreur: $lastError"
}

function Assert-ValidatorRejects {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Fixture,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedFragment,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    $result = Invoke-M010TraceabilityValidator `
        -MatrixPath $Fixture.Matrix `
        -SpecificationPath $Fixture.Specification `
        -TestGatePath $Fixture.TestGate `
        -LintGatePath $Fixture.LintGate `
        -MetricsModulePath $Fixture.MetricsModule

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message $Message
    Assert-OutputContains -Output $result.Output -Expected $ExpectedFragment -Message $Message
}

Assert-File -Path $validatorPath -Message "Validateur de tracabilite M-010 absent."
Assert-File -Path $metricsModulePath -Message "Module de metriques SD M-010 absent."

$temporaryRoot = Join-Path $repoRoot ("docs/traceability/.tmp_m010_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validFixture = Copy-CanonicalFixture -TemporaryRoot $temporaryRoot
    $validResult = Invoke-M010TraceabilityValidator `
        -MatrixPath $validFixture.Matrix `
        -SpecificationPath $validFixture.Specification `
        -TestGatePath $validFixture.TestGate `
        -LintGatePath $validFixture.LintGate `
        -MetricsModulePath $validFixture.MetricsModule

    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une tracabilite M-010 complete doit etre acceptee."

    $missingRequirementFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_requirement")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingRequirementFixture.Matrix) -Force | Out-Null
    $missingRequirementContent = ((Get-Content -Encoding UTF8 -LiteralPath $missingRequirementFixture.Matrix) | Where-Object {
        -not $_.StartsWith("| REQ-M010-011 ")
    }) -join "`n"
    Set-Text -Path $missingRequirementFixture.Matrix -Content $missingRequirementContent
    Assert-ValidatorRejects -Fixture $missingRequirementFixture -ExpectedFragment "Exigence M-010 absente: REQ-M010-011" -Message "Une exigence M-010 sans ligne doit etre refusee."

    $missingTestFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_test")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingTestFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingTestFixture.Matrix `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingTestFixture.Matrix).Replace("tests/m010/validate_m010_traceability_acceptance.ps1", "tests/m010/test_absent.ps1"))
    Assert-ValidatorRejects -Fixture $missingTestFixture -ExpectedFragment "Test M-010 invalide pour REQ-M010-011" -Message "Une exigence M-010 sans test attendu doit etre refusee."

    $missingCommandFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_command")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingCommandFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingCommandFixture.Matrix `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingCommandFixture.Matrix).Replace("powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_acceptance.ps1", "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1"))
    Assert-ValidatorRejects -Fixture $missingCommandFixture -ExpectedFragment "Commande M-010 invalide pour REQ-M010-011" -Message "Une exigence M-010 sans commande attendue doit etre refusee."

    $missingMetricFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_metric")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingMetricFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingMetricFixture.MetricsModule `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingMetricFixture.MetricsModule).Replace("strategy_compilable_rate", "strategy_compilable_rate_absente"))
    Assert-ValidatorRejects -Fixture $missingMetricFixture -ExpectedFragment "Metrique M-010 absente: strategy_compilable_rate" -Message "Une metrique normative absente doit etre refusee."

    $sensitiveMetricFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "sensitive_metric")
    New-Item -ItemType Directory -Path (Split-Path -Parent $sensitiveMetricFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $sensitiveMetricFixture.MetricsModule `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $sensitiveMetricFixture.MetricsModule) + "`nPROMPT_COMPLET_INTERDIT_M010")
    Assert-ValidatorRejects -Fixture $sensitiveMetricFixture -ExpectedFragment "Payload sensible M-010 expose" -Message "Une metrique contenant un payload sensible doit etre refusee."

    $inconsistentCounterFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "inconsistent_counter")
    New-Item -ItemType Directory -Path (Split-Path -Parent $inconsistentCounterFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $inconsistentCounterFixture.MetricsModule `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $inconsistentCounterFixture.MetricsModule).Replace('"strategy_versions_per_strategy"', '"strategy_versions_per_strategy", "strategy_metric_extra_total"'))
    Assert-ValidatorRejects -Fixture $inconsistentCounterFixture -ExpectedFragment "Compteur normatif M-010 incoherent" -Message "Un compteur de metriques incoherent doit etre refuse."

    $missingConcurrencyFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_concurrency")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingConcurrencyFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingConcurrencyFixture.Matrix `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingConcurrencyFixture.Matrix).Replace("concurrence optimiste", "concurrence non tracee"))
    Assert-ValidatorRejects -Fixture $missingConcurrencyFixture -ExpectedFragment "Concurrence optimiste M-010 absente" -Message "La concurrence optimiste non tracee doit etre refusee."

    $missingOutboxFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_outbox")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingOutboxFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingOutboxFixture.Matrix `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingOutboxFixture.Matrix).Replace("StrategySnapshotCreated", "StrategySnapshotMissing"))
    Assert-ValidatorRejects -Fixture $missingOutboxFixture -ExpectedFragment "Outbox StrategySnapshotCreated M-010 absente" -Message "L'outbox StrategySnapshotCreated non tracee doit etre refusee."

    $missingSupersessionFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_supersession")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingSupersessionFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingSupersessionFixture.Matrix `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingSupersessionFixture.Matrix).Replace("supersession de version", "version non tracee"))
    Assert-ValidatorRejects -Fixture $missingSupersessionFixture -ExpectedFragment "Supersession de version M-010 absente" -Message "La supersession non tracee doit etre refusee."

    $missingGateFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_gate")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingGateFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingGateFixture.TestGate `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingGateFixture.TestGate).Replace("tests/m010/validate_m010_traceability_unit.ps1", "tests/m010/test_non_enrole.ps1"))
    Assert-ValidatorRejects -Fixture $missingGateFixture -ExpectedFragment "Gate test sans test M-010: tests/m010/validate_m010_traceability_unit.ps1" -Message "Un test M-010 hors scripts/test.ps1 doit etre refuse."

    $missingLintFixture = Copy-CanonicalFixture -TemporaryRoot (Join-Path $temporaryRoot "missing_lint")
    New-Item -ItemType Directory -Path (Split-Path -Parent $missingLintFixture.Matrix) -Force | Out-Null
    Set-Text `
        -Path $missingLintFixture.LintGate `
        -Content ((Get-Content -Raw -Encoding UTF8 -LiteralPath $missingLintFixture.LintGate).Replace("scripts/validate_m010_traceability.ps1", "scripts/validate_m010_traceability_absent.ps1"))
    Assert-ValidatorRejects -Fixture $missingLintFixture -ExpectedFragment "Gate lint sans validateur M-010" -Message "Le validateur M-010 hors scripts/lint.ps1 doit etre refuse."
}
finally {
    Remove-M010TemporaryRoot -Path $temporaryRoot
}

. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.strategy_design.application.traceability_metrics import (
    StrategyDesignAuditSignal,
    StrategyDesignMetricObservation,
    StrategyDesignMetricsPublisher,
    assert_no_sensitive_payload_in_audit_payload,
)


def expect_raises(expected_fragment, action):
    try:
        action()
    except Exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


observations = (
    StrategyDesignMetricObservation(
        trace_id="TRACE-M010-METRIC-1",
        strategy_id="STRAT-M010-METRIC",
        strategy_version=1,
        compilation_status="COMPILABLE",
        rejection_reason_code=None,
        rule_origin_type="SOURCE",
        parameter_without_calibration_plan=False,
        compatibility_conflict_category=None,
        snapshot_event_type="StrategySnapshotCreated",
        supersedes_snapshot_id=None,
        payload_hash="a" * 64,
        observed_at="2026-07-04T12:00:00Z",
    ),
    StrategyDesignMetricObservation(
        trace_id="TRACE-M010-METRIC-2",
        strategy_id="STRAT-M010-METRIC",
        strategy_version=2,
        compilation_status="INCONSISTENT",
        rejection_reason_code="STRATEGY_COMPATIBILITY_FAILED",
        rule_origin_type="PARAMETER_TO_CALIBRATE",
        parameter_without_calibration_plan=True,
        compatibility_conflict_category="DATA_FREQUENCY_INCOMPATIBLE",
        snapshot_event_type="StrategyVersionSuperseded",
        supersedes_snapshot_id="SVER-M010-METRIC-V000001",
        payload_hash="b" * 64,
        observed_at="2026-07-04T12:05:00Z",
    ),
)

snapshot = StrategyDesignMetricsPublisher().publish(
    fixture_id="M010_TRACEABILITY_UNIT",
    fixture_path="tests/m010/validate_m010_traceability_unit.ps1",
    observations=observations,
    measured_at="2026-07-04T12:10:00Z",
)

expected_metric_names = (
    "strategy_compilable_rate",
    "strategy_rejection_reason_top",
    "strategy_rule_origin_proportion",
    "strategy_parameter_without_calibration_plan_total",
    "strategy_compatibility_conflict_by_category",
    "strategy_versions_per_strategy",
)

assert tuple(snapshot.normative_metrics) == expected_metric_names
assert snapshot.normative_metrics["strategy_compilable_rate"] == 0.5
assert snapshot.normative_metrics["strategy_rejection_reason_top"]["STRATEGY_COMPATIBILITY_FAILED"] == 1
assert snapshot.normative_metrics["strategy_rule_origin_proportion"]["SOURCE"] == 0.5
assert snapshot.normative_metrics["strategy_parameter_without_calibration_plan_total"] == 1
assert snapshot.normative_metrics["strategy_compatibility_conflict_by_category"]["DATA_FREQUENCY_INCOMPATIBLE"] == 1
assert snapshot.normative_metrics["strategy_versions_per_strategy"]["STRAT-M010-METRIC"] == 2

signal = StrategyDesignAuditSignal.from_metric_snapshot(
    audit_signal_id="SD-AUDIT-M010-METRIC",
    trace_id="TRACE-M010-METRIC-SIGNAL",
    metric_snapshot=snapshot,
    strategy_refs=(
        {
            "strategy_id": "STRAT-M010-METRIC",
            "latest_version": 2,
            "strategy_hash": "c" * 64,
        },
    ),
    forbidden_sensitive_payloads=(
        "PROMPT_COMPLET_INTERDIT_M010",
        "secret-token-m010",
        "texte source complet interdit m010",
        "payload documentaire complet interdit m010",
        "mutable_snapshot_payload_complet_interdit",
    ),
)
payload = signal.to_payload()
assert payload["signal_name"] == "strategy_design_metrics_published"
assert payload["metric_scope"] == "M010_STRATEGY_DESIGN"
assert "prompt" not in str(payload).lower()
assert "secret-token-m010" not in str(payload)

expect_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"payload": "PROMPT_COMPLET_INTERDIT_M010"},
        forbidden_sensitive_payloads=("PROMPT_COMPLET_INTERDIT_M010",),
    ),
)
expect_raises(
    "parameter_without_calibration_plan incompatible",
    lambda: StrategyDesignMetricObservation(
        trace_id="TRACE-M010-METRIC-3",
        strategy_id="STRAT-M010-METRIC",
        strategy_version=3,
        compilation_status="COMPILABLE",
        rejection_reason_code=None,
        rule_origin_type="SOURCE",
        parameter_without_calibration_plan=True,
        compatibility_conflict_category=None,
        snapshot_event_type="StrategySnapshotCreated",
        supersedes_snapshot_id=None,
        payload_hash="d" * 64,
        observed_at="2026-07-04T12:15:00Z",
    ),
)

print("Tests Python des metriques SD M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_traceability_metrics_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests Python des metriques SD M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

Write-Host "Tests unitaires T-011 tracabilite, metriques et gates M-010: OK"
