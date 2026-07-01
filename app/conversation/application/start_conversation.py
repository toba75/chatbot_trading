"""Commande CV de création explicite de conversation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.conversation.domain.conversation import Conversation


class ConversationRepository(Protocol):
    """Port applicatif de persistance Conversation."""

    def save(self, conversation: Conversation) -> Conversation:
        """Persiste une conversation nouvelle."""


@dataclass(frozen=True)
class StartConversationCommand:
    """Commande de création d'une conversation CV."""

    conversation_id: str
    title: str
    default_mandate: Mapping[str, Any]
    presentation_preferences: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True)
class StartConversationResult:
    """Résultat public de création de conversation."""

    conversation_id: str
    status: str
    events: tuple[object, ...]


class StartConversationHandler:
    """Cas d'usage CV de création de conversation."""

    def __init__(self, *, conversation_repository: ConversationRepository) -> None:
        if not callable(getattr(conversation_repository, "save", None)):
            raise ValueError("conversation_repository sans save")
        self._conversation_repository = conversation_repository

    def start(self, command: StartConversationCommand) -> StartConversationResult:
        if not isinstance(command, StartConversationCommand):
            raise ValueError("commande StartConversation invalide")
        conversation = Conversation.start(
            conversation_id=command.conversation_id,
            title=command.title,
            default_mandate=command.default_mandate,
            presentation_preferences=command.presentation_preferences,
            occurred_at=command.occurred_at,
        )
        saved = self._conversation_repository.save(conversation)
        return StartConversationResult(
            conversation_id=saved.conversation_id,
            status="CONVERSATION_CREATED",
            events=saved.events,
        )


__all__ = [
    "ConversationRepository",
    "StartConversationCommand",
    "StartConversationHandler",
    "StartConversationResult",
]
