"""Metriques RA approfondies et signaux d'audit de cloture M-009."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_METRIC_SCOPE = "M009_DEEP_RESEARCH"
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")
_ANSWER_ID_PATTERN = re.compile(r"^ANS-[A-Z0-9][A-Z0-9-]*$")
_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_ALLOWED_SUPPORT_STATUSES = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
)
_ALLOWED_COVERAGE_STATUSES = ("COVERED", "INSUFFICIENT", "OUT_OF_SCOPE")
_ALLOWED_CONTRADICTION_CLASSIFICATIONS = (
    "DIRECT_CONFLICT",
    "POSITIVE_COMPATIBILITY",
    "GENUINE_CONTRADICTION",
    "APPARENT_CONTRADICTION",
    "CONTEXT_DEPENDENT",
    "DIFFERENT_HORIZON",
    "DIFFERENT_METRIC",
    "DIFFERENT_FREQUENCY",
    "DIFFERENT_UNIVERSE",
    "DIFFERENT_COST_ASSUMPTION",
    "DIFFERENT_REGIME",
    "RESOLVED_BY_QUALIFICATION",
)
_ALLOWED_DOCUMENTARY_GAP_TYPES = (
    "COVERAGE_OBLIGATION_MISSING",
    "CURRENT_DATA_REQUIRED",
    "SOURCE_DIVERSIFICATION_INSUFFICIENT",
    "CLAIM_DEPENDENCY_UNRESOLVED",
)
_ALLOWED_SUPPORT_DECISION_BASES = (
    "DEEP_RESEARCH_POLICY",
    "COVERAGE_AND_CLAIM_POLICY",
    "PUBLIC_ERROR",
)
_NORMATIVE_SIGNAL_NAMES = (
    "deep_research_requested_total",
    "deep_research_plan_created_total",
    "deep_research_coverage_obligation_met_total",
    "deep_research_coverage_obligation_missing_total",
    "deep_research_query_executed_total",
    "deep_research_independent_source_group_total",
    "deep_research_contradiction_classified_total",
    "deep_research_documentary_gap_total",
    "deep_research_support_status_total",
    "deep_research_public_error_total",
    "deep_research_synthesis_published_total",
    "deep_research_claim_version_recorded_total",
)
_DOCUMENTARY_DIVERSITY_KEYS = (
    "distinct_document_total",
    "minimum_document_count_per_research",
    "maximum_document_count_per_research",
)


@dataclass(frozen=True)
class DeepResearchMetricObservation:
    """Observation RA approfondie agregee sans source, prompt, reponse complete ni donnee personnelle."""

    trace_id: str
    research_case_id: str
    answer_id: str
    support_status: str
    support_decision_basis: str
    coverage_obligation_statuses: Sequence[str]
    document_ids: Sequence[str]
    query_count: int
    independent_dependency_group_ids: Sequence[str]
    contradiction_classifications: Sequence[str]
    documentary_gap_types: Sequence[str]
    projection_version_refs: Sequence[str]
    verified_claim_version_refs: Sequence[Mapping[str, Any]]
    public_error_code: str | None
    synthesis_published: bool
    completed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(self, "support_status", _ensure_support_status(self.support_status))
        object.__setattr__(
            self,
            "support_decision_basis",
            _ensure_support_decision_basis(self.support_decision_basis),
        )
        object.__setattr__(
            self,
            "coverage_obligation_statuses",
            _ensure_allowed_text_tuple(
                self.coverage_obligation_statuses,
                "coverage_obligation_statuses",
                _ALLOWED_COVERAGE_STATUSES,
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "document_ids",
            _ensure_prefixed_text_tuple(self.document_ids, "DOC-", "document_ids", allow_empty=False),
        )
        object.__setattr__(self, "query_count", _ensure_positive_integer(self.query_count, "query_count"))
        object.__setattr__(
            self,
            "independent_dependency_group_ids",
            _ensure_prefixed_text_tuple(
                self.independent_dependency_group_ids,
                "DEP-",
                "independent_dependency_group_ids",
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
        object.__setattr__(
            self,
            "documentary_gap_types",
            _ensure_allowed_text_tuple(
                self.documentary_gap_types,
                "documentary_gap_types",
                _ALLOWED_DOCUMENTARY_GAP_TYPES,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "projection_version_refs",
            _ensure_prefixed_text_tuple(self.projection_version_refs, "PROJ-", "projection_version_refs", allow_empty=False),
        )
        object.__setattr__(
            self,
            "verified_claim_version_refs",
            _ensure_verified_claim_version_refs(self.verified_claim_version_refs),
        )
        if self.public_error_code is not None:
            object.__setattr__(self, "public_error_code", _ensure_text(self.public_error_code, "public_error_code"))
        if not isinstance(self.synthesis_published, bool):
            raise ValueError("synthesis_published non booleen")
        object.__setattr__(self, "completed_at", _ensure_utc_instant(self.completed_at, "completed_at"))
        self._ensure_support_consistency()

    def _ensure_support_consistency(self) -> None:
        non_covered_statuses = tuple(
            status
            for status in self.coverage_obligation_statuses
            if status != "COVERED"
        )
        if self.support_status == "SUPPORTED":
            if len(non_covered_statuses) > 0:
                raise ValueError("SUPPORTED avec couverture incomplete")
            if len(self.contradiction_classifications) > 0:
                raise ValueError("SUPPORTED avec contradiction")
            if len(self.documentary_gap_types) > 0:
                raise ValueError("SUPPORTED avec lacune")
        elif self.support_status == "PARTIALLY_SUPPORTED":
            if (
                len(non_covered_statuses) == 0
                and len(self.contradiction_classifications) == 0
                and len(self.documentary_gap_types) == 0
            ):
                raise ValueError("PARTIALLY_SUPPORTED sans qualification")
        elif self.support_status == "INSUFFICIENT_EVIDENCE":
            if len(self.documentary_gap_types) == 0:
                raise ValueError("lacune requise pour INSUFFICIENT_EVIDENCE")
        elif self.support_status == "CONFLICTING_EVIDENCE":
            if len(self.contradiction_classifications) == 0:
                raise ValueError("contradiction requise pour CONFLICTING_EVIDENCE")
        elif self.support_status == "REQUIRES_CURRENT_DATA":
            if "CURRENT_DATA_REQUIRED" not in self.documentary_gap_types:
                raise ValueError("CURRENT_DATA_REQUIRED requis")

        if self.support_status in {"SUPPORTED", "PARTIALLY_SUPPORTED"} and not self.synthesis_published:
            raise ValueError("synthesis_published incompatible")
        if self.support_status in {
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING_EVIDENCE",
            "REQUIRES_CURRENT_DATA",
        } and self.synthesis_published:
            raise ValueError("synthesis_published incompatible")


@dataclass(frozen=True)
class DeepResearchMetricSnapshot:
    """Snapshot de metriques M-009 sans payload documentaire ou conversationnel sensible."""

    fixture_id: str
    fixture_path: str
    measured_at: str
    research_case_count: int
    coverage_obligation_status_counts: Mapping[str, int]
    coverage_rate: float
    documentary_diversity: Mapping[str, int]
    independent_dependency_group_total: int
    contradiction_classification_counts: Mapping[str, int]
    documentary_gap_type_counts: Mapping[str, int]
    support_status_counts: Mapping[str, int]
    public_error_code_counts: Mapping[str, int]
    projection_version_refs: Sequence[str]
    verified_claim_version_refs: Sequence[Mapping[str, Any]]
    normative_signals: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(
            self,
            "research_case_count",
            _ensure_positive_integer(self.research_case_count, "research_case_count"),
        )
        object.__setattr__(
            self,
            "coverage_obligation_status_counts",
            _ensure_coverage_status_counts(self.coverage_obligation_status_counts),
        )
        object.__setattr__(self, "coverage_rate", _ensure_ratio(self.coverage_rate, "coverage_rate"))
        object.__setattr__(
            self,
            "documentary_diversity",
            _ensure_documentary_diversity(self.documentary_diversity),
        )
        object.__setattr__(
            self,
            "independent_dependency_group_total",
            _ensure_non_negative_integer(
                self.independent_dependency_group_total,
                "independent_dependency_group_total",
            ),
        )
        object.__setattr__(
            self,
            "contradiction_classification_counts",
            _ensure_count_mapping(
                self.contradiction_classification_counts,
                "contradiction_classification_counts",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "documentary_gap_type_counts",
            _ensure_count_mapping(self.documentary_gap_type_counts, "documentary_gap_type_counts", allow_empty=True),
        )
        object.__setattr__(
            self,
            "support_status_counts",
            _ensure_support_status_counts(self.support_status_counts),
        )
        object.__setattr__(
            self,
            "public_error_code_counts",
            _ensure_count_mapping(self.public_error_code_counts, "public_error_code_counts", allow_empty=True),
        )
        object.__setattr__(
            self,
            "projection_version_refs",
            _ensure_prefixed_text_tuple(self.projection_version_refs, "PROJ-", "projection_version_refs", allow_empty=False),
        )
        object.__setattr__(
            self,
            "verified_claim_version_refs",
            _ensure_verified_claim_version_refs(self.verified_claim_version_refs),
        )
        object.__setattr__(self, "normative_signals", _ensure_normative_signals(self.normative_signals))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "research_case_count": self.research_case_count,
            "coverage_obligation_status_counts": dict(self.coverage_obligation_status_counts),
            "coverage_rate": self.coverage_rate,
            "documentary_diversity": dict(self.documentary_diversity),
            "independent_dependency_group_total": self.independent_dependency_group_total,
            "contradiction_classification_counts": dict(self.contradiction_classification_counts),
            "documentary_gap_type_counts": dict(self.documentary_gap_type_counts),
            "support_status_counts": dict(self.support_status_counts),
            "public_error_code_counts": dict(self.public_error_code_counts),
            "projection_version_refs": list(self.projection_version_refs),
            "verified_claim_version_refs": [dict(ref) for ref in self.verified_claim_version_refs],
            "normative_signals": dict(self.normative_signals),
        }


class DeepResearchMetricsPublisher:
    """Calcule les metriques RA approfondies depuis des observations agregees."""

    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[DeepResearchMetricObservation],
        measured_at: str,
    ) -> DeepResearchMetricSnapshot:
        parsed_fixture_id = _ensure_text(fixture_id, "fixture_id")
        parsed_fixture_path = _ensure_relative_path(fixture_path, "fixture_path")
        parsed_observations = _ensure_observations(observations)
        parsed_measured_at = _ensure_utc_instant(measured_at, "measured_at")
        coverage_counts = _coverage_status_counts_for(parsed_observations)
        support_counts = _support_status_counts_for(parsed_observations)
        contradiction_counts = _contradiction_classification_counts_for(parsed_observations)
        gap_counts = _documentary_gap_type_counts_for(parsed_observations)
        dependency_group_total = _independent_dependency_group_total_for(parsed_observations)
        public_error_counts = _public_error_code_counts_for(parsed_observations)
        verified_claim_refs = _verified_claim_version_refs_for(parsed_observations)

        return DeepResearchMetricSnapshot(
            fixture_id=parsed_fixture_id,
            fixture_path=parsed_fixture_path,
            measured_at=parsed_measured_at,
            research_case_count=len(parsed_observations),
            coverage_obligation_status_counts=coverage_counts,
            coverage_rate=_coverage_rate_for(coverage_counts),
            documentary_diversity=_documentary_diversity_for(parsed_observations),
            independent_dependency_group_total=dependency_group_total,
            contradiction_classification_counts=contradiction_counts,
            documentary_gap_type_counts=gap_counts,
            support_status_counts=support_counts,
            public_error_code_counts=public_error_counts,
            projection_version_refs=_projection_version_refs_for(parsed_observations),
            verified_claim_version_refs=verified_claim_refs,
            normative_signals=_normative_signals_for(
                observations=parsed_observations,
                coverage_counts=coverage_counts,
                dependency_group_total=dependency_group_total,
                contradiction_counts=contradiction_counts,
                gap_counts=gap_counts,
                support_counts=support_counts,
                public_error_counts=public_error_counts,
                verified_claim_refs=verified_claim_refs,
            ),
        )


@dataclass(frozen=True)
class DeepResearchAuditSignal:
    """Signal RA de publication des metriques approfondies sans contenu complet."""

    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: DeepResearchMetricSnapshot
    research_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: DeepResearchMetricSnapshot,
        research_refs: Sequence[Mapping[str, Any]],
        forbidden_sensitive_payloads: Sequence[str],
    ) -> "DeepResearchAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="deep_research_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            research_refs=research_refs,
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
            _ensure_expected_text(self.signal_name, "deep_research_metrics_published", "signal_name"),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, DeepResearchMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "research_refs", _ensure_research_refs(self.research_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "research_refs": tuple(dict(ref) for ref in self.research_refs),
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
    value: Sequence[DeepResearchMetricObservation],
) -> tuple[DeepResearchMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    trace_ids: list[str] = []
    research_case_ids: list[str] = []
    for observation in observations:
        if not isinstance(observation, DeepResearchMetricObservation):
            raise ValueError("observation invalide")
        if observation.trace_id in trace_ids:
            raise ValueError("trace_id duplique")
        if observation.research_case_id in research_case_ids:
            raise ValueError("research_case_id duplique")
        trace_ids.append(observation.trace_id)
        research_case_ids.append(observation.research_case_id)
    return observations


def _coverage_status_counts_for(observations: tuple[DeepResearchMetricObservation, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _ALLOWED_COVERAGE_STATUSES}
    for observation in observations:
        for status in observation.coverage_obligation_statuses:
            counts[status] += 1
    return counts


def _coverage_rate_for(coverage_counts: Mapping[str, int]) -> float:
    total = sum(coverage_counts.values())
    if total == 0:
        raise ValueError("coverage_obligation_statuses absents")
    return coverage_counts["COVERED"] / total


def _documentary_diversity_for(observations: tuple[DeepResearchMetricObservation, ...]) -> dict[str, int]:
    document_counts = tuple(len(observation.document_ids) for observation in observations)
    distinct_document_ids = {
        document_id
        for observation in observations
        for document_id in observation.document_ids
    }
    return {
        "distinct_document_total": len(distinct_document_ids),
        "minimum_document_count_per_research": min(document_counts),
        "maximum_document_count_per_research": max(document_counts),
    }


def _independent_dependency_group_total_for(observations: tuple[DeepResearchMetricObservation, ...]) -> int:
    return len(
        {
            group_id
            for observation in observations
            for group_id in observation.independent_dependency_group_ids
        }
    )


def _contradiction_classification_counts_for(
    observations: tuple[DeepResearchMetricObservation, ...],
) -> dict[str, int]:
    counts = {classification: 0 for classification in _ALLOWED_CONTRADICTION_CLASSIFICATIONS}
    for observation in observations:
        for classification in observation.contradiction_classifications:
            counts[classification] += 1
    return {
        classification: counts[classification]
        for classification in _ALLOWED_CONTRADICTION_CLASSIFICATIONS
        if counts[classification] > 0
    }


def _documentary_gap_type_counts_for(observations: tuple[DeepResearchMetricObservation, ...]) -> dict[str, int]:
    counts = {gap_type: 0 for gap_type in _ALLOWED_DOCUMENTARY_GAP_TYPES}
    for observation in observations:
        for gap_type in observation.documentary_gap_types:
            counts[gap_type] += 1
    return {
        gap_type: counts[gap_type]
        for gap_type in _ALLOWED_DOCUMENTARY_GAP_TYPES
        if counts[gap_type] > 0
    }


def _support_status_counts_for(observations: tuple[DeepResearchMetricObservation, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _ALLOWED_SUPPORT_STATUSES}
    for observation in observations:
        counts[observation.support_status] += 1
    return counts


def _public_error_code_counts_for(observations: tuple[DeepResearchMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.public_error_code is not None:
            counts[observation.public_error_code] = counts.get(observation.public_error_code, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _projection_version_refs_for(observations: tuple[DeepResearchMetricObservation, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                projection_version_ref
                for observation in observations
                for projection_version_ref in observation.projection_version_refs
            }
        )
    )


def _verified_claim_version_refs_for(
    observations: tuple[DeepResearchMetricObservation, ...],
) -> tuple[dict[str, int | str], ...]:
    refs = {
        (ref["claim_id"], ref["claim_version"])
        for observation in observations
        for ref in observation.verified_claim_version_refs
    }
    return tuple(
        {"claim_id": claim_id, "claim_version": claim_version}
        for claim_id, claim_version in sorted(refs)
    )


def _normative_signals_for(
    *,
    observations: tuple[DeepResearchMetricObservation, ...],
    coverage_counts: Mapping[str, int],
    dependency_group_total: int,
    contradiction_counts: Mapping[str, int],
    gap_counts: Mapping[str, int],
    support_counts: Mapping[str, int],
    public_error_counts: Mapping[str, int],
    verified_claim_refs: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "deep_research_requested_total": len(observations),
        "deep_research_plan_created_total": len(observations),
        "deep_research_coverage_obligation_met_total": coverage_counts["COVERED"],
        "deep_research_coverage_obligation_missing_total": coverage_counts["INSUFFICIENT"],
        "deep_research_query_executed_total": sum(observation.query_count for observation in observations),
        "deep_research_independent_source_group_total": dependency_group_total,
        "deep_research_contradiction_classified_total": sum(contradiction_counts.values()),
        "deep_research_documentary_gap_total": sum(gap_counts.values()),
        "deep_research_support_status_total": sum(support_counts.values()),
        "deep_research_public_error_total": sum(public_error_counts.values()),
        "deep_research_synthesis_published_total": sum(
            1
            for observation in observations
            if observation.synthesis_published
        ),
        "deep_research_claim_version_recorded_total": len(verified_claim_refs),
    }


def _ensure_research_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("research_refs invalides")
    refs = tuple(_ensure_mapping(item, "research_ref") for item in value)
    if len(refs) == 0:
        raise ValueError("research_refs absentes")
    allowed_keys = frozenset(
        {
            "research_case_id",
            "answer_id",
            "support_status",
            "answer_text_hash",
            "projection_version_refs",
            "verified_claim_version_refs",
        }
    )
    for ref in refs:
        actual_keys = frozenset(str(key) for key in ref)
        if actual_keys != allowed_keys:
            raise ValueError("payload sensible interdit dans research_refs")
        ref["research_case_id"] = _ensure_research_case_id(ref["research_case_id"])
        ref["answer_id"] = _ensure_answer_id(ref["answer_id"])
        ref["support_status"] = _ensure_support_status(ref["support_status"])
        ref["answer_text_hash"] = _ensure_sha256(ref["answer_text_hash"], "answer_text_hash")
        ref["projection_version_refs"] = _ensure_prefixed_text_tuple(
            ref["projection_version_refs"],
            "PROJ-",
            "projection_version_refs",
            allow_empty=False,
        )
        ref["verified_claim_version_refs"] = _ensure_verified_claim_version_refs(
            ref["verified_claim_version_refs"],
        )
    return refs


def _ensure_coverage_status_counts(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("coverage_obligation_status_counts non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _ALLOWED_COVERAGE_STATUSES:
        raise ValueError("coverage_obligation_status_counts incomplets")
    return {
        status: _ensure_non_negative_integer(value[status], status)
        for status in _ALLOWED_COVERAGE_STATUSES
    }


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


def _ensure_documentary_diversity(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("documentary_diversity non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _DOCUMENTARY_DIVERSITY_KEYS:
        raise ValueError("documentary_diversity incomplet")
    parsed = {
        key: _ensure_positive_integer(value[key], key)
        for key in _DOCUMENTARY_DIVERSITY_KEYS
    }
    if parsed["minimum_document_count_per_research"] > parsed["maximum_document_count_per_research"]:
        raise ValueError("documentary_diversity incoherent")
    return parsed


def _ensure_count_mapping(value: Mapping[str, int], field_name: str, *, allow_empty: bool) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    parsed: dict[str, int] = {}
    for key, count in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_positive_integer(count, field_name)
    return parsed


def _ensure_normative_signals(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("normative_signals non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _NORMATIVE_SIGNAL_NAMES:
        raise ValueError("normative_signals incomplets")
    return {
        signal_name: _ensure_non_negative_integer(value[signal_name], signal_name)
        for signal_name in _NORMATIVE_SIGNAL_NAMES
    }


def _ensure_verified_claim_version_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, int | str], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verified_claim_version_refs invalides")
    refs = tuple(_ensure_mapping(item, "verified_claim_version_ref") for item in value)
    if len(refs) == 0:
        raise ValueError("verified_claim_version_refs absentes")
    parsed: list[dict[str, int | str]] = []
    seen: list[tuple[str, int]] = []
    allowed_keys = frozenset({"claim_id", "claim_version"})
    for ref in refs:
        if frozenset(str(key) for key in ref) != allowed_keys:
            raise ValueError("verified_claim_version_ref invalide")
        claim_id = _ensure_claim_id(ref["claim_id"])
        claim_version = _ensure_positive_integer(ref["claim_version"], "claim_version")
        key = (claim_id, claim_version)
        if key in seen:
            raise ValueError("verified_claim_version_ref duplique")
        seen.append(key)
        parsed.append({"claim_id": claim_id, "claim_version": claim_version})
    return tuple(parsed)


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


def _ensure_support_decision_basis(value: Any) -> str:
    text = _ensure_text(value, "support_decision_basis")
    if text == "MENTION_COUNT_CONSENSUS":
        raise ValueError("support_decision_basis par consensus interdit")
    if text not in _ALLOWED_SUPPORT_DECISION_BASES:
        raise ValueError("support_decision_basis invalide")
    return text


def _ensure_support_status(value: Any) -> str:
    text = _ensure_text(value, "support_status")
    if text not in _ALLOWED_SUPPORT_STATUSES:
        raise ValueError("support_status invalide")
    return text


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
    return parsed


def _ensure_prefixed_text_tuple(
    value: Sequence[str],
    expected_prefix: str,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    parsed = _ensure_text_tuple(value, field_name, allow_empty=allow_empty)
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliques")
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


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
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
    "DeepResearchAuditSignal",
    "DeepResearchMetricObservation",
    "DeepResearchMetricSnapshot",
    "DeepResearchMetricsPublisher",
    "assert_no_sensitive_payload_in_audit_payload",
]
