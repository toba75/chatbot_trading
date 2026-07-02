"""Repository mémoire append-only des tours CV."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.contracts.identity import DomainIdentifier
from app.conversation.domain.conversation import ConversationTurn


class InMemoryTurnRepository:
    """Repository non durable de ConversationTurn ordonné par conversation."""

    def __init__(self, *, turns: Sequence[ConversationTurn]) -> None:
        self._lock = threading.Lock()
        self._turns_by_id: dict[str, ConversationTurn] = {}
        self._turn_ids_by_conversation_id: dict[str, list[str]] = {}
        for turn in _ensure_turns(turns):
            self.save(turn)

    @classmethod
    def empty(cls) -> "InMemoryTurnRepository":
        return cls(turns=())

    def save(self, turn: ConversationTurn) -> ConversationTurn:
        parsed_turn = _ensure_turn(turn)
        with self._lock:
            existing = self._turns_by_id.get(parsed_turn.turn_id)
            if existing is not None and existing != parsed_turn:
                raise ValueError("turn deja enregistre")
            if existing is not None:
                return existing
            expected_sequence = self._next_sequence_for_conversation_without_lock(
                parsed_turn.conversation_id
            )
            if parsed_turn.sequence != expected_sequence:
                raise ValueError("sequence conversation incoherente")
            self._turns_by_id[parsed_turn.turn_id] = parsed_turn
            self._turn_ids_by_conversation_id.setdefault(parsed_turn.conversation_id, []).append(
                parsed_turn.turn_id
            )
            return parsed_turn

    def turn_for_id(self, turn_id: str) -> ConversationTurn:
        parsed_id = _ensure_turn_id(turn_id)
        with self._lock:
            turn = self._turns_by_id.get(parsed_id)
            if turn is None:
                raise ValueError(f"turn inconnu: {parsed_id}")
            return turn

    def turns_for_conversation(self, conversation_id: str) -> tuple[ConversationTurn, ...]:
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        with self._lock:
            turn_ids = tuple(self._turn_ids_by_conversation_id.get(parsed_conversation_id, ()))
            turns = tuple(self._turns_by_id[turn_id] for turn_id in turn_ids)
            return tuple(sorted(turns, key=lambda turn: turn.sequence))

    def next_sequence_for_conversation(self, conversation_id: str) -> int:
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        with self._lock:
            return self._next_sequence_for_conversation_without_lock(parsed_conversation_id)

    def _next_sequence_for_conversation_without_lock(self, conversation_id: str) -> int:
        turn_ids = tuple(self._turn_ids_by_conversation_id.get(conversation_id, ()))
        if len(turn_ids) == 0:
            return 1
        return max(self._turns_by_id[turn_id].sequence for turn_id in turn_ids) + 1


def _ensure_turns(value: Sequence[ConversationTurn]) -> tuple[ConversationTurn, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("turns invalides")
    turns = tuple(value)
    for turn in turns:
        _ensure_turn(turn)
    ids = tuple(turn.turn_id for turn in turns)
    if len(ids) != len(set(ids)):
        raise ValueError("turn duplique")
    return turns


def _ensure_turn(value: object) -> ConversationTurn:
    if not isinstance(value, ConversationTurn):
        raise ValueError("turn invalide")
    return value


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


__all__ = ["InMemoryTurnRepository"]
