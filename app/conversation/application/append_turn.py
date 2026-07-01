"""Commande CV d'ajout append-only d'un tour utilisateur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.conversation.domain.conversation import Conversation, ConversationTurn


class ConversationReader(Protocol):
    """Port de lecture Conversation."""

    def conversation_for_id(self, conversation_id: str) -> Conversation:
        """Retourne une conversation existante."""


class ConversationTurnRepository(Protocol):
    """Port de persistance append-only des tours."""

    def next_sequence_for_conversation(self, conversation_id: str) -> int:
        """Retourne la prochaine séquence attendue."""

    def save(self, turn: ConversationTurn) -> ConversationTurn:
        """Persiste un tour nouveau."""


@dataclass(frozen=True)
class AppendUserTurnCommand:
    """Commande d'ajout d'un message utilisateur dans une conversation existante."""

    conversation_id: str
    turn_id: str
    message: str
    idempotency_key: str
    occurred_at: str


@dataclass(frozen=True)
class AppendUserTurnResult:
    """Résultat public d'ajout append-only."""

    conversation_id: str
    turn_id: str
    sequence: int
    status: str
    events: tuple[object, ...]


class AppendUserTurnHandler:
    """Cas d'usage CV d'ajout d'un tour utilisateur."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationReader,
        turn_repository: ConversationTurnRepository,
    ) -> None:
        if not callable(getattr(conversation_repository, "conversation_for_id", None)):
            raise ValueError("conversation_repository sans conversation_for_id")
        if not callable(getattr(turn_repository, "next_sequence_for_conversation", None)):
            raise ValueError("turn_repository sans next_sequence_for_conversation")
        if not callable(getattr(turn_repository, "save", None)):
            raise ValueError("turn_repository sans save")
        self._conversation_repository = conversation_repository
        self._turn_repository = turn_repository

    def append_user_turn(self, command: AppendUserTurnCommand) -> AppendUserTurnResult:
        if not isinstance(command, AppendUserTurnCommand):
            raise ValueError("commande AppendUserTurn invalide")
        conversation = self._conversation_repository.conversation_for_id(command.conversation_id)
        conversation.ensure_can_append_turn()
        sequence = self._turn_repository.next_sequence_for_conversation(conversation.conversation_id)
        turn = ConversationTurn.user_turn(
            conversation_id=conversation.conversation_id,
            turn_id=command.turn_id,
            sequence=sequence,
            message=command.message,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
        )
        saved = self._turn_repository.save(turn)
        return AppendUserTurnResult(
            conversation_id=saved.conversation_id,
            turn_id=saved.turn_id,
            sequence=saved.sequence,
            status="USER_TURN_APPENDED",
            events=saved.events,
        )


__all__ = [
    "AppendUserTurnCommand",
    "AppendUserTurnHandler",
    "AppendUserTurnResult",
    "ConversationReader",
    "ConversationTurnRepository",
]
