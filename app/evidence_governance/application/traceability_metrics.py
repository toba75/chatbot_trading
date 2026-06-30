"""Métriques EG et signaux d'audit de clôture M-006."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_EVIDENCE_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_DEPENDENCY_GROUP_ID_PATTERN = re.compile(r"^DEP-[A-Z0-9][A-Z0-9-]*$")
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_METRIC_SCOPE = "M006_CLAIMS_VERIFIABLES"
_ALLOWED_STATUSES = (
    "DRAFT",
    "EVIDENCE_ATTACHED",
    "UNDER_VERIFICATION",
    "VERIFIED",
    "REJECTED",
    "SUPERSEDED",
    "ABANDONED",
)
_TERMINAL_VERIFICATION_STATUSES = frozenset({"VERIFIED", "REJECTED", "SUPERSEDED"})
_ALLOWED_VERDICTS = ("ENTAILED", "PARTIALLY_ENTAILED", "NOT_ENTAILED")
_NORMATIVE_SIGNAL_NAMES = (
    "claims_drafted_total",
    "claims_verified_total",
    "claims_rejected_total",
    "claim_verification_latency_seconds",
    "claim_scope_refusal_total",
    "claim_independent_support_groups",
    "claim_superseded_total",
    "claim_model_proposal_total",
    "claim_public_evidence_resolution_failed_total",
)


@dataclass(frozen=True)
class ClaimMetricObservation:
    """Observation EG agrégée sans texte de claim ni payload documentaire."""

    claim_id: str
    claim_version: int
    status: str
    direct_evidence_count: int
    verification_verdict: str | None
    reason_codes: Sequence[str]
    dependency_group_ids: Sequence[str]
    submitted_at: str | None
    decided_at: str | None
    superseded_by_claim_version: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(self, "claim_version", _ensure_positive_integer(self.claim_version, "claim_version"))
        object.__setattr__(self, "status", _ensure_status(self.status))
        object.__setattr__(
            self,
            "direct_evidence_count",
            _ensure_non_negative_integer(self.direct_evidence_count, "direct_evidence_count"),
        )
        object.__setattr__(
            self,
            "verification_verdict",
            _ensure_optional_verdict(self.verification_verdict),
        )
        object.__setattr__(self, "reason_codes", _ensure_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "dependency_group_ids",
            _ensure_dependency_group_ids(self.dependency_group_ids),
        )
        if self.submitted_at is not None:
            object.__setattr__(self, "submitted_at", _ensure_utc_instant(self.submitted_at, "submitted_at"))
        if self.decided_at is not None:
            object.__setattr__(self, "decided_at", _ensure_utc_instant(self.decided_at, "decided_at"))
        if self.superseded_by_claim_version is not None:
            object.__setattr__(
                self,
                "superseded_by_claim_version",
                _ensure_positive_integer(
                    self.superseded_by_claim_version,
                    "superseded_by_claim_version",
                ),
            )
        self._ensure_status_consistency()

    @property
    def has_direct_evidence(self) -> bool:
        return self.direct_evidence_count > 0

    @property
    def dependency_group_count(self) -> int:
        return len(self.dependency_group_ids)

    def verification_latency_seconds(self) -> float | None:
        if self.submitted_at is None or self.decided_at is None:
            return None
        submitted_at = _parse_utc_instant(self.submitted_at)
        decided_at = _parse_utc_instant(self.decided_at)
        latency_seconds = (decided_at - submitted_at).total_seconds()
        if latency_seconds < 0.0:
            raise ValueError("delai verification negatif")
        return latency_seconds

    def _ensure_status_consistency(self) -> None:
        if self.status in _TERMINAL_VERIFICATION_STATUSES:
            if self.verification_verdict is None:
                raise ValueError("verification_verdict requis")
            if self.submitted_at is None:
                raise ValueError("submitted_at requis")
            if self.decided_at is None:
                raise ValueError("decided_at requis")
        if self.status == "UNDER_VERIFICATION":
            if self.submitted_at is None:
                raise ValueError("submitted_at requis")
            if self.decided_at is not None:
                raise ValueError("decided_at incompatible avec UNDER_VERIFICATION")
            if self.verification_verdict is not None:
                raise ValueError("verification_verdict incompatible avec UNDER_VERIFICATION")
        if self.status == "REJECTED" and len(self.reason_codes) == 0:
            raise ValueError("reason_codes requis")
        if self.status != "REJECTED" and len(self.reason_codes) > 0:
            raise ValueError("reason_codes incompatibles avec status courant")
        if self.status == "VERIFIED" and not self.has_direct_evidence:
            raise ValueError("preuve directe requise pour VERIFIED")
        if self.status == "SUPERSEDED":
            if self.superseded_by_claim_version is None:
                raise ValueError("superseded_by_claim_version requis")
            if self.superseded_by_claim_version <= self.claim_version:
                raise ValueError("superseded_by_claim_version invalide")
        elif self.superseded_by_claim_version is not None:
            raise ValueError("superseded_by_claim_version incompatible avec status courant")


@dataclass(frozen=True)
class EvidenceGovernanceMetricSnapshot:
    """Snapshot de métriques M-006 publié sans payload documentaire."""

    fixture_id: str
    fixture_path: str
    measured_at: str
    claim_count: int
    status_counts: Mapping[str, int]
    verified_rate: float
    rejected_rate: float
    in_review_rate: float
    without_direct_evidence_ratio: float
    supersession_rate: float
    verdict_distribution: Mapping[str, int]
    dependency_group_count_distribution: Mapping[str, int]
    average_verification_latency_seconds: float
    normative_signals: Mapping[str, int | float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(self, "claim_count", _ensure_positive_integer(self.claim_count, "claim_count"))
        object.__setattr__(self, "status_counts", _ensure_status_counts(self.status_counts))
        object.__setattr__(self, "verified_rate", _ensure_ratio(self.verified_rate, "verified_rate"))
        object.__setattr__(self, "rejected_rate", _ensure_ratio(self.rejected_rate, "rejected_rate"))
        object.__setattr__(self, "in_review_rate", _ensure_ratio(self.in_review_rate, "in_review_rate"))
        object.__setattr__(
            self,
            "without_direct_evidence_ratio",
            _ensure_ratio(self.without_direct_evidence_ratio, "without_direct_evidence_ratio"),
        )
        object.__setattr__(self, "supersession_rate", _ensure_ratio(self.supersession_rate, "supersession_rate"))
        object.__setattr__(
            self,
            "verdict_distribution",
            _ensure_count_mapping(self.verdict_distribution, "verdict_distribution"),
        )
        object.__setattr__(
            self,
            "dependency_group_count_distribution",
            _ensure_count_mapping(
                self.dependency_group_count_distribution,
                "dependency_group_count_distribution",
            ),
        )
        object.__setattr__(
            self,
            "average_verification_latency_seconds",
            _ensure_non_negative_float(
                self.average_verification_latency_seconds,
                "average_verification_latency_seconds",
            ),
        )
        object.__setattr__(
            self,
            "normative_signals",
            _ensure_normative_signals(self.normative_signals),
        )
        if sum(self.status_counts.values()) != self.claim_count:
            raise ValueError("status_counts incoherents")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "claim_count": self.claim_count,
            "status_counts": dict(self.status_counts),
            "rates": {
                "verified_rate": self.verified_rate,
                "rejected_rate": self.rejected_rate,
                "in_review_rate": self.in_review_rate,
                "without_direct_evidence_ratio": self.without_direct_evidence_ratio,
                "supersession_rate": self.supersession_rate,
            },
            "verdict_distribution": dict(self.verdict_distribution),
            "dependency_group_count_distribution": dict(self.dependency_group_count_distribution),
            "average_verification_latency_seconds": self.average_verification_latency_seconds,
            "normative_signals": dict(self.normative_signals),
        }


class EvidenceGovernanceMetricsPublisher:
    """Calcule les métriques EG déterministes à partir d'observations agrégées."""

    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[ClaimMetricObservation],
        measured_at: str,
    ) -> EvidenceGovernanceMetricSnapshot:
        parsed_fixture_id = _ensure_text(fixture_id, "fixture_id")
        parsed_fixture_path = _ensure_relative_path(fixture_path, "fixture_path")
        parsed_observations = _ensure_observations(observations)
        parsed_measured_at = _ensure_utc_instant(measured_at, "measured_at")
        claim_count = len(parsed_observations)
        status_counts = _status_counts_for(parsed_observations)
        verdict_distribution = _verdict_distribution_for(parsed_observations)
        dependency_group_count_distribution = _dependency_group_count_distribution_for(parsed_observations)
        average_latency_seconds = _average_verification_latency_seconds(parsed_observations)
        normative_signals = _normative_signals_for(
            observations=parsed_observations,
            status_counts=status_counts,
            average_latency_seconds=average_latency_seconds,
        )

        return EvidenceGovernanceMetricSnapshot(
            fixture_id=parsed_fixture_id,
            fixture_path=parsed_fixture_path,
            measured_at=parsed_measured_at,
            claim_count=claim_count,
            status_counts=status_counts,
            verified_rate=status_counts["VERIFIED"] / claim_count,
            rejected_rate=status_counts["REJECTED"] / claim_count,
            in_review_rate=status_counts["UNDER_VERIFICATION"] / claim_count,
            without_direct_evidence_ratio=(
                sum(1 for observation in parsed_observations if not observation.has_direct_evidence) / claim_count
            ),
            supersession_rate=status_counts["SUPERSEDED"] / claim_count,
            verdict_distribution=verdict_distribution,
            dependency_group_count_distribution=dependency_group_count_distribution,
            average_verification_latency_seconds=average_latency_seconds,
            normative_signals=normative_signals,
        )


@dataclass(frozen=True)
class EvidenceGovernanceAuditSignal:
    """Signal EG de publication des métriques sans claim complet ni preuve complète."""

    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: EvidenceGovernanceMetricSnapshot
    claim_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: EvidenceGovernanceMetricSnapshot,
        claim_refs: Sequence[Mapping[str, Any]],
        forbidden_documentary_payloads: Sequence[str],
    ) -> "EvidenceGovernanceAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="evidence_governance_claim_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            claim_refs=claim_refs,
        )
        assert_no_documentary_payload_in_audit_payload(
            signal.to_payload(),
            forbidden_documentary_payloads=forbidden_documentary_payloads,
        )
        return signal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "audit_signal_id",
            _ensure_prefixed_text(self.audit_signal_id, "EG-AUDIT-", "audit_signal_id"),
        )
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(
            self,
            "signal_name",
            _ensure_expected_text(
                self.signal_name,
                "evidence_governance_claim_metrics_published",
                "signal_name",
            ),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, EvidenceGovernanceMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "claim_refs", _ensure_claim_refs(self.claim_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "claim_refs": tuple(dict(claim_ref) for claim_ref in self.claim_refs),
            "metrics": self.metric_snapshot.to_payload(),
        }


def assert_no_documentary_payload_in_audit_payload(
    payload: Mapping[str, Any],
    *,
    forbidden_documentary_payloads: Sequence[str],
) -> None:
    parsed_payload = _ensure_mapping(payload, "payload")
    forbidden_payloads = _ensure_text_tuple(
        forbidden_documentary_payloads,
        "forbidden_documentary_payloads",
    )
    serialized_payload = json.dumps(_json_ready(parsed_payload), ensure_ascii=False, sort_keys=True)
    for forbidden_payload in forbidden_payloads:
        if forbidden_payload in serialized_payload:
            raise ValueError("payload documentaire interdit dans signal d'audit")


def _status_counts_for(observations: tuple[ClaimMetricObservation, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _ALLOWED_STATUSES}
    for observation in observations:
        counts[observation.status] += 1
    return counts


def _verdict_distribution_for(observations: tuple[ClaimMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for verdict in _ALLOWED_VERDICTS:
        verdict_count = sum(1 for observation in observations if observation.verification_verdict == verdict)
        if verdict_count > 0:
            counts[verdict] = verdict_count
    return counts


def _dependency_group_count_distribution_for(observations: tuple[ClaimMetricObservation, ...]) -> dict[str, int]:
    counts: dict[int, int] = {}
    for observation in observations:
        counts[observation.dependency_group_count] = counts.get(observation.dependency_group_count, 0) + 1
    return {str(group_count): counts[group_count] for group_count in sorted(counts)}


def _average_verification_latency_seconds(observations: tuple[ClaimMetricObservation, ...]) -> float:
    latencies = tuple(
        latency
        for latency in (observation.verification_latency_seconds() for observation in observations)
        if latency is not None
    )
    if len(latencies) == 0:
        raise ValueError("delai verification absent")
    return sum(latencies) / len(latencies)


def _normative_signals_for(
    *,
    observations: tuple[ClaimMetricObservation, ...],
    status_counts: Mapping[str, int],
    average_latency_seconds: float,
) -> dict[str, int | float]:
    return {
        "claims_drafted_total": len(observations),
        "claims_verified_total": status_counts["VERIFIED"],
        "claims_rejected_total": status_counts["REJECTED"],
        "claim_verification_latency_seconds": average_latency_seconds,
        "claim_scope_refusal_total": _reason_code_count(
            observations,
            "CLAIM_SCOPE_EXCEEDS_EVIDENCE",
        ),
        "claim_independent_support_groups": sum(
            observation.dependency_group_count for observation in observations
        ),
        "claim_superseded_total": status_counts["SUPERSEDED"],
        "claim_model_proposal_total": len(observations),
        "claim_public_evidence_resolution_failed_total": _reason_code_count(
            observations,
            "CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE",
        ),
    }


def _reason_code_count(observations: tuple[ClaimMetricObservation, ...], reason_code: str) -> int:
    parsed_reason_code = _ensure_text(reason_code, "reason_code")
    return sum(1 for observation in observations if parsed_reason_code in observation.reason_codes)


def _ensure_observations(value: Sequence[ClaimMetricObservation]) -> tuple[ClaimMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    claim_version_refs: list[tuple[str, int]] = []
    for observation in observations:
        if not isinstance(observation, ClaimMetricObservation):
            raise ValueError("observation invalide")
        claim_version_ref = (observation.claim_id, observation.claim_version)
        if claim_version_ref in claim_version_refs:
            raise ValueError("observation claim dupliquee")
        claim_version_refs.append(claim_version_ref)
    return observations


def _ensure_claim_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claim_refs invalides")
    claim_refs = tuple(_ensure_mapping(item, "claim_ref") for item in value)
    if len(claim_refs) == 0:
        raise ValueError("claim_refs absentes")
    allowed_keys = frozenset(
        {
            "claim_id",
            "claim_version",
            "status",
            "proposition_hash",
            "evidence_ref_ids",
            "dependency_group_ids",
        }
    )
    for claim_ref in claim_refs:
        actual_keys = frozenset(str(key) for key in claim_ref)
        if actual_keys != allowed_keys:
            raise ValueError("contenu documentaire interdit dans claim_refs")
        claim_ref["claim_id"] = _ensure_claim_id(claim_ref["claim_id"])
        claim_ref["claim_version"] = _ensure_positive_integer(claim_ref["claim_version"], "claim_version")
        claim_ref["status"] = _ensure_status(claim_ref["status"])
        claim_ref["proposition_hash"] = _ensure_sha256(claim_ref["proposition_hash"], "proposition_hash")
        claim_ref["evidence_ref_ids"] = _ensure_evidence_ids(claim_ref["evidence_ref_ids"])
        claim_ref["dependency_group_ids"] = _ensure_dependency_group_ids(claim_ref["dependency_group_ids"])
    return claim_refs


def _ensure_status_counts(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("status_counts non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _ALLOWED_STATUSES:
        raise ValueError("status_counts incomplets")
    return {status: _ensure_non_negative_integer(value[status], status) for status in _ALLOWED_STATUSES}


def _ensure_count_mapping(value: Mapping[str, int], field_name: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    parsed: dict[str, int] = {}
    for key, count in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_positive_integer(count, field_name)
    return parsed


def _ensure_normative_signals(value: Mapping[str, int | float]) -> dict[str, int | float]:
    if not isinstance(value, Mapping):
        raise ValueError("normative_signals non objet")
    actual_keys = tuple(str(key) for key in value)
    if actual_keys != _NORMATIVE_SIGNAL_NAMES:
        raise ValueError("normative_signals incomplets")
    parsed: dict[str, int | float] = {}
    for signal_name in _NORMATIVE_SIGNAL_NAMES:
        signal_value = value[signal_name]
        if signal_name == "claim_verification_latency_seconds":
            parsed[signal_name] = _ensure_non_negative_float(signal_value, signal_name)
        else:
            parsed[signal_name] = _ensure_non_negative_integer(signal_value, signal_name)
    return parsed


def _ensure_reason_codes(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("reason_codes absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("reason_codes invalides")
    reason_codes = tuple(_ensure_text(reason_code, "reason_code") for reason_code in value)
    if len(reason_codes) != len(set(reason_codes)):
        raise ValueError("reason_codes dupliques")
    return reason_codes


def _ensure_evidence_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_ref_ids invalides")
    evidence_ids = tuple(_ensure_evidence_id(item) for item in value)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence_ref_ids dupliques")
    return evidence_ids


def _ensure_dependency_group_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("dependency_group_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_group_ids invalides")
    dependency_group_ids = tuple(_ensure_dependency_group_id(item) for item in value)
    if len(dependency_group_ids) != len(set(dependency_group_ids)):
        raise ValueError("dependency_group_ids dupliques")
    return dependency_group_ids


def _ensure_text_tuple(value: Sequence[str], field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliques")
    return parsed


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_status(value: Any) -> str:
    text = _ensure_text(value, "status")
    if text not in _ALLOWED_STATUSES:
        raise ValueError("status invalide")
    return text


def _ensure_optional_verdict(value: Any) -> str | None:
    if value is None:
        return None
    text = _ensure_text(value, "verification_verdict")
    if text not in _ALLOWED_VERDICTS:
        raise ValueError("verification_verdict invalide")
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


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_evidence_id(value: Any) -> str:
    text = _ensure_text(value, "evidence_id")
    if _EVIDENCE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_id invalide")
    return text


def _ensure_dependency_group_id(value: Any) -> str:
    text = _ensure_text(value, "dependency_group_id")
    if _DEPENDENCY_GROUP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("dependency_group_id invalide")
    return text


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


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


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc_instant(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _parse_utc_instant(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple) or isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "ClaimMetricObservation",
    "EvidenceGovernanceAuditSignal",
    "EvidenceGovernanceMetricSnapshot",
    "EvidenceGovernanceMetricsPublisher",
    "assert_no_documentary_payload_in_audit_payload",
]
