$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.strategy_backtest_benchmark import (
    BACKTEST_ASSUMPTION_COUNT,
    EXPERIMENT_FAILURE_RATE_BY_CAUSE,
    EXPERIMENT_REPRODUCIBLE_RATE,
    EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL,
    INVALIDATED_RESULT_RATIO,
    NEGATIVE_EXPERIMENT_RETENTION_RATIO,
    STRATEGY_COMPATIBILITY_CONFLICT_TOTAL,
    STRATEGY_COMPILABLE_RATE,
    STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL,
    STRATEGY_REJECTION_REASON_DISTRIBUTION,
    STRATEGY_RULE_ORIGIN_RATIO,
    STRATEGY_VERSION_COUNT,
    BacktestBenchmarkResult,
    CalibrationProtocol,
    StrategyDesignBenchmark,
    StrategyEvaluationCase,
)

HASH = "b" * 64


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def calibration_protocol(**overrides):
    payload = {
        "parameter_name": "lookback",
        "domain": {"lower_bound": 20, "upper_bound": 120, "unit": "jours"},
        "protocol_version": "CAL-M012-UNIT-WALK-FORWARD",
        "out_of_sample_period": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    payload.update(overrides)
    return CalibrationProtocol(**payload)


def strategy_case(**overrides):
    payload = {
        "case_id": "CASE-M012-T010-UNIT",
        "strategy_id": "STRAT-UNIT",
        "strategy_version_id": "SVER-M012-T010-UNIT-1",
        "strategy_version": 1,
        "compilation_status": "COMPILABLE",
        "rejection_reasons": (),
        "rule_origins": ("SOURCE", "DEDUCTION"),
        "parameters_without_calibration_plan": (),
        "compatibility_conflicts": (),
        "metric_source": "SD",
    }
    payload.update(overrides)
    return StrategyEvaluationCase(**payload)


def result(**overrides):
    payload = {
        "experiment_id": "EXP-M012-T010-UNIT",
        "strategy_version_id": "SVER-M012-T010-UNIT-1",
        "data_snapshot_id": "DATA-M012-T010-UNIT",
        "period_start": "2023-01-01",
        "period_end": "2023-12-31",
        "universe": ("CAC40",),
        "cost_model": {"commission_bps": "5.000000000000", "slippage_bps": "3.000000000000", "currency": "EUR"},
        "assumptions": ("hypothese pilote explicite",),
        "calibration_protocols": (calibration_protocol(),),
        "status": "COMPLETED",
        "metrics": {"return_pct": "0.000000000000"},
        "result_negative": False,
        "failure_cause": None,
        "retained": True,
        "cost_model_complete": True,
        "repeat_coherent": False,
        "invalidated_after_audit": False,
        "profitability_verdict": None,
        "profitability_qualification": None,
        "result_hash": HASH,
        "metric_source": "EX",
    }
    payload.update(overrides)
    return BacktestBenchmarkResult(**payload)


def measure(strategy_cases, results):
    return StrategyDesignBenchmark(policy_version="StrategyExperimentBenchmarkPolicy-1.0").measure(
        run_id="SBRUN-M012-T010-UNIT",
        strategy_cases=strategy_cases,
        backtest_results=results,
        measured_at="2026-07-06T10:00:00Z",
    )


assert_raises("domaine de calibration requis", lambda: calibration_protocol(domain={}))
assert_raises("protocole de calibration requis", lambda: calibration_protocol(protocol_version=""))
assert_raises(
    "periode hors echantillon requise",
    lambda: calibration_protocol(out_of_sample_period={"start": "2024-01-01"}),
)
assert_raises(
    "periode de backtest requise",
    lambda: result(period_start=""),
)
assert_raises(
    "univers de backtest requis",
    lambda: result(universe=()),
)
assert_raises(
    "modele de couts complet requis",
    lambda: result(cost_model={"commission_bps": "5.000000000000"}),
)
assert_raises(
    "hypothese de backtest requise",
    lambda: result(assumptions=()),
)
assert_raises(
    "entrees figees requises",
    lambda: result(data_snapshot_id="DATA-LATEST"),
)
assert_raises(
    "source metrique LLM interdite",
    lambda: result(metric_source="LLM"),
)
assert_raises(
    "failure_cause requis",
    lambda: result(status="FAILED", failure_cause=None),
)
assert_raises(
    "failure_cause incompatible",
    lambda: result(status="COMPLETED", failure_cause="ENGINE_ERROR"),
)
assert_raises(
    "qualification de rentabilite requise",
    lambda: result(profitability_verdict="rentable", profitability_qualification=None),
)
assert_raises(
    "promesse de rentabilite interdite",
    lambda: result(profitability_verdict="rentabilite garantie", profitability_qualification="qualification explicite"),
)

non_compilable = strategy_case(
    case_id="CASE-M012-T010-REJECT",
    strategy_version_id="SVER-M012-T010-UNIT-2",
    strategy_version=2,
    compilation_status="INCOMPLETE",
    rejection_reasons=("PARAMETER_CALIBRATION_REQUIRED",),
    rule_origins=("SOURCE", "USER_CONSTRAINT"),
    parameters_without_calibration_plan=("lookback",),
    compatibility_conflicts=("data",),
)
assert_equal(non_compilable.compilable, False, "Une strategie INCOMPLETE ne doit pas etre compilable.")
assert_raises(
    "raison de rejet requise",
    lambda: strategy_case(compilation_status="INCOMPLETE", rejection_reasons=()),
)
assert_raises(
    "source metrique LLM interdite",
    lambda: strategy_case(metric_source="LLM"),
)
assert_raises(
    "origine de regle requise",
    lambda: strategy_case(rule_origins=()),
)

run = measure(
    (
        strategy_case(rule_origins=("SOURCE", "DEDUCTION", "DESIGN_CHOICE")),
        non_compilable,
    ),
    (
        result(
            experiment_id="EXP-M012-T010-UNIT-1",
            repeat_coherent=True,
        ),
        result(
            experiment_id="EXP-M012-T010-UNIT-2",
            status="FAILED",
            result_negative=True,
            failure_cause="DATA_SNAPSHOT_REJECTED",
            cost_model_complete=False,
        ),
        result(
            experiment_id="EXP-M012-T010-UNIT-3",
            result_negative=True,
            invalidated_after_audit=True,
        ),
    ),
)

assert_equal(run.sd_metrics[STRATEGY_COMPILABLE_RATE].value, "0.500000000000", "Le taux compilable doit garder le rejet au denominateur.")
assert_equal(run.sd_metrics[STRATEGY_REJECTION_REASON_DISTRIBUTION].counts, {"PARAMETER_CALIBRATION_REQUIRED": 1}, "Les rejets doivent etre comptes.")
assert_equal(run.sd_metrics[STRATEGY_RULE_ORIGIN_RATIO].ratios["SOURCE"], "0.400000000000", "Les origines doivent etre agregees.")
assert_equal(run.sd_metrics[STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL].numerator, 1, "Les parametres sans plan doivent etre comptes.")
assert_equal(run.sd_metrics[STRATEGY_COMPATIBILITY_CONFLICT_TOTAL].counts, {"data": 1}, "Les conflits doivent etre categorises.")
assert_equal(run.sd_metrics[STRATEGY_VERSION_COUNT].counts, {"STRAT-UNIT": 2}, "Les versions invalides doivent rester visibles.")
assert_equal(run.ex_metrics[EXPERIMENT_REPRODUCIBLE_RATE].value, "0.333333333333", "Le taux reproductible doit utiliser tous les resultats.")
assert_equal(run.ex_metrics[EXPERIMENT_FAILURE_RATE_BY_CAUSE].counts, {"DATA_SNAPSHOT_REJECTED": 1}, "Les echecs doivent etre par cause.")
assert_equal(run.ex_metrics[NEGATIVE_EXPERIMENT_RETENTION_RATIO].value, "1.000000000000", "Les negatifs et echecs conserves doivent etre comptes.")
assert_equal(run.ex_metrics[EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL].numerator, 1, "Les couts incomplets doivent etre signales.")
assert_equal(run.ex_metrics[INVALIDATED_RESULT_RATIO].value, "0.333333333333", "Les resultats invalides doivent rester dans le denominateur.")
assert_equal(run.ex_metrics[BACKTEST_ASSUMPTION_COUNT].numerator, 3, "Les hypotheses doivent rester publiees.")

assert_raises(
    "resultat de strategie absente du benchmark SD",
    lambda: measure(
        (strategy_case(),),
        (result(strategy_version_id="SVER-M012-T010-UNKNOWN"),),
    ),
)
assert_raises(
    "strategie dupliquee dans le benchmark",
    lambda: measure(
        (strategy_case(case_id="CASE-A"), strategy_case(case_id="CASE-A")),
        (result(),),
    ),
)
assert_raises(
    "resultat duplique dans le benchmark",
    lambda: measure(
        (strategy_case(),),
        (result(experiment_id="EXP-M012-T010-DUP"), result(experiment_id="EXP-M012-T010-DUP")),
    ),
)

print("Tests unitaires T-010 benchmark strategies et backtests M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_strategy_backtest_benchmark_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires T-010 benchmark strategies et backtests M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
