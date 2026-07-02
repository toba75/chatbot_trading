"""CV policy for reusing or revalidating historical answer results."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.attach_verified_answer import (
    AttachVerifiedAnswerToTurnCommand,
    AttachVerifiedAnswerToTurnHandler,
    VerifiedAnswerAttachment,
    VerifiedAnswerAttachmentStore,
    VerifiedAnswerAttachedToTurn,
)
from app.conversation.application.resolve_followup_question import ResolvedQuestion


VERIFIED_RESULT_REUSE_POLICY_VERSION = "verified-result-reuse-m008-v1"


class ResearchFacade(Protocol):
    """CV port toward RA public answer workflow."""

    def answer(self, request: "ResearchRevalidationRequest") -> PublicResearchAnswerResult:
        """Return a public RA answer result."""


@dataclass(frozen=True)
class HistoricalAssertionRef:
    """Historical assertion candidate for reuse."""

    assertion_text: str
    verified_answer_ref: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assertion_text",
            _ensure_text(self.assertion_text, "historical_assertion"),
        )
        if self.verified_answer_ref is not None:
            object.__setattr__(
                self,
                "verified_answer_ref",
                _ensure_verified_answer_ref(self.verified_answer_ref),
            )


@dataclass(frozen=True)
class VerifiedResultReuseDecision:
    """Decision separating reusable versions from assertions to revalidate."""

    assertions_to_revalidate: tuple[str, ...]
    reusable_answer_refs: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalAssertionRevalidationRequested:
    """Event emitted before CV asks RA to revalidate historical text."""

    conversation_id: str
    turn_id: str
    historical_assertion_hash: str
    reason_code: str
    policy_version: str

    @property
    def event_type(self) -> str:
        return "HistoricalAssertionRevalidationRequested"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "historical_assertion_hash",
            _ensure_hash(self.historical_assertion_hash, "historical_assertion_hash"),
        )
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


@dataclass(frozen=True)
class ResearchRevalidationRequest:
    """Public CV request toward RA for historical assertion revalidation."""

    conversation_id: str
    turn_id: str
    resolved_question_text: str
    historical_assertions: tuple[str, ...]
    research_mandate: Mapping[str, Any]
    requested_by_context: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "resolved_question_text",
            _ensure_text(self.resolved_question_text, "resolved_question_text"),
        )
        object.__setattr__(
            self,
            "historical_assertions",
            _ensure_text_sequence(self.historical_assertions, "historical_assertion"),
        )
        object.__setattr__(
            self,
            "research_mandate",
            _freeze_mapping(self.research_mandate, "research_mandate"),
        )
        if self.requested_by_context != "CV":
            raise ValueError("requested_by_context CV requis")
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ReuseVerifiedResultCommand:
    """Command that revalidates historical assertions before attachment."""

    conversation_id: str
    turn_id: str
    resolved_question: ResolvedQuestion
    historical_assertions: Sequence[HistoricalAssertionRef]
    research_mandate: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True)
class ReuseVerifiedResultResult:
    """Result of historical reuse or RA revalidation."""

    status: str
    attachment: VerifiedAnswerAttachment | None
    reusable_answer_refs: tuple[str, ...]
    events: tuple[HistoricalAssertionRevalidationRequested | VerifiedAnswerAttachedToTurn, ...]


class VerifiedResultReusePolicy:
    """Requires RA revalidation for historical assertions without version."""

    def plan(
        self,
        historical_assertions: Sequence[HistoricalAssertionRef],
    ) -> VerifiedResultReuseDecision:
        assertions = _ensure_historical_assertions(historical_assertions)
        to_revalidate: list[str] = []
        reusable_refs: list[str] = []
        for assertion in assertions:
            if assertion.verified_answer_ref is None:
                to_revalidate.append(assertion.assertion_text)
            else:
                reusable_refs.append(assertion.verified_answer_ref)
        return VerifiedResultReuseDecision(
            assertions_to_revalidate=tuple(to_revalidate),
            reusable_answer_refs=tuple(reusable_refs),
        )


class ReuseVerifiedResultHandler:
    """Orchestrates RA revalidation and CV answer attachment."""

    def __init__(
        self,
        *,
        research_facade: ResearchFacade,
        attachment_store: VerifiedAnswerAttachmentStore,
        policy: VerifiedResultReusePolicy | None = None,
    ) -> None:
        if not callable(getattr(research_facade, "answer", None)):
            raise ValueError("research_facade sans answer")
        self._research_facade = research_facade
        self._attachment_handler = AttachVerifiedAnswerToTurnHandler(
            attachment_store=attachment_store
        )
        self._policy = policy if policy is not None else VerifiedResultReusePolicy()

    def reuse_or_revalidate(
        self,
        command: ReuseVerifiedResultCommand,
    ) -> ReuseVerifiedResultResult:
        parsed = _ensure_command(command)
        decision = self._policy.plan(parsed.historical_assertions)
        if len(decision.assertions_to_revalidate) == 0:
            return ReuseVerifiedResultResult(
                status="VERIFIED_RESULT_REUSED",
                attachment=None,
                reusable_answer_refs=decision.reusable_answer_refs,
                events=(),
            )
        revalidation_events = tuple(
            HistoricalAssertionRevalidationRequested(
                conversation_id=parsed.conversation_id,
                turn_id=parsed.turn_id,
                historical_assertion_hash=_hash_text(assertion),
                reason_code="VERIFIED_ANSWER_VERSION_REQUIRED",
                policy_version=VERIFIED_RESULT_REUSE_POLICY_VERSION,
            )
            for assertion in decision.assertions_to_revalidate
        )
        request = ResearchRevalidationRequest(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            resolved_question_text=parsed.resolved_question.text,
            historical_assertions=decision.assertions_to_revalidate,
            research_mandate=parsed.research_mandate,
            requested_by_context="CV",
            occurred_at=parsed.occurred_at,
        )
        answer_result = self._research_facade.answer(request)
        if not isinstance(answer_result, PublicResearchAnswerResult):
            raise ValueError("answer_result invalide")
        attached = self._attachment_handler.attach(
            AttachVerifiedAnswerToTurnCommand(
                conversation_id=parsed.conversation_id,
                turn_id=parsed.turn_id,
                resolved_question=parsed.resolved_question,
                answer_result=answer_result,
                occurred_at=parsed.occurred_at,
            )
        )
        return ReuseVerifiedResultResult(
            status=attached.status,
            attachment=attached.attachment,
            reusable_answer_refs=decision.reusable_answer_refs,
            events=revalidation_events + attached.events,
        )


def _ensure_command(command: object) -> ReuseVerifiedResultCommand:
    if not isinstance(command, ReuseVerifiedResultCommand):
        raise ValueError("commande ReuseVerifiedResult invalide")
    conversation_id = _ensure_conversation_id(command.conversation_id)
    turn_id = _ensure_turn_id(command.turn_id)
    if not isinstance(command.resolved_question, ResolvedQuestion):
        raise ValueError("resolved_question invalide")
    if command.resolved_question.conversation_id != conversation_id:
        raise ValueError("resolved_question conversation incoherente")
    if command.resolved_question.turn_id != turn_id:
        raise ValueError("resolved_question turn incoherent")
    _ensure_historical_assertions(command.historical_assertions)
    _freeze_mapping(command.research_mandate, "research_mandate")
    _ensure_utc(command.occurred_at, "occurred_at")
    return command


def _ensure_historical_assertions(
    value: object,
) -> tuple[HistoricalAssertionRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("historical_assertions invalides")
    assertions = tuple(value)
    if len(assertions) == 0:
        raise ValueError("historical_assertions absentes")
    for assertion in assertions:
        if not isinstance(assertion, HistoricalAssertionRef):
            raise ValueError("historical_assertion invalide")
    return assertions


def _ensure_text_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absent")
    return parsed


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
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_value(child, field_name) for child in value)
    raise ValueError(f"{field_name} invalide")


def _ensure_conversation_id(value: object) -> str:
    return _ensure_domain_identifier(value, "CONV", "conversation_id")


def _ensure_turn_id(value: object) -> str:
    return _ensure_domain_identifier(value, "TURN", "turn_id")


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    answer_id, separator, version = text.partition("@")
    if separator != "@" or not version.isdigit() or int(version) < 1:
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


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _hash_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "historical_assertion").encode("utf-8")).hexdigest()


__all__ = [
    "HistoricalAssertionRef",
    "HistoricalAssertionRevalidationRequested",
    "ResearchFacade",
    "ResearchRevalidationRequest",
    "ReuseVerifiedResultCommand",
    "ReuseVerifiedResultHandler",
    "ReuseVerifiedResultResult",
    "VERIFIED_RESULT_REUSE_POLICY_VERSION",
    "VerifiedResultReuseDecision",
    "VerifiedResultReusePolicy",
]
