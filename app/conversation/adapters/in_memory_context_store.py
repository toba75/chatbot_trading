"""In-memory store for compact CV context snapshots."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.contracts.identity import DomainIdentifier
from app.conversation.domain.context_snapshot import ConversationContextSnapshot


class InMemoryConversationContextStore:
    """Non-durable store keyed by conversation identifier."""

    def __init__(self, *, snapshots: Sequence[ConversationContextSnapshot]) -> None:
        self._lock = threading.Lock()
        self._snapshots_by_conversation_id: dict[str, ConversationContextSnapshot] = {}
        for snapshot in _ensure_snapshots(snapshots):
            self.save(snapshot)

    @classmethod
    def empty(cls) -> "InMemoryConversationContextStore":
        return cls(snapshots=())

    def save(self, snapshot: ConversationContextSnapshot) -> ConversationContextSnapshot:
        parsed_snapshot = _ensure_snapshot(snapshot)
        with self._lock:
            existing = self._snapshots_by_conversation_id.get(parsed_snapshot.conversation_id)
            if existing is not None and existing != parsed_snapshot:
                raise ValueError("snapshot deja enregistre")
            if existing is not None:
                return existing
            self._snapshots_by_conversation_id[parsed_snapshot.conversation_id] = parsed_snapshot
            return parsed_snapshot

    def snapshot_for_conversation(self, conversation_id: str) -> ConversationContextSnapshot:
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        with self._lock:
            snapshot = self._snapshots_by_conversation_id.get(parsed_conversation_id)
            if snapshot is None:
                raise ValueError("snapshot conversation inconnu")
            return snapshot


def _ensure_snapshots(
    value: Sequence[ConversationContextSnapshot],
) -> tuple[ConversationContextSnapshot, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conversation_context_snapshots invalides")
    snapshots = tuple(value)
    for snapshot in snapshots:
        _ensure_snapshot(snapshot)
    conversation_ids = tuple(snapshot.conversation_id for snapshot in snapshots)
    if len(conversation_ids) != len(set(conversation_ids)):
        raise ValueError("conversation_context_snapshot duplique")
    return snapshots


def _ensure_snapshot(value: object) -> ConversationContextSnapshot:
    if not isinstance(value, ConversationContextSnapshot):
        raise ValueError("conversation_context_snapshot invalide")
    return value


def _ensure_conversation_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("conversation_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "CONV"))
    except ValueError as exc:
        raise ValueError(f"conversation_id invalide: {exc}") from exc


__all__ = ["InMemoryConversationContextStore"]
