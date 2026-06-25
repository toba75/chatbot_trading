"""Primitives locales d'observabilite technique M-002."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


SECRET_MASK = "<secret-masked>"
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


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


__all__ = [
    "GatewayObservation",
    "InMemoryObservabilityCollector",
    "JobObservation",
    "ObservabilityContractError",
    "OutboxObservation",
    "SECRET_MASK",
    "StructuredLogEvent",
    "TechnicalMetricEvent",
    "redact_secret_fields",
    "sha256_text",
]
