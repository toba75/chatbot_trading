"""Orchestration CV du mode recherche approfondie M-009."""

from __future__ import annotations

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
from app.conversation.application.select_mode import (
    DeterministicModeClassifier,
    SelectConversationModeCommand,
    SelectConversationModeHandler,
)
from app.conversation.domain.mode_routing import (
    ConversationMode,
    ConversationModeSelected,
    ConversationModeSelection,
)


class DeepResearchConversationFacade(Protocol):
    """Port CV vers la facade RA approfondie M-009."""

    def answer_deep_research(
        self,
        request: "DeepResearchConversationRequest",
    ) -> PublicResearchAnswerResult:
        """Retourne le resultat RA public a rattacher au tour."""


@dataclass(frozen=True)
class DeepResearchConversationResolvedQuestion:
    """Vue minimale de question resolue transmise aux adaptateurs de facade."""

    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_text(self.text, "resolved_question_text"))


@dataclass(frozen=True)
class DeepResearchConversationRequest:
    """Requete CV publique transmise a RA pour le mode approfondi."""

    conversation_id: str
    turn_id: str
    resolved_question_text: str
    research_mandate: Mapping[str, Any]
    selected_document_ids: Sequence[str]
    research_mode: str
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
            "research_mandate",
            _freeze_mapping(self.research_mandate, "research_mandate"),
        )
        object.__setattr__(
            self,
            "selected_document_ids",
            _ensure_document_ids(self.selected_document_ids),
        )
        if self.research_mode != "DEEP_RESEARCH":
            raise ValueError("research_mode DEEP_RESEARCH requis")
        if self.requested_by_context != "CV":
            raise ValueError("requested_by_context CV requis")
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))

    @property
    def resolved_question(self) -> DeepResearchConversationResolvedQuestion:
        return DeepResearchConversationResolvedQuestion(text=self.resolved_question_text)


@dataclass(frozen=True)
class AnswerDeepResearchConversationTurnCommand:
    """Commande CV qui selectionne le mode approfondi puis appelle RA."""

    conversation_id: str
    turn_id: str
    resolved_question: ResolvedQuestion
    requested_mode: str | ConversationMode | None
    research_mandate: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True)
class AnswerDeepResearchConversationTurnResult:
    """Resultat CV apres rattachement d'une recherche approfondie."""

    status: str
    selection: ConversationModeSelection
    attachment: VerifiedAnswerAttachment
    events: tuple[ConversationModeSelected | VerifiedAnswerAttachedToTurn, ...]

    def __post_init__(self) -> None:
        if self.status != "DEEP_RESEARCH_RESULT_ATTACHED":
            raise ValueError("status AnswerDeepResearchConversationTurn invalide")
        if not isinstance(self.selection, ConversationModeSelection):
            raise ValueError("selection mode invalide")
        if not isinstance(self.attachment, VerifiedAnswerAttachment):
            raise ValueError("verified_answer_attachment invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


class AnswerDeepResearchConversationTurnHandler:
    """Execute seulement le mode CV RECHERCHE_APPROFONDIE configure."""

    def __init__(
        self,
        *,
        deep_research_facade: DeepResearchConversationFacade | None,
        attachment_store: VerifiedAnswerAttachmentStore,
        mode_selector: SelectConversationModeHandler | None = None,
    ) -> None:
        if deep_research_facade is not None and not callable(
            getattr(deep_research_facade, "answer_deep_research", None)
        ):
            raise ValueError("deep_research_facade sans answer_deep_research")
        if not callable(getattr(attachment_store, "save", None)):
            raise ValueError("attachment_store sans save")
        self._deep_research_facade = deep_research_facade
        self._mode_selector = (
            mode_selector
            if mode_selector is not None
            else SelectConversationModeHandler(mode_classifier=DeterministicModeClassifier())
        )
        self._attachment_handler = AttachVerifiedAnswerToTurnHandler(
            attachment_store=attachment_store
        )

    def answer(
        self,
        command: AnswerDeepResearchConversationTurnCommand,
    ) -> AnswerDeepResearchConversationTurnResult:
        parsed = _ensure_command(command)
        selected = self._mode_selector.select(
            SelectConversationModeCommand(
                conversation_id=parsed.conversation_id,
                turn_id=parsed.turn_id,
                resolved_question=parsed.resolved_question,
                requested_mode=parsed.requested_mode,
                available_modes=available_modes_for_deep_research_facade(
                    self._deep_research_facade
                ),
                occurred_at=parsed.occurred_at,
            )
        )
        if selected.selection.mode is not ConversationMode.RECHERCHE_APPROFONDIE:
            raise ValueError("mode conversation non execute par T-009")
        if self._deep_research_facade is None:
            raise ValueError("mode conversation indisponible")
        if parsed.resolved_question.active_mandate != parsed.research_mandate:
            raise ValueError("research_mandate incoherent avec question resolue")

        request = DeepResearchConversationRequest(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            resolved_question_text=parsed.resolved_question.text,
            research_mandate=parsed.resolved_question.active_mandate,
            selected_document_ids=parsed.resolved_question.selected_document_ids,
            research_mode="DEEP_RESEARCH",
            requested_by_context="CV",
            occurred_at=parsed.occurred_at,
        )
        answer_result = self._deep_research_facade.answer_deep_research(request)
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
        return AnswerDeepResearchConversationTurnResult(
            status="DEEP_RESEARCH_RESULT_ATTACHED",
            selection=selected.selection,
            attachment=attached.attachment,
            events=selected.events + attached.events,
        )


def available_modes_for_deep_research_facade(
    deep_research_facade: DeepResearchConversationFacade | None,
) -> tuple[ConversationMode, ...]:
    """Expose le mode approfondi seulement quand la facade RA M-009 existe."""

    if deep_research_facade is None:
        return (ConversationMode.CHAT_DOCUMENTAIRE,)
    if not callable(getattr(deep_research_facade, "answer_deep_research", None)):
        raise ValueError("deep_research_facade sans answer_deep_research")
    return (
        ConversationMode.CHAT_DOCUMENTAIRE,
        ConversationMode.RECHERCHE_APPROFONDIE,
    )


def _ensure_command(
    command: object,
) -> AnswerDeepResearchConversationTurnCommand:
    if not isinstance(command, AnswerDeepResearchConversationTurnCommand):
        raise ValueError("commande AnswerDeepResearchConversationTurn invalide")
    conversation_id = _ensure_conversation_id(command.conversation_id)
    turn_id = _ensure_turn_id(command.turn_id)
    if not isinstance(command.resolved_question, ResolvedQuestion):
        raise ValueError("resolved_question invalide")
    if command.resolved_question.conversation_id != conversation_id:
        raise ValueError("resolved_question conversation incoherente")
    if command.resolved_question.turn_id != turn_id:
        raise ValueError("resolved_question turn incoherent")
    _freeze_mapping(command.research_mandate, "research_mandate")
    _ensure_utc(command.occurred_at, "occurred_at")
    return command


def _ensure_events(
    value: object,
) -> tuple[ConversationModeSelected | VerifiedAnswerAttachedToTurn, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    for event in events:
        if not isinstance(event, (ConversationModeSelected, VerifiedAnswerAttachedToTurn)):
            raise ValueError("event CV invalide")
    return events


def _ensure_document_ids(value: object) -> tuple[str, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("selected_documents invalides")
    document_ids = tuple(_ensure_domain_identifier(item, "DOC", "selected_documents") for item in value)
    if len(document_ids) == 0:
        raise ValueError("selected_documents absents")
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("selected_documents dupliques")
    return document_ids


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
        if not value == value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{field_name} invalide")
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


__all__ = [
    "AnswerDeepResearchConversationTurnCommand",
    "AnswerDeepResearchConversationTurnHandler",
    "AnswerDeepResearchConversationTurnResult",
    "DeepResearchConversationFacade",
    "DeepResearchConversationRequest",
    "available_modes_for_deep_research_facade",
]
