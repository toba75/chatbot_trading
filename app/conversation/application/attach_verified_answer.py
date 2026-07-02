"""Attach public verified RA answers to CV turns."""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.resolve_followup_question import ResolvedQuestion


@dataclass(frozen=True)
class VerifiedAnswerAttachedToTurn:
    """Event emitted when CV references a public RA answer."""

    conversation_id: str
    turn_id: str
    answer_id: str
    support_status: str
    verified_answer_ref: str

    @property
    def event_type(self) -> str:
        return "VerifiedAnswerAttachedToTurn"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "support_status",
            _ensure_text(self.support_status, "support_status"),
        )
        object.__setattr__(
            self,
            "verified_answer_ref",
            _ensure_verified_answer_ref(self.verified_answer_ref),
        )


@dataclass(frozen=True)
class VerifiedAnswerAttachment:
    """CV reference to a public RA answer attached to one turn."""

    conversation_id: str
    turn_id: str
    resolved_question_text_hash: str
    answer_id: str
    verified_answer_ref: str
    support_status: str
    verified_research_outcome: Any
    answer_text: str
    citations: tuple[Mapping[str, Any], ...]
    attached_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "resolved_question_text_hash",
            _ensure_hash(self.resolved_question_text_hash, "resolved_question_text_hash"),
        )
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "verified_answer_ref",
            _ensure_verified_answer_ref(self.verified_answer_ref),
        )
        object.__setattr__(
            self,
            "support_status",
            _ensure_text(self.support_status, "support_status"),
        )
        object.__setattr__(
            self,
            "verified_research_outcome",
            _ensure_verified_research_outcome(self.verified_research_outcome),
        )
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        object.__setattr__(
            self,
            "citations",
            _ensure_citations(self.citations),
        )
        object.__setattr__(self, "attached_at", _ensure_utc(self.attached_at, "attached_at"))
        if self.verified_research_outcome.answer_id != self.answer_id:
            raise ValueError("answer_id incoherent")
        if self.verified_research_outcome.support_status != self.support_status:
            raise ValueError("support_status incoherent")


class VerifiedAnswerAttachmentStore(Protocol):
    """Port storing answer attachment references by turn."""

    def save(self, attachment: VerifiedAnswerAttachment) -> VerifiedAnswerAttachment:
        """Persist one attachment."""


@dataclass(frozen=True)
class AttachVerifiedAnswerToTurnCommand:
    """Command attaching a public RA answer result to one CV turn."""

    conversation_id: str
    turn_id: str
    resolved_question: ResolvedQuestion
    answer_result: PublicResearchAnswerResult
    occurred_at: str


@dataclass(frozen=True)
class AttachVerifiedAnswerToTurnResult:
    """Result of a verified answer attachment."""

    status: str
    attachment: VerifiedAnswerAttachment
    events: tuple[VerifiedAnswerAttachedToTurn, ...]


class AttachVerifiedAnswerToTurnHandler:
    """Application handler for answer attachment."""

    def __init__(self, *, attachment_store: VerifiedAnswerAttachmentStore) -> None:
        if not callable(getattr(attachment_store, "save", None)):
            raise ValueError("attachment_store sans save")
        self._attachment_store = attachment_store

    def attach(
        self,
        command: AttachVerifiedAnswerToTurnCommand,
    ) -> AttachVerifiedAnswerToTurnResult:
        parsed = _ensure_command(command)
        answer_result = parsed.answer_result
        if answer_result.verified_research_outcome.question != parsed.resolved_question.text:
            raise ValueError("question reponse incoherente")
        attachment = VerifiedAnswerAttachment(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            resolved_question_text_hash=_hash_text(parsed.resolved_question.text),
            answer_id=answer_result.answer_id,
            verified_answer_ref=answer_result.verified_answer_ref,
            support_status=answer_result.support_status,
            verified_research_outcome=answer_result.verified_research_outcome,
            answer_text=answer_result.answer_text,
            citations=tuple(answer_result.citations),
            attached_at=parsed.occurred_at,
        )
        saved = self._attachment_store.save(attachment)
        event = VerifiedAnswerAttachedToTurn(
            conversation_id=saved.conversation_id,
            turn_id=saved.turn_id,
            answer_id=saved.answer_id,
            support_status=saved.support_status,
            verified_answer_ref=saved.verified_answer_ref,
        )
        return AttachVerifiedAnswerToTurnResult(
            status="VERIFIED_RESULT_ATTACHED",
            attachment=saved,
            events=(event,),
        )


class InMemoryVerifiedAnswerAttachmentStore:
    """In-memory strict store for one answer attachment per turn."""

    def __init__(self, *, known_turn_ids: Sequence[str]) -> None:
        self._lock = threading.Lock()
        self._known_turn_ids = frozenset(_ensure_turn_id(turn_id) for turn_id in known_turn_ids)
        self._attachments_by_turn_id: dict[str, VerifiedAnswerAttachment] = {}

    def save(self, attachment: VerifiedAnswerAttachment) -> VerifiedAnswerAttachment:
        parsed = _ensure_attachment(attachment)
        with self._lock:
            if parsed.turn_id not in self._known_turn_ids:
                raise ValueError("turn conversation inconnu")
            if parsed.turn_id in self._attachments_by_turn_id:
                raise ValueError("verified_answer deja rattachee")
            self._attachments_by_turn_id[parsed.turn_id] = parsed
            return parsed

    def attachment_for_turn(self, turn_id: str) -> VerifiedAnswerAttachment:
        parsed_turn_id = _ensure_turn_id(turn_id)
        with self._lock:
            attachment = self._attachments_by_turn_id.get(parsed_turn_id)
            if attachment is None:
                raise ValueError("verified_answer inconnue")
            return attachment


def _ensure_command(command: object) -> AttachVerifiedAnswerToTurnCommand:
    if not isinstance(command, AttachVerifiedAnswerToTurnCommand):
        raise ValueError("commande AttachVerifiedAnswerToTurn invalide")
    conversation_id = _ensure_conversation_id(command.conversation_id)
    turn_id = _ensure_turn_id(command.turn_id)
    if not isinstance(command.resolved_question, ResolvedQuestion):
        raise ValueError("resolved_question invalide")
    if command.resolved_question.conversation_id != conversation_id:
        raise ValueError("resolved_question conversation incoherente")
    if command.resolved_question.turn_id != turn_id:
        raise ValueError("resolved_question turn incoherent")
    if not isinstance(command.answer_result, PublicResearchAnswerResult):
        raise ValueError("answer_result invalide")
    _ensure_utc(command.occurred_at, "occurred_at")
    return command


def _ensure_attachment(value: object) -> VerifiedAnswerAttachment:
    if not isinstance(value, VerifiedAnswerAttachment):
        raise ValueError("verified_answer_attachment invalide")
    return value


def _ensure_citations(value: object) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(value)
    if len(citations) == 0:
        raise ValueError("citations absentes")
    for citation in citations:
        if not isinstance(citation, Mapping):
            raise ValueError("citation non objet")
    return citations


def _ensure_conversation_id(value: object) -> str:
    return _ensure_domain_identifier(value, "CONV", "conversation_id")


def _ensure_turn_id(value: object) -> str:
    return _ensure_domain_identifier(value, "TURN", "turn_id")


def _ensure_answer_id(value: object) -> str:
    return _ensure_domain_identifier(value, "ANS", "answer_id")


def _ensure_verified_research_outcome(value: object) -> object:
    required_attributes = ("answer_id", "question", "support_status", "to_payload")
    if not all(hasattr(value, attribute) for attribute in required_attributes):
        raise ValueError("verified_research_outcome invalide")
    if not callable(getattr(value, "to_payload")):
        raise ValueError("verified_research_outcome invalide")
    if hasattr(value, "answer_text") or hasattr(value, "citations"):
        raise ValueError("verified_research_outcome enrichi interdit")
    _ensure_answer_id(getattr(value, "answer_id"))
    _ensure_text(getattr(value, "question"), "question")
    _ensure_text(getattr(value, "support_status"), "support_status")
    return value


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    answer_id, separator, version = text.partition("@")
    if separator != "@" or not version.isdigit() or int(version) < 1:
        raise ValueError("verified_answer_ref invalide")
    _ensure_answer_id(answer_id)
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
    return hashlib.sha256(_ensure_text(value, "resolved_question").encode("utf-8")).hexdigest()


__all__ = [
    "AttachVerifiedAnswerToTurnCommand",
    "AttachVerifiedAnswerToTurnHandler",
    "AttachVerifiedAnswerToTurnResult",
    "InMemoryVerifiedAnswerAttachmentStore",
    "VerifiedAnswerAttachedToTurn",
    "VerifiedAnswerAttachment",
    "VerifiedAnswerAttachmentStore",
]
