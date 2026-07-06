"""Benchmark SD/EX des stratégies et backtests pilotes M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import re
from typing import Any


STRATEGY_COMPILABLE_RATE = "strategy_compilable_rate"
STRATEGY_REJECTION_REASON_DISTRIBUTION = "strategy_rejection_reason_distribution"
STRATEGY_RULE_ORIGIN_RATIO = "strategy_rule_origin_ratio"
STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL = "strategy_parameter_without_calibration_plan_total"
STRATEGY_COMPATIBILITY_CONFLICT_TOTAL = "strategy_compatibility_conflict_total"
STRATEGY_VERSION_COUNT = "strategy_version_count"

EXPERIMENT_REPRODUCIBLE_RATE = "experiment_reproducible_rate"
EXPERIMENT_FAILURE_RATE_BY_CAUSE = "experiment_failure_rate_by_cause"
NEGATIVE_EXPERIMENT_RETENTION_RATIO = "negative_experiment_retention_ratio"
EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL = "experiment_without_complete_cost_model_total"
COHERENT_REPEAT_COUNT = "coherent_repeat_count"
INVALIDATED_RESULT_RATIO = "invalidated_result_ratio"
BACKTEST_ASSUMPTION_COUNT = "backtest_assumption_count"

REQUIRED_SD_METRICS = frozenset(
    {
        STRATEGY_COMPILABLE_RATE,
        STRATEGY_REJECTION_REASON_DISTRIBUTION,
        STRATEGY_RULE_ORIGIN_RATIO,
        STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL,
        STRATEGY_COMPATIBILITY_CONFLICT_TOTAL,
        STRATEGY_VERSION_COUNT,
    }
)
REQUIRED_EX_METRICS = frozenset(
    {
        EXPERIMENT_REPRODUCIBLE_RATE,
        EXPERIMENT_FAILURE_RATE_BY_CAUSE,
        NEGATIVE_EXPERIMENT_RETENTION_RATIO,
        EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL,
        COHERENT_REPEAT_COUNT,
        INVALIDATED_RESULT_RATIO,
        BACKTEST_ASSUMPTION_COUNT,
    }
)

_COMPILABLE_STATUSES = frozenset({"COMPILABLE", "SNAPSHOTTED"})
_NON_COMPILABLE_STATUSES = frozenset({"INCOMPLETE", "INCONSISTENT", "REJECTED", "FAILED_COMPILATION"})
_BACKTEST_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
_RULE_ORIGINS = frozenset({"SOURCE", "DEDUCTION", "DESIGN_CHOICE", "PARAMETER_TO_CALIBRATE", "USER_CONSTRAINT"})
_DECIMAL_SCALE = Decimal("0.000000000001")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_MUTABLE_REFERENCE_FRAGMENTS = ("/current", "/latest", ":latest", "latest", "current")
_PROFITABILITY_PROMISE_FRAGMENTS = ("garantie", "garanti", "promesse", "assuree", "assurée")


@dataclass(frozen=True)
class BenchmarkMetric:
    name: str
    value: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text(self.name, "metric_name"))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur metrique invalide"))
        object.__setattr__(self, "numerator", _required_non_negative_integer(self.numerator, "metric_numerator"))
        object.__setattr__(self, "denominator", _required_metric_denominator(self.denominator))


@dataclass(frozen=True)
class CountDistributionMetric:
    name: str
    counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text(self.name, "metric_name"))
        object.__setattr__(self, "counts", _required_count_mapping(self.counts, "counts"))


@dataclass(frozen=True)
class RatioDistributionMetric:
    name: str
    ratios: Mapping[str, str]
    counts: Mapping[str, int]
    denominator: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text(self.name, "metric_name"))
        object.__setattr__(self, "ratios", _required_ratio_mapping(self.ratios, "ratios"))
        object.__setattr__(self, "counts", _required_count_mapping(self.counts, "counts"))
        object.__setattr__(self, "denominator", _required_metric_denominator(self.denominator))


@dataclass(frozen=True)
class CalibrationProtocol:
    parameter_name: str
    domain: Mapping[str, Any]
    protocol_version: str
    out_of_sample_period: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameter_name", _required_text(self.parameter_name, "parameter_name"))
        object.__setattr__(self, "domain", _required_calibration_domain(self.domain))
        object.__setattr__(self, "protocol_version", _required_text(self.protocol_version, "protocole de calibration requis"))
        object.__setattr__(
            self,
            "out_of_sample_period",
            _required_out_of_sample_period(self.out_of_sample_period),
        )


@dataclass(frozen=True)
class StrategyEvaluationCase:
    case_id: str
    strategy_id: str
    strategy_version_id: str
    strategy_version: int
    compilation_status: str
    rejection_reasons: tuple[str, ...]
    rule_origins: tuple[str, ...]
    parameters_without_calibration_plan: tuple[str, ...]
    compatibility_conflicts: tuple[str, ...]
    metric_source: str

    def __init__(
        self,
        *,
        case_id: str,
        strategy_id: str,
        strategy_version_id: str,
        strategy_version: int,
        compilation_status: str,
        rejection_reasons: Sequence[str],
        rule_origins: Sequence[str],
        parameters_without_calibration_plan: Sequence[str],
        compatibility_conflicts: Sequence[str],
        metric_source: str,
    ) -> None:
        object.__setattr__(self, "case_id", _required_text(case_id, "case_id"))
        object.__setattr__(self, "strategy_id", _required_prefixed_text(strategy_id, "STRAT-", "strategy_id"))
        object.__setattr__(
            self,
            "strategy_version_id",
            _required_prefixed_text(strategy_version_id, "SVER-", "strategy_version_id"),
        )
        object.__setattr__(self, "strategy_version", _required_positive_integer(strategy_version, "strategy_version"))
        object.__setattr__(self, "compilation_status", _required_compilation_status(compilation_status))
        object.__setattr__(self, "rejection_reasons", _required_text_tuple(rejection_reasons, "rejection_reasons", allow_empty=True))
        object.__setattr__(self, "rule_origins", _required_rule_origins(rule_origins))
        object.__setattr__(
            self,
            "parameters_without_calibration_plan",
            _required_text_tuple(
                parameters_without_calibration_plan,
                "parameters_without_calibration_plan",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "compatibility_conflicts",
            _required_text_tuple(compatibility_conflicts, "compatibility_conflicts", allow_empty=True),
        )
        object.__setattr__(self, "metric_source", _required_metric_source(metric_source, expected="SD"))
        self._ensure_status_consistency()

    @property
    def compilable(self) -> bool:
        return self.compilation_status in _COMPILABLE_STATUSES

    def _ensure_status_consistency(self) -> None:
        if not self.compilable and len(self.rejection_reasons) == 0:
            raise ValueError("raison de rejet requise")


@dataclass(frozen=True)
class BacktestBenchmarkResult:
    experiment_id: str
    strategy_version_id: str
    data_snapshot_id: str
    period_start: str
    period_end: str
    universe: tuple[str, ...]
    cost_model: Mapping[str, str]
    assumptions: tuple[str, ...]
    calibration_protocols: tuple[CalibrationProtocol, ...]
    status: str
    metrics: Mapping[str, str]
    result_negative: bool
    failure_cause: str | None
    retained: bool
    cost_model_complete: bool
    repeat_coherent: bool
    invalidated_after_audit: bool
    profitability_verdict: str | None
    profitability_qualification: str | None
    result_hash: str
    metric_source: str

    def __init__(
        self,
        *,
        experiment_id: str,
        strategy_version_id: str,
        data_snapshot_id: str,
        period_start: str,
        period_end: str,
        universe: Sequence[str],
        cost_model: Mapping[str, Any],
        assumptions: Sequence[str],
        calibration_protocols: Sequence[CalibrationProtocol],
        status: str,
        metrics: Mapping[str, Any],
        result_negative: bool,
        failure_cause: str | None,
        retained: bool,
        cost_model_complete: bool,
        repeat_coherent: bool,
        invalidated_after_audit: bool,
        profitability_verdict: str | None,
        profitability_qualification: str | None,
        result_hash: str,
        metric_source: str,
    ) -> None:
        object.__setattr__(self, "experiment_id", _required_prefixed_text(experiment_id, "EXP-", "experiment_id"))
        object.__setattr__(
            self,
            "strategy_version_id",
            _required_prefixed_text(strategy_version_id, "SVER-", "strategy_version_id"),
        )
        parsed_data_snapshot_id = _required_prefixed_text(data_snapshot_id, "DATA-", "data_snapshot_id")
        _ensure_frozen_reference(parsed_data_snapshot_id)
        object.__setattr__(self, "data_snapshot_id", parsed_data_snapshot_id)
        object.__setattr__(self, "period_start", _required_date(period_start, "periode de backtest requise"))
        object.__setattr__(self, "period_end", _required_date(period_end, "periode de backtest requise"))
        if self.period_start > self.period_end:
            raise ValueError("periode de backtest incoherente")
        object.__setattr__(self, "universe", _required_text_tuple(universe, "univers de backtest requis", allow_empty=False))
        object.__setattr__(self, "cost_model", _required_cost_model(cost_model))
        object.__setattr__(self, "assumptions", _required_text_tuple(assumptions, "hypothese de backtest requise", allow_empty=False))
        object.__setattr__(self, "calibration_protocols", _required_calibration_protocols(calibration_protocols))
        object.__setattr__(self, "status", _required_backtest_status(status))
        object.__setattr__(self, "metrics", _required_metric_mapping(metrics))
        object.__setattr__(self, "result_negative", _required_bool(result_negative, "result_negative"))
        object.__setattr__(self, "failure_cause", _optional_text(failure_cause, "failure_cause"))
        object.__setattr__(self, "retained", _required_bool(retained, "retained"))
        object.__setattr__(self, "cost_model_complete", _required_bool(cost_model_complete, "cost_model_complete"))
        object.__setattr__(self, "repeat_coherent", _required_bool(repeat_coherent, "repeat_coherent"))
        object.__setattr__(self, "invalidated_after_audit", _required_bool(invalidated_after_audit, "invalidated_after_audit"))
        object.__setattr__(self, "profitability_verdict", _optional_text(profitability_verdict, "profitability_verdict"))
        object.__setattr__(
            self,
            "profitability_qualification",
            _optional_text(profitability_qualification, "profitability_qualification"),
        )
        object.__setattr__(self, "result_hash", _required_hash(result_hash, "result_hash"))
        object.__setattr__(self, "metric_source", _required_metric_source(metric_source, expected="EX"))
        self._ensure_consistency()

    def with_profitability_verdict(
        self,
        profitability_verdict: str | None,
        profitability_qualification: str | None,
    ) -> "BacktestBenchmarkResult":
        return replace(
            self,
            profitability_verdict=profitability_verdict,
            profitability_qualification=profitability_qualification,
        )

    def _ensure_consistency(self) -> None:
        if self.status == "FAILED" and self.failure_cause is None:
            raise ValueError("failure_cause requis")
        if self.status != "FAILED" and self.failure_cause is not None:
            raise ValueError("failure_cause incompatible")
        if self.profitability_verdict is not None and self.profitability_qualification is None:
            raise ValueError("qualification de rentabilite requise")
        if self.profitability_verdict is not None:
            normalized_verdict = _without_accents(self.profitability_verdict).lower()
            normalized_qualification = _without_accents(self.profitability_qualification or "").lower()
            if any(fragment in normalized_verdict for fragment in _PROFITABILITY_PROMISE_FRAGMENTS):
                raise ValueError("promesse de rentabilite interdite")
            if "pilote" not in normalized_qualification:
                raise ValueError("qualification de rentabilite requise")


@dataclass(frozen=True)
class BacktestBenchmarkRun:
    run_id: str
    policy_version: str
    measured_at: str
    strategy_case_count: int
    result_count: int
    sd_metrics: Mapping[str, Any]
    ex_metrics: Mapping[str, Any]
    strategy_cases: tuple[StrategyEvaluationCase, ...]
    results: tuple[BacktestBenchmarkResult, ...]
    results_by_experiment_id: Mapping[str, BacktestBenchmarkResult]
    coherent_repeat_count: int


@dataclass(frozen=True)
class StrategyDesignBenchmark:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def measure(
        self,
        *,
        run_id: str,
        strategy_cases: Sequence[StrategyEvaluationCase],
        backtest_results: Sequence[BacktestBenchmarkResult],
        measured_at: str,
        metric_source: str = "SD_EX",
    ) -> BacktestBenchmarkRun:
        _ensure_not_llm_metric_source(metric_source)
        parsed_strategy_cases = _required_strategy_cases(strategy_cases)
        parsed_results = _required_backtest_results(backtest_results)
        _ensure_results_reference_strategy_cases(parsed_strategy_cases, parsed_results)
        results_by_experiment_id = {result.experiment_id: result for result in parsed_results}
        sd_metrics = _sd_metrics(parsed_strategy_cases)
        ex_metrics = _ex_metrics(parsed_results)
        return BacktestBenchmarkRun(
            run_id=_required_text(run_id, "run_id"),
            policy_version=self.policy_version,
            measured_at=_required_utc_instant(measured_at, "measured_at"),
            strategy_case_count=len(parsed_strategy_cases),
            result_count=len(parsed_results),
            sd_metrics=sd_metrics,
            ex_metrics=ex_metrics,
            strategy_cases=parsed_strategy_cases,
            results=parsed_results,
            results_by_experiment_id=results_by_experiment_id,
            coherent_repeat_count=ex_metrics[COHERENT_REPEAT_COUNT].numerator,
        )


def _sd_metrics(cases: tuple[StrategyEvaluationCase, ...]) -> Mapping[str, Any]:
    rule_origin_counts = _counts_for(value for case in cases for value in case.rule_origins)
    sd_metrics = {
        STRATEGY_COMPILABLE_RATE: _ratio_metric(
            STRATEGY_COMPILABLE_RATE,
            sum(1 for case in cases if case.compilable),
            len(cases),
        ),
        STRATEGY_REJECTION_REASON_DISTRIBUTION: CountDistributionMetric(
            STRATEGY_REJECTION_REASON_DISTRIBUTION,
            _counts_for(reason for case in cases for reason in case.rejection_reasons),
        ),
        STRATEGY_RULE_ORIGIN_RATIO: RatioDistributionMetric(
            STRATEGY_RULE_ORIGIN_RATIO,
            _ratio_distribution(rule_origin_counts),
            rule_origin_counts,
            sum(rule_origin_counts.values()),
        ),
        STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL: _count_metric(
            STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL,
            sum(len(case.parameters_without_calibration_plan) for case in cases),
        ),
        STRATEGY_COMPATIBILITY_CONFLICT_TOTAL: CountDistributionMetric(
            STRATEGY_COMPATIBILITY_CONFLICT_TOTAL,
            _counts_for(conflict for case in cases for conflict in case.compatibility_conflicts),
        ),
        STRATEGY_VERSION_COUNT: CountDistributionMetric(
            STRATEGY_VERSION_COUNT,
            _counts_for(case.strategy_id for case in cases),
        ),
    }
    _ensure_metric_keys(sd_metrics, REQUIRED_SD_METRICS, "metrique SD absente")
    return sd_metrics


def _ex_metrics(results: tuple[BacktestBenchmarkResult, ...]) -> Mapping[str, Any]:
    negative_results = tuple(result for result in results if result.result_negative or result.status == "FAILED")
    ex_metrics = {
        EXPERIMENT_REPRODUCIBLE_RATE: _ratio_metric(
            EXPERIMENT_REPRODUCIBLE_RATE,
            sum(1 for result in results if result.repeat_coherent),
            len(results),
        ),
        EXPERIMENT_FAILURE_RATE_BY_CAUSE: CountDistributionMetric(
            EXPERIMENT_FAILURE_RATE_BY_CAUSE,
            _counts_for(result.failure_cause for result in results if result.failure_cause is not None),
        ),
        NEGATIVE_EXPERIMENT_RETENTION_RATIO: _ratio_metric(
            NEGATIVE_EXPERIMENT_RETENTION_RATIO,
            sum(1 for result in negative_results if result.retained),
            len(negative_results) if negative_results else len(results),
        ),
        EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL: _count_metric(
            EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL,
            sum(1 for result in results if not result.cost_model_complete),
        ),
        COHERENT_REPEAT_COUNT: _count_metric(
            COHERENT_REPEAT_COUNT,
            sum(1 for result in results if result.repeat_coherent),
        ),
        INVALIDATED_RESULT_RATIO: _ratio_metric(
            INVALIDATED_RESULT_RATIO,
            sum(1 for result in results if result.invalidated_after_audit),
            len(results),
        ),
        BACKTEST_ASSUMPTION_COUNT: _count_metric(
            BACKTEST_ASSUMPTION_COUNT,
            sum(len(result.assumptions) for result in results),
        ),
    }
    _ensure_metric_keys(ex_metrics, REQUIRED_EX_METRICS, "metrique EX absente")
    return ex_metrics


def _required_strategy_cases(values: Sequence[StrategyEvaluationCase]) -> tuple[StrategyEvaluationCase, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("strategy_cases invalides")
    cases = tuple(values)
    if len(cases) == 0:
        raise ValueError("strategy_cases absentes")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, StrategyEvaluationCase):
            raise ValueError("StrategyEvaluationCase requis")
        if case.case_id in case_ids:
            raise ValueError("strategie dupliquee dans le benchmark")
        case_ids.add(case.case_id)
    return cases


def _required_backtest_results(values: Sequence[BacktestBenchmarkResult]) -> tuple[BacktestBenchmarkResult, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("backtest_results invalides")
    results = tuple(values)
    if len(results) == 0:
        raise ValueError("backtest_results absents")
    experiment_ids: set[str] = set()
    for result in results:
        if not isinstance(result, BacktestBenchmarkResult):
            raise ValueError("BacktestBenchmarkResult requis")
        if result.experiment_id in experiment_ids:
            raise ValueError("resultat duplique dans le benchmark")
        experiment_ids.add(result.experiment_id)
    return results


def _ensure_results_reference_strategy_cases(
    strategy_cases: tuple[StrategyEvaluationCase, ...],
    results: tuple[BacktestBenchmarkResult, ...],
) -> None:
    strategy_version_ids = {case.strategy_version_id for case in strategy_cases}
    for result in results:
        if result.strategy_version_id not in strategy_version_ids:
            raise ValueError("resultat de strategie absente du benchmark SD")


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "policy_version")
    if not text.startswith("StrategyExperimentBenchmarkPolicy-"):
        raise ValueError("version de politique incoherente")
    return text


def _required_compilation_status(value: Any) -> str:
    text = _required_text(value, "compilation_status")
    if text not in _COMPILABLE_STATUSES and text not in _NON_COMPILABLE_STATUSES:
        raise ValueError("compilation_status invalide")
    return text


def _required_backtest_status(value: Any) -> str:
    text = _required_text(value, "status")
    if text not in _BACKTEST_STATUSES:
        raise ValueError("status backtest invalide")
    return text


def _required_rule_origins(values: Sequence[str]) -> tuple[str, ...]:
    origins = _required_text_tuple(values, "origine de regle requise", allow_empty=False)
    for origin in origins:
        if origin not in _RULE_ORIGINS:
            raise ValueError("origine de regle invalide")
    return origins


def _required_metric_source(value: Any, *, expected: str) -> str:
    text = _required_text(value, "metric_source")
    if text == "LLM":
        raise ValueError("source metrique LLM interdite")
    if text != expected:
        raise ValueError("source metrique invalide")
    return text


def _ensure_not_llm_metric_source(value: Any) -> None:
    text = _required_text(value, "metric_source")
    if text == "LLM":
        raise ValueError("source metrique LLM interdite")
    if text != "SD_EX":
        raise ValueError("source metrique invalide")


def _required_calibration_domain(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError("domaine de calibration requis")
    required_fields = {"lower_bound", "upper_bound", "unit"}
    missing = sorted(required_fields.difference(value.keys()))
    if missing:
        raise ValueError("domaine de calibration requis")
    lower_bound = _decimal(value["lower_bound"], "domaine de calibration requis")
    upper_bound = _decimal(value["upper_bound"], "domaine de calibration requis")
    if lower_bound >= upper_bound:
        raise ValueError("domaine de calibration requis")
    return {
        "lower_bound": _format_decimal(lower_bound),
        "upper_bound": _format_decimal(upper_bound),
        "unit": _required_text(value["unit"], "unit"),
    }


def _required_out_of_sample_period(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("periode hors echantillon requise")
    if "start" not in value or "end" not in value:
        raise ValueError("periode hors echantillon requise")
    start = _required_date(value["start"], "periode hors echantillon requise")
    end = _required_date(value["end"], "periode hors echantillon requise")
    if start > end:
        raise ValueError("periode hors echantillon incoherente")
    return {"start": start, "end": end}


def _required_calibration_protocols(values: Sequence[CalibrationProtocol]) -> tuple[CalibrationProtocol, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("protocole de calibration requis")
    protocols = tuple(values)
    if len(protocols) == 0:
        raise ValueError("protocole de calibration requis")
    parameter_names: set[str] = set()
    for protocol in protocols:
        if not isinstance(protocol, CalibrationProtocol):
            raise ValueError("CalibrationProtocol requis")
        if protocol.parameter_name in parameter_names:
            raise ValueError("protocole de calibration duplique")
        parameter_names.add(protocol.parameter_name)
    return protocols


def _required_cost_model(value: Mapping[str, Any]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("modele de couts complet requis")
    required_fields = ("commission_bps", "slippage_bps", "currency")
    if any(field_name not in value for field_name in required_fields):
        raise ValueError("modele de couts complet requis")
    return {
        "commission_bps": _required_decimal_text(value["commission_bps"], "modele de couts complet requis"),
        "slippage_bps": _required_decimal_text(value["slippage_bps"], "modele de couts complet requis"),
        "currency": _required_text(value["currency"], "currency"),
    }


def _required_metric_mapping(value: Mapping[str, Any]) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError("metriques backtest requises")
    return {
        _required_text(metric_name, "metric_name"): _required_decimal_text(metric_value, "valeur metrique invalide")
        for metric_name, metric_value in value.items()
    }


def _required_count_mapping(value: Mapping[str, int], field_name: str) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return {
        _required_text(key, field_name): _required_non_negative_integer(count, field_name)
        for key, count in sorted(value.items())
    }


def _required_ratio_mapping(value: Mapping[str, str], field_name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return {
        _required_text(key, field_name): _required_decimal_text(ratio, "valeur metrique invalide")
        for key, ratio in sorted(value.items())
    }


def _counts_for(values: Any) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = _required_text(value, "valeur distribution")
        counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _ratio_distribution(counts: Mapping[str, int]) -> Mapping[str, str]:
    denominator = sum(counts.values())
    if denominator <= 0:
        raise ValueError("dénominateur métrique invalide")
    return {key: _metric_value(count, denominator) for key, count in sorted(counts.items())}


def _ratio_metric(metric_name: str, numerator: int, denominator: int) -> BenchmarkMetric:
    return BenchmarkMetric(metric_name, _metric_value(numerator, denominator), numerator, denominator)


def _count_metric(metric_name: str, count: int) -> BenchmarkMetric:
    parsed_count = _required_non_negative_integer(count, metric_name)
    return BenchmarkMetric(metric_name, _format_decimal(Decimal(parsed_count)), parsed_count, 1)


def _ensure_metric_keys(metrics: Mapping[str, Any], required: frozenset[str], message_prefix: str) -> None:
    missing = sorted(required.difference(metrics.keys()))
    if missing:
        raise ValueError(f"{message_prefix}: {', '.join(missing)}")


def _metric_value(numerator: int, denominator: int) -> str:
    parsed_numerator = _required_non_negative_integer(numerator, "metric_numerator")
    parsed_denominator = _required_metric_denominator(denominator)
    return _format_decimal(Decimal(parsed_numerator) / Decimal(parsed_denominator))


def _required_text_tuple(values: Sequence[str], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(field_name)
    parsed = tuple(_required_text(value, field_name) for value in values)
    if len(parsed) == 0 and not allow_empty:
        raise ValueError(field_name)
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} duplique")
    return parsed


def _required_prefixed_text(value: Any, prefix: str, field_name: str) -> str:
    text = _required_text(value, field_name)
    if not text.startswith(prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booleen")
    return value


def _required_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_metric_denominator(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("dénominateur métrique invalide")
    return value


def _required_date(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise ValueError(field_name)
    datetime.strptime(text, "%Y-%m-%d")
    return text


def _required_utc_instant(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _required_hash(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    if _HASH_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text.lower()


def _ensure_frozen_reference(value: str) -> None:
    normalized = value.lower()
    if any(fragment in normalized for fragment in _MUTABLE_REFERENCE_FRAGMENTS):
        raise ValueError("entrees figees requises")


def _required_decimal_text(value: Any, error_message: str) -> str:
    return _format_decimal(_decimal(value, error_message))


def _decimal(value: Any, error_message: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(error_message)
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(error_message) from exc
    if not decimal_value.is_finite():
        raise ValueError(error_message)
    return decimal_value


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN):.12f}"


def _without_accents(value: str) -> str:
    return (
        value.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ù", "u")
        .replace("ç", "c")
    )


__all__ = [
    "BACKTEST_ASSUMPTION_COUNT",
    "COHERENT_REPEAT_COUNT",
    "EXPERIMENT_FAILURE_RATE_BY_CAUSE",
    "EXPERIMENT_REPRODUCIBLE_RATE",
    "EXPERIMENT_WITHOUT_COMPLETE_COST_MODEL_TOTAL",
    "INVALIDATED_RESULT_RATIO",
    "NEGATIVE_EXPERIMENT_RETENTION_RATIO",
    "REQUIRED_EX_METRICS",
    "REQUIRED_SD_METRICS",
    "STRATEGY_COMPATIBILITY_CONFLICT_TOTAL",
    "STRATEGY_COMPILABLE_RATE",
    "STRATEGY_PARAMETER_WITHOUT_CALIBRATION_PLAN_TOTAL",
    "STRATEGY_REJECTION_REASON_DISTRIBUTION",
    "STRATEGY_RULE_ORIGIN_RATIO",
    "STRATEGY_VERSION_COUNT",
    "BacktestBenchmarkResult",
    "BacktestBenchmarkRun",
    "BenchmarkMetric",
    "CalibrationProtocol",
    "CountDistributionMetric",
    "RatioDistributionMetric",
    "StrategyDesignBenchmark",
    "StrategyEvaluationCase",
]
