"""Product presentation for CV answer turns."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult


_SUPPORT_STATUSES = frozenset(
    {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
        "REQUIRES_CURRENT_DATA",
    }
)
_FORBIDDEN_PUBLIC_TOKENS = ("prompt", "qdrant", "ra_storage", "eg_registry", "draft_text")


@dataclass(frozen=True)
class ConversationPublicResponsePresented:
    """Event emitted when a CV answer is rendered for product use."""

    conversation_id: str
    turn_id: str
    support_status: str
    citation_count: int
    presentation_hash: str

    @property
    def event_type(self) -> str:
        return "ConversationPublicResponsePresented"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "support_status",
            _ensure_support_status(self.support_status),
        )
        object.__setattr__(
            self,
            "citation_count",
            _ensure_non_negative_integer(self.citation_count, "citation_count"),
        )
        object.__setattr__(
            self,
            "presentation_hash",
            _ensure_hash(self.presentation_hash, "presentation_hash"),
        )


@dataclass(frozen=True)
class PublicAnswerPresentationDto:
    """Public CV answer view built from the public RA DTO."""

    conversation_id: str
    turn_id: str
    answer_id: str
    verified_answer_ref: str
    answer_text: str
    support_status: str
    citations: Sequence[Mapping[str, Any]]
    knowledge_gaps: Sequence[Mapping[str, Any]]
    unresolved_conflicts: Sequence[Mapping[str, Any]]
    abstention_reason: str | None
    presented_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "verified_answer_ref",
            _ensure_verified_answer_ref(self.verified_answer_ref),
        )
        object.__setattr__(self, "answer_text", _ensure_public_text(self.answer_text, "answer_text"))
        status = _ensure_support_status(self.support_status)
        object.__setattr__(self, "support_status", status)
        citations = _ensure_public_citations(
            self.citations,
            allow_empty=status == "REQUIRES_CURRENT_DATA",
        )
        object.__setattr__(self, "citations", citations)
        knowledge_gaps = _ensure_public_refs(self.knowledge_gaps, "knowledge_gap")
        unresolved_conflicts = _ensure_public_refs(
            self.unresolved_conflicts,
            "unresolved_conflict",
        )
        if status in {"INSUFFICIENT_EVIDENCE", "REQUIRES_CURRENT_DATA"} and len(knowledge_gaps) == 0:
            raise ValueError("knowledge_gaps absentes")
        if status == "CONFLICTING_EVIDENCE" and len(unresolved_conflicts) == 0:
            raise ValueError("unresolved_conflicts absents")
        object.__setattr__(self, "knowledge_gaps", knowledge_gaps)
        object.__setattr__(self, "unresolved_conflicts", unresolved_conflicts)
        object.__setattr__(
            self,
            "abstention_reason",
            _ensure_abstention_reason(
                self.abstention_reason,
                requires_current_data=status == "REQUIRES_CURRENT_DATA",
            ),
        )
        object.__setattr__(self, "presented_at", _ensure_utc(self.presented_at, "presented_at"))

    def to_payload(self) -> Mapping[str, Any]:
        payload = MappingProxyType(
            {
                "abstention_reason": self.abstention_reason,
                "answer_id": self.answer_id,
                "answer_text": self.answer_text,
                "citations": tuple(self.citations),
                "conversation_id": self.conversation_id,
                "knowledge_gaps": tuple(self.knowledge_gaps),
                "presented_at": self.presented_at,
                "support_status": self.support_status,
                "turn_id": self.turn_id,
                "unresolved_conflicts": tuple(self.unresolved_conflicts),
                "verified_answer_ref": self.verified_answer_ref,
            }
        )
        _ensure_no_forbidden_public_tokens(payload)
        return payload


@dataclass(frozen=True)
class PresentConversationAnswerCommand:
    """Command rendering a public answer result for one CV turn."""

    conversation_id: str
    turn_id: str
    answer_result: PublicResearchAnswerResult
    occurred_at: str


@dataclass(frozen=True)
class PresentConversationAnswerResult:
    """Application result for public answer presentation."""

    status: str
    presentation: PublicAnswerPresentationDto
    events: tuple[ConversationPublicResponsePresented, ...]


class PublicAnswerPresentationPolicy:
    """Maps public RA answer DTOs to product-facing CV DTOs."""

    def present(
        self,
        *,
        conversation_id: str,
        turn_id: str,
        answer_result: PublicResearchAnswerResult,
        occurred_at: str,
    ) -> PublicAnswerPresentationDto:
        if not isinstance(answer_result, PublicResearchAnswerResult):
            raise ValueError("answer_result invalide")
        outcome_payload = _ensure_outcome_payload(answer_result.verified_research_outcome)
        support_status = _ensure_support_status(outcome_payload["support_status"])
        if support_status != answer_result.support_status:
            raise ValueError("support_status incoherent")
        if outcome_payload["answer_id"] != answer_result.answer_id:
            raise ValueError("answer_id incoherent")
        return PublicAnswerPresentationDto(
            conversation_id=conversation_id,
            turn_id=turn_id,
            answer_id=answer_result.answer_id,
            verified_answer_ref=answer_result.verified_answer_ref,
            answer_text=answer_result.answer_text,
            support_status=support_status,
            citations=answer_result.citations,
            knowledge_gaps=tuple(outcome_payload.get("knowledge_gaps", ())),
            unresolved_conflicts=tuple(outcome_payload.get("unresolved_conflicts", ())),
            abstention_reason=answer_result.abstention_reason,
            presented_at=occurred_at,
        )


class PresentConversationAnswerHandler:
    """Application handler for answer presentation."""

    def __init__(self, *, policy: PublicAnswerPresentationPolicy | None = None) -> None:
        self._policy = policy if policy is not None else PublicAnswerPresentationPolicy()

    def present(
        self,
        command: PresentConversationAnswerCommand,
    ) -> PresentConversationAnswerResult:
        parsed = _ensure_command(command)
        presentation = self._policy.present(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            answer_result=parsed.answer_result,
            occurred_at=parsed.occurred_at,
        )
        event = ConversationPublicResponsePresented(
            conversation_id=presentation.conversation_id,
            turn_id=presentation.turn_id,
            support_status=presentation.support_status,
            citation_count=len(presentation.citations),
            presentation_hash=_hash_text(repr(presentation.to_payload())),
        )
        return PresentConversationAnswerResult(
            status="CONVERSATION_PUBLIC_RESPONSE_PRESENTED",
            presentation=presentation,
            events=(event,),
        )


def _ensure_command(command: object) -> PresentConversationAnswerCommand:
    if not isinstance(command, PresentConversationAnswerCommand):
        raise ValueError("commande PresentConversationAnswer invalide")
    _ensure_conversation_id(command.conversation_id)
    _ensure_turn_id(command.turn_id)
    if not isinstance(command.answer_result, PublicResearchAnswerResult):
        raise ValueError("answer_result invalide")
    _ensure_utc(command.occurred_at, "occurred_at")
    return command


def _ensure_outcome_payload(verified_research_outcome: object) -> Mapping[str, Any]:
    if not callable(getattr(verified_research_outcome, "to_payload", None)):
        raise ValueError("verified_research_outcome invalide")
    payload = verified_research_outcome.to_payload()
    if not isinstance(payload, Mapping):
        raise ValueError("verified_research_outcome payload invalide")
    if "answer_id" not in payload:
        raise ValueError("answer_id absent")
    if "support_status" not in payload:
        raise ValueError("support_status absent")
    return payload


def _ensure_public_citations(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(_ensure_public_citation(citation) for citation in value)
    if len(citations) == 0 and not allow_empty:
        raise ValueError("citations absentes")
    return citations


def _ensure_public_citation(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("citation non objet")
    for field_name in ("citation_id", "evidence_id", "source_locator", "quoted_span_hash"):
        if field_name not in value:
            raise ValueError(f"citation {field_name} absent")
    source_locator = _ensure_source_locator(value["source_locator"])
    citation = MappingProxyType(
        {
            "citation_id": _ensure_public_text(value["citation_id"], "citation_id"),
            "evidence_id": _ensure_public_text(value["evidence_id"], "evidence_id"),
            "quoted_span_hash": _ensure_public_text(
                value["quoted_span_hash"],
                "quoted_span_hash",
            ),
            "source_locator": source_locator,
        }
    )
    _ensure_no_forbidden_public_tokens(citation)
    return citation


def _ensure_source_locator(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("source_locator non objet")
    required_fields = (
        "schema_version",
        "canonical_version_id",
        "document_id",
        "page_pdf",
        "item_id",
        "bbox",
        "content_hash",
    )
    for field_name in required_fields:
        if field_name not in value:
            raise ValueError(f"source_locator {field_name} absent")
    return MappingProxyType(
        {
            "bbox": tuple(value["bbox"]),
            "canonical_version_id": _ensure_public_text(
                value["canonical_version_id"],
                "canonical_version_id",
            ),
            "content_hash": _ensure_public_text(value["content_hash"], "content_hash"),
            "document_id": _ensure_document_id(value["document_id"]),
            "item_id": _ensure_public_text(value["item_id"], "item_id"),
            "page_pdf": _ensure_positive_integer(value["page_pdf"], "page_pdf"),
            "schema_version": _ensure_public_text(value["schema_version"], "schema_version"),
        }
    )


def _ensure_public_refs(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    refs = tuple(_freeze_mapping(item, field_name) for item in value)
    for ref in refs:
        _ensure_no_forbidden_public_tokens(ref)
    return refs


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return MappingProxyType(
        {
            _ensure_public_text(key, "cle"): _freeze_value(child, field_name)
            for key, child in value.items()
        }
    )


def _freeze_value(value: object, field_name: str) -> Any:
    if isinstance(value, str):
        return _ensure_public_text(value, field_name)
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


def _ensure_no_forbidden_public_tokens(value: object) -> None:
    serialized = repr(value).lower()
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        if forbidden in serialized:
            raise ValueError(f"payload sensible interdit: {forbidden}")


def _ensure_abstention_reason(value: object, *, requires_current_data: bool) -> str | None:
    if requires_current_data:
        reason = _ensure_public_text(value, "abstention_reason")
        if reason != "CURRENT_DATA_REQUIRED":
            raise ValueError("abstention_reason CURRENT_DATA_REQUIRED requis")
        return reason
    if value is not None:
        raise ValueError("abstention_reason interdit")
    return None


def _ensure_conversation_id(value: object) -> str:
    return _ensure_domain_identifier(value, "CONV", "conversation_id")


def _ensure_turn_id(value: object) -> str:
    return _ensure_domain_identifier(value, "TURN", "turn_id")


def _ensure_answer_id(value: object) -> str:
    return _ensure_domain_identifier(value, "ANS", "answer_id")


def _ensure_document_id(value: object) -> str:
    return _ensure_domain_identifier(value, "DOC", "document_id")


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_public_text(value, "verified_answer_ref")
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


def _ensure_support_status(value: object) -> str:
    status = _ensure_public_text(value, "support_status")
    if status not in _SUPPORT_STATUSES:
        raise ValueError("support_status invalide")
    return status


def _ensure_public_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    lowered = value.lower()
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        if forbidden in lowered:
            raise ValueError(f"payload sensible interdit: {forbidden}")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc(value: object, field_name: str) -> str:
    text = _ensure_public_text(value, field_name)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_public_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _hash_text(value: str) -> str:
    return hashlib.sha256(_ensure_public_text(value, "presentation").encode("utf-8")).hexdigest()


__all__ = [
    "ConversationPublicResponsePresented",
    "PresentConversationAnswerCommand",
    "PresentConversationAnswerHandler",
    "PresentConversationAnswerResult",
    "PublicAnswerPresentationDto",
    "PublicAnswerPresentationPolicy",
]
