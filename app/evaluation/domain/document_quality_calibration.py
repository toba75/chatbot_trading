"""Calibration documentaire M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.evaluation.domain.document_route_benchmark import (
    REQUIRED_DOCUMENT_ROUTES,
    REQUIRED_ROUTE_METRICS,
    RouteBenchmarkResult,
    RouteBenchmarkRun,
)


SOURCE_BENCHMARK_RESULT = "BENCHMARK_RESULT"
SOURCE_DEVELOPMENT_VALUE = "DEVELOPMENT_VALUE"
THRESHOLD_MINIMUM = "MINIMUM"
THRESHOLD_MAXIMUM = "MAXIMUM"
CALIBRATION_ACCEPTED = "ACCEPTED"
CALIBRATION_REJECTED = "REJECTED"
V1_GAP_BLOCKING = "BLOCKING"

_EXPECTED_SOURCE_KINDS = frozenset({SOURCE_BENCHMARK_RESULT})
_EXPECTED_OPERATORS = frozenset({THRESHOLD_MINIMUM, THRESHOLD_MAXIMUM})
_EXPECTED_DIAGNOSTIC_STATUSES = frozenset({CALIBRATION_ACCEPTED, CALIBRATION_REJECTED})
_EXPECTED_GAP_STATUSES = frozenset({V1_GAP_BLOCKING})
_POLICY_VERSION_PREFIX = "DocumentQualityCalibrationPolicy-"


@dataclass(frozen=True)
class DocumentQualityThreshold:
    threshold_id: str
    policy_version: str
    source_kind: str
    benchmark_result_id: str
    corpus_id: str
    route_name: str
    metric_name: str
    operator: str
    value: str
    justification_by_stratum: Mapping[str, str]
    v1_criterion_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "threshold_id", _required_text_value(self.threshold_id, "threshold_id"))
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))
        object.__setattr__(self, "source_kind", _required_source_kind(self.source_kind))
        object.__setattr__(self, "benchmark_result_id", _required_text_value(self.benchmark_result_id, "benchmark source absent"))
        object.__setattr__(self, "corpus_id", _required_text_value(self.corpus_id, "corpus_id"))
        object.__setattr__(self, "route_name", _required_route_name(self.route_name))
        object.__setattr__(self, "metric_name", _required_metric_name(self.metric_name))
        object.__setattr__(self, "operator", _required_operator(self.operator))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur de seuil invalide"))
        object.__setattr__(
            self,
            "justification_by_stratum",
            _required_strata_justifications(self.justification_by_stratum),
        )
        object.__setattr__(self, "v1_criterion_id", _required_text_value(self.v1_criterion_id, "v1_criterion_id"))


@dataclass(frozen=True)
class DocumentQualityThresholdReport:
    report_id: str
    policy_version: str
    benchmark_run_id: str
    corpus_id: str
    thresholds: tuple[DocumentQualityThreshold, ...]

    def __init__(
        self,
        *,
        report_id: str,
        policy_version: str,
        benchmark_run_id: str,
        corpus_id: str,
        thresholds: Sequence[DocumentQualityThreshold],
    ) -> None:
        object.__setattr__(self, "report_id", _required_text_value(report_id, "report_id"))
        object.__setattr__(self, "policy_version", _required_policy_version(policy_version))
        object.__setattr__(self, "benchmark_run_id", _required_text_value(benchmark_run_id, "benchmark_run_id"))
        object.__setattr__(self, "corpus_id", _required_text_value(corpus_id, "corpus_id"))
        threshold_tuple = _required_threshold_tuple(thresholds)
        for threshold in threshold_tuple:
            if threshold.policy_version != policy_version:
                raise ValueError("version de politique incoherente")
            if threshold.corpus_id != corpus_id:
                raise ValueError("corpus seuil incoherent")
        object.__setattr__(self, "thresholds", threshold_tuple)


@dataclass(frozen=True)
class DocumentRouteCalibrationDiagnostic:
    route_name: str
    benchmark_result_id: str
    status: str
    blocking_metrics: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_name", _required_route_name(self.route_name))
        object.__setattr__(self, "benchmark_result_id", _required_text_value(self.benchmark_result_id, "benchmark_result_id"))
        object.__setattr__(self, "status", _required_status(self.status, _EXPECTED_DIAGNOSTIC_STATUSES, "statut diagnostic"))
        object.__setattr__(self, "blocking_metrics", _required_metric_tuple(self.blocking_metrics))
        object.__setattr__(self, "reason", _required_text_value(self.reason, "reason"))


@dataclass(frozen=True)
class DocumentV1Gap:
    gap_id: str
    policy_version: str
    corpus_id: str
    route_name: str
    metric_name: str
    benchmark_result_id: str
    threshold_id: str
    v1_criterion_id: str
    stratum: str
    status: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "gap_id", _required_text_value(self.gap_id, "gap_id"))
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))
        object.__setattr__(self, "corpus_id", _required_text_value(self.corpus_id, "corpus_id"))
        object.__setattr__(self, "route_name", _required_route_name(self.route_name))
        object.__setattr__(self, "metric_name", _required_metric_name(self.metric_name))
        object.__setattr__(self, "benchmark_result_id", _required_text_value(self.benchmark_result_id, "benchmark_result_id"))
        object.__setattr__(self, "threshold_id", _required_text_value(self.threshold_id, "threshold_id"))
        object.__setattr__(self, "v1_criterion_id", _required_text_value(self.v1_criterion_id, "v1_criterion_id"))
        object.__setattr__(self, "stratum", _required_text_value(self.stratum, "stratum"))
        object.__setattr__(self, "status", _required_status(self.status, _EXPECTED_GAP_STATUSES, "statut ecart V1"))
        object.__setattr__(self, "reason", _required_text_value(self.reason, "reason"))


@dataclass(frozen=True)
class CalibrationDecision:
    decision_id: str
    policy_version: str
    benchmark_run_id: str
    corpus_id: str
    threshold_report: DocumentQualityThresholdReport
    route_diagnostics: tuple[DocumentRouteCalibrationDiagnostic, ...]
    v1_gaps: tuple[DocumentV1Gap, ...]
    status: str

    def __init__(
        self,
        *,
        decision_id: str,
        policy_version: str,
        benchmark_run_id: str,
        corpus_id: str,
        threshold_report: DocumentQualityThresholdReport,
        route_diagnostics: Sequence[DocumentRouteCalibrationDiagnostic],
        v1_gaps: Sequence[DocumentV1Gap],
        status: str,
    ) -> None:
        object.__setattr__(self, "decision_id", _required_text_value(decision_id, "decision_id"))
        object.__setattr__(self, "policy_version", _required_policy_version(policy_version))
        object.__setattr__(self, "benchmark_run_id", _required_text_value(benchmark_run_id, "benchmark_run_id"))
        object.__setattr__(self, "corpus_id", _required_text_value(corpus_id, "corpus_id"))
        if not isinstance(threshold_report, DocumentQualityThresholdReport):
            raise ValueError("rapport de seuils SP requis")
        object.__setattr__(self, "threshold_report", threshold_report)
        object.__setattr__(self, "route_diagnostics", _required_diagnostic_tuple(route_diagnostics))
        object.__setattr__(self, "v1_gaps", _required_gap_tuple(v1_gaps))
        object.__setattr__(self, "status", _required_status(status, _EXPECTED_DIAGNOSTIC_STATUSES, "statut decision"))


@dataclass(frozen=True)
class DocumentQualityCalibrationPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def calibrate(
        self,
        *,
        decision_id: str,
        benchmark_run: RouteBenchmarkRun,
        threshold_report: DocumentQualityThresholdReport,
    ) -> CalibrationDecision:
        _required_text_value(decision_id, "decision_id")
        if not isinstance(benchmark_run, RouteBenchmarkRun):
            raise ValueError("RouteBenchmarkRun requis")
        if not isinstance(threshold_report, DocumentQualityThresholdReport):
            raise ValueError("rapport de seuils SP requis")
        if threshold_report.policy_version != self.policy_version:
            raise ValueError("version de politique incoherente")
        if threshold_report.benchmark_run_id != benchmark_run.run_id:
            raise ValueError("benchmark source incoherent")
        if threshold_report.corpus_id != benchmark_run.corpus_id:
            raise ValueError("corpus seuil incoherent")

        results_by_id = _results_by_id(benchmark_run.results)
        thresholds_by_route = _thresholds_by_route(threshold_report.thresholds)
        route_diagnostics: list[DocumentRouteCalibrationDiagnostic] = []
        v1_gaps: list[DocumentV1Gap] = []

        for route_name in sorted(thresholds_by_route):
            thresholds = thresholds_by_route[route_name]
            route_gaps = self._evaluate_route_thresholds(
                thresholds=thresholds,
                results_by_id=results_by_id,
                corpus_id=benchmark_run.corpus_id,
            )
            v1_gaps.extend(route_gaps)
            blocking_metrics = tuple(sorted({gap.metric_name for gap in route_gaps}))
            status = CALIBRATION_REJECTED if blocking_metrics else CALIBRATION_ACCEPTED
            route_diagnostics.append(
                DocumentRouteCalibrationDiagnostic(
                    route_name=route_name,
                    benchmark_result_id=thresholds[0].benchmark_result_id,
                    status=status,
                    blocking_metrics=blocking_metrics,
                    reason=_diagnostic_reason(status, blocking_metrics),
                )
            )

        decision_status = CALIBRATION_REJECTED if v1_gaps else CALIBRATION_ACCEPTED
        return CalibrationDecision(
            decision_id=decision_id,
            policy_version=self.policy_version,
            benchmark_run_id=benchmark_run.run_id,
            corpus_id=benchmark_run.corpus_id,
            threshold_report=threshold_report,
            route_diagnostics=tuple(route_diagnostics),
            v1_gaps=tuple(v1_gaps),
            status=decision_status,
        )

    def _evaluate_route_thresholds(
        self,
        *,
        thresholds: Sequence[DocumentQualityThreshold],
        results_by_id: Mapping[str, RouteBenchmarkResult],
        corpus_id: str,
    ) -> tuple[DocumentV1Gap, ...]:
        gaps: list[DocumentV1Gap] = []
        for threshold in thresholds:
            result = results_by_id.get(threshold.benchmark_result_id)
            if result is None:
                raise ValueError("benchmark source absent")
            if result.corpus_id != corpus_id or threshold.corpus_id != corpus_id:
                raise ValueError("corpus seuil incoherent")
            if result.route_name != threshold.route_name:
                raise ValueError("route seuil incoherente")
            if set(threshold.justification_by_stratum) != set(result.strata_details):
                raise ValueError("justification par strate absente")
            route_gaps = _evaluate_route_metric(threshold, result)
            strata_gaps: list[DocumentV1Gap] = []
            for stratum, strata_result in sorted(result.strata_details.items()):
                strata_gaps.extend(_evaluate_stratum_metric(threshold, result, stratum, strata_result.metrics))
            missing_route_gaps = tuple(gap for gap in route_gaps if gap.reason.startswith("metrique documentaire absente"))
            threshold_route_gaps = tuple(gap for gap in route_gaps if gap not in missing_route_gaps)
            gaps.extend(missing_route_gaps)
            if not strata_gaps:
                gaps.extend(threshold_route_gaps)
            gaps.extend(strata_gaps)
        return tuple(gaps)


def _evaluate_route_metric(threshold: DocumentQualityThreshold, result: RouteBenchmarkResult) -> tuple[DocumentV1Gap, ...]:
    metric = result.metrics.get(threshold.metric_name)
    if metric is None:
        return (
            _gap(
                threshold=threshold,
                stratum="ROUTE",
                reason=f"metrique documentaire absente: {threshold.metric_name}",
            ),
        )
    if _metric_satisfies_threshold(metric.value, threshold):
        return ()
    return (
        _gap(
            threshold=threshold,
            stratum="ROUTE",
            reason=f"route sous seuil: {threshold.metric_name}={metric.value}",
        ),
    )


def _evaluate_stratum_metric(
    threshold: DocumentQualityThreshold,
    result: RouteBenchmarkResult,
    stratum: str,
    metrics: Mapping[str, Any],
) -> tuple[DocumentV1Gap, ...]:
    metric = metrics.get(threshold.metric_name)
    if metric is None:
        return (
            _gap(
                threshold=threshold,
                stratum=stratum,
                reason=f"metrique documentaire absente pour strate {stratum}: {threshold.metric_name}",
            ),
        )
    if _metric_satisfies_threshold(metric.value, threshold):
        return ()
    return (
        _gap(
            threshold=threshold,
            stratum=stratum,
            reason=f"strate sous seuil {stratum}: {threshold.metric_name}={metric.value}",
        ),
    )


def _gap(*, threshold: DocumentQualityThreshold, stratum: str, reason: str) -> DocumentV1Gap:
    return DocumentV1Gap(
        gap_id=f"GAP-M012-{threshold.route_name}-{threshold.metric_name}-{stratum}",
        policy_version=threshold.policy_version,
        corpus_id=threshold.corpus_id,
        route_name=threshold.route_name,
        metric_name=threshold.metric_name,
        benchmark_result_id=threshold.benchmark_result_id,
        threshold_id=threshold.threshold_id,
        v1_criterion_id=threshold.v1_criterion_id,
        stratum=stratum,
        status=V1_GAP_BLOCKING,
        reason=reason,
    )


def _metric_satisfies_threshold(metric_value: str, threshold: DocumentQualityThreshold) -> bool:
    measured = _decimal(metric_value, "valeur metrique invalide")
    threshold_value = _decimal(threshold.value, "valeur de seuil invalide")
    if threshold.operator == THRESHOLD_MINIMUM:
        return measured >= threshold_value
    if threshold.operator == THRESHOLD_MAXIMUM:
        return measured <= threshold_value
    raise ValueError("operateur de seuil inconnu")


def _diagnostic_reason(status: str, blocking_metrics: Sequence[str]) -> str:
    if status == CALIBRATION_ACCEPTED:
        return "route conforme aux seuils calibres"
    return "route refusee par seuil documentaire: " + ", ".join(blocking_metrics)


def _results_by_id(results: Sequence[RouteBenchmarkResult]) -> Mapping[str, RouteBenchmarkResult]:
    results_by_id: dict[str, RouteBenchmarkResult] = {}
    for result in results:
        if not isinstance(result, RouteBenchmarkResult):
            raise ValueError("RouteBenchmarkResult requis")
        if result.result_id in results_by_id:
            raise ValueError("benchmark source duplique")
        results_by_id[result.result_id] = result
    if not results_by_id:
        raise ValueError("benchmark source absent")
    return results_by_id


def _thresholds_by_route(thresholds: Sequence[DocumentQualityThreshold]) -> Mapping[str, tuple[DocumentQualityThreshold, ...]]:
    grouped: dict[str, list[DocumentQualityThreshold]] = {}
    threshold_ids: set[str] = set()
    for threshold in thresholds:
        if threshold.threshold_id in threshold_ids:
            raise ValueError("seuil documentaire duplique")
        threshold_ids.add(threshold.threshold_id)
        grouped.setdefault(threshold.route_name, []).append(threshold)
    return {route_name: tuple(route_thresholds) for route_name, route_thresholds in grouped.items()}


def _required_threshold_tuple(values: Sequence[DocumentQualityThreshold]) -> tuple[DocumentQualityThreshold, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("seuils documentaires invalides")
    thresholds = tuple(values)
    if len(thresholds) == 0:
        raise ValueError("seuil documentaire absent")
    for threshold in thresholds:
        if not isinstance(threshold, DocumentQualityThreshold):
            raise ValueError("DocumentQualityThreshold requis")
    return thresholds


def _required_diagnostic_tuple(
    values: Sequence[DocumentRouteCalibrationDiagnostic],
) -> tuple[DocumentRouteCalibrationDiagnostic, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("diagnostics de route invalides")
    diagnostics = tuple(values)
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, DocumentRouteCalibrationDiagnostic):
            raise ValueError("DocumentRouteCalibrationDiagnostic requis")
    return diagnostics


def _required_gap_tuple(values: Sequence[DocumentV1Gap]) -> tuple[DocumentV1Gap, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("ecarts V1 invalides")
    gaps = tuple(values)
    for gap in gaps:
        if not isinstance(gap, DocumentV1Gap):
            raise ValueError("DocumentV1Gap requis")
    return gaps


def _required_metric_tuple(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("metriques bloquantes invalides")
    return tuple(_required_metric_name(value) for value in values)


def _required_strata_justifications(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise ValueError("justification par strate absente")
    if len(values) < 2:
        raise ValueError("justification par strate absente")
    normalized: dict[str, str] = {}
    for stratum, justification in values.items():
        normalized[_required_text_value(stratum, "stratum")] = _required_text_value(justification, "justification")
    return normalized


def _required_policy_version(value: Any) -> str:
    text_value = _required_text_value(value, "policy_version")
    if not text_value.startswith(_POLICY_VERSION_PREFIX):
        raise ValueError("version de politique incoherente")
    return text_value


def _required_source_kind(value: Any) -> str:
    text_value = _required_text_value(value, "source_kind")
    if text_value == SOURCE_DEVELOPMENT_VALUE:
        raise ValueError("valeur de developpement non promouvable")
    if text_value not in _EXPECTED_SOURCE_KINDS:
        raise ValueError("source de seuil inconnue")
    return text_value


def _required_route_name(value: Any) -> str:
    text_value = _required_text_value(value, "route_name")
    if text_value not in REQUIRED_DOCUMENT_ROUTES:
        raise ValueError(f"route documentaire inconnue: {text_value}")
    return text_value


def _required_metric_name(value: Any) -> str:
    text_value = _required_text_value(value, "metric_name")
    if text_value not in REQUIRED_ROUTE_METRICS:
        raise ValueError(f"metrique documentaire inconnue: {text_value}")
    return text_value


def _required_operator(value: Any) -> str:
    text_value = _required_text_value(value, "operator")
    if text_value not in _EXPECTED_OPERATORS:
        raise ValueError("operateur de seuil inconnu")
    return text_value


def _required_status(value: Any, expected_values: frozenset[str], label: str) -> str:
    text_value = _required_text_value(value, label)
    if text_value not in expected_values:
        raise ValueError(f"{label} inconnu")
    return text_value


def _required_decimal_text(value: Any, error_message: str) -> str:
    return f"{_decimal(value, error_message):.12f}"


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


def _required_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "CALIBRATION_ACCEPTED",
    "CALIBRATION_REJECTED",
    "CalibrationDecision",
    "DocumentQualityCalibrationPolicy",
    "DocumentQualityThreshold",
    "DocumentQualityThresholdReport",
    "DocumentRouteCalibrationDiagnostic",
    "DocumentV1Gap",
    "SOURCE_BENCHMARK_RESULT",
    "SOURCE_DEVELOPMENT_VALUE",
    "THRESHOLD_MAXIMUM",
    "THRESHOLD_MINIMUM",
    "V1_GAP_BLOCKING",
]
