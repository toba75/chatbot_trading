"""Benchmark du LLM principal par le chemin réel M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import json
from typing import Any


CHECKPOINT_NVIDIA_GEMMA = "nvidia/Gemma-4-31B-IT-NVFP4"
CHECKPOINT_YCWTG_GEMMA = "YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ"
CHECKPOINT_GOOGLE_GEMMA = "google/gemma-4-31B-it-qat-w4a16-ct"
REQUIRED_LLM_CHECKPOINTS = (
    CHECKPOINT_NVIDIA_GEMMA,
    CHECKPOINT_YCWTG_GEMMA,
    CHECKPOINT_GOOGLE_GEMMA,
)

OFFICIAL_CHECKPOINT_ORIGIN = "OFFICIAL"
COMMUNITY_CHECKPOINT_ORIGIN = "COMMUNITY"
_EXPECTED_ORIGIN_BY_CHECKPOINT = {
    CHECKPOINT_NVIDIA_GEMMA: OFFICIAL_CHECKPOINT_ORIGIN,
    CHECKPOINT_YCWTG_GEMMA: COMMUNITY_CHECKPOINT_ORIGIN,
    CHECKPOINT_GOOGLE_GEMMA: OFFICIAL_CHECKPOINT_ORIGIN,
}

LLM_TASK_JSON_VALID = "json_valide"
LLM_TASK_ATOMIC_EXTRACTION = "extraction_atomique"
LLM_TASK_NEGATION_PRESERVATION = "conservation_negations"
LLM_TASK_NUMBER_ACCURACY = "exactitude_nombres"
LLM_TASK_APPLICATION_CONDITIONS = "conditions_application"
LLM_TASK_LIMITS = "limites"
LLM_TASK_ENTAILMENT = "entailment"
LLM_TASK_CONTRADICTION = "contradiction"
LLM_TASK_FR_EN_SYNTHESIS = "synthese_fr_en"
LLM_TASK_TOOL_CALLING = "tool_calling"
LLM_TASK_CITATIONS = "citations"
REQUIRED_LLM_TASKS = (
    LLM_TASK_JSON_VALID,
    LLM_TASK_ATOMIC_EXTRACTION,
    LLM_TASK_NEGATION_PRESERVATION,
    LLM_TASK_NUMBER_ACCURACY,
    LLM_TASK_APPLICATION_CONDITIONS,
    LLM_TASK_LIMITS,
    LLM_TASK_ENTAILMENT,
    LLM_TASK_CONTRADICTION,
    LLM_TASK_FR_EN_SYNTHESIS,
    LLM_TASK_TOOL_CALLING,
    LLM_TASK_CITATIONS,
)

LLM_GATEWAY_LATENCY_MS = "llm_gateway_latency_ms"
LLM_NETWORK_LATENCY_MS = "llm_network_latency_ms"
LLM_VLLM_QUEUE_TIME_MS = "llm_vllm_queue_time_ms"
LLM_TIME_TO_FIRST_TOKEN_MS = "llm_time_to_first_token_ms"
LLM_TOKENS_PER_SECOND = "llm_tokens_per_second"
LLM_ERROR_RATE = "llm_error_rate"
LLM_RETRY_BEFORE_FIRST_TOKEN_TOTAL = "llm_retry_before_first_token_total"
LLM_STRUCTURED_OUTPUT_STABILITY_RATE = "llm_structured_output_stability_rate"
LLM_SPARK_RESTART_RECOVERY_RATE = "llm_spark_restart_recovery_rate"
REQUIRED_LLM_TECHNICAL_METRICS = (
    LLM_GATEWAY_LATENCY_MS,
    LLM_NETWORK_LATENCY_MS,
    LLM_VLLM_QUEUE_TIME_MS,
    LLM_TIME_TO_FIRST_TOKEN_MS,
    LLM_TOKENS_PER_SECOND,
    LLM_ERROR_RATE,
    LLM_RETRY_BEFORE_FIRST_TOKEN_TOTAL,
    LLM_STRUCTURED_OUTPUT_STABILITY_RATE,
    LLM_SPARK_RESTART_RECOVERY_RATE,
)

PROMOTION_ACCEPTED = "ACCEPTED"
PROMOTION_REJECTED = "REJECTED"
REAL_PATH_SEGMENTS = ("docker-local", "llm-gateway", "reseau-prive", "vllm-spark")
_DECIMAL_SCALE = Decimal("0.000000000001")
_SENSITIVE_PUBLIC_FRAGMENTS = (
    "prompt complet",
    "preuve complète",
    "preuve complete",
    "réponse complète",
    "reponse complete",
    "secret",
    "payload sensible",
)


@dataclass(frozen=True)
class BenchmarkMetric:
    name: str
    value: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text_value(self.name, "metric_name"))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur métrique invalide"))
        object.__setattr__(self, "numerator", _required_non_negative_integer(self.numerator, "metric_numerator"))
        object.__setattr__(self, "denominator", _required_metric_denominator(self.denominator))


@dataclass(frozen=True)
class CheckpointCandidate:
    checkpoint_id: str
    origin: str
    serving_profile_id: str

    def __post_init__(self) -> None:
        checkpoint_id = _required_text_value(self.checkpoint_id, "checkpoint_id")
        if checkpoint_id not in REQUIRED_LLM_CHECKPOINTS:
            raise ValueError("checkpoint inconnu")
        origin = _required_text_value(self.origin, "origin")
        if origin not in {OFFICIAL_CHECKPOINT_ORIGIN, COMMUNITY_CHECKPOINT_ORIGIN}:
            raise ValueError("origine checkpoint invalide")
        if _EXPECTED_ORIGIN_BY_CHECKPOINT[checkpoint_id] != origin:
            raise ValueError("origine checkpoint incohérente")
        object.__setattr__(self, "checkpoint_id", checkpoint_id)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "serving_profile_id", _required_text_value(self.serving_profile_id, "serving_profile_id"))


@dataclass(frozen=True)
class LlmRealPathAttestation:
    path_id: str
    segments: tuple[str, ...]
    gateway_trace_id: str
    network_policy_id: str
    vllm_route_id: str

    def __init__(
        self,
        *,
        path_id: str,
        segments: Sequence[str],
        gateway_trace_id: str,
        network_policy_id: str,
        vllm_route_id: str,
    ) -> None:
        object.__setattr__(self, "path_id", _required_text_value(path_id, "path_id"))
        parsed_segments = _required_text_tuple(segments, "segments")
        if parsed_segments == ("docker-local", "vllm-spark") or (
            "vllm-spark" in parsed_segments and "llm-gateway" not in parsed_segments
        ):
            raise ValueError("chemin direct Spark interdit")
        if parsed_segments != REAL_PATH_SEGMENTS:
            raise ValueError("chemin LLM réel invalide")
        object.__setattr__(self, "segments", parsed_segments)
        object.__setattr__(self, "gateway_trace_id", _required_text_value(gateway_trace_id, "gateway_trace_id"))
        object.__setattr__(self, "network_policy_id", _required_text_value(network_policy_id, "network_policy_id"))
        object.__setattr__(self, "vllm_route_id", _required_text_value(vllm_route_id, "vllm_route_id"))


@dataclass(frozen=True)
class LlmTechnicalMetric:
    name: str
    value: str
    numerator: int
    denominator: int
    public_labels: tuple[str, ...]

    def __init__(
        self,
        *,
        name: str,
        value: str,
        numerator: int,
        denominator: int,
        public_labels: Sequence[str],
    ) -> None:
        metric_name = _required_text_value(name, "metric_name")
        if metric_name not in REQUIRED_LLM_TECHNICAL_METRICS:
            raise ValueError("métrique technique LLM inconnue")
        object.__setattr__(self, "name", metric_name)
        object.__setattr__(self, "value", _required_decimal_text(value, "valeur métrique invalide"))
        object.__setattr__(self, "numerator", _required_non_negative_integer(numerator, "metric_numerator"))
        object.__setattr__(self, "denominator", _required_metric_denominator(denominator))
        labels = _required_text_tuple(public_labels, "public_labels")
        for label in labels:
            _ensure_public_label(label)
        object.__setattr__(self, "public_labels", labels)

    def as_benchmark_metric(self) -> BenchmarkMetric:
        return BenchmarkMetric(
            name=self.name,
            value=self.value,
            numerator=self.numerator,
            denominator=self.denominator,
        )


@dataclass(frozen=True)
class StructuredOutputEvaluation:
    evaluation_id: str
    task_name: str
    response_json: str
    atomic_extraction_complete: bool
    negations_preserved: bool
    numeric_values_exact: bool
    conditions_preserved: bool
    limits_preserved: bool
    entailment_correct: bool
    contradiction_detected: bool
    fr_en_synthesis_valid: bool
    tool_call_valid: bool
    citations_resolved: bool
    retry_before_first_token_total: int
    retry_after_first_token_total: int
    retry_limit: int
    retry_idempotency_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluation_id", _required_text_value(self.evaluation_id, "evaluation_id"))
        task_name = _required_text_value(self.task_name, "task_name")
        if task_name not in REQUIRED_LLM_TASKS:
            raise ValueError("tache LLM inconnue")
        object.__setattr__(self, "task_name", task_name)
        object.__setattr__(self, "response_json", _required_text_value(self.response_json, "response_json"))
        for field_name in (
            "atomic_extraction_complete",
            "negations_preserved",
            "numeric_values_exact",
            "conditions_preserved",
            "limits_preserved",
            "entailment_correct",
            "contradiction_detected",
            "fr_en_synthesis_valid",
            "tool_call_valid",
            "citations_resolved",
        ):
            object.__setattr__(self, field_name, _required_bool(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "retry_before_first_token_total",
            _required_non_negative_integer(self.retry_before_first_token_total, "retry_before_first_token_total"),
        )
        retry_after_first_token_total = _required_non_negative_integer(
            self.retry_after_first_token_total,
            "retry_after_first_token_total",
        )
        if retry_after_first_token_total > 0:
            raise ValueError("retry après premier token interdit")
        object.__setattr__(self, "retry_after_first_token_total", retry_after_first_token_total)
        if isinstance(self.retry_limit, bool) or not isinstance(self.retry_limit, int) or self.retry_limit < 1:
            raise ValueError("retry illimité interdit")
        retry_limit = self.retry_limit
        object.__setattr__(self, "retry_limit", retry_limit)
        if self.retry_before_first_token_total > retry_limit:
            raise ValueError("retry illimité interdit")
        if not isinstance(self.retry_idempotency_key, str):
            raise ValueError("retry_idempotency_key non textuel")
        if self.retry_before_first_token_total > 0 and self.retry_idempotency_key.strip() == "":
            raise ValueError("clé idempotence retry requise")
        retry_idempotency_key = _required_text_value(self.retry_idempotency_key, "retry_idempotency_key")
        object.__setattr__(self, "retry_idempotency_key", retry_idempotency_key)

    @property
    def json_valid(self) -> bool:
        try:
            json.loads(self.response_json)
        except json.JSONDecodeError:
            return False
        return True

    @property
    def passed(self) -> bool:
        if not self.json_valid:
            return False
        task_success_by_name = {
            LLM_TASK_JSON_VALID: True,
            LLM_TASK_ATOMIC_EXTRACTION: self.atomic_extraction_complete,
            LLM_TASK_NEGATION_PRESERVATION: self.negations_preserved,
            LLM_TASK_NUMBER_ACCURACY: self.numeric_values_exact,
            LLM_TASK_APPLICATION_CONDITIONS: self.conditions_preserved,
            LLM_TASK_LIMITS: self.limits_preserved,
            LLM_TASK_ENTAILMENT: self.entailment_correct,
            LLM_TASK_CONTRADICTION: self.contradiction_detected,
            LLM_TASK_FR_EN_SYNTHESIS: self.fr_en_synthesis_valid,
            LLM_TASK_TOOL_CALLING: self.tool_call_valid,
            LLM_TASK_CITATIONS: self.citations_resolved,
        }
        return task_success_by_name[self.task_name]

    @property
    def benchmark_metric(self) -> BenchmarkMetric:
        numerator = 1 if self.passed else 0
        return BenchmarkMetric(
            name=f"llm_task_{self.task_name}_success_rate",
            value=_metric_value(numerator, 1),
            numerator=numerator,
            denominator=1,
        )


@dataclass(frozen=True)
class CheckpointMeasurement:
    candidate: CheckpointCandidate
    path_attestation: LlmRealPathAttestation
    structured_outputs: tuple[StructuredOutputEvaluation, ...]
    technical_metrics: tuple[LlmTechnicalMetric, ...]
    fallback_checkpoint_id: str | None = None

    def __init__(
        self,
        *,
        candidate: CheckpointCandidate,
        path_attestation: LlmRealPathAttestation,
        structured_outputs: Sequence[StructuredOutputEvaluation],
        technical_metrics: Sequence[LlmTechnicalMetric],
        fallback_checkpoint_id: str | None = None,
    ) -> None:
        if not isinstance(candidate, CheckpointCandidate):
            raise ValueError("CheckpointCandidate requis")
        if not isinstance(path_attestation, LlmRealPathAttestation):
            raise ValueError("LlmRealPathAttestation requise")
        if fallback_checkpoint_id is not None:
            raise ValueError("fallback checkpoint interdit")
        object.__setattr__(self, "candidate", candidate)
        object.__setattr__(self, "path_attestation", path_attestation)
        object.__setattr__(self, "structured_outputs", _required_structured_outputs(structured_outputs))
        object.__setattr__(self, "technical_metrics", _required_technical_metrics(technical_metrics))
        object.__setattr__(self, "fallback_checkpoint_id", fallback_checkpoint_id)

    @property
    def task_success_rates(self) -> Mapping[str, BenchmarkMetric]:
        return {evaluation.task_name: evaluation.benchmark_metric for evaluation in self.structured_outputs}

    @property
    def technical_metrics_by_name(self) -> Mapping[str, BenchmarkMetric]:
        return {metric.name: metric.as_benchmark_metric() for metric in self.technical_metrics}

    @property
    def eligible_for_promotion(self) -> bool:
        return all(metric.numerator == metric.denominator for metric in self.task_success_rates.values())


@dataclass(frozen=True)
class LlmBenchmarkRun:
    run_id: str
    policy_version: str
    checkpoint_count: int
    task_names: tuple[str, ...]
    technical_metric_names: tuple[str, ...]
    measurements: tuple[CheckpointMeasurement, ...]
    measurements_by_checkpoint: Mapping[str, CheckpointMeasurement]


@dataclass(frozen=True)
class CheckpointComparisonReport:
    checkpoint_id: str
    official_reference_checkpoint_ids: tuple[str, ...]
    task_success_rates: Mapping[str, BenchmarkMetric]
    reference_task_success_rates: Mapping[str, BenchmarkMetric]
    technical_metric_names: tuple[str, ...]


@dataclass(frozen=True)
class CheckpointPromotionDecision:
    checkpoint_id: str
    status: str
    reasons: tuple[str, ...]
    comparison_report: CheckpointComparisonReport


@dataclass(frozen=True)
class CheckpointPromotionPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_text_value(self.policy_version, "policy_version"))

    def evaluate(self, *, run: LlmBenchmarkRun, checkpoint_id: str) -> CheckpointPromotionDecision:
        if not isinstance(run, LlmBenchmarkRun):
            raise ValueError("LlmBenchmarkRun requis")
        parsed_checkpoint_id = _required_text_value(checkpoint_id, "checkpoint_id")
        if parsed_checkpoint_id not in run.measurements_by_checkpoint:
            raise ValueError("checkpoint benchmark absent")
        measurement = run.measurements_by_checkpoint[parsed_checkpoint_id]
        if measurement.candidate.origin != COMMUNITY_CHECKPOINT_ORIGIN:
            raise ValueError("promotion réservée aux checkpoints communautaires")

        official_measurements = tuple(
            candidate_measurement
            for candidate_measurement in run.measurements
            if candidate_measurement.candidate.origin == OFFICIAL_CHECKPOINT_ORIGIN
        )
        if len(official_measurements) == 0:
            raise ValueError("référence officielle absente")

        reference_rates = _reference_task_rates(official_measurements)
        reasons: list[str] = []
        for task_name, candidate_metric in measurement.task_success_rates.items():
            reference_metric = reference_rates[task_name]
            if Decimal(candidate_metric.value) < Decimal(reference_metric.value):
                reasons.append(f"tâche {task_name} inférieure aux références officielles")
        if set(measurement.technical_metrics_by_name.keys()) != set(REQUIRED_LLM_TECHNICAL_METRICS):
            reasons.append("métriques techniques exploitables absentes")

        report = CheckpointComparisonReport(
            checkpoint_id=parsed_checkpoint_id,
            official_reference_checkpoint_ids=tuple(
                official_measurement.candidate.checkpoint_id for official_measurement in official_measurements
            ),
            task_success_rates=measurement.task_success_rates,
            reference_task_success_rates=reference_rates,
            technical_metric_names=run.technical_metric_names,
        )
        return CheckpointPromotionDecision(
            checkpoint_id=parsed_checkpoint_id,
            status=PROMOTION_REJECTED if reasons else PROMOTION_ACCEPTED,
            reasons=tuple(reasons),
            comparison_report=report,
        )


@dataclass(frozen=True)
class LlmBenchmarkSuite:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_text_value(self.policy_version, "policy_version"))

    def measure(
        self,
        *,
        run_id: str,
        measurements: Sequence[CheckpointMeasurement],
    ) -> LlmBenchmarkRun:
        parsed_run_id = _required_text_value(run_id, "run_id")
        parsed_measurements = _required_checkpoint_measurements(measurements)
        missing_checkpoints = sorted(
            set(REQUIRED_LLM_CHECKPOINTS).difference(
                measurement.candidate.checkpoint_id for measurement in parsed_measurements
            )
        )
        if missing_checkpoints:
            raise ValueError(f"checkpoint obligatoire absent: {', '.join(missing_checkpoints)}")
        measurements_by_checkpoint = {
            measurement.candidate.checkpoint_id: measurement for measurement in parsed_measurements
        }
        return LlmBenchmarkRun(
            run_id=parsed_run_id,
            policy_version=self.policy_version,
            checkpoint_count=len(parsed_measurements),
            task_names=REQUIRED_LLM_TASKS,
            technical_metric_names=REQUIRED_LLM_TECHNICAL_METRICS,
            measurements=parsed_measurements,
            measurements_by_checkpoint=measurements_by_checkpoint,
        )

    def evaluate_promotion(self, *, run: LlmBenchmarkRun, checkpoint_id: str) -> CheckpointPromotionDecision:
        return CheckpointPromotionPolicy(policy_version=self.policy_version).evaluate(
            run=run,
            checkpoint_id=checkpoint_id,
        )


def _reference_task_rates(measurements: Sequence[CheckpointMeasurement]) -> Mapping[str, BenchmarkMetric]:
    reference_rates: dict[str, BenchmarkMetric] = {}
    for task_name in REQUIRED_LLM_TASKS:
        numerator = min(measurement.task_success_rates[task_name].numerator for measurement in measurements)
        reference_rates[task_name] = BenchmarkMetric(
            name=f"llm_reference_task_{task_name}_success_rate",
            value=_metric_value(numerator, 1),
            numerator=numerator,
            denominator=1,
        )
    return reference_rates


def _required_structured_outputs(values: Sequence[StructuredOutputEvaluation]) -> tuple[StructuredOutputEvaluation, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("sorties structurees LLM invalides")
    outputs = tuple(values)
    task_names: set[str] = set()
    for output in outputs:
        if not isinstance(output, StructuredOutputEvaluation):
            raise ValueError("StructuredOutputEvaluation requise")
        if output.task_name in task_names:
            raise ValueError("tache LLM dupliquee")
        task_names.add(output.task_name)
    missing_tasks = sorted(set(REQUIRED_LLM_TASKS).difference(task_names))
    if missing_tasks:
        raise ValueError(f"tache LLM obligatoire absente: {', '.join(missing_tasks)}")
    return outputs


def _required_technical_metrics(values: Sequence[LlmTechnicalMetric]) -> tuple[LlmTechnicalMetric, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("metriques techniques LLM invalides")
    metrics = tuple(values)
    metric_names: set[str] = set()
    for metric in metrics:
        if not isinstance(metric, LlmTechnicalMetric):
            raise ValueError("LlmTechnicalMetric requise")
        if metric.name in metric_names:
            raise ValueError("metrique technique LLM dupliquee")
        metric_names.add(metric.name)
    missing_metrics = sorted(set(REQUIRED_LLM_TECHNICAL_METRICS).difference(metric_names))
    if missing_metrics:
        raise ValueError(f"metrique technique LLM absente: {', '.join(missing_metrics)}")
    return metrics


def _required_checkpoint_measurements(values: Sequence[CheckpointMeasurement]) -> tuple[CheckpointMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("mesures checkpoint invalides")
    measurements = tuple(values)
    checkpoint_ids: set[str] = set()
    for measurement in measurements:
        if not isinstance(measurement, CheckpointMeasurement):
            raise ValueError("CheckpointMeasurement requise")
        checkpoint_id = measurement.candidate.checkpoint_id
        if checkpoint_id in checkpoint_ids:
            raise ValueError("checkpoint benchmark duplique")
        checkpoint_ids.add(checkpoint_id)
    return measurements


def _ensure_public_label(value: str) -> None:
    normalized = value.lower()
    for fragment in _SENSITIVE_PUBLIC_FRAGMENTS:
        if fragment in normalized:
            raise ValueError("payload sensible interdit")


def _required_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_required_text_value(value, field_name) for value in values)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} vide")
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field_name} duplique")
    return parsed


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


def _required_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
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


def _metric_value(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("dénominateur métrique invalide")
    return _format_decimal(Decimal(numerator) / Decimal(denominator))


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN):.12f}"


__all__ = [
    "CHECKPOINT_GOOGLE_GEMMA",
    "CHECKPOINT_NVIDIA_GEMMA",
    "CHECKPOINT_YCWTG_GEMMA",
    "COMMUNITY_CHECKPOINT_ORIGIN",
    "LLM_ERROR_RATE",
    "LLM_GATEWAY_LATENCY_MS",
    "LLM_NETWORK_LATENCY_MS",
    "LLM_RETRY_BEFORE_FIRST_TOKEN_TOTAL",
    "LLM_SPARK_RESTART_RECOVERY_RATE",
    "LLM_STRUCTURED_OUTPUT_STABILITY_RATE",
    "LLM_TASK_APPLICATION_CONDITIONS",
    "LLM_TASK_ATOMIC_EXTRACTION",
    "LLM_TASK_CITATIONS",
    "LLM_TASK_CONTRADICTION",
    "LLM_TASK_ENTAILMENT",
    "LLM_TASK_FR_EN_SYNTHESIS",
    "LLM_TASK_JSON_VALID",
    "LLM_TASK_LIMITS",
    "LLM_TASK_NEGATION_PRESERVATION",
    "LLM_TASK_NUMBER_ACCURACY",
    "LLM_TASK_TOOL_CALLING",
    "LLM_TIME_TO_FIRST_TOKEN_MS",
    "LLM_TOKENS_PER_SECOND",
    "LLM_VLLM_QUEUE_TIME_MS",
    "OFFICIAL_CHECKPOINT_ORIGIN",
    "PROMOTION_ACCEPTED",
    "PROMOTION_REJECTED",
    "REAL_PATH_SEGMENTS",
    "REQUIRED_LLM_CHECKPOINTS",
    "REQUIRED_LLM_TASKS",
    "REQUIRED_LLM_TECHNICAL_METRICS",
    "BenchmarkMetric",
    "CheckpointCandidate",
    "CheckpointComparisonReport",
    "CheckpointMeasurement",
    "CheckpointPromotionDecision",
    "CheckpointPromotionPolicy",
    "LlmBenchmarkRun",
    "LlmBenchmarkSuite",
    "LlmRealPathAttestation",
    "LlmTechnicalMetric",
    "StructuredOutputEvaluation",
]
