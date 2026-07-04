"""Métriques SD et signaux d'audit de clôture M-010."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_METRIC_SCOPE = "M010_STRATEGY_DESIGN"
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_STRATEGY_ID_PATTERN = re.compile(r"^STRAT-[A-Z0-9][A-Z0-9-]*$")
_SNAPSHOT_ID_PATTERN = re.compile(r"^SVER-[A-Z0-9][A-Z0-9-]*-V\d{6}$")
_ALLOWED_STATUSES = (
    "DRAFT",
    "SPECIFIED",
    "VALIDATING",
    "COMPILABLE",
    "INCOMPLETE",
    "INCONSISTENT",
    "SNAPSHOTTED",
    "SUPERSEDED",
)
_REJECTED_STATUSES = frozenset({"INCOMPLETE", "INCONSISTENT"})
_COMPILABLE_STATUSES = frozenset({"COMPILABLE", "SNAPSHOTTED"})
_ALLOWED_ORIGIN_TYPES = (
    "SOURCE",
    "DEDUCTION",
    "DESIGN_CHOICE",
    "PARAMETER_TO_CALIBRATE",
    "USER_CONSTRAINT",
)
_ALLOWED_SNAPSHOT_EVENTS = (
    "StrategySnapshotCreated",
    "StrategyVersionSuperseded",
)
_NORMATIVE_METRIC_NAMES = (
    "strategy_compilable_rate",
    "strategy_rejection_reason_top",
    "strategy_rule_origin_proportion",
    "strategy_parameter_without_calibration_plan_total",
    "strategy_compatibility_conflict_by_category",
    "strategy_versions_per_strategy",
)


@dataclass(frozen=True)
class StrategyDesignMetricObservation:
    """Observation SD agrégée sans prompt, texte source complet ni payload documentaire."""

    trace_id: str
    strategy_id: str
    strategy_version: int
    compilation_status: str
    rejection_reason_code: str | None
    rule_origin_type: str
    parameter_without_calibration_plan: bool
    compatibility_conflict_category: str | None
    snapshot_event_type: str | None
    supersedes_snapshot_id: str | None
    payload_hash: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "strategy_id", _ensure_strategy_id(self.strategy_id))
        object.__setattr__(
            self,
            "strategy_version",
            _ensure_positive_integer(self.strategy_version, "strategy_version"),
        )
        object.__setattr__(
            self,
            "compilation_status",
            _ensure_allowed_text(self.compilation_status, "compilation_status", _ALLOWED_STATUSES),
        )
        if self.rejection_reason_code is not None:
            object.__setattr__(self, "rejection_reason_code", _ensure_text(self.rejection_reason_code, "rejection_reason_code"))
        object.__setattr__(
            self,
            "rule_origin_type",
            _ensure_allowed_text(self.rule_origin_type, "rule_origin_type", _ALLOWED_ORIGIN_TYPES),
        )
        if not isinstance(self.parameter_without_calibration_plan, bool):
            raise ValueError("parameter_without_calibration_plan non booléen")
        if self.compatibility_conflict_category is not None:
            object.__setattr__(
                self,
                "compatibility_conflict_category",
                _ensure_text(self.compatibility_conflict_category, "compatibility_conflict_category"),
            )
        if self.snapshot_event_type is not None:
            object.__setattr__(
                self,
                "snapshot_event_type",
                _ensure_allowed_text(self.snapshot_event_type, "snapshot_event_type", _ALLOWED_SNAPSHOT_EVENTS),
            )
        if self.supersedes_snapshot_id is not None:
            object.__setattr__(
                self,
                "supersedes_snapshot_id",
                _ensure_snapshot_id(self.supersedes_snapshot_id),
            )
        object.__setattr__(self, "payload_hash", _ensure_sha256(self.payload_hash, "payload_hash"))
        object.__setattr__(self, "observed_at", _ensure_utc_instant(self.observed_at, "observed_at"))
        self._ensure_consistency()

    def _ensure_consistency(self) -> None:
        if self.compilation_status in _COMPILABLE_STATUSES and self.rejection_reason_code is not None:
            raise ValueError("rejection_reason_code incompatible")
        if self.compilation_status in _REJECTED_STATUSES and self.rejection_reason_code is None:
            raise ValueError("rejection_reason_code requis")
        if self.parameter_without_calibration_plan and self.compilation_status in _COMPILABLE_STATUSES:
            raise ValueError("parameter_without_calibration_plan incompatible")
        if self.compatibility_conflict_category is not None and self.compilation_status != "INCONSISTENT":
            raise ValueError("compatibility_conflict_category incompatible")
        if self.snapshot_event_type == "StrategyVersionSuperseded" and self.supersedes_snapshot_id is None:
            raise ValueError("supersedes_snapshot_id requis")
        if self.snapshot_event_type != "StrategyVersionSuperseded" and self.supersedes_snapshot_id is not None:
            raise ValueError("supersedes_snapshot_id incompatible")


@dataclass(frozen=True)
class StrategyDesignMetricSnapshot:
    """Snapshot de métriques M-010 sans contenu de recherche, prompt ou stratégie mutable complète."""

    fixture_id: str
    fixture_path: str
    measured_at: str
    observation_count: int
    normative_metrics: Mapping[str, Any]
    snapshot_event_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(
            self,
            "observation_count",
            _ensure_positive_integer(self.observation_count, "observation_count"),
        )
        object.__setattr__(self, "normative_metrics", _ensure_normative_metrics(self.normative_metrics))
        object.__setattr__(
            self,
            "snapshot_event_counts",
            _ensure_count_mapping(self.snapshot_event_counts, "snapshot_event_counts", allow_empty=True),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "observation_count": self.observation_count,
            "normative_metrics": _json_ready(self.normative_metrics),
            "snapshot_event_counts": dict(self.snapshot_event_counts),
        }


class StrategyDesignMetricsPublisher:
    """Calcule les six métriques normatives SD depuis des observations agrégées."""

    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[StrategyDesignMetricObservation],
        measured_at: str,
    ) -> StrategyDesignMetricSnapshot:
        parsed_fixture_id = _ensure_text(fixture_id, "fixture_id")
        parsed_fixture_path = _ensure_relative_path(fixture_path, "fixture_path")
        parsed_observations = _ensure_observations(observations)
        parsed_measured_at = _ensure_utc_instant(measured_at, "measured_at")
        return StrategyDesignMetricSnapshot(
            fixture_id=parsed_fixture_id,
            fixture_path=parsed_fixture_path,
            measured_at=parsed_measured_at,
            observation_count=len(parsed_observations),
            normative_metrics=_normative_metrics_for(parsed_observations),
            snapshot_event_counts=_snapshot_event_counts_for(parsed_observations),
        )


@dataclass(frozen=True)
class StrategyDesignAuditSignal:
    """Signal SD de publication des métriques sans payload sensible."""

    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: StrategyDesignMetricSnapshot
    strategy_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: StrategyDesignMetricSnapshot,
        strategy_refs: Sequence[Mapping[str, Any]],
        forbidden_sensitive_payloads: Sequence[str],
    ) -> "StrategyDesignAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="strategy_design_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            strategy_refs=strategy_refs,
        )
        assert_no_sensitive_payload_in_audit_payload(
            signal.to_payload(),
            forbidden_sensitive_payloads=forbidden_sensitive_payloads,
        )
        return signal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "audit_signal_id",
            _ensure_prefixed_text(self.audit_signal_id, "SD-AUDIT-", "audit_signal_id"),
        )
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(
            self,
            "signal_name",
            _ensure_expected_text(self.signal_name, "strategy_design_metrics_published", "signal_name"),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, StrategyDesignMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "strategy_refs", _ensure_strategy_refs(self.strategy_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "strategy_refs": tuple(dict(ref) for ref in self.strategy_refs),
            "metrics": self.metric_snapshot.to_payload(),
        }


def assert_no_sensitive_payload_in_audit_payload(
    payload: Mapping[str, Any],
    *,
    forbidden_sensitive_payloads: Sequence[str],
) -> None:
    parsed_payload = _ensure_mapping(payload, "payload")
    forbidden_payloads = _ensure_text_tuple(
        forbidden_sensitive_payloads,
        "forbidden_sensitive_payloads",
        allow_empty=False,
    )
    serialized_payload = json.dumps(_json_ready(parsed_payload), ensure_ascii=False, sort_keys=True)
    for forbidden_payload in forbidden_payloads:
        if forbidden_payload in serialized_payload:
            raise ValueError("payload sensible interdit dans signal d'audit")


def _ensure_observations(
    value: Sequence[StrategyDesignMetricObservation],
) -> tuple[StrategyDesignMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    trace_ids: list[str] = []
    for observation in observations:
        if not isinstance(observation, StrategyDesignMetricObservation):
            raise ValueError("observation invalide")
        if observation.trace_id in trace_ids:
            raise ValueError("trace_id dupliqué")
        trace_ids.append(observation.trace_id)
    return observations


def _normative_metrics_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, Any]:
    return {
        "strategy_compilable_rate": _strategy_compilable_rate_for(observations),
        "strategy_rejection_reason_top": _rejection_reason_counts_for(observations),
        "strategy_rule_origin_proportion": _rule_origin_proportions_for(observations),
        "strategy_parameter_without_calibration_plan_total": sum(
            1
            for observation in observations
            if observation.parameter_without_calibration_plan
        ),
        "strategy_compatibility_conflict_by_category": _compatibility_conflict_counts_for(observations),
        "strategy_versions_per_strategy": _version_counts_for(observations),
    }


def _strategy_compilable_rate_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> float:
    return sum(
        1
        for observation in observations
        if observation.compilation_status in _COMPILABLE_STATUSES
    ) / len(observations)


def _rejection_reason_counts_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.rejection_reason_code is not None:
            counts[observation.rejection_reason_code] = counts.get(observation.rejection_reason_code, 0) + 1
    return {
        key: counts[key]
        for key in sorted(counts, key=lambda item: (-counts[item], item))
    }


def _rule_origin_proportions_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, float]:
    counts = {origin_type: 0 for origin_type in _ALLOWED_ORIGIN_TYPES}
    for observation in observations:
        counts[observation.rule_origin_type] += 1
    return {
        origin_type: counts[origin_type] / len(observations)
        for origin_type in _ALLOWED_ORIGIN_TYPES
        if counts[origin_type] > 0
    }


def _compatibility_conflict_counts_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.compatibility_conflict_category is not None:
            counts[observation.compatibility_conflict_category] = (
                counts.get(observation.compatibility_conflict_category, 0) + 1
            )
    return {key: counts[key] for key in sorted(counts)}


def _version_counts_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, int]:
    versions_by_strategy: dict[str, set[int]] = {}
    for observation in observations:
        versions_by_strategy.setdefault(observation.strategy_id, set()).add(observation.strategy_version)
    return {
        strategy_id: len(versions_by_strategy[strategy_id])
        for strategy_id in sorted(versions_by_strategy)
    }


def _snapshot_event_counts_for(observations: tuple[StrategyDesignMetricObservation, ...]) -> dict[str, int]:
    counts = {event_type: 0 for event_type in _ALLOWED_SNAPSHOT_EVENTS}
    for observation in observations:
        if observation.snapshot_event_type is not None:
            counts[observation.snapshot_event_type] += 1
    return {
        event_type: counts[event_type]
        for event_type in _ALLOWED_SNAPSHOT_EVENTS
        if counts[event_type] > 0
    }


def _ensure_strategy_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("strategy_refs invalides")
    refs = tuple(_ensure_mapping(item, "strategy_ref") for item in value)
    if len(refs) == 0:
        raise ValueError("strategy_refs absentes")
    allowed_keys = frozenset({"strategy_id", "latest_version", "strategy_hash"})
    for ref in refs:
        if frozenset(str(key) for key in ref) != allowed_keys:
            raise ValueError("payload sensible interdit dans strategy_refs")
        ref["strategy_id"] = _ensure_strategy_id(ref["strategy_id"])
        ref["latest_version"] = _ensure_positive_integer(ref["latest_version"], "latest_version")
        ref["strategy_hash"] = _ensure_sha256(ref["strategy_hash"], "strategy_hash")
    return refs


def _ensure_normative_metrics(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("normative_metrics non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _NORMATIVE_METRIC_NAMES:
        raise ValueError("normative_metrics incomplètes")
    return {
        "strategy_compilable_rate": _ensure_ratio(
            value["strategy_compilable_rate"],
            "strategy_compilable_rate",
        ),
        "strategy_rejection_reason_top": _ensure_count_mapping(
            value["strategy_rejection_reason_top"],
            "strategy_rejection_reason_top",
            allow_empty=True,
        ),
        "strategy_rule_origin_proportion": _ensure_ratio_mapping(
            value["strategy_rule_origin_proportion"],
            "strategy_rule_origin_proportion",
        ),
        "strategy_parameter_without_calibration_plan_total": _ensure_non_negative_integer(
            value["strategy_parameter_without_calibration_plan_total"],
            "strategy_parameter_without_calibration_plan_total",
        ),
        "strategy_compatibility_conflict_by_category": _ensure_count_mapping(
            value["strategy_compatibility_conflict_by_category"],
            "strategy_compatibility_conflict_by_category",
            allow_empty=True,
        ),
        "strategy_versions_per_strategy": _ensure_count_mapping(
            value["strategy_versions_per_strategy"],
            "strategy_versions_per_strategy",
            allow_empty=False,
        ),
    }


def _ensure_count_mapping(value: Any, field_name: str, *, allow_empty: bool) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    parsed: dict[str, int] = {}
    for key, count in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_positive_integer(count, field_name)
    return parsed


def _ensure_ratio_mapping(value: Any, field_name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    parsed: dict[str, float] = {}
    for key, ratio in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_ratio(ratio, field_name)
    total = sum(parsed.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=0.000001):
        raise ValueError(f"{field_name} incohérent")
    return parsed


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_text_tuple(value: Sequence[str], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if not allow_empty and len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliqués")
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


def _ensure_strategy_id(value: Any) -> str:
    text = _ensure_text(value, "strategy_id")
    if _STRATEGY_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("strategy_id invalide")
    return text


def _ensure_snapshot_id(value: Any) -> str:
    text = _ensure_text(value, "snapshot_id")
    if _SNAPSHOT_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("snapshot_id invalide")
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
        raise ValueError(f"{field_name} non normalisé")
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
    "StrategyDesignAuditSignal",
    "StrategyDesignMetricObservation",
    "StrategyDesignMetricSnapshot",
    "StrategyDesignMetricsPublisher",
    "assert_no_sensitive_payload_in_audit_payload",
]
