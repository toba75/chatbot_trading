"""Metriques EX et signaux d'audit M-011."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_METRIC_SCOPE = "M011_EXPERIMENTATION"
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_EXPERIMENT_ID_PATTERN = re.compile(r"^EXP-[A-Z0-9][A-Z0-9-]*$")
_ALLOWED_STATUSES = ("PLANNED", "SCHEDULED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
_NORMATIVE_METRIC_NAMES = (
    "experiment_reproducible_rate",
    "experiment_failure_rate_by_cause",
    "negative_experiment_retention_ratio",
    "experiment_without_complete_cost_model_total",
    "coherent_repeat_count",
    "invalidated_result_ratio",
)


@dataclass(frozen=True)
class ExperimentMetricObservation:
    trace_id: str
    experiment_id: str
    status: str
    failure_cause: str | None
    negative_result_retained: bool
    cost_model_complete: bool
    repeat_coherent: bool
    invalidated_after_audit: bool
    payload_hash: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "experiment_id", _ensure_experiment_id(self.experiment_id))
        object.__setattr__(self, "status", _ensure_allowed_text(self.status, "status", _ALLOWED_STATUSES))
        if self.failure_cause is not None:
            object.__setattr__(self, "failure_cause", _ensure_text(self.failure_cause, "failure_cause"))
        for field_name in (
            "negative_result_retained",
            "cost_model_complete",
            "repeat_coherent",
            "invalidated_after_audit",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} non booleen")
        object.__setattr__(self, "payload_hash", _ensure_sha256(self.payload_hash, "payload_hash"))
        object.__setattr__(self, "observed_at", _ensure_utc_instant(self.observed_at, "observed_at"))
        if self.status == "FAILED" and self.failure_cause is None:
            raise ValueError("failure_cause requis")
        if self.status != "FAILED" and self.failure_cause is not None:
            raise ValueError("failure_cause incompatible")


@dataclass(frozen=True)
class ExperimentMetricSnapshot:
    fixture_id: str
    fixture_path: str
    measured_at: str
    observation_count: int
    normative_metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(self, "observation_count", _ensure_positive_integer(self.observation_count, "observation_count"))
        object.__setattr__(self, "normative_metrics", _ensure_normative_metrics(self.normative_metrics))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "observation_count": self.observation_count,
            "normative_metrics": _json_ready(self.normative_metrics),
        }


class ExperimentMetricsPublisher:
    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[ExperimentMetricObservation],
        measured_at: str,
    ) -> ExperimentMetricSnapshot:
        parsed_observations = _ensure_observations(observations)
        return ExperimentMetricSnapshot(
            fixture_id=_ensure_text(fixture_id, "fixture_id"),
            fixture_path=_ensure_relative_path(fixture_path, "fixture_path"),
            measured_at=_ensure_utc_instant(measured_at, "measured_at"),
            observation_count=len(parsed_observations),
            normative_metrics=_normative_metrics_for(parsed_observations),
        )


@dataclass(frozen=True)
class ExperimentAuditSignal:
    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: ExperimentMetricSnapshot
    experiment_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: ExperimentMetricSnapshot,
        experiment_refs: Sequence[Mapping[str, Any]],
        forbidden_sensitive_payloads: Sequence[str],
    ) -> "ExperimentAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="experimentation_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            experiment_refs=experiment_refs,
        )
        assert_no_sensitive_payload_in_audit_payload(
            signal.to_payload(),
            forbidden_sensitive_payloads=forbidden_sensitive_payloads,
        )
        return signal

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_signal_id", _ensure_prefixed_text(self.audit_signal_id, "EX-AUDIT-", "audit_signal_id"))
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "signal_name", _ensure_expected_text(self.signal_name, "experimentation_metrics_published", "signal_name"))
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, ExperimentMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "experiment_refs", _ensure_experiment_refs(self.experiment_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "experiment_refs": tuple(dict(ref) for ref in self.experiment_refs),
            "metrics": self.metric_snapshot.to_payload(),
        }


def assert_no_sensitive_payload_in_audit_payload(
    payload: Mapping[str, Any],
    *,
    forbidden_sensitive_payloads: Sequence[str],
) -> None:
    serialized = json.dumps(_json_ready(_ensure_mapping(payload, "payload")), ensure_ascii=False, sort_keys=True)
    for forbidden_payload in _ensure_text_tuple(
        forbidden_sensitive_payloads,
        "forbidden_sensitive_payloads",
        allow_empty=False,
    ):
        if forbidden_payload in serialized:
            raise ValueError("payload sensible interdit dans signal d'audit")


def _normative_metrics_for(observations: tuple[ExperimentMetricObservation, ...]) -> dict[str, Any]:
    failed_count = sum(1 for observation in observations if observation.status == "FAILED")
    negative_count = sum(1 for observation in observations if observation.status == "FAILED" or _is_negative(observation))
    invalidated_count = sum(1 for observation in observations if observation.invalidated_after_audit)
    return {
        "experiment_reproducible_rate": (
            sum(1 for observation in observations if observation.repeat_coherent) / len(observations)
        ),
        "experiment_failure_rate_by_cause": _failure_rates_for(observations, failed_count),
        "negative_experiment_retention_ratio": (
            1.0
            if negative_count == 0
            else sum(1 for observation in observations if observation.negative_result_retained) / negative_count
        ),
        "experiment_without_complete_cost_model_total": sum(
            1 for observation in observations if not observation.cost_model_complete
        ),
        "coherent_repeat_count": sum(1 for observation in observations if observation.repeat_coherent),
        "invalidated_result_ratio": invalidated_count / len(observations),
    }


def _failure_rates_for(observations: tuple[ExperimentMetricObservation, ...], failed_count: int) -> dict[str, float]:
    if failed_count == 0:
        return {}
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.failure_cause is not None:
            counts[observation.failure_cause] = counts.get(observation.failure_cause, 0) + 1
    return {key: counts[key] / failed_count for key in sorted(counts)}


def _is_negative(observation: ExperimentMetricObservation) -> bool:
    return observation.status == "FAILED"


def _ensure_observations(value: Sequence[ExperimentMetricObservation]) -> tuple[ExperimentMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    trace_ids = set()
    for observation in observations:
        if not isinstance(observation, ExperimentMetricObservation):
            raise ValueError("observation invalide")
        if observation.trace_id in trace_ids:
            raise ValueError("trace_id duplique")
        trace_ids.add(observation.trace_id)
    return observations


def _ensure_normative_metrics(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("normative_metrics non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _NORMATIVE_METRIC_NAMES:
        raise ValueError("normative_metrics incompletes")
    return {
        "experiment_reproducible_rate": _ensure_ratio(value["experiment_reproducible_rate"], "experiment_reproducible_rate"),
        "experiment_failure_rate_by_cause": _ensure_ratio_mapping(value["experiment_failure_rate_by_cause"], "experiment_failure_rate_by_cause", allow_empty=True),
        "negative_experiment_retention_ratio": _ensure_ratio(value["negative_experiment_retention_ratio"], "negative_experiment_retention_ratio"),
        "experiment_without_complete_cost_model_total": _ensure_non_negative_integer(value["experiment_without_complete_cost_model_total"], "experiment_without_complete_cost_model_total"),
        "coherent_repeat_count": _ensure_non_negative_integer(value["coherent_repeat_count"], "coherent_repeat_count"),
        "invalidated_result_ratio": _ensure_ratio(value["invalidated_result_ratio"], "invalidated_result_ratio"),
    }


def _ensure_ratio_mapping(value: Any, field_name: str, *, allow_empty: bool) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    return {_ensure_text(key, field_name): _ensure_ratio(ratio, field_name) for key, ratio in value.items()}


def _ensure_experiment_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("experiment_refs invalides")
    refs = tuple(_ensure_mapping(item, "experiment_ref") for item in value)
    if len(refs) == 0:
        raise ValueError("experiment_refs absentes")
    for ref in refs:
        if frozenset(ref.keys()) != {"experiment_id", "result_hash"}:
            raise ValueError("payload sensible interdit dans experiment_refs")
        ref["experiment_id"] = _ensure_experiment_id(ref["experiment_id"])
        ref["result_hash"] = _ensure_sha256(ref["result_hash"], "result_hash")
    return refs


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_text_tuple(value: Sequence[str], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0 and not allow_empty:
        raise ValueError(f"{field_name} absents")
    return parsed


def _ensure_allowed_text(value: Any, field_name: str, allowed_values: Sequence[str]) -> str:
    text = _ensure_text(value, field_name)
    if text not in allowed_values:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_expected_text(value: Any, expected: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if text != expected:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_prefixed_text(value: Any, expected_prefix: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(expected_prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_relative_path(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name).replace("\\", "/")
    if text.startswith("/") or text.startswith("../") or "/../" in text or ":" in text:
        raise ValueError(f"{field_name} hors depot")
    return text


def _ensure_experiment_id(value: Any) -> str:
    text = _ensure_text(value, "experiment_id")
    if _EXPERIMENT_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("experiment_id invalide")
    return text


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


def _ensure_utc_instant(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "ExperimentAuditSignal",
    "ExperimentMetricObservation",
    "ExperimentMetricSnapshot",
    "ExperimentMetricsPublisher",
    "assert_no_sensitive_payload_in_audit_payload",
]
