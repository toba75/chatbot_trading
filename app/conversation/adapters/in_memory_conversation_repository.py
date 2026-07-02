"""Repository mémoire strict des conversations CV."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.conversation.domain.conversation import Conversation, ConversationStatus


class InMemoryConversationRepository:
    """Repository non durable utilisé par les tests applicatifs CV."""

    def __init__(self, *, conversations: Sequence[Conversation]) -> None:
        self._lock = threading.Lock()
        self._conversations_by_id: dict[str, Conversation] = {}
        for conversation in _ensure_conversations(conversations):
            self.save(conversation)

    @classmethod
    def empty(cls) -> "InMemoryConversationRepository":
        return cls(conversations=())

    def save(self, conversation: Conversation) -> Conversation:
        parsed_conversation = _ensure_conversation(conversation)
        with self._lock:
            existing = self._conversations_by_id.get(parsed_conversation.conversation_id)
            if existing is not None and existing != parsed_conversation:
                raise ValueError("conversation deja enregistree")
            self._conversations_by_id[parsed_conversation.conversation_id] = parsed_conversation
            return parsed_conversation

    def update(self, conversation: Conversation) -> Conversation:
        parsed_conversation = _ensure_conversation(conversation)
        with self._lock:
            existing = self._conversations_by_id.get(parsed_conversation.conversation_id)
            if existing is None:
                raise ValueError(f"conversation inconnue: {parsed_conversation.conversation_id}")
            _ensure_same_conversation_identity(existing, parsed_conversation)
            _ensure_status_transition(existing, parsed_conversation)
            _ensure_event_history_extends(existing.events, parsed_conversation.events)
            self._conversations_by_id[parsed_conversation.conversation_id] = parsed_conversation
            return parsed_conversation

    def conversation_for_id(self, conversation_id: str) -> Conversation:
        parsed_id = _ensure_conversation_id(conversation_id)
        with self._lock:
            conversation = self._conversations_by_id.get(parsed_id)
            if conversation is None:
                raise ValueError(f"conversation inconnue: {parsed_id}")
            return conversation

    def conversation_count(self) -> int:
        with self._lock:
            return len(self._conversations_by_id)


def _ensure_conversations(value: Sequence[Conversation]) -> tuple[Conversation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conversations invalides")
    conversations = tuple(value)
    for conversation in conversations:
        _ensure_conversation(conversation)
    ids = tuple(conversation.conversation_id for conversation in conversations)
    if len(ids) != len(set(ids)):
        raise ValueError("conversation dupliquee")
    return conversations


def _ensure_conversation(value: object) -> Conversation:
    if not isinstance(value, Conversation):
        raise ValueError("conversation invalide")
    return value


def _ensure_conversation_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("conversation_id non textuel")
    if value.strip() == "":
        raise ValueError("conversation_id vide")
    if value != value.strip():
        raise ValueError("conversation_id non normalise")
    if not value.startswith("CONV-"):
        raise ValueError("conversation_id invalide")
    return value


def _ensure_same_conversation_identity(existing: Conversation, updated: Conversation) -> None:
    if existing.conversation_id != updated.conversation_id:
        raise ValueError("conversation_id incoherent")
    if existing.title != updated.title:
        raise ValueError("title incoherent")
    if existing.default_mandate != updated.default_mandate:
        raise ValueError("default_mandate incoherent")
    if existing.presentation_preferences != updated.presentation_preferences:
        raise ValueError("presentation_preferences incoherentes")
    if existing.created_at != updated.created_at:
        raise ValueError("created_at incoherent")


def _ensure_status_transition(existing: Conversation, updated: Conversation) -> None:
    if existing.status is ConversationStatus.ARCHIVED and updated.status is not ConversationStatus.ARCHIVED:
        raise ValueError("conversation version obsolete")
    if existing.status is ConversationStatus.ARCHIVED and existing != updated:
        raise ValueError("conversation version obsolete")
    if existing.status is ConversationStatus.ACTIVE and updated.status not in {
        ConversationStatus.ACTIVE,
        ConversationStatus.ARCHIVED,
    }:
        raise ValueError("conversation_status transition interdite")


def _ensure_event_history_extends(existing_events: tuple[object, ...], updated_events: tuple[object, ...]) -> None:
    if len(updated_events) < len(existing_events):
        raise ValueError("conversation version obsolete")
    if updated_events[: len(existing_events)] != existing_events:
        raise ValueError("conversation version obsolete")


__all__ = ["InMemoryConversationRepository"]
