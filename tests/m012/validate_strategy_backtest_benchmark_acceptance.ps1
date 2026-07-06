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

HASH = "a" * 64
POLICY_VERSION = "StrategyExperimentBenchmarkPolicy-1.0"


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


def calibration_protocol(name="lookback"):
    return CalibrationProtocol(
        parameter_name=name,
        domain={"lower_bound": 20, "upper_bound": 120, "unit": "jours"},
        protocol_version="CAL-M012-WALK-FORWARD-1",
        out_of_sample_period={"start": "2024-01-01", "end": "2024-12-31"},
    )


def strategy_case(
    case_id,
    strategy_id,
    version,
    *,
    compilable,
    rejection_reasons=(),
    origins=("SOURCE",),
    parameters_without_plan=(),
    conflicts=(),
):
    return StrategyEvaluationCase(
        case_id=case_id,
        strategy_id=strategy_id,
        strategy_version_id=f"SVER-M012-T010-{strategy_id}-{version}",
        strategy_version=version,
        compilation_status="COMPILABLE" if compilable else "INCOMPLETE",
        rejection_reasons=rejection_reasons,
        rule_origins=origins,
        parameters_without_calibration_plan=parameters_without_plan,
        compatibility_conflicts=conflicts,
        metric_source="SD",
    )


def backtest_result(
    experiment_id,
    strategy_version_id,
    *,
    status="COMPLETED",
    return_pct="0.020000000000",
    negative=False,
    failure_cause=None,
    cost_complete=True,
    repeat_coherent=False,
    invalidated=False,
):
    return BacktestBenchmarkResult(
        experiment_id=experiment_id,
        strategy_version_id=strategy_version_id,
        data_snapshot_id="DATA-M012-T010-PILOT",
        period_start="2023-01-01",
        period_end="2023-12-31",
        universe=("CAC40", "STOXX600"),
        cost_model={"commission_bps": "5.000000000000", "slippage_bps": "3.000000000000", "currency": "EUR"},
        assumptions=("hors échantillon déclaré", "dividendes ajustés", "liquidité pilote limitée"),
        calibration_protocols=(calibration_protocol(),),
        status=status,
        metrics={"return_pct": return_pct, "max_drawdown_pct": "-0.080000000000"},
        result_negative=negative,
        failure_cause=failure_cause,
        retained=True,
        cost_model_complete=cost_complete,
        repeat_coherent=repeat_coherent,
        invalidated_after_audit=invalidated,
        profitability_verdict="résultat pilote descriptif",
        profitability_qualification="qualification explicite: mesure pilote non generalisable et sans promesse de rentabilite",
        result_hash=HASH,
        metric_source="EX",
    )


# Given des stratégies candidates snapshotées et des expériences reproductibles M-011.
compiled_case = strategy_case(
    "CASE-M012-T010-COMPILED",
    "STRAT-A",
    1,
    compilable=True,
    origins=("SOURCE", "DEDUCTION", "PARAMETER_TO_CALIBRATE"),
)
rejected_case = strategy_case(
    "CASE-M012-T010-REJECTED",
    "STRAT-A",
    2,
    compilable=False,
    rejection_reasons=("PARAMETER_CALIBRATION_REQUIRED", "STRATEGY_CONFLICT_BLOCKING"),
    origins=("DESIGN_CHOICE", "USER_CONSTRAINT"),
    parameters_without_plan=("lookback",),
    conflicts=("cost", "liquidity"),
)
second_strategy_case = strategy_case(
    "CASE-M012-T010-SECOND",
    "STRAT-B",
    1,
    compilable=True,
    origins=("SOURCE", "DESIGN_CHOICE"),
)

results = (
    backtest_result(
        "EXP-M012-T010-POSITIVE",
        compiled_case.strategy_version_id,
        repeat_coherent=True,
    ),
    backtest_result(
        "EXP-M012-T010-NEGATIVE",
        compiled_case.strategy_version_id,
        return_pct="-0.030000000000",
        negative=True,
        repeat_coherent=True,
        invalidated=True,
    ),
    backtest_result(
        "EXP-M012-T010-FAILED",
        rejected_case.strategy_version_id,
        status="FAILED",
        return_pct="0.000000000000",
        negative=True,
        failure_cause="ENGINE_INPUT_REJECTED",
        cost_complete=False,
    ),
)

# When les backtests pilotes sont mesures selon un protocole M-012.
run = StrategyDesignBenchmark(policy_version=POLICY_VERSION).measure(
    run_id="SBRUN-M012-T010",
    strategy_cases=(compiled_case, rejected_case, second_strategy_case),
    backtest_results=results,
    measured_at="2026-07-06T10:00:00Z",
    metric_source="SD_EX",
)

# Then les métriques SD et EX conservent limites, coûts, périodes, univers, résultats négatifs et échecs.
assert_equal(run.strategy_case_count, 3, "Toutes les versions SD doivent rester dans le dénominateur.")
assert_equal(run.result_count, 3, "Tous les résultats EX doivent rester dans le benchmark.")
assert_equal(run.sd_metrics[STRATEGY_COMPILABLE_RATE].value, "0.666666666667", "Le taux compilable doit compter les stratégies non compilables.")
assert_equal(
    run.sd_metrics[STRATEGY_REJECTION_REASON_DISTRIBUTION].counts,
    {"PARAMETER_CALIBRATION_REQUIRED": 1, "STRATEGY_CONFLICT_BLOCKING": 1},
    "Les raisons de rejet doivent rester agregees.",
)
assert_equal(
    run.sd_metrics[STRATEGY_RULE_ORIGIN_RATIO].ratios,
    {
        "DEDUCTION": "0.142857142857",
        "DESIGN_CHOICE": "0.285714285714",
        "PARAMETER_TO_CALIBRATE": "0.142857142857",
        "SOURCE": "0.285714285714",
        "USER_CONSTRAINT": "0.142857142857",
    },
    "Les origines de règles doivent être proportionnées.",
)
assert_equal(
    run.sd_metrics[STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL].numerator,
    1,
    "Les paramètres sans plan doivent rester visibles.",
)
assert_equal(
    run.sd_metrics[STRATEGY_COMPATIBILITY_CONFLICT_TOTAL].counts,
    {"cost": 1, "liquidity": 1},
    "Les conflits de compatibilite doivent etre categorises.",
)
assert_equal(
    run.sd_metrics[STRATEGY_VERSION_COUNT].counts,
    {"STRAT-A": 2, "STRAT-B": 1},
    "Les versions par stratégie doivent inclure les versions rejetées.",
)
assert_equal(
    run.ex_metrics[EXPERIMENT_REPRODUCIBLE_RATE].value,
    "0.666666666667",
    "Les repetitions coherentes doivent etre mesurees.",
)
assert_equal(
    run.ex_metrics[EXPERIMENT_FAILURE_RATE_BY_CAUSE].counts,
    {"ENGINE_INPUT_REJECTED": 1},
    "Les échecs doivent rester comptés par cause.",
)
assert_equal(
    run.ex_metrics[NEGATIVE_EXPERIMENT_RETENTION_RATIO].value,
    "1.000000000000",
    "Les résultats négatifs et échoués doivent être conservés.",
)
assert_equal(
    run.ex_metrics[EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL].numerator,
    1,
    "Le cout complet doit etre controle.",
)
assert_equal(run.coherent_repeat_count, 2, "Les répétitions cohérentes doivent être publiées.")
assert_equal(
    run.ex_metrics[INVALIDATED_RESULT_RATIO].value,
    "0.333333333333",
    "Les invalidations après audit doivent rester au dénominateur.",
)
assert_equal(
    run.ex_metrics[BACKTEST_ASSUMPTION_COUNT].numerator,
    9,
    "Les hypothèses de backtest doivent être publiées.",
)
assert_equal(
    run.results_by_experiment_id["EXP-M012-T010-NEGATIVE"].result_negative,
    True,
    "Le résultat négatif ne doit pas être retiré.",
)
assert_equal(
    run.results_by_experiment_id["EXP-M012-T010-FAILED"].status,
    "FAILED",
    "L'échec EX doit rester publié.",
)

assert_raises(
    "source métrique LLM interdite",
    lambda: StrategyDesignBenchmark(policy_version=POLICY_VERSION).measure(
        run_id="SBRUN-M012-T010-LLM",
        strategy_cases=(strategy_case("CASE-M012-T010-LLM", "STRAT-C", 1, compilable=True),),
        backtest_results=(
            backtest_result(
                "EXP-M012-T010-LLM",
                "SVER-M012-T010-STRAT-C-1",
            ),
        ),
        measured_at="2026-07-06T10:00:00Z",
        metric_source="LLM",
    ),
)
assert_raises(
    "periode de backtest requise",
    lambda: BacktestBenchmarkResult(
        experiment_id="EXP-M012-T010-NO-PERIOD",
        strategy_version_id=compiled_case.strategy_version_id,
        data_snapshot_id="DATA-M012-T010-PILOT",
        period_start="",
        period_end="2023-12-31",
        universe=("CAC40",),
        cost_model={"commission_bps": "5.000000000000", "slippage_bps": "3.000000000000", "currency": "EUR"},
        assumptions=("hypothese explicite",),
        calibration_protocols=(calibration_protocol(),),
        status="COMPLETED",
        metrics={"return_pct": "0.000000000000"},
        result_negative=False,
        failure_cause=None,
        retained=True,
        cost_model_complete=True,
        repeat_coherent=False,
        invalidated_after_audit=False,
        profitability_verdict=None,
        profitability_qualification=None,
        result_hash=HASH,
        metric_source="EX",
    ),
)
assert_raises(
    "qualification de rentabilite requise",
    lambda: backtest_result(
        "EXP-M012-T010-PROFITABILITY",
        compiled_case.strategy_version_id,
    ).with_profitability_verdict("stratégie rentable", None),
)

print("Test d'acceptation T-010 benchmark stratégies et backtests M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_strategy_backtest_benchmark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-010 benchmark stratégies et backtests M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
