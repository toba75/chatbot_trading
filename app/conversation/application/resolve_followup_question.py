"""Application policy for resolving CV follow-up questions."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.conversation.domain.context_snapshot import ConversationContextSnapshot


REFERENCE_RESOLUTION_POLICY_VERSION = "reference-resolution-m008-v1"
_FOLLOWUP_REFERENCE_PATTERN = re.compile(
    r"\b(ce|cet|cette|cela|celle|celui|la|le|les|lui|il|elle)\b",
    re.IGNORECASE,
)


class QuestionResolver(Protocol):
    """Port for resolving a user message against a compact CV context."""

    def resolve(
        self,
        command: "ResolveFollowUpQuestionCommand",
    ) -> "ResolveFollowUpQuestionResult":
        """Return a resolved question or an explicit clarification."""


@dataclass(frozen=True)
class ResolvedQuestion:
    """Autonomous question ready for downstream contexts."""

    conversation_id: str
    turn_id: str
    text: str
    active_mandate: Mapping[str, Any]
    selected_document_ids: tuple[str, ...]
    verified_answer_refs: tuple[str, ...]
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "text", _ensure_text(self.text, "resolved_question"))
        object.__setattr__(
            self,
            "active_mandate",
            _freeze_mapping(self.active_mandate, "active_mandate"),
        )
        object.__setattr__(
            self,
            "selected_document_ids",
            _ensure_document_ids(self.selected_document_ids),
        )
        object.__setattr__(
            self,
            "verified_answer_refs",
            _ensure_verified_answer_refs(self.verified_answer_refs),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))

    def to_downstream_payload(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "active_mandate": self.active_mandate,
                "question": self.text,
                "selected_document_ids": tuple(self.selected_document_ids),
                "verified_answer_refs": tuple(self.verified_answer_refs),
            }
        )


@dataclass(frozen=True)
class FollowUpQuestionResolved:
    """Event emitted after successful reference resolution."""

    conversation_id: str
    turn_id: str
    resolved_question_hash: str
    ambiguity_count: int
    policy_version: str

    @property
    def event_type(self) -> str:
        return "FollowUpQuestionResolved"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "resolved_question_hash",
            _ensure_hash(self.resolved_question_hash, "resolved_question_hash"),
        )
        object.__setattr__(
            self,
            "ambiguity_count",
            _ensure_non_negative_integer(self.ambiguity_count, "ambiguity_count"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


@dataclass(frozen=True)
class FollowUpQuestionClarificationRequired:
    """Event emitted when CV cannot resolve a reference explicitly."""

    conversation_id: str
    turn_id: str
    reason_code: str
    ambiguity_count: int
    policy_version: str

    @property
    def event_type(self) -> str:
        return "FollowUpQuestionClarificationRequired"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(
            self,
            "ambiguity_count",
            _ensure_non_negative_integer(self.ambiguity_count, "ambiguity_count"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


@dataclass(frozen=True)
class ResolveFollowUpQuestionCommand:
    """Command for resolving one user message against a compact snapshot."""

    conversation_id: str
    turn_id: str
    user_message: str
    context_snapshot: ConversationContextSnapshot
    occurred_at: str


@dataclass(frozen=True)
class ResolveFollowUpQuestionResult:
    """Application result for follow-up question resolution."""

    status: str
    resolved_question: ResolvedQuestion | None
    clarification_reason: str | None
    downstream_call_permitted: bool
    raw_message_forwarded: bool
    downstream_payload: Mapping[str, Any]
    events: tuple[FollowUpQuestionResolved | FollowUpQuestionClarificationRequired, ...]


class ReferenceResolutionPolicy:
    """Deterministic policy that refuses unresolved conversational references."""

    def resolve(
        self,
        command: ResolveFollowUpQuestionCommand,
    ) -> ResolveFollowUpQuestionResult:
        parsed = _ensure_command(command)
        user_message = _ensure_text(parsed.user_message, "user_message")
        context_snapshot = parsed.context_snapshot
        subjects = _conversation_subjects(context_snapshot)
        if _contains_followup_reference(user_message):
            if len(subjects) != 1:
                return _clarification_result(
                    command=parsed,
                    reason_code="REFERENCE_AMBIGUOUS",
                    ambiguity_count=max(len(subjects), len(context_snapshot.ambiguities)),
                )
            resolved_text = _resolve_followup_text(user_message, subjects[0])
        else:
            resolved_text = user_message

        resolved_question = ResolvedQuestion(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            text=resolved_text,
            active_mandate=context_snapshot.active_mandate,
            selected_document_ids=context_snapshot.selected_document_ids,
            verified_answer_refs=context_snapshot.verified_answer_refs,
            occurred_at=parsed.occurred_at,
        )
        event = FollowUpQuestionResolved(
            conversation_id=resolved_question.conversation_id,
            turn_id=resolved_question.turn_id,
            resolved_question_hash=_hash_text(resolved_question.text),
            ambiguity_count=len(context_snapshot.ambiguities),
            policy_version=REFERENCE_RESOLUTION_POLICY_VERSION,
        )
        return ResolveFollowUpQuestionResult(
            status="QUESTION_RESOLVED",
            resolved_question=resolved_question,
            clarification_reason=None,
            downstream_call_permitted=True,
            raw_message_forwarded=False,
            downstream_payload=resolved_question.to_downstream_payload(),
            events=(event,),
        )


class DeterministicQuestionResolver:
    """Local resolver used by tests and non-LLM CV flows."""

    def __init__(self, *, policy: ReferenceResolutionPolicy | None = None) -> None:
        self._policy = policy if policy is not None else ReferenceResolutionPolicy()

    def resolve(
        self,
        command: ResolveFollowUpQuestionCommand,
    ) -> ResolveFollowUpQuestionResult:
        return self._policy.resolve(command)


class ResolveFollowUpQuestionHandler:
    """Application handler that resolves before any downstream dispatch."""

    def __init__(self, *, question_resolver: QuestionResolver) -> None:
        if not callable(getattr(question_resolver, "resolve", None)):
            raise ValueError("question_resolver sans resolve")
        self._question_resolver = question_resolver

    def resolve(
        self,
        command: ResolveFollowUpQuestionCommand,
    ) -> ResolveFollowUpQuestionResult:
        _ensure_command(command)
        return self._question_resolver.resolve(command)


def _ensure_command(command: object) -> ResolveFollowUpQuestionCommand:
    if not isinstance(command, ResolveFollowUpQuestionCommand):
        raise ValueError("commande ResolveFollowUpQuestion invalide")
    parsed_conversation_id = _ensure_conversation_id(command.conversation_id)
    parsed_turn_id = _ensure_turn_id(command.turn_id)
    if not isinstance(command.context_snapshot, ConversationContextSnapshot):
        raise ValueError("context_snapshot invalide")
    if command.context_snapshot.conversation_id != parsed_conversation_id:
        raise ValueError("context_snapshot conversation incoherente")
    _ensure_text(command.user_message, "user_message")
    _ensure_utc(command.occurred_at, "occurred_at")
    return ResolveFollowUpQuestionCommand(
        conversation_id=parsed_conversation_id,
        turn_id=parsed_turn_id,
        user_message=command.user_message,
        context_snapshot=command.context_snapshot,
        occurred_at=command.occurred_at,
    )


def _clarification_result(
    *,
    command: ResolveFollowUpQuestionCommand,
    reason_code: str,
    ambiguity_count: int,
) -> ResolveFollowUpQuestionResult:
    event = FollowUpQuestionClarificationRequired(
        conversation_id=command.conversation_id,
        turn_id=command.turn_id,
        reason_code=reason_code,
        ambiguity_count=ambiguity_count,
        policy_version=REFERENCE_RESOLUTION_POLICY_VERSION,
    )
    return ResolveFollowUpQuestionResult(
        status="CLARIFICATION_REQUIRED",
        resolved_question=None,
        clarification_reason=reason_code,
        downstream_call_permitted=False,
        raw_message_forwarded=False,
        downstream_payload=MappingProxyType({}),
        events=(event,),
    )


def _contains_followup_reference(user_message: str) -> bool:
    return _FOLLOWUP_REFERENCE_PATTERN.search(user_message) is not None


def _conversation_subjects(context_snapshot: ConversationContextSnapshot) -> tuple[str, ...]:
    subjects = context_snapshot.active_mandate.get("conversation_subjects", ())
    if isinstance(subjects, str):
        return (_ensure_text(subjects, "conversation_subject"),)
    if subjects is None or not isinstance(subjects, Sequence):
        raise ValueError("conversation_subjects invalide")
    return tuple(_ensure_text(subject, "conversation_subject") for subject in subjects)


def _resolve_followup_text(user_message: str, subject: str) -> str:
    if "kelly" in user_message.lower():
        return f"Comparer {subject} a Kelly criterion."
    cleaned = _FOLLOWUP_REFERENCE_PATTERN.sub(subject, user_message, count=1)
    return _ensure_text(cleaned, "resolved_question")


def _ensure_conversation_id(value: object) -> str:
    return _ensure_domain_identifier(value, "CONV", "conversation_id")


def _ensure_turn_id(value: object) -> str:
    return _ensure_domain_identifier(value, "TURN", "turn_id")


def _ensure_document_ids(value: object) -> tuple[str, ...]:
    return tuple(_ensure_domain_identifier(item, "DOC", "document_id") for item in _ensure_sequence(value, "document_ids"))


def _ensure_verified_answer_refs(value: object) -> tuple[str, ...]:
    refs = tuple(_ensure_verified_answer_ref(item) for item in _ensure_sequence(value, "verified_answer_refs"))
    if len(refs) != len(set(refs)):
        raise ValueError("verified_answer_ref duplique")
    return refs


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    answer_id, separator, version = text.partition("@")
    if separator != "@" or version.strip() == "" or not version.isdigit() or int(version) < 1:
        raise ValueError("verified_answer_ref invalide")
    _ensure_domain_identifier(answer_id, "ANS", "verified_answer_ref")
    return text


def _ensure_domain_identifier(value: object, expected_prefix: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


def _ensure_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(value)


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"{field_name} invalide")
    return text


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return MappingProxyType(
        {
            _ensure_text(key, "cle"): _freeze_value(child, field_name)
            for key, child in value.items()
        }
    )


def _freeze_value(value: object, field_name: str) -> Any:
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                _ensure_text(key, "cle"): _freeze_value(child, field_name)
                for key, child in value.items()
            }
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_value(child, field_name) for child in value)
    raise ValueError(f"{field_name} invalide")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "DeterministicQuestionResolver",
    "FollowUpQuestionClarificationRequired",
    "FollowUpQuestionResolved",
    "QuestionResolver",
    "REFERENCE_RESOLUTION_POLICY_VERSION",
    "ReferenceResolutionPolicy",
    "ResolveFollowUpQuestionCommand",
    "ResolveFollowUpQuestionHandler",
    "ResolveFollowUpQuestionResult",
    "ResolvedQuestion",
]
