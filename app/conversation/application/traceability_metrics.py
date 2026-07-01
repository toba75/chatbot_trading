"""Métriques CV et signaux d'audit de clôture M-008."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_METRIC_SCOPE = "M008_PRODUCT_CONVERSATION"
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_CONVERSATION_ID_PATTERN = re.compile(r"^CONV-[A-Z0-9][A-Z0-9-]*$")
_TURN_ID_PATTERN = re.compile(r"^TURN-[A-Z0-9][A-Z0-9-]*$")
_ALLOWED_EVENT_TYPES = (
    "ConversationCreated",
    "UserTurnAppended",
    "FollowUpQuestionResolved",
    "FollowUpQuestionClarificationRequired",
    "ConversationModeSelected",
    "HistoricalAssertionRevalidationRequested",
    "VerifiedAnswerAttachedToTurn",
    "ConversationPublicResponsePresented",
    "ConversationArchived",
    "ConversationPublicError",
    "ConversationPromptPayloadRejected",
)
_TURN_EVENT_TYPES = frozenset(
    {
        "UserTurnAppended",
        "FollowUpQuestionResolved",
        "FollowUpQuestionClarificationRequired",
        "ConversationModeSelected",
        "HistoricalAssertionRevalidationRequested",
        "VerifiedAnswerAttachedToTurn",
        "ConversationPublicResponsePresented",
    }
)
_ALLOWED_MODES = (
    "CHAT_DOCUMENTAIRE",
    "RECHERCHE_APPROFONDIE",
    "COMPARAISON",
    "CONCEPTION_STRATEGIE",
    "CALCUL",
    "BACKTEST",
    "CLARIFICATION_INTERNE",
)
_ALLOWED_SUPPORT_STATUSES = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
)
_NORMATIVE_SIGNAL_NAMES = (
    "conversation_created_total",
    "conversation_turn_appended_total",
    "follow_up_question_resolved_total",
    "conversation_mode_selected_total",
    "historical_assertion_revalidated_total",
    "verified_answer_attached_total",
    "conversation_archived_total",
    "conversation_public_error_total",
    "conversation_prompt_payload_rejected_total",
)


@dataclass(frozen=True)
class ConversationMetricObservation:
    """Observation CV agrégée sans message, prompt ni texte documentaire."""

    trace_id: str
    conversation_id: str
    turn_id: str | None
    event_type: str
    mode: str | None
    support_status: str | None
    public_error_code: str | None
    payload_hash: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        if self.turn_id is not None:
            object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "event_type", _ensure_allowed_text(self.event_type, "event_type", _ALLOWED_EVENT_TYPES))
        if self.mode is not None:
            object.__setattr__(self, "mode", _ensure_allowed_text(self.mode, "mode", _ALLOWED_MODES))
        if self.support_status is not None:
            object.__setattr__(
                self,
                "support_status",
                _ensure_allowed_text(self.support_status, "support_status", _ALLOWED_SUPPORT_STATUSES),
            )
        if self.public_error_code is not None:
            object.__setattr__(self, "public_error_code", _ensure_text(self.public_error_code, "public_error_code"))
        object.__setattr__(self, "payload_hash", _ensure_sha256(self.payload_hash, "payload_hash"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))
        self._ensure_event_consistency()

    def _ensure_event_consistency(self) -> None:
        if self.event_type in _TURN_EVENT_TYPES and self.turn_id is None:
            raise ValueError("turn_id requis")
        if self.event_type == "ConversationModeSelected":
            if self.mode is None:
                raise ValueError("mode requis")
        elif self.mode is not None:
            raise ValueError("mode incompatible")

        if self.event_type in {"VerifiedAnswerAttachedToTurn", "ConversationPublicResponsePresented"}:
            if self.support_status is None:
                raise ValueError("support_status requis")
        elif self.support_status is not None:
            raise ValueError("support_status incompatible")

        if self.event_type in {"ConversationPublicError", "ConversationPromptPayloadRejected"}:
            if self.public_error_code is None:
                raise ValueError("public_error_code requis")
        if self.event_type == "ConversationPromptPayloadRejected" and self.public_error_code != "HTTP_REQUEST_INVALID":
            raise ValueError("public_error_code HTTP_REQUEST_INVALID requis")


@dataclass(frozen=True)
class ConversationMetricSnapshot:
    """Snapshot de métriques M-008 sans contenu conversationnel sensible."""

    fixture_id: str
    fixture_path: str
    measured_at: str
    observation_count: int
    normative_signals: Mapping[str, int]
    mode_counts: Mapping[str, int]
    support_status_counts: Mapping[str, int]
    public_error_code_counts: Mapping[str, int]
    clarification_required_total: int
    presentation_published_total: int
    archive_rate: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_id", _ensure_text(self.fixture_id, "fixture_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "measured_at", _ensure_utc_instant(self.measured_at, "measured_at"))
        object.__setattr__(
            self,
            "observation_count",
            _ensure_positive_integer(self.observation_count, "observation_count"),
        )
        object.__setattr__(self, "normative_signals", _ensure_normative_signals(self.normative_signals))
        object.__setattr__(self, "mode_counts", _ensure_count_mapping(self.mode_counts, "mode_counts", allow_empty=True))
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
            "clarification_required_total",
            _ensure_non_negative_integer(self.clarification_required_total, "clarification_required_total"),
        )
        object.__setattr__(
            self,
            "presentation_published_total",
            _ensure_non_negative_integer(self.presentation_published_total, "presentation_published_total"),
        )
        object.__setattr__(self, "archive_rate", _ensure_ratio(self.archive_rate, "archive_rate"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "fixture_id": self.fixture_id,
            "fixture_path": self.fixture_path,
            "measured_at": self.measured_at,
            "observation_count": self.observation_count,
            "normative_signals": dict(self.normative_signals),
            "mode_counts": dict(self.mode_counts),
            "support_status_counts": dict(self.support_status_counts),
            "public_error_code_counts": dict(self.public_error_code_counts),
            "clarification_required_total": self.clarification_required_total,
            "presentation_published_total": self.presentation_published_total,
            "archive_rate": self.archive_rate,
        }


class ConversationMetricsPublisher:
    """Calcule les métriques CV déterministes depuis des observations agrégées."""

    def publish(
        self,
        *,
        fixture_id: str,
        fixture_path: str,
        observations: Sequence[ConversationMetricObservation],
        measured_at: str,
    ) -> ConversationMetricSnapshot:
        parsed_fixture_id = _ensure_text(fixture_id, "fixture_id")
        parsed_fixture_path = _ensure_relative_path(fixture_path, "fixture_path")
        parsed_observations = _ensure_observations(observations)
        parsed_measured_at = _ensure_utc_instant(measured_at, "measured_at")
        event_counts = _event_counts_for(parsed_observations)
        created_count = event_counts["ConversationCreated"]
        archived_count = event_counts["ConversationArchived"]
        if created_count == 0:
            raise ValueError("conversation_created_total absent")
        return ConversationMetricSnapshot(
            fixture_id=parsed_fixture_id,
            fixture_path=parsed_fixture_path,
            measured_at=parsed_measured_at,
            observation_count=len(parsed_observations),
            normative_signals=_normative_signals_for(event_counts),
            mode_counts=_mode_counts_for(parsed_observations),
            support_status_counts=_support_status_counts_for(parsed_observations),
            public_error_code_counts=_public_error_code_counts_for(parsed_observations),
            clarification_required_total=event_counts["FollowUpQuestionClarificationRequired"],
            presentation_published_total=event_counts["ConversationPublicResponsePresented"],
            archive_rate=archived_count / created_count,
        )


@dataclass(frozen=True)
class ConversationAuditSignal:
    """Signal CV de publication des métriques sans message ni prompt."""

    audit_signal_id: str
    trace_id: str
    signal_name: str
    metric_scope: str
    metric_snapshot: ConversationMetricSnapshot
    conversation_refs: Sequence[Mapping[str, Any]]

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        audit_signal_id: str,
        trace_id: str,
        metric_snapshot: ConversationMetricSnapshot,
        conversation_refs: Sequence[Mapping[str, Any]],
        forbidden_sensitive_payloads: Sequence[str],
    ) -> "ConversationAuditSignal":
        signal = cls(
            audit_signal_id=audit_signal_id,
            trace_id=trace_id,
            signal_name="conversation_metrics_published",
            metric_scope=_METRIC_SCOPE,
            metric_snapshot=metric_snapshot,
            conversation_refs=conversation_refs,
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
            _ensure_prefixed_text(self.audit_signal_id, "CV-AUDIT-", "audit_signal_id"),
        )
        object.__setattr__(self, "trace_id", _ensure_prefixed_text(self.trace_id, "TRACE-", "trace_id"))
        object.__setattr__(
            self,
            "signal_name",
            _ensure_expected_text(self.signal_name, "conversation_metrics_published", "signal_name"),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        if not isinstance(self.metric_snapshot, ConversationMetricSnapshot):
            raise ValueError("metric_snapshot invalide")
        object.__setattr__(self, "conversation_refs", _ensure_conversation_refs(self.conversation_refs))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "audit_signal_id": self.audit_signal_id,
            "trace_id": self.trace_id,
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "conversation_refs": tuple(dict(ref) for ref in self.conversation_refs),
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


def _event_counts_for(observations: tuple[ConversationMetricObservation, ...]) -> dict[str, int]:
    counts = {event_type: 0 for event_type in _ALLOWED_EVENT_TYPES}
    for observation in observations:
        counts[observation.event_type] += 1
    return counts


def _normative_signals_for(event_counts: Mapping[str, int]) -> dict[str, int]:
    return {
        "conversation_created_total": event_counts["ConversationCreated"],
        "conversation_turn_appended_total": event_counts["UserTurnAppended"],
        "follow_up_question_resolved_total": event_counts["FollowUpQuestionResolved"],
        "conversation_mode_selected_total": event_counts["ConversationModeSelected"],
        "historical_assertion_revalidated_total": event_counts["HistoricalAssertionRevalidationRequested"],
        "verified_answer_attached_total": event_counts["VerifiedAnswerAttachedToTurn"],
        "conversation_archived_total": event_counts["ConversationArchived"],
        "conversation_public_error_total": (
            event_counts["ConversationPublicError"] + event_counts["ConversationPromptPayloadRejected"]
        ),
        "conversation_prompt_payload_rejected_total": event_counts["ConversationPromptPayloadRejected"],
    }


def _mode_counts_for(observations: tuple[ConversationMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.mode is not None:
            counts[observation.mode] = counts.get(observation.mode, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _support_status_counts_for(observations: tuple[ConversationMetricObservation, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _ALLOWED_SUPPORT_STATUSES}
    for observation in observations:
        if observation.support_status is not None:
            counts[observation.support_status] += 1
    return counts


def _public_error_code_counts_for(observations: tuple[ConversationMetricObservation, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        if observation.public_error_code is not None:
            counts[observation.public_error_code] = counts.get(observation.public_error_code, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _ensure_observations(
    value: Sequence[ConversationMetricObservation],
) -> tuple[ConversationMetricObservation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("observations invalides")
    observations = tuple(value)
    if len(observations) == 0:
        raise ValueError("observations absentes")
    trace_ids: list[str] = []
    for observation in observations:
        if not isinstance(observation, ConversationMetricObservation):
            raise ValueError("observation invalide")
        if observation.trace_id in trace_ids:
            raise ValueError("trace_id duplique")
        trace_ids.append(observation.trace_id)
    return observations


def _ensure_conversation_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conversation_refs invalides")
    refs = tuple(_ensure_mapping(item, "conversation_ref") for item in value)
    if len(refs) == 0:
        raise ValueError("conversation_refs absentes")
    allowed_keys = frozenset(
        {
            "conversation_id",
            "conversation_status",
            "turn_count",
            "last_turn_id",
            "last_question_hash",
        }
    )
    for ref in refs:
        actual_keys = frozenset(str(key) for key in ref)
        if actual_keys != allowed_keys:
            raise ValueError("payload sensible interdit dans conversation_refs")
        ref["conversation_id"] = _ensure_conversation_id(ref["conversation_id"])
        ref["conversation_status"] = _ensure_allowed_text(
            ref["conversation_status"],
            "conversation_status",
            ("ACTIVE", "ARCHIVED"),
        )
        ref["turn_count"] = _ensure_non_negative_integer(ref["turn_count"], "turn_count")
        if ref["last_turn_id"] is not None:
            ref["last_turn_id"] = _ensure_turn_id(ref["last_turn_id"])
        ref["last_question_hash"] = _ensure_sha256(ref["last_question_hash"], "last_question_hash")
    return refs


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


def _ensure_count_mapping(
    value: Mapping[str, int],
    field_name: str,
    *,
    allow_empty: bool,
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    parsed: dict[str, int] = {}
    for key, count in value.items():
        parsed[_ensure_text(key, field_name)] = _ensure_positive_integer(count, field_name)
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
        raise ValueError(f"{field_name} dupliques")
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


def _ensure_conversation_id(value: Any) -> str:
    text = _ensure_text(value, "conversation_id")
    if _CONVERSATION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("conversation_id invalide")
    return text


def _ensure_turn_id(value: Any) -> str:
    text = _ensure_text(value, "turn_id")
    if _TURN_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("turn_id invalide")
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
    "ConversationAuditSignal",
    "ConversationMetricObservation",
    "ConversationMetricSnapshot",
    "ConversationMetricsPublisher",
    "assert_no_sensitive_payload_in_audit_payload",
]
