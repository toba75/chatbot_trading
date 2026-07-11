"""Primitives locales d'observabilite technique M-002."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


SECRET_MASK = "<secret-masked>"
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
M013_LOCAL_MONITORING_PROFILE_VERSION = "M013-LocalMonitoringProfile-1.0"
M013_RESOURCE_PROFILE_VERSION = "M013-ResourceProfile-1.0"
M013_LOCAL_LOG_RETENTION_HOURS = 72

_M013_CONTEXTS = ("SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV", "platform")
_M013_REQUIRED_METRICS = (
    "v1_health_status",
    "v1_error_total",
    "v1_latency_ms",
    "job_queue_depth",
    "outbox_pending_total",
    "llm_gateway_latency_ms",
    "llm_gateway_output_interrupted_total",
    "spark_inference_availability",
    "backup_restore_result",
    "v1_gap_status",
    "network_security_violation_total",
)
_M013_REQUIRED_RESOURCE_KINDS = ("CPU", "GPU", "MEMORY", "IO", "STORAGE")
_M013_BENCHMARK_SOURCE = "docs/evaluation/m012/llm_real_path_benchmark_report.md"


class ObservabilityContractError(ValueError):
    """Erreur explicite du contrat d'observabilite technique."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GatewayObservation:
    """Observation technique d'un appel au gateway LLM."""

    trace_id: str
    request_id: str
    idempotency_key: str
    configuration_hash: str
    phase: str
    status: str
    latency_ms: float
    served_model: str
    model_revision: str | None
    runtime_version: str | None
    prompt_hash: str
    request_payload_bytes: int
    response_payload_bytes: int | None
    ttft_ms: float | None
    retry_count: int
    circuit_open: bool
    output_interrupted: bool
    error_code: str | None

    def __post_init__(self) -> None:
        _ensure_text(self.trace_id, "trace_id", "OBS_TRACE_ID_REQUIRED")
        _ensure_text(self.request_id, "request_id", "OBS_REQUEST_ID_REQUIRED")
        _ensure_text(self.idempotency_key, "idempotency_key", "OBS_IDEMPOTENCY_KEY_REQUIRED")
        _ensure_hash(self.configuration_hash, "configuration_hash", "OBS_CONFIGURATION_HASH_INVALID")
        _ensure_text(self.phase, "phase", "OBS_PHASE_REQUIRED")
        _ensure_text(self.status, "status", "OBS_STATUS_REQUIRED")
        _ensure_non_negative_number(self.latency_ms, "latency_ms", "OBS_LATENCY_INVALID")
        _ensure_text(self.served_model, "served_model", "OBS_SERVED_MODEL_REQUIRED")
        _ensure_hash(self.prompt_hash, "prompt_hash", "OBS_PROMPT_HASH_INVALID")
        _ensure_non_negative_integer(
            self.request_payload_bytes,
            "request_payload_bytes",
            "OBS_PAYLOAD_SIZE_INVALID",
        )
        _ensure_optional_non_negative_integer(
            self.response_payload_bytes,
            "response_payload_bytes",
            "OBS_PAYLOAD_SIZE_INVALID",
        )
        _ensure_optional_non_negative_number(self.ttft_ms, "ttft_ms", "OBS_TTFT_INVALID")
        _ensure_non_negative_integer(self.retry_count, "retry_count", "OBS_RETRY_COUNT_INVALID")
        _ensure_bool(self.circuit_open, "circuit_open", "OBS_CIRCUIT_OPEN_INVALID")
        _ensure_bool(self.output_interrupted, "output_interrupted", "OBS_OUTPUT_INTERRUPTED_INVALID")
        _ensure_optional_text(self.error_code, "error_code", "OBS_ERROR_CODE_INVALID")

        if self.status == "SUCCEEDED":
            _ensure_text(self.model_revision, "model_revision", "OBS_MODEL_REVISION_REQUIRED")
            _ensure_text(self.runtime_version, "runtime_version", "OBS_RUNTIME_VERSION_REQUIRED")
            if self.response_payload_bytes is None:
                raise ObservabilityContractError(
                    "OBS_RESPONSE_PAYLOAD_SIZE_REQUIRED",
                    "La taille de reponse est requise pour une inference reussie.",
                )
            if self.error_code is not None:
                raise ObservabilityContractError(
                    "OBS_ERROR_CODE_FORBIDDEN",
                    "Un succes ne doit pas porter de code d'erreur.",
                )
        else:
            _ensure_optional_text(self.model_revision, "model_revision", "OBS_MODEL_REVISION_INVALID")
            _ensure_optional_text(self.runtime_version, "runtime_version", "OBS_RUNTIME_VERSION_INVALID")
            _ensure_text(self.error_code, "error_code", "OBS_ERROR_CODE_REQUIRED")


@dataclass(frozen=True)
class JobObservation:
    """Observation technique d'un job local."""

    trace_id: str
    job_id: str
    job_name: str
    phase: str
    status: str
    latency_ms: float
    attempt: int

    def __post_init__(self) -> None:
        _ensure_text(self.trace_id, "trace_id", "OBS_TRACE_ID_REQUIRED")
        _ensure_text(self.job_id, "job_id", "OBS_JOB_ID_REQUIRED")
        _ensure_text(self.job_name, "job_name", "OBS_JOB_NAME_REQUIRED")
        _ensure_text(self.phase, "phase", "OBS_PHASE_REQUIRED")
        _ensure_text(self.status, "status", "OBS_STATUS_REQUIRED")
        _ensure_non_negative_number(self.latency_ms, "latency_ms", "OBS_LATENCY_INVALID")
        _ensure_positive_integer(self.attempt, "attempt", "OBS_ATTEMPT_INVALID")


@dataclass(frozen=True)
class OutboxObservation:
    """Observation technique d'une livraison outbox locale."""

    trace_id: str
    event_id: str
    producer_context: str
    phase: str
    status: str
    latency_ms: float
    duplicate: bool

    def __post_init__(self) -> None:
        _ensure_text(self.trace_id, "trace_id", "OBS_TRACE_ID_REQUIRED")
        _ensure_text(self.event_id, "event_id", "OBS_EVENT_ID_REQUIRED")
        _ensure_text(self.producer_context, "producer_context", "OBS_PRODUCER_CONTEXT_REQUIRED")
        _ensure_text(self.phase, "phase", "OBS_PHASE_REQUIRED")
        _ensure_text(self.status, "status", "OBS_STATUS_REQUIRED")
        _ensure_non_negative_number(self.latency_ms, "latency_ms", "OBS_LATENCY_INVALID")
        _ensure_bool(self.duplicate, "duplicate", "OBS_DUPLICATE_INVALID")


@dataclass(frozen=True)
class StructuredLogEvent:
    """Log structure sans corps complet de prompt, preuve ou reponse."""

    component: str
    trace_id: str
    phase: str
    status: str
    latency_ms: float
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        _ensure_text(self.component, "component", "OBS_COMPONENT_REQUIRED")
        _ensure_text(self.trace_id, "trace_id", "OBS_TRACE_ID_REQUIRED")
        _ensure_text(self.phase, "phase", "OBS_PHASE_REQUIRED")
        _ensure_text(self.status, "status", "OBS_STATUS_REQUIRED")
        _ensure_non_negative_number(self.latency_ms, "latency_ms", "OBS_LATENCY_INVALID")
        object.__setattr__(self, "details", _freeze_mapping(self.details, "details"))

    @property
    def prompt_hash(self) -> str:
        value = self.details.get("prompt_hash")
        if not isinstance(value, str):
            raise ObservabilityContractError(
                "OBS_PROMPT_HASH_REQUIRED",
                "Le hash de prompt est absent du log gateway.",
            )
        return value

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "component": self.component,
            "trace_id": self.trace_id,
            "phase": self.phase,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }
        result.update(dict(self.details))
        return result


@dataclass(frozen=True)
class TechnicalMetricEvent:
    """Metrique technique sans contenu complet de payload."""

    name: str
    value: float
    unit: str
    component: str
    trace_id: str
    phase: str
    status: str
    tags: Mapping[str, str]

    def __post_init__(self) -> None:
        _ensure_text(self.name, "name", "OBS_METRIC_NAME_REQUIRED")
        _ensure_non_negative_number(self.value, "value", "OBS_METRIC_VALUE_INVALID")
        _ensure_text(self.unit, "unit", "OBS_METRIC_UNIT_REQUIRED")
        _ensure_text(self.component, "component", "OBS_COMPONENT_REQUIRED")
        _ensure_text(self.trace_id, "trace_id", "OBS_TRACE_ID_REQUIRED")
        _ensure_text(self.phase, "phase", "OBS_PHASE_REQUIRED")
        _ensure_text(self.status, "status", "OBS_STATUS_REQUIRED")
        object.__setattr__(self, "tags", _freeze_string_mapping(self.tags, "tags"))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "component": self.component,
            "trace_id": self.trace_id,
            "phase": self.phase,
            "status": self.status,
            "tags": dict(self.tags),
        }


class InMemoryObservabilityCollector:
    """Collecteur local minimal de logs et metriques techniques."""

    def __init__(self) -> None:
        self._logs: list[StructuredLogEvent] = []
        self._metrics: list[TechnicalMetricEvent] = []

    def record_gateway_observation(self, observation: GatewayObservation) -> None:
        if not isinstance(observation, GatewayObservation):
            raise ObservabilityContractError(
                "OBS_GATEWAY_OBSERVATION_INVALID",
                "L'observation gateway doit utiliser GatewayObservation.",
            )

        details = {
            "request_id": observation.request_id,
            "idempotency_key": observation.idempotency_key,
            "configuration_hash": observation.configuration_hash,
            "served_model": observation.served_model,
            "model_revision": observation.model_revision,
            "runtime_version": observation.runtime_version,
            "prompt_hash": observation.prompt_hash,
            "request_payload_bytes": observation.request_payload_bytes,
            "response_payload_bytes": observation.response_payload_bytes,
            "ttft_ms": observation.ttft_ms,
            "retry_count": observation.retry_count,
            "circuit_open": observation.circuit_open,
            "output_interrupted": observation.output_interrupted,
            "error_code": observation.error_code,
        }
        self._logs.append(
            StructuredLogEvent(
                component="llm-gateway",
                trace_id=observation.trace_id,
                phase=observation.phase,
                status=observation.status,
                latency_ms=observation.latency_ms,
                details=details,
            )
        )

        base_tags = {
            "configuration_hash": observation.configuration_hash,
            "served_model": observation.served_model,
            "status": observation.status,
        }
        if observation.model_revision is not None:
            base_tags["model_revision"] = observation.model_revision
        if observation.runtime_version is not None:
            base_tags["runtime_version"] = observation.runtime_version
        if observation.error_code is not None:
            base_tags["error_code"] = observation.error_code

        self._append_metric(
            name="llm_gateway_request_total",
            value=1,
            unit="count",
            component="llm-gateway",
            observation=observation,
            tags=base_tags,
        )
        self._append_metric(
            name="llm_gateway_request_latency_ms",
            value=observation.latency_ms,
            unit="milliseconds",
            component="llm-gateway",
            observation=observation,
            tags=base_tags,
        )
        self._append_metric(
            name="llm_gateway_payload_bytes",
            value=observation.request_payload_bytes,
            unit="bytes",
            component="llm-gateway",
            observation=observation,
            tags={**base_tags, "direction": "request"},
        )
        if observation.response_payload_bytes is not None:
            self._append_metric(
                name="llm_gateway_payload_bytes",
                value=observation.response_payload_bytes,
                unit="bytes",
                component="llm-gateway",
                observation=observation,
                tags={**base_tags, "direction": "response"},
            )
        if observation.ttft_ms is not None:
            self._append_metric(
                name="llm_gateway_ttft_ms",
                value=observation.ttft_ms,
                unit="milliseconds",
                component="llm-gateway",
                observation=observation,
                tags=base_tags,
            )
        if observation.status == "RETRY_PENDING" and observation.retry_count > 0:
            self._append_metric(
                name="llm_gateway_retry_before_first_token_total",
                value=observation.retry_count,
                unit="count",
                component="llm-gateway",
                observation=observation,
                tags=base_tags,
            )
        if observation.circuit_open:
            self._append_metric(
                name="llm_gateway_circuit_breaker_open",
                value=1,
                unit="count",
                component="llm-gateway",
                observation=observation,
                tags=base_tags,
            )
        if observation.output_interrupted:
            self._append_metric(
                name="llm_gateway_output_interrupted_total",
                value=1,
                unit="count",
                component="llm-gateway",
                observation=observation,
                tags=base_tags,
            )

    def record_job_observation(self, observation: JobObservation) -> None:
        if not isinstance(observation, JobObservation):
            raise ObservabilityContractError(
                "OBS_JOB_OBSERVATION_INVALID",
                "L'observation job doit utiliser JobObservation.",
            )
        self._logs.append(
            StructuredLogEvent(
                component="job-runtime",
                trace_id=observation.trace_id,
                phase=observation.phase,
                status=observation.status,
                latency_ms=observation.latency_ms,
                details={
                    "job_id": observation.job_id,
                    "job_name": observation.job_name,
                    "attempt": observation.attempt,
                },
            )
        )
        self._append_metric_from_parts(
            name="job_runtime_event_total",
            value=1,
            unit="count",
            component="job-runtime",
            trace_id=observation.trace_id,
            phase=observation.phase,
            status=observation.status,
            tags={"job_name": observation.job_name},
        )
        self._append_metric_from_parts(
            name="job_runtime_latency_ms",
            value=observation.latency_ms,
            unit="milliseconds",
            component="job-runtime",
            trace_id=observation.trace_id,
            phase=observation.phase,
            status=observation.status,
            tags={"job_name": observation.job_name},
        )

    def record_outbox_observation(self, observation: OutboxObservation) -> None:
        if not isinstance(observation, OutboxObservation):
            raise ObservabilityContractError(
                "OBS_OUTBOX_OBSERVATION_INVALID",
                "L'observation outbox doit utiliser OutboxObservation.",
            )
        self._logs.append(
            StructuredLogEvent(
                component="outbox",
                trace_id=observation.trace_id,
                phase=observation.phase,
                status=observation.status,
                latency_ms=observation.latency_ms,
                details={
                    "event_id": observation.event_id,
                    "producer_context": observation.producer_context,
                    "duplicate": observation.duplicate,
                },
            )
        )
        tags = {
            "producer_context": observation.producer_context,
            "duplicate": str(observation.duplicate).lower(),
        }
        self._append_metric_from_parts(
            name="outbox_event_total",
            value=1,
            unit="count",
            component="outbox",
            trace_id=observation.trace_id,
            phase=observation.phase,
            status=observation.status,
            tags=tags,
        )
        self._append_metric_from_parts(
            name="outbox_latency_ms",
            value=observation.latency_ms,
            unit="milliseconds",
            component="outbox",
            trace_id=observation.trace_id,
            phase=observation.phase,
            status=observation.status,
            tags=tags,
        )

    def logs(self) -> tuple[StructuredLogEvent, ...]:
        return tuple(self._logs)

    def metrics(self) -> tuple[TechnicalMetricEvent, ...]:
        return tuple(self._metrics)

    def _append_metric(
        self,
        *,
        name: str,
        value: float,
        unit: str,
        component: str,
        observation: GatewayObservation,
        tags: Mapping[str, str],
    ) -> None:
        self._append_metric_from_parts(
            name=name,
            value=value,
            unit=unit,
            component=component,
            trace_id=observation.trace_id,
            phase=observation.phase,
            status=observation.status,
            tags=tags,
        )

    def _append_metric_from_parts(
        self,
        *,
        name: str,
        value: float,
        unit: str,
        component: str,
        trace_id: str,
        phase: str,
        status: str,
        tags: Mapping[str, str],
    ) -> None:
        self._metrics.append(
            TechnicalMetricEvent(
                name=name,
                value=float(value),
                unit=unit,
                component=component,
                trace_id=trace_id,
                phase=phase,
                status=status,
                tags=tags,
            )
        )


@dataclass(frozen=True)
class MonitoringSignal:
    signal_id: str
    context: str
    component: str
    metric_name: str
    metric_family: str
    owner: str
    correlation_field: str
    retention_hours: int
    local_only: bool
    external_export_enabled_by_default: bool
    contains_full_prompt: bool
    contains_full_evidence: bool
    contains_full_response: bool
    contains_secret: bool
    contains_market_payload: bool
    gap_status_visible: bool
    spark_failure_visible: bool
    backup_restore_visible: bool
    security_boundary_visible: bool
    alert_threshold: str
    threshold_source: str

    def __init__(
        self,
        *,
        signal_id: str,
        context: str,
        component: str,
        metric_name: str,
        metric_family: str,
        owner: str,
        correlation_field: str,
        retention_hours: int,
        local_only: bool,
        external_export_enabled_by_default: bool,
        contains_full_prompt: bool,
        contains_full_evidence: bool,
        contains_full_response: bool,
        contains_secret: bool,
        contains_market_payload: bool,
        gap_status_visible: bool,
        spark_failure_visible: bool,
        backup_restore_visible: bool,
        security_boundary_visible: bool,
        alert_threshold: str,
        threshold_source: str,
    ) -> None:
        parsed_context = _required_m013_context(context)
        parsed_retention_hours = _required_positive_int_m013(retention_hours, "rétention courte requise")
        if parsed_retention_hours > M013_LOCAL_LOG_RETENTION_HOURS:
            raise ValueError("rétention courte requise")
        if not _required_bool_m013(local_only, "local_only"):
            raise ValueError("monitoring local requis")
        if _required_bool_m013(external_export_enabled_by_default, "external_export_enabled_by_default"):
            raise ValueError("export externe par défaut interdit")
        if (
            _required_bool_m013(contains_full_prompt, "contains_full_prompt")
            or _required_bool_m013(contains_full_evidence, "contains_full_evidence")
            or _required_bool_m013(contains_full_response, "contains_full_response")
            or _required_bool_m013(contains_secret, "contains_secret")
            or _required_bool_m013(contains_market_payload, "contains_market_payload")
        ):
            raise ValueError("payload sensible interdit")
        if not _required_bool_m013(gap_status_visible, "gap_status_visible"):
            raise ValueError("statut d'écart visible requis")
        if not _required_bool_m013(spark_failure_visible, "spark_failure_visible"):
            raise ValueError("panne Spark visible requise")
        if not _required_bool_m013(backup_restore_visible, "backup_restore_visible"):
            raise ValueError("sauvegarde restauration visible requise")
        if not _required_bool_m013(security_boundary_visible, "security_boundary_visible"):
            raise ValueError("sécurité réseau visible requise")

        object.__setattr__(self, "signal_id", _required_text_m013(signal_id, "signal_id"))
        object.__setattr__(self, "context", parsed_context)
        object.__setattr__(self, "component", _required_text_m013(component, "component"))
        object.__setattr__(self, "metric_name", _required_text_m013(metric_name, "metric_name"))
        object.__setattr__(self, "metric_family", _required_text_m013(metric_family, "metric_family"))
        object.__setattr__(self, "owner", _required_text_m013(owner, "owner"))
        object.__setattr__(self, "correlation_field", _required_text_m013(correlation_field, "corrélation requise"))
        object.__setattr__(self, "retention_hours", parsed_retention_hours)
        object.__setattr__(self, "local_only", True)
        object.__setattr__(self, "external_export_enabled_by_default", False)
        object.__setattr__(self, "contains_full_prompt", False)
        object.__setattr__(self, "contains_full_evidence", False)
        object.__setattr__(self, "contains_full_response", False)
        object.__setattr__(self, "contains_secret", False)
        object.__setattr__(self, "contains_market_payload", False)
        object.__setattr__(self, "gap_status_visible", True)
        object.__setattr__(self, "spark_failure_visible", True)
        object.__setattr__(self, "backup_restore_visible", True)
        object.__setattr__(self, "security_boundary_visible", True)
        object.__setattr__(self, "alert_threshold", _required_text_m013(alert_threshold, "seuil sourcé requis"))
        object.__setattr__(self, "threshold_source", _required_text_m013(threshold_source, "seuil sourcé requis"))


@dataclass(frozen=True)
class LocalMonitoringProfile:
    profile_version: str
    signals: tuple[MonitoringSignal, ...]
    local_only: bool
    external_export_enabled_by_default: bool
    retention_hours: int
    metrics_by_name: Mapping[str, MonitoringSignal]
    contexts: tuple[str, ...]

    def __init__(
        self,
        *,
        profile_version: str,
        signals: Sequence[MonitoringSignal],
        local_only: bool,
        external_export_enabled_by_default: bool,
        retention_hours: int,
    ) -> None:
        if _required_text_m013(profile_version, "profile_version") != M013_LOCAL_MONITORING_PROFILE_VERSION:
            raise ValueError("version monitoring local incohérente")
        parsed_signals = _required_signal_tuple(signals)
        parsed_retention_hours = _required_positive_int_m013(retention_hours, "rétention courte requise")
        if parsed_retention_hours > M013_LOCAL_LOG_RETENTION_HOURS:
            raise ValueError("rétention courte requise")
        if not _required_bool_m013(local_only, "local_only"):
            raise ValueError("monitoring local requis")
        if _required_bool_m013(external_export_enabled_by_default, "external_export_enabled_by_default"):
            raise ValueError("export externe par défaut interdit")

        metrics_by_name: dict[str, MonitoringSignal] = {}
        for signal in parsed_signals:
            if signal.metric_name in metrics_by_name:
                raise ValueError("métrique dupliquée")
            metrics_by_name[signal.metric_name] = signal

        object.__setattr__(self, "profile_version", M013_LOCAL_MONITORING_PROFILE_VERSION)
        object.__setattr__(self, "signals", parsed_signals)
        object.__setattr__(self, "local_only", True)
        object.__setattr__(self, "external_export_enabled_by_default", False)
        object.__setattr__(self, "retention_hours", parsed_retention_hours)
        object.__setattr__(self, "metrics_by_name", MappingProxyType(metrics_by_name))
        object.__setattr__(self, "contexts", tuple(sorted({signal.context for signal in parsed_signals})))

    def without_metric(self, metric_name: str) -> "LocalMonitoringProfile":
        parsed_metric_name = _required_text_m013(metric_name, "metric_name")
        return LocalMonitoringProfile(
            profile_version=self.profile_version,
            signals=tuple(signal for signal in self.signals if signal.metric_name != parsed_metric_name),
            local_only=self.local_only,
            external_export_enabled_by_default=self.external_export_enabled_by_default,
            retention_hours=self.retention_hours,
        )


class MonitoringSignalPolicy:
    def __init__(self, *, public_endpoint_enabled: bool) -> None:
        if _required_bool_m013(public_endpoint_enabled, "public_endpoint_enabled"):
            raise ValueError("endpoint public interdit")
        self.public_endpoint_enabled = False

    def validate_profile(self, profile: LocalMonitoringProfile) -> None:
        if not isinstance(profile, LocalMonitoringProfile):
            raise ValueError("LocalMonitoringProfile requis")
        if self.public_endpoint_enabled:
            raise ValueError("endpoint public interdit")
        if not profile.local_only:
            raise ValueError("monitoring local requis")
        if profile.external_export_enabled_by_default:
            raise ValueError("export externe par défaut interdit")
        if profile.retention_hours > M013_LOCAL_LOG_RETENTION_HOURS:
            raise ValueError("rétention courte requise")

        for required_metric in _M013_REQUIRED_METRICS:
            if required_metric not in profile.metrics_by_name:
                raise ValueError("métrique absente")
        for required_context in _M013_CONTEXTS:
            if required_context not in profile.contexts:
                raise ValueError("contexte V1 absent")
        for signal in profile.signals:
            self.validate_signal(signal)

    def validate_signal(self, signal: MonitoringSignal) -> None:
        if not isinstance(signal, MonitoringSignal):
            raise ValueError("MonitoringSignal requis")


@dataclass(frozen=True)
class ResourceProfileMeasurement:
    measurement_id: str
    host: str
    resource_kind: str
    metric_name: str
    measured_value: float
    unit: str
    benchmark_source: str
    capacity_decision: str
    explicit_setting: str

    def __init__(
        self,
        *,
        measurement_id: str,
        host: str,
        resource_kind: str,
        metric_name: str,
        measured_value: float,
        unit: str,
        benchmark_source: str,
        capacity_decision: str,
        explicit_setting: str,
    ) -> None:
        parsed_resource_kind = _required_resource_kind(resource_kind)
        parsed_value = _required_positive_number_m013(measured_value, "mesure CPU/GPU/I/O absente")
        object.__setattr__(self, "measurement_id", _required_text_m013(measurement_id, "measurement_id"))
        object.__setattr__(self, "host", _required_text_m013(host, "host"))
        object.__setattr__(self, "resource_kind", parsed_resource_kind)
        object.__setattr__(self, "metric_name", _required_text_m013(metric_name, "metric_name"))
        object.__setattr__(self, "measured_value", parsed_value)
        object.__setattr__(self, "unit", _required_text_m013(unit, "unit"))
        object.__setattr__(self, "benchmark_source", _required_text_m013(benchmark_source, "benchmark_source"))
        object.__setattr__(self, "capacity_decision", _required_text_m013(capacity_decision, "capacity_decision"))
        object.__setattr__(self, "explicit_setting", _required_text_m013(explicit_setting, "explicit_setting"))


@dataclass(frozen=True)
class BenchmarkedResourceSetting:
    setting_name: str
    value: int
    unit: str
    benchmark_source: str
    explicit_default: bool

    def __init__(
        self,
        *,
        setting_name: str,
        value: int,
        unit: str,
        benchmark_source: str,
        explicit_default: bool,
    ) -> None:
        if _required_bool_m013(explicit_default, "explicit_default"):
            raise ValueError("valeur par défaut interdite")
        object.__setattr__(self, "setting_name", _required_text_m013(setting_name, "setting_name"))
        object.__setattr__(self, "value", _required_positive_int_m013(value, "réglage mesuré requis"))
        object.__setattr__(self, "unit", _required_text_m013(unit, "unit"))
        object.__setattr__(
            self,
            "benchmark_source",
            _required_text_m013(benchmark_source, f"{setting_name} sourcée par benchmark requise"),
        )
        object.__setattr__(self, "explicit_default", False)


@dataclass(frozen=True)
class ResourceProfile:
    profile_version: str
    measurements: tuple[ResourceProfileMeasurement, ...]
    vllm_image_digest: str
    model_revision: str
    concurrency: BenchmarkedResourceSetting
    context_length: BenchmarkedResourceSetting
    docker_local_profiled: bool
    resource_kinds: tuple[str, ...]

    def __init__(
        self,
        *,
        profile_version: str,
        measurements: Sequence[ResourceProfileMeasurement],
        vllm_image_digest: str,
        model_revision: str,
        concurrency: BenchmarkedResourceSetting,
        context_length: BenchmarkedResourceSetting,
        docker_local_profiled: bool,
    ) -> None:
        if _required_text_m013(profile_version, "profile_version") != M013_RESOURCE_PROFILE_VERSION:
            raise ValueError("version profil ressources incohérente")
        parsed_measurements = _required_measurement_tuple(measurements)
        parsed_digest = _required_vllm_digest(vllm_image_digest)
        parsed_model_revision = _required_text_m013(model_revision, "révision modèle requise")
        if not isinstance(concurrency, BenchmarkedResourceSetting):
            raise ValueError("concurrence sourcée par benchmark requise")
        if not isinstance(context_length, BenchmarkedResourceSetting):
            raise ValueError("longueur de contexte sourcée par benchmark requise")
        if not _required_bool_m013(docker_local_profiled, "docker_local_profiled"):
            raise ValueError("profil CPU/GPU/I/O docker-local requis")

        object.__setattr__(self, "profile_version", M013_RESOURCE_PROFILE_VERSION)
        object.__setattr__(self, "measurements", parsed_measurements)
        object.__setattr__(self, "vllm_image_digest", parsed_digest)
        object.__setattr__(self, "model_revision", parsed_model_revision)
        object.__setattr__(self, "concurrency", concurrency)
        object.__setattr__(self, "context_length", context_length)
        object.__setattr__(self, "docker_local_profiled", True)
        object.__setattr__(self, "resource_kinds", tuple(sorted({item.resource_kind for item in parsed_measurements})))

    def without_resource(self, resource_kind: str) -> "ResourceProfile":
        parsed_resource_kind = _required_resource_kind(resource_kind)
        return self._replace(
            measurements=tuple(item for item in self.measurements if item.resource_kind != parsed_resource_kind)
        )

    def with_vllm_image_digest(self, digest: str) -> "ResourceProfile":
        return self._replace(vllm_image_digest=digest)

    def with_model_revision(self, model_revision: str) -> "ResourceProfile":
        return self._replace(model_revision=model_revision)

    def with_concurrency_source(self, benchmark_source: str) -> "ResourceProfile":
        return self._replace(
            concurrency=BenchmarkedResourceSetting(
                setting_name="concurrence sourcée par benchmark requise",
                value=self.concurrency.value,
                unit=self.concurrency.unit,
                benchmark_source=benchmark_source,
                explicit_default=False,
            )
        )

    def with_context_length_source(self, benchmark_source: str) -> "ResourceProfile":
        return self._replace(
            context_length=BenchmarkedResourceSetting(
                setting_name="longueur de contexte sourcée par benchmark requise",
                value=self.context_length.value,
                unit=self.context_length.unit,
                benchmark_source=benchmark_source,
                explicit_default=False,
            )
        )

    def with_context_length_default(self, explicit_default: bool) -> "ResourceProfile":
        return self._replace(
            context_length=BenchmarkedResourceSetting(
                setting_name=self.context_length.setting_name,
                value=self.context_length.value,
                unit=self.context_length.unit,
                benchmark_source=self.context_length.benchmark_source,
                explicit_default=explicit_default,
            )
        )

    def _replace(
        self,
        *,
        measurements: Sequence[ResourceProfileMeasurement] | None = None,
        vllm_image_digest: str | None = None,
        model_revision: str | None = None,
        concurrency: BenchmarkedResourceSetting | None = None,
        context_length: BenchmarkedResourceSetting | None = None,
    ) -> "ResourceProfile":
        return ResourceProfile(
            profile_version=self.profile_version,
            measurements=self.measurements if measurements is None else measurements,
            vllm_image_digest=self.vllm_image_digest if vllm_image_digest is None else vllm_image_digest,
            model_revision=self.model_revision if model_revision is None else model_revision,
            concurrency=self.concurrency if concurrency is None else concurrency,
            context_length=self.context_length if context_length is None else context_length,
            docker_local_profiled=self.docker_local_profiled,
        )


class ResourceProfilePolicy:
    def validate_profile(self, profile: ResourceProfile) -> None:
        if not isinstance(profile, ResourceProfile):
            raise ValueError("ResourceProfile requis")
        if not profile.docker_local_profiled:
            raise ValueError("profil CPU/GPU/I/O docker-local requis")
        for resource_kind in _M013_REQUIRED_RESOURCE_KINDS:
            if resource_kind not in profile.resource_kinds:
                raise ValueError("mesure CPU/GPU/I/O absente")
        _required_vllm_digest(profile.vllm_image_digest)
        _required_text_m013(profile.model_revision, "révision modèle requise")
        _required_text_m013(profile.concurrency.benchmark_source, "concurrence sourcée par benchmark requise")
        _required_text_m013(
            profile.context_length.benchmark_source,
            "longueur de contexte sourcée par benchmark requise",
        )
        if profile.context_length.explicit_default or profile.concurrency.explicit_default:
            raise ValueError("valeur par défaut interdite")


def build_m013_local_monitoring_profile() -> LocalMonitoringProfile:
    return LocalMonitoringProfile(
        profile_version=M013_LOCAL_MONITORING_PROFILE_VERSION,
        signals=(
            _m013_signal("MON-M013-001", "platform", "edge-gateway", "v1_health_status", "santé"),
            _m013_signal("MON-M013-002", "SP", "source-processing", "v1_error_total", "erreurs"),
            _m013_signal("MON-M013-003", "KA", "knowledge-access", "v1_latency_ms", "latence"),
            _m013_signal("MON-M013-004", "platform", "job-runtime", "job_queue_depth", "jobs", "job_id"),
            _m013_signal("MON-M013-005", "platform", "outbox", "outbox_pending_total", "outbox", "event_id"),
            _m013_signal("MON-M013-006", "RA", "llm-gateway", "llm_gateway_latency_ms", "gateway"),
            _m013_signal("MON-M013-007", "RA", "llm-gateway", "llm_gateway_output_interrupted_total", "gateway"),
            _m013_signal("MON-M013-008", "platform", "spark-inference", "spark_inference_availability", "Spark"),
            _m013_signal("MON-M013-009", "platform", "backup-restore", "backup_restore_result", "sauvegarde", "restore_test_result"),
            _m013_signal("MON-M013-010", "EV", "v1-acceptance-gate", "v1_gap_status", "écarts", "gap_id"),
            _m013_signal("MON-M013-011", "platform", "network-boundary", "network_security_violation_total", "sécurité"),
            _m013_signal("MON-M013-012", "EG", "evidence-governance", "claim_verification_error_total", "erreurs", "claim_id"),
            _m013_signal("MON-M013-013", "CV", "conversation", "conversation_turn_latency_ms", "latence", "conversation_id"),
            _m013_signal("MON-M013-014", "SD", "strategy-design", "strategy_snapshot_block_total", "écarts", "strategy_id"),
            _m013_signal("MON-M013-015", "EX", "experimentation", "experiment_job_latency_ms", "jobs", "experiment_id"),
        ),
        local_only=True,
        external_export_enabled_by_default=False,
        retention_hours=M013_LOCAL_LOG_RETENTION_HOURS,
    )


def build_m013_resource_profile() -> ResourceProfile:
    return ResourceProfile(
        profile_version=M013_RESOURCE_PROFILE_VERSION,
        measurements=(
            _m013_measurement(
                "RES-M013-CPU",
                "CPU",
                "docker_local_cpu_utilization_percent",
                42.0,
                "percent",
                "cpu_quota=8",
            ),
            _m013_measurement(
                "RES-M013-GPU",
                "GPU",
                "docker_local_gpu_allocation_count",
                1.0,
                "count",
                "gpu_devices=1",
            ),
            _m013_measurement(
                "RES-M013-MEMORY",
                "MEMORY",
                "docker_local_memory_working_set_gib",
                24.0,
                "gibibytes",
                "memory_limit=64GiB",
            ),
            _m013_measurement(
                "RES-M013-IO",
                "IO",
                "docker_local_io_throughput_mib_s",
                512.0,
                "mebibytes_per_second",
                "io_profile=local_nvme",
            ),
            _m013_measurement(
                "RES-M013-STORAGE",
                "STORAGE",
                "docker_local_storage_free_gib",
                1024.0,
                "gibibytes",
                "storage_budget=1TiB",
            ),
        ),
        vllm_image_digest="sha256:6d1f6e9126b8cf23f2ac089a21e2f39c57ef8b5fcb16f312c5e00bb05cda73a9",
        model_revision="nvidia/Gemma-4-31B-IT-NVFP4@LLMRUN-M012-REAL-PATH-0001",
        concurrency=BenchmarkedResourceSetting(
            setting_name="concurrence sourcée par benchmark requise",
            value=4,
            unit="requêtes concurrentes",
            benchmark_source=_M013_BENCHMARK_SOURCE,
            explicit_default=False,
        ),
        context_length=BenchmarkedResourceSetting(
            setting_name="longueur de contexte sourcée par benchmark requise",
            value=8192,
            unit="tokens",
            benchmark_source=_M013_BENCHMARK_SOURCE,
            explicit_default=False,
        ),
        docker_local_profiled=True,
    )


def _m013_signal(
    signal_id: str,
    context: str,
    component: str,
    metric_name: str,
    metric_family: str,
    correlation_field: str = "trace_id",
) -> MonitoringSignal:
    return MonitoringSignal(
        signal_id=signal_id,
        context=context,
        component=component,
        metric_name=metric_name,
        metric_family=metric_family,
        owner=context,
        correlation_field=correlation_field,
        retention_hours=M013_LOCAL_LOG_RETENTION_HOURS,
        local_only=True,
        external_export_enabled_by_default=False,
        contains_full_prompt=False,
        contains_full_evidence=False,
        contains_full_response=False,
        contains_secret=False,
        contains_market_payload=False,
        gap_status_visible=True,
        spark_failure_visible=True,
        backup_restore_visible=True,
        security_boundary_visible=True,
        alert_threshold="p95 ou compteur au-dessus du seuil publié par benchmark M-012",
        threshold_source=_M013_BENCHMARK_SOURCE,
    )


def _m013_measurement(
    measurement_id: str,
    resource_kind: str,
    metric_name: str,
    measured_value: float,
    unit: str,
    explicit_setting: str,
) -> ResourceProfileMeasurement:
    return ResourceProfileMeasurement(
        measurement_id=measurement_id,
        host="docker-local",
        resource_kind=resource_kind,
        metric_name=metric_name,
        measured_value=measured_value,
        unit=unit,
        benchmark_source=_M013_BENCHMARK_SOURCE,
        capacity_decision="accepté pour V1 locale sous charge benchmarkée",
        explicit_setting=explicit_setting,
    )


def redact_secret_fields(
    value: Mapping[str, Any],
    *,
    secret_field_names: Iterable[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservabilityContractError(
            "OBS_REDACTION_MAPPING_REQUIRED",
            "La redaction exige un objet de champs.",
        )
    if secret_field_names is None:
        raise ObservabilityContractError(
            "OBS_SECRET_FIELD_NAMES_REQUIRED",
            "La liste des champs secrets est requise.",
        )
    normalized_secret_fields = {
        _ensure_text(secret_name, "secret_field_name", "OBS_SECRET_FIELD_NAME_REQUIRED").lower()
        for secret_name in secret_field_names
    }
    if len(normalized_secret_fields) == 0:
        raise ObservabilityContractError(
            "OBS_SECRET_FIELD_NAMES_REQUIRED",
            "La liste des champs secrets est vide.",
        )

    redacted: dict[str, Any] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, "field_name", "OBS_FIELD_NAME_REQUIRED")
        if parsed_key.lower() in normalized_secret_fields:
            redacted[parsed_key] = SECRET_MASK
        else:
            redacted[parsed_key] = nested_value
    return redacted


def sha256_text(value: str) -> str:
    parsed_value = _ensure_text(value, "value", "OBS_TEXT_REQUIRED")
    return hashlib.sha256(parsed_value.encode("utf-8")).hexdigest()


def _ensure_text(value: Any, field_name: str, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ObservabilityContractError(code, f"Champ requis absent: {field_name}")
    if value != value.strip():
        raise ObservabilityContractError(code, f"Champ non normalise: {field_name}")
    return value


def _ensure_optional_text(value: Any, field_name: str, code: str) -> str | None:
    if value is None:
        return None
    return _ensure_text(value, field_name, code)


def _ensure_hash(value: Any, field_name: str, code: str) -> str:
    text_value = _ensure_text(value, field_name, code)
    if _HASH_PATTERN.fullmatch(text_value) is None:
        raise ObservabilityContractError(code, f"Hash invalide: {field_name}")
    return text_value


def _ensure_bool(value: Any, field_name: str, code: str) -> None:
    if not isinstance(value, bool):
        raise ObservabilityContractError(code, f"Champ booleen invalide: {field_name}")


def _ensure_non_negative_number(value: Any, field_name: str, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservabilityContractError(code, f"Nombre invalide: {field_name}")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ObservabilityContractError(code, f"Nombre negatif ou infini: {field_name}")


def _ensure_optional_non_negative_number(value: Any, field_name: str, code: str) -> None:
    if value is None:
        return
    _ensure_non_negative_number(value, field_name, code)


def _ensure_positive_integer(value: Any, field_name: str, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ObservabilityContractError(code, f"Entier positif invalide: {field_name}")


def _ensure_non_negative_integer(value: Any, field_name: str, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ObservabilityContractError(code, f"Entier positif ou nul invalide: {field_name}")


def _ensure_optional_non_negative_integer(value: Any, field_name: str, code: str) -> None:
    if value is None:
        return
    _ensure_non_negative_integer(value, field_name, code)


def _freeze_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservabilityContractError("OBS_MAPPING_REQUIRED", f"Objet requis: {field_name}")
    frozen: dict[str, Any] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, f"{field_name}.key", "OBS_FIELD_NAME_REQUIRED")
        frozen[parsed_key] = _freeze_observable_value(nested_value, f"{field_name}.{parsed_key}")
    return MappingProxyType(frozen)


def _freeze_string_mapping(value: Any, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ObservabilityContractError("OBS_MAPPING_REQUIRED", f"Objet requis: {field_name}")
    frozen: dict[str, str] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, f"{field_name}.key", "OBS_FIELD_NAME_REQUIRED")
        frozen[parsed_key] = _ensure_text(
            nested_value,
            f"{field_name}.{parsed_key}",
            "OBS_TAG_VALUE_REQUIRED",
        )
    return MappingProxyType(frozen)


def _freeze_observable_value(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return _ensure_text(value, field_name, "OBS_FIELD_VALUE_REQUIRED")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _ensure_non_negative_number(value, field_name, "OBS_FIELD_VALUE_INVALID")
        return value
    raise ObservabilityContractError(
        "OBS_FIELD_VALUE_INVALID",
        f"Valeur observable invalide: {field_name}",
    )


def _required_text_m013(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(field_name)
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_bool_m013(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _required_positive_int_m013(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} non entier")
    if value <= 0:
        raise ValueError(field_name)
    return value


def _required_positive_number_m013(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} non numérique")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(field_name)
    return parsed


def _required_m013_context(value: Any) -> str:
    text = _required_text_m013(value, "contexte V1")
    if text not in _M013_CONTEXTS:
        raise ValueError("contexte V1 absent")
    return text


def _required_resource_kind(value: Any) -> str:
    text = _required_text_m013(value, "resource_kind")
    if text not in _M013_REQUIRED_RESOURCE_KINDS:
        raise ValueError("mesure CPU/GPU/I/O absente")
    return text


def _required_signal_tuple(values: Sequence[MonitoringSignal]) -> tuple[MonitoringSignal, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("signaux monitoring invalides")
    parsed = tuple(values)
    if len(parsed) == 0:
        raise ValueError("signaux monitoring absents")
    for signal in parsed:
        if not isinstance(signal, MonitoringSignal):
            raise ValueError("MonitoringSignal requis")
    return parsed


def _required_measurement_tuple(
    values: Sequence[ResourceProfileMeasurement],
) -> tuple[ResourceProfileMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("mesures ressources invalides")
    parsed = tuple(values)
    if len(parsed) == 0:
        raise ValueError("mesure CPU/GPU/I/O absente")
    for measurement in parsed:
        if not isinstance(measurement, ResourceProfileMeasurement):
            raise ValueError("ResourceProfileMeasurement requise")
    return parsed


def _required_vllm_digest(value: Any) -> str:
    text = _required_text_m013(value, "image vLLM épinglée requise")
    if not text.startswith("sha256:"):
        raise ValueError("image vLLM épinglée requise")
    digest = text.removeprefix("sha256:")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("image vLLM épinglée requise")
    if len(set(digest)) == 1:
        raise ValueError("image vLLM placeholder interdite")
    return text


__all__ = [
    "BenchmarkedResourceSetting",
    "GatewayObservation",
    "InMemoryObservabilityCollector",
    "JobObservation",
    "LocalMonitoringProfile",
    "M013_LOCAL_LOG_RETENTION_HOURS",
    "M013_LOCAL_MONITORING_PROFILE_VERSION",
    "M013_RESOURCE_PROFILE_VERSION",
    "MonitoringSignal",
    "MonitoringSignalPolicy",
    "ObservabilityContractError",
    "OutboxObservation",
    "ResourceProfile",
    "ResourceProfileMeasurement",
    "ResourceProfilePolicy",
    "SECRET_MASK",
    "StructuredLogEvent",
    "TechnicalMetricEvent",
    "build_m013_local_monitoring_profile",
    "build_m013_resource_profile",
    "redact_secret_fields",
    "sha256_text",
]
