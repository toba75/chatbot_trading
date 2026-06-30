"""Métriques RA et signaux d'audit de clôture M-007."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_METRIC_SCOPE = "M007_VERIFIED_DOCUMENTARY_ANSWER"
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_ALLOWED_SUPPORT_STATUSES = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
)
_ALLOWED_KNOWLEDGE_GAP_TYPES = (
    "COVERAGE_OBLIGATION_MISSING",
    "CURRENT_DATA_REQUIRED",
)
_ALLOWED_CONTRADICTION_CLASSIFICATIONS = (
    "DIRECT_CONFLICT",
    "DIFFERENT_HORIZON",
    "DIFFERENT_METRIC",
    "DIFFERENT_FREQUENCY",
    "DIFFERENT_UNIVERSE",
    "RESOLVED_BY_QUALIFICATION",
)
_ALLOWED_ABSTENTION_REASONS = ("CURRENT_DATA_REQUIRED",)
_NORMATIVE_SIGNAL_NAMES = (
    "answer_support_status_total",
    "answer_unsupported_assertions_removed_total",
    "answer_citation_resolution_failed_total",
    "answer_abstention_total",
    "research_coverage_obligation_met_total",
    "answer_conflict_detected_total",
    "answer_knowledge_gap_total",
    "answer_evidence_set_sealed_total",
    "answer_model_draft_total",
)
_RATE_NAMES = (
    "supported_rate",
    "partially_supported_rate",
    "insufficient_evidence_rate",
    "conflicting_evidence_rate",
    "abstention_rate",
)
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")
_ANSWER_ID_PATTERN = re.compile(r"^ANS-[A-Z0-9][A-Z0-9-]*$")


@dataclass(frozen=True)
class ResponseMetricObservation:
    """Observation RA agrégée sans prompt, brouillon, réponse complète ni preuve complète."""

    trace_id: str
    research_case_id: str
    answer_id: str
    support_status: str
    citation_count: int
    citation_resolution_failed_count: int
    unsupported_assertion_count: int
    coverage_obligation_count: int
    coverage_obligation_met_count: int
    knowledge_gap_types: Sequence[str]
    contradiction_classifications: Sequence[str]
    abstention_reason: str | None
    evidence_set_sealed: bool
    model_draft_hash: str
    started_at: str
    completed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(self, "support_status", _ensure_support_status(self.support_status))
        object.__setattr__(
            self,
            "citation_count",
            _ensure_non_negative_integer(self.citation_count, "citation_count"),
        )
        object.__setattr__(
            self,
            "citation_resolution_failed_count",
            _ensure_non_negative_integer(
                self.citation_resolution_failed_count,
                "citation_resolution_failed_count",
            ),
        )
        object.__setattr__(
            self,
            "unsupported_assertion_count",
            _ensure_non_negative_integer(
                self.unsupported_assertion_count,
                "unsupported_assertion_count",
            ),
        )
        object.__setattr__(
            self,
            "coverage_obligation_count",
            _ensure_positive_integer(self.coverage_obligation_count, "coverage_obligation_count"),
        )
        object.__setattr__(
            self,
            "coverage_obligation_met_count",
            _ensure_non_negative_integer(
                self.coverage_obligation_met_count,
                "coverage_obligation_met_count",
            ),
        )
        if self.coverage_obligation_met_count > self.coverage_obligation_count:
            raise ValueError("coverage_obligation_met_count incoherent")
        object.__setattr__(
            self,
            "knowledge_gap_types",
            _ensure_allowed_text_tuple(
                self.knowledge_gap_types,
                "knowledge_gap_types",
                _ALLOWED_KNOWLEDGE_GAP_TYPES,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "contradiction_classifications",
            _ensure_allowed_text_tuple(
                self.contradiction_classifications,
                "contradiction_classifications",
                _ALLOWED_CONTRADICTION_CLASSIFICATIONS,
                allow_empty=True,
            ),
        )
        if self.abstention_reason is not None:
            object.__setattr__(
                self,
                "abstention_reason",
                _ensure_allowed_text(self.abstention_reason, "abstention_reason", _ALLOWED_ABSTENTION_REASONS),
            )
        if not isinstance(self.evidence_set_sealed, bool):
            raise ValueError("evidence_set_sealed non booleen")
        if not self.evidence_set_sealed:
            raise ValueError("evidence_set non scelle")
        object.__setattr__(self, "model_draft_hash", _ensure_sha256(self.model_draft_hash, "model_draft_hash"))
        object.__setattr__(self, "started_at", _ensure_utc_instant(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", _ensure_utc_instant(self.completed_at, "completed_at"))
        self._ensure_status_consistency()

    def publication_latency_seconds(self) -> float:
        started_at = _parse_utc_instant(self.started_at)
        completed_at = _parse_utc_instant(self.completed_at)
        latency_seconds = (completed_at - started_at).total_seconds()
        if latency_seconds < 0.0:
            raise ValueError("delai publication negatif")
        return latency_seconds

    def _ensure_status_consistency(self) -> None:
        if self.support_status == "SUPPORTED":
            if self.citation_count == 0:
                raise ValueError("citation requise pour SUPPORTED")
            if self.unsupported_assertion_count > 0:
                raise ValueError("SUPPORTED avec assertion non supportee")
            if len(self.knowledge_gap_types) > 0:
                raise ValueError("SUPPORTED avec knowledge_gap")
            if len(self.contradiction_classifications) > 0:
                raise ValueError("SUPPORTED avec contradiction")
            if self.abstention_reason is not None:
                raise ValueError("SUPPORTED avec abstention_reason")
        elif self.support_status == "PARTIALLY_SUPPORTED":
            if self.citation_count == 0:
                raise ValueError("citation requise pour PARTIALLY_SUPPORTED")
            if (
                self.unsupported_assertion_count == 0
                and len(self.knowledge_gap_types) == 0
                and len(self.contradiction_classifications) == 0
            ):
                raise ValueError("PARTIALLY_SUPPORTED sans qualification")
            if self.abstention_reason is not None:
                raise ValueError("PARTIALLY_SUPPORTED avec abstention_reason")
        elif self.support_status == "INSUFFICIENT_EVIDENCE":
            if len(self.knowledge_gap_types) == 0:
                raise ValueError("knowledge_gap requis pour INSUFFICIENT_EVIDENCE")
            if self.abstention_reason is not None:
                raise ValueError("INSUFFICIENT_EVIDENCE avec abstention_reason")
        elif self.support_status == "CONFLICTING_EVIDENCE":
            if len(self.contradiction_classifications) == 0:
                raise ValueError("contradiction requise pour CONFLICTING_EVIDENCE")
            if self.abstention_reason is not None:
                raise ValueError("CONFLICTING_EVIDENCE avec abstention_reason")
        elif self.support_status == "REQUIRES_CURRENT_DATA":
            if self.abstention_reason is None:
                raise ValueError("abstention_reason requis")
            if self.abstention_reason != "CURRENT_DATA_REQUIRED":
                raise ValueError("abstention_reason CURRENT_DATA_REQUIRED requis")
            if "CURRENT_DATA_REQUIRED" not in self.knowledge_gap_types:
                raise ValueError("knowledge_gap CURRENT_DATA_REQUIRED requis")
            if self.citation_count != 0:
                raise ValueError("citation interdite pour REQUIRES_CURRENT_DATA")


@dataclass(frozen=True)
class ResearchAnsweringMetricSnapshot:
    """Snapshot de métriques M-007 publié sans contenu documentaire sensible."""

    fixture_id: str
    fixture_path: str
    measured_at: str
    response_count: int
    support_status_counts: Mapping[str, int]
    rates: Mapping[str, float]
    citation_count_distribution: Mapping[str, int]
    knowledge_gap_type_counts: Mapping[str, int]
    contradiction_classification_counts: Mapping[str, int]
    abstention_reason_counts: Mapping[str, int]
    average_publication_latency_seconds: float
    normative_signals: Mapping[str, int | float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(
            self,
            "response_count",
            _ensure_positive_integer(self.response_count, "response_count"),
        )
        object.__setattr__(
            self,
            "support_status_counts",
            _ensure_support_status_counts(self.support_status_counts),
        )
        if sum(self.support_status_counts.values()) != self.response_count:
            raise ValueError("support_status_counts incoherents")
        object.__setattr__(self, "rates", _ensure_rates(self.rates))
        object.__setattr__(
            self,
            "citation_count_distribution",
            _ensure_count_mapping(self.citation_count_distribution, "citation_count_distribution"),
        )
        object.__setattr__(
            self,
            "knowledge_gap_type_counts",
            _ensure_count_mapping(self.knowledge_gap_type_counts, "knowledge_gap_type_counts"),
        )
        object.__setattr__(
            self,
            "contradiction_classification_counts",
            _ensure_count_mapping(
                self.contradiction_classification_counts,
                "contradiction_classification_counts",
            ),
        )
        object.__setattr__(
            self,
            "abstention_reason_counts",
            _ensure_count_mapping(self.abstention_reason_counts, "abstention_reason_counts"),
        )
        object.__setattr__(
            self,
            "average_publication_latency_seconds",
            _ensure_non_negative_float(
                self.average_publication_latency_seconds,
                "average_publication_latency_seconds",
            ),
        )
        object.__setattr__(
            self,
            "normative_signals",
            _ensure_normative_signals(self.normative_signals),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "response_count": self.response_count,
            "support_status_counts": dict(self.support_status_counts),
            "rates": dict(self.rates),
            "citation_count_distribution": dict(self.citation_count_distribution),
            "knowledge_gap_type_counts": dict(self.knowledge_gap_type_counts),
            "contradiction_classification_counts": dict(self.contradiction_classification_counts),
            "abstention_reason_counts": dict(self.abstention_reason_counts),
            "average_publication_latency_seconds": self.average_publication_latency_seconds,
            "normative_signals": dict(self.normative_signals),
        }


class ResearchAnsweringMetricsPublisher:
    """Calcule les métriques RA déterministes depuis des observations agrégées."""

    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[ResponseMetricObservation],
        measured_at: str,
    ) -> ResearchAnsweringMetricSnapshot:
        parsed_fixture_id = _ensure_text(fixture_id, "fixture_id")
        parsed_fixture_path = _ensure_relative_path(fixture_path, "fixture_path")
        parsed_observations = _ensure_observations(observations)
        parsed_measured_at = _ensure_utc_instant(measured_at, "measured_at")
        response_count = len(parsed_observations)
        support_status_counts = _support_status_counts_for(parsed_observations)
        average_latency_seconds = _average_publication_latency_seconds(parsed_observations)

        return ResearchAnsweringMetricSnapshot(
            fixture_id=parsed_fixture_id,
            fixture_path=parsed_fixture_path,
            measured_at=parsed_measured_at,
            response_count=response_count,
            support_status_counts=support_status_counts,
            rates=_rates_for(status_counts=support_status_counts, response_count=response_count),
            citation_count_distribution=_citation_count_distribution_for(parsed_observations),
            knowledge_gap_type_counts=_knowledge_gap_type_counts_for(parsed_observations),
            contradiction_classification_counts=_contradiction_classification_counts_for(parsed_observations),
            abstention_reason_counts=_abstention_reason_counts_for(parsed_observations),
            average_publication_latency_seconds=average_latency_seconds,
            normative_signals=_normative_signals_for(
                observations=parsed_observations,
                support_status_counts=support_status_counts,
            ),
        )


@dataclass(frozen=True)
class ResearchAnsweringAuditSignal:
    """Signal RA de publication des métriques sans prompt ni texte complet."""

    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: ResearchAnsweringMetricSnapshot
    answer_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: ResearchAnsweringMetricSnapshot,
        answer_refs: Sequence[Mapping[str, Any]],
        forbidden_sensitive_payloads: Sequence[str],
    ) -> "ResearchAnsweringAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="research_answering_response_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            answer_refs=answer_refs,
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
            _ensure_prefixed_text(self.audit_signal_id, "RA-AUDIT-", "audit_signal_id"),
        )
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(
            self,
            "signal_name",
            _ensure_expected_text(
                self.signal_name,
                "research_answering_response_metrics_published",
                "signal_name",
            ),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, ResearchAnsweringMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "answer_refs", _ensure_answer_refs(self.answer_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "answer_refs": tuple(dict(answer_ref) for answer_ref in self.answer_refs),
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


def _support_status_counts_for(observations: tuple[ResponseMetricObservation, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _ALLOWED_SUPPORT_STATUSES}
    for observation in observations:
        counts[observation.support_status] += 1
    return counts


def _rates_for(*, status_counts: Mapping[str, int], response_count: int) -> dict[str, float]:
    return {
        "supported_rate": status_counts["SUPPORTED"] / response_count,
        "partially_supported_rate": status_counts["PARTIALLY_SUPPORTED"] / response_count,
        "insufficient_evidence_rate": status_counts["INSUFFICIENT_EVIDENCE"] / response_count,
        "conflicting_evidence_rate": status_counts["CONFLICTING_EVIDENCE"] / response_count,
        "abstention_rate": status_counts["REQUIRES_CURRENT_DATA"] / response_count,
    }


def _citation_count_distribution_for(observations: tuple[ResponseMetricObservation, ...]) -> dict[str, int]:
    counts: dict[int, int] = {}
    for observation in observations:
        counts[observation.citation_count] = counts.get(observation.citation_count, 0) + 1
    return {str(citation_count): counts[citation_count] for citation_count in sorted(counts)}


def _knowledge_gap_type_counts_for(observations: tuple[ResponseMetricObservation, ...]) -> dict[str, int]:
    counts = {gap_type: 0 for gap_type in _ALLOWED_KNOWLEDGE_GAP_TYPES}
    for observation in observations:
        for gap_type in observation.knowledge_gap_types:
            counts[gap_type] += 1
    return {gap_type: counts[gap_type] for gap_type in _ALLOWED_KNOWLEDGE_GAP_TYPES if counts[gap_type] > 0}


def _contradiction_classification_counts_for(observations: tuple[ResponseMetricObservation, ...]) -> dict[str, int]:
    counts = {classification: 0 for classification in _ALLOWED_CONTRADICTION_CLASSIFICATIONS}
    for observation in observations:
        for classification in observation.contradiction_classifications:
            counts[classification] += 1
    return {
        classification: counts[classification]
        for classification in _ALLOWED_CONTRADICTION_CLASSIFICATIONS
        if counts[classification] > 0
    }


def _abstention_reason_counts_for(observations: tuple[ResponseMetricObservation, ...]) -> dict[str, int]:
    counts = {reason: 0 for reason in _ALLOWED_ABSTENTION_REASONS}
    for observation in observations:
        if observation.abstention_reason is not None:
            counts[observation.abstention_reason] += 1
    return {reason: counts[reason] for reason in _ALLOWED_ABSTENTION_REASONS if counts[reason] > 0}


def _average_publication_latency_seconds(observations: tuple[ResponseMetricObservation, ...]) -> float:
    latencies = tuple(observation.publication_latency_seconds() for observation in observations)
    if len(latencies) == 0:
        raise ValueError("delai publication absent")
    return sum(latencies) / len(latencies)


def _normative_signals_for(
    *,
    observations: tuple[ResponseMetricObservation, ...],
    support_status_counts: Mapping[str, int],
) -> dict[str, int | float]:
    return {
        "answer_support_status_total": len(observations),
        "answer_unsupported_assertions_removed_total": sum(
            observation.unsupported_assertion_count
            for observation in observations
        ),
        "answer_citation_resolution_failed_total": sum(
            observation.citation_resolution_failed_count
            for observation in observations
        ),
        "answer_abstention_total": support_status_counts["REQUIRES_CURRENT_DATA"],
        "research_coverage_obligation_met_total": sum(
            observation.coverage_obligation_met_count
            for observation in observations
        ),
        "answer_conflict_detected_total": sum(
            len(observation.contradiction_classifications)
            for observation in observations
        ),
        "answer_knowledge_gap_total": sum(
            len(observation.knowledge_gap_types)
            for observation in observations
        ),
        "answer_evidence_set_sealed_total": sum(
            1
            for observation in observations
            if observation.evidence_set_sealed
        ),
        "answer_model_draft_total": sum(
            1
            for observation in observations
            if observation.model_draft_hash
        ),
    }


def _ensure_observations(value: Sequence[ResponseMetricObservation]) -> tuple[ResponseMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    trace_ids: list[str] = []
    for observation in observations:
        if not isinstance(observation, ResponseMetricObservation):
            raise ValueError("observation invalide")
        if observation.trace_id in trace_ids:
            raise ValueError("trace_id duplique")
        trace_ids.append(observation.trace_id)
    return observations


def _ensure_answer_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_refs invalides")
    answer_refs = tuple(_ensure_mapping(item, "answer_ref") for item in value)
    if len(answer_refs) == 0:
        raise ValueError("answer_refs absentes")
    allowed_keys = frozenset(
        {
            "answer_id",
            "answer_version",
            "support_status",
            "answer_text_hash",
            "citation_ids",
            "knowledge_gap_ids",
            "contradiction_ids",
        }
    )
    for answer_ref in answer_refs:
        actual_keys = frozenset(str(key) for key in answer_ref)
        if actual_keys != allowed_keys:
            raise ValueError("payload sensible interdit dans answer_refs")
        answer_ref["answer_id"] = _ensure_answer_id(answer_ref["answer_id"])
        answer_ref["answer_version"] = _ensure_positive_integer(answer_ref["answer_version"], "answer_version")
        answer_ref["support_status"] = _ensure_support_status(answer_ref["support_status"])
        answer_ref["answer_text_hash"] = _ensure_sha256(answer_ref["answer_text_hash"], "answer_text_hash")
        answer_ref["citation_ids"] = _ensure_prefixed_text_tuple(
            answer_ref["citation_ids"],
            "CIT-",
            "citation_ids",
            allow_empty=True,
        )
        answer_ref["knowledge_gap_ids"] = _ensure_prefixed_text_tuple(
            answer_ref["knowledge_gap_ids"],
            "KGP-",
            "knowledge_gap_ids",
            allow_empty=True,
        )
        answer_ref["contradiction_ids"] = _ensure_prefixed_text_tuple(
            answer_ref["contradiction_ids"],
            "REL-",
            "contradiction_ids",
            allow_empty=True,
        )
    return answer_refs


def _ensure_support_status_counts(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("support_status_counts non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _ALLOWED_SUPPORT_STATUSES:
        raise ValueError("support_status_counts incomplets")
    return {
        status: _ensure_non_negative_integer(value[status], status)
        for status in _ALLOWED_SUPPORT_STATUSES
    }


def _ensure_rates(value: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("rates non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _RATE_NAMES:
        raise ValueError("rates incomplets")
    return {rate_name: _ensure_ratio(value[rate_name], rate_name) for rate_name in _RATE_NAMES}


def _ensure_normative_signals(value: Mapping[str, int | float]) -> dict[str, int | float]:
    if not isinstance(value, Mapping):
        raise ValueError("normative_signals non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _NORMATIVE_SIGNAL_NAMES:
        raise ValueError("normative_signals incomplets")
    return {
        signal_name: _ensure_non_negative_integer(value[signal_name], signal_name)
        for signal_name in _NORMATIVE_SIGNAL_NAMES
    }


def _ensure_count_mapping(value: Mapping[str, int], field_name: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    parsed: dict[str, int] = {}
    for key, count in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_positive_integer(count, field_name)
    return parsed


def _ensure_allowed_text_tuple(
    value: Sequence[str],
    field_name: str,
    allowed_values: Sequence[str],
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    values = _ensure_text_tuple(value, field_name, allow_empty=allow_empty)
    allowed = frozenset(allowed_values)
    for item in values:
        if item not in allowed:
            raise ValueError(f"{field_name} invalide")
    return values


def _ensure_allowed_text(value: Any, field_name: str, allowed_values: Sequence[str]) -> str:
    text = _ensure_text(value, field_name)
    if text not in allowed_values:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_support_status(value: Any) -> str:
    return _ensure_allowed_text(value, "support_status", _ALLOWED_SUPPORT_STATUSES)


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
        raise ValueError(f"{field_name} dupliques")
    return parsed


def _ensure_prefixed_text_tuple(
    value: Sequence[str],
    expected_prefix: str,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    parsed = _ensure_text_tuple(value, field_name, allow_empty=allow_empty)
    for item in parsed:
        _ensure_prefixed_text(item, expected_prefix, field_name)
    return parsed


def _ensure_prefixed_text(value: Any, expected_prefix: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(expected_prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_expected_text(value: Any, expected: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if text != expected:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_relative_path(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name).replace("\\", "/")
    if text.startswith("/") or text.startswith("../") or "/../" in text or ":" in text:
        raise ValueError(f"{field_name} hors depot")
    return text


def _ensure_research_case_id(value: Any) -> str:
    text = _ensure_text(value, "research_case_id")
    if _RESEARCH_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("research_case_id invalide")
    return text


def _ensure_answer_id(value: Any) -> str:
    text = _ensure_text(value, "answer_id")
    if _ANSWER_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("answer_id invalide")
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
    parsed = _ensure_non_negative_float(value, field_name)
    if parsed > 1.0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _ensure_non_negative_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _parse_utc_instant(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "ResearchAnsweringAuditSignal",
    "ResearchAnsweringMetricSnapshot",
    "ResearchAnsweringMetricsPublisher",
    "ResponseMetricObservation",
    "assert_no_sensitive_payload_in_audit_payload",
]
