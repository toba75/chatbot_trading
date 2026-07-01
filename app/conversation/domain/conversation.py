"""Agrégats CV de conversation et de tours append-only."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from app.contracts.identity import DomainIdentifier


_CONVERSATION_POLICY_VERSION = "conversation-lifecycle-m008-v1"


class ConversationStatus(str, Enum):
    """État métier d'une conversation CV."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ConversationTurnRole(str, Enum):
    """Rôle public d'un tour de conversation."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


@dataclass(frozen=True)
class ConversationCreated:
    """Événement de création explicite d'une conversation."""

    conversation_id: str
    title: str
    occurred_at: str
    policy_version: str

    @property
    def event_type(self) -> str:
        return "ConversationCreated"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "title", _ensure_text(self.title, "title"))
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


@dataclass(frozen=True)
class ConversationArchived:
    """Événement d'archivage CV sans suppression cascade."""

    conversation_id: str
    archived_at: str
    retention_policy_version: str

    @property
    def event_type(self) -> str:
        return "ConversationArchived"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "archived_at", _ensure_utc(self.archived_at, "archived_at"))
        object.__setattr__(
            self,
            "retention_policy_version",
            _ensure_text(self.retention_policy_version, "retention_policy_version"),
        )


@dataclass(frozen=True)
class UserTurnAppended:
    """Événement de tour utilisateur append-only."""

    conversation_id: str
    turn_id: str
    sequence: int
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "UserTurnAppended"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "sequence", _ensure_positive_integer(self.sequence, "sequence"))
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class Conversation:
    """Agrégat CV de conversation sans chargement des tours."""

    conversation_id: str
    title: str
    default_mandate: Mapping[str, Any]
    presentation_preferences: Mapping[str, Any]
    status: ConversationStatus
    created_at: str
    archived_at: str | None
    events: tuple[ConversationCreated | ConversationArchived, ...]

    @classmethod
    def start(
        cls,
        conversation_id: str,
        title: str,
        default_mandate: Mapping[str, Any],
        presentation_preferences: Mapping[str, Any],
        occurred_at: str,
    ) -> "Conversation":
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        parsed_title = _ensure_text(title, "title")
        parsed_default_mandate = _freeze_required_mapping(default_mandate, "default_mandate")
        parsed_preferences = _freeze_optional_mapping(
            presentation_preferences,
            "presentation_preferences",
        )
        parsed_occurred_at = _ensure_utc(occurred_at, "occurred_at")
        event = ConversationCreated(
            conversation_id=parsed_conversation_id,
            title=parsed_title,
            occurred_at=parsed_occurred_at,
            policy_version=_CONVERSATION_POLICY_VERSION,
        )
        return cls(
            conversation_id=parsed_conversation_id,
            title=parsed_title,
            default_mandate=parsed_default_mandate,
            presentation_preferences=parsed_preferences,
            status=ConversationStatus.ACTIVE,
            created_at=parsed_occurred_at,
            archived_at=None,
            events=(event,),
        )

    def archive(self, *, archived_at: str, retention_policy_version: str) -> "Conversation":
        self.ensure_can_append_turn()
        parsed_archived_at = _ensure_utc(archived_at, "archived_at")
        event = ConversationArchived(
            conversation_id=self.conversation_id,
            archived_at=parsed_archived_at,
            retention_policy_version=retention_policy_version,
        )
        return Conversation(
            conversation_id=self.conversation_id,
            title=self.title,
            default_mandate=self.default_mandate,
            presentation_preferences=self.presentation_preferences,
            status=ConversationStatus.ARCHIVED,
            created_at=self.created_at,
            archived_at=parsed_archived_at,
            events=self.events + (event,),
        )

    def ensure_can_append_turn(self) -> None:
        if self.status is ConversationStatus.ACTIVE:
            return
        raise ValueError("conversation archivee")

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "title", _ensure_text(self.title, "title"))
        object.__setattr__(
            self,
            "default_mandate",
            _freeze_required_mapping(self.default_mandate, "default_mandate"),
        )
        object.__setattr__(
            self,
            "presentation_preferences",
            _freeze_optional_mapping(
                self.presentation_preferences,
                "presentation_preferences",
            ),
        )
        if not isinstance(self.status, ConversationStatus):
            raise ValueError("conversation_status invalide")
        object.__setattr__(self, "created_at", _ensure_utc(self.created_at, "created_at"))
        if self.archived_at is not None:
            object.__setattr__(self, "archived_at", _ensure_utc(self.archived_at, "archived_at"))
        object.__setattr__(self, "events", _ensure_conversation_events(self.events))
        if not isinstance(self.events[0], ConversationCreated):
            raise ValueError("premier event conversation invalide")
        if self.status is ConversationStatus.ACTIVE and self.archived_at is not None:
            raise ValueError("archived_at interdit pour conversation active")
        if self.status is ConversationStatus.ARCHIVED:
            if self.archived_at is None:
                raise ValueError("archived_at absent")
            if not isinstance(self.events[-1], ConversationArchived):
                raise ValueError("event ConversationArchived absent")


@dataclass(frozen=True)
class ConversationTurn:
    """Agrégat CV de tour append-only."""

    conversation_id: str
    turn_id: str
    sequence: int
    role: ConversationTurnRole
    message: str
    idempotency_key: str
    occurred_at: str
    events: tuple[UserTurnAppended, ...]

    @classmethod
    def user_turn(
        cls,
        conversation_id: str,
        turn_id: str,
        sequence: int,
        message: str,
        idempotency_key: str,
        occurred_at: str,
    ) -> "ConversationTurn":
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        parsed_turn_id = _ensure_turn_id(turn_id)
        parsed_sequence = _ensure_positive_integer(sequence, "sequence")
        parsed_occurred_at = _ensure_utc(occurred_at, "occurred_at")
        event = UserTurnAppended(
            conversation_id=parsed_conversation_id,
            turn_id=parsed_turn_id,
            sequence=parsed_sequence,
            occurred_at=parsed_occurred_at,
        )
        return cls(
            conversation_id=parsed_conversation_id,
            turn_id=parsed_turn_id,
            sequence=parsed_sequence,
            role=ConversationTurnRole.USER,
            message=message,
            idempotency_key=idempotency_key,
            occurred_at=parsed_occurred_at,
            events=(event,),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "sequence", _ensure_positive_integer(self.sequence, "sequence"))
        if not isinstance(self.role, ConversationTurnRole):
            raise ValueError("conversation_turn_role invalide")
        object.__setattr__(self, "message", _ensure_text(self.message, "message"))
        object.__setattr__(
            self,
            "idempotency_key",
            _ensure_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "events", _ensure_turn_events(self.events))
        if self.role is ConversationTurnRole.USER and not isinstance(self.events[0], UserTurnAppended):
            raise ValueError("event UserTurnAppended absent")


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


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _freeze_required_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return _freeze_value(value, field_name, allow_empty_mapping=False)


def _freeze_optional_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return _freeze_value(value, field_name, allow_empty_mapping=True)


class _FrozenList(tuple):
    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return tuple(self) == tuple(other)
        return tuple.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


def _freeze_value(value: object, field_name: str, *, allow_empty_mapping: bool) -> Any:
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
        if len(value) == 0 and not allow_empty_mapping:
            raise ValueError(f"{field_name} vide")
        frozen: dict[str, Any] = {}
        for key, child_value in value.items():
            parsed_key = _ensure_text(key, field_name)
            frozen[parsed_key] = _freeze_value(
                child_value,
                field_name,
                allow_empty_mapping=allow_empty_mapping,
            )
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            raise ValueError(f"{field_name} vide")
        return _FrozenList(
            _freeze_value(
                child_value,
                field_name,
                allow_empty_mapping=allow_empty_mapping,
            )
            for child_value in value
        )
    raise ValueError(f"{field_name} invalide")


def _ensure_conversation_events(
    value: object,
) -> tuple[ConversationCreated | ConversationArchived, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events conversation invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events conversation vides")
    for event in events:
        if not isinstance(event, (ConversationCreated, ConversationArchived)):
            raise ValueError("event conversation invalide")
    return events


def _ensure_turn_events(value: object) -> tuple[UserTurnAppended, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events turn invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events turn vides")
    for event in events:
        if not isinstance(event, UserTurnAppended):
            raise ValueError("event turn invalide")
    return events


__all__ = [
    "Conversation",
    "ConversationArchived",
    "ConversationCreated",
    "ConversationStatus",
    "ConversationTurn",
    "ConversationTurnRole",
    "UserTurnAppended",
]
