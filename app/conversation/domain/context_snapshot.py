"""Value objects CV for compact conversation context snapshots."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contracts.identity import DomainIdentifier


CONVERSATION_CONTEXT_COMPACTION_POLICY_VERSION = "conversation-context-compaction-m008-v1"
_ANSWER_VERSION_REF_PATTERN = re.compile(r"^(?P<answer_id>ANS-[A-Z0-9][A-Z0-9-]*)@[1-9][0-9]*$")
_FORBIDDEN_KEYS = frozenset(
    {
        "answer_text",
        "conversation_history",
        "document_text",
        "prompt",
        "prompt_override",
        "raw_history",
        "raw_turns",
        "verified_research_outcome_text",
    }
)


@dataclass(frozen=True)
class ConversationContextCompacted:
    """Event emitted when CV stores a compact context snapshot."""

    conversation_id: str
    snapshot_created_at: str
    verified_answer_ref_count: int
    historical_assertion_count: int
    policy_version: str

    @property
    def event_type(self) -> str:
        return "ConversationContextCompacted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(
            self,
            "snapshot_created_at",
            _ensure_utc(self.snapshot_created_at, "snapshot_created_at"),
        )
        object.__setattr__(
            self,
            "verified_answer_ref_count",
            _ensure_non_negative_integer(
                self.verified_answer_ref_count,
                "verified_answer_ref_count",
            ),
        )
        object.__setattr__(
            self,
            "historical_assertion_count",
            _ensure_non_negative_integer(
                self.historical_assertion_count,
                "historical_assertion_count",
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


@dataclass(frozen=True)
class ConversationContextSnapshot:
    """Compact CV context without raw turns or documentary proof."""

    conversation_id: str
    active_mandate: Mapping[str, Any]
    user_preferences: Mapping[str, Any]
    selected_document_ids: tuple[str, ...]
    verified_answer_refs: tuple[str, ...]
    historical_assertions_to_revalidate: tuple[str, ...]
    ambiguities: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(
            self,
            "active_mandate",
            _freeze_mapping(self.active_mandate, "active_mandate", allow_empty=False),
        )
        object.__setattr__(
            self,
            "user_preferences",
            _freeze_mapping(self.user_preferences, "user_preferences", allow_empty=True),
        )
        object.__setattr__(
            self,
            "selected_document_ids",
            _ensure_document_ids(self.selected_document_ids),
        )
        object.__setattr__(
            self,
            "verified_answer_refs",
            _ensure_verified_answer_refs(self.verified_answer_refs),
        )
        object.__setattr__(
            self,
            "historical_assertions_to_revalidate",
            _ensure_text_sequence(
                self.historical_assertions_to_revalidate,
                "historical_assertion",
            ),
        )
        object.__setattr__(
            self,
            "ambiguities",
            _ensure_text_sequence(self.ambiguities, "ambiguity"),
        )
        object.__setattr__(self, "created_at", _ensure_utc(self.created_at, "created_at"))

    def to_payload(self) -> Mapping[str, Any]:
        """Return a stable public payload for CV adapters."""

        return MappingProxyType(
            {
                "active_mandate": _to_payload_value(self.active_mandate),
                "ambiguities": tuple(self.ambiguities),
                "conversation_id": self.conversation_id,
                "created_at": self.created_at,
                "historical_assertions_to_revalidate": tuple(
                    self.historical_assertions_to_revalidate
                ),
                "selected_document_ids": tuple(self.selected_document_ids),
                "user_preferences": _to_payload_value(self.user_preferences),
                "verified_answer_refs": tuple(self.verified_answer_refs),
            }
        )


class ConversationContextCompactionPolicy:
    """Compacts CV context while keeping history distinct from proof."""

    def compact(
        self,
        *,
        conversation_id: str,
        active_mandate: Mapping[str, Any],
        user_preferences: Mapping[str, Any],
        selected_document_ids: Sequence[str],
        verified_answer_refs: Sequence[str],
        historical_assertions: Sequence[str],
        ambiguities: Sequence[str],
        occurred_at: str,
    ) -> ConversationContextSnapshot:
        return ConversationContextSnapshot(
            conversation_id=conversation_id,
            active_mandate=active_mandate,
            user_preferences=user_preferences,
            selected_document_ids=_ensure_document_ids(selected_document_ids),
            verified_answer_refs=_ensure_verified_answer_refs(verified_answer_refs),
            historical_assertions_to_revalidate=_ensure_text_sequence(
                historical_assertions,
                "historical_assertion",
            ),
            ambiguities=_ensure_text_sequence(ambiguities, "ambiguity"),
            created_at=occurred_at,
        )


def _ensure_conversation_id(value: object) -> str:
    return _ensure_domain_identifier(value, "CONV", "conversation_id")


def _ensure_document_id(value: object) -> str:
    return _ensure_domain_identifier(value, "DOC", "document_id")


def _ensure_domain_identifier(value: object, expected_prefix: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


def _ensure_utc(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_document_ids(value: object) -> tuple[str, ...]:
    return tuple(_ensure_document_id(item) for item in _ensure_sequence(value, "document_ids"))


def _ensure_verified_answer_refs(value: object) -> tuple[str, ...]:
    refs = tuple(
        _ensure_verified_answer_ref(item)
        for item in _ensure_sequence(value, "verified_answer_refs")
    )
    if len(refs) != len(set(refs)):
        raise ValueError("verified_answer_ref duplique")
    return refs


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    match = _ANSWER_VERSION_REF_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("verified_answer_ref invalide")
    DomainIdentifier.parse_with_prefix(match.group("answer_id"), "ANS")
    return text


def _ensure_text_sequence(value: object, field_name: str) -> tuple[str, ...]:
    return tuple(_ensure_text(item, field_name) for item in _ensure_sequence(value, field_name))


def _ensure_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(value)


def _freeze_mapping(
    value: object,
    field_name: str,
    *,
    allow_empty: bool,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    frozen: dict[str, Any] = {}
    for key, child_value in value.items():
        parsed_key = _ensure_mapping_key(key)
        frozen[parsed_key] = _freeze_value(child_value, field_name)
    return MappingProxyType(frozen)


def _ensure_mapping_key(value: object) -> str:
    key = _ensure_text(value, "cle")
    if key in _FORBIDDEN_KEYS:
        raise ValueError(f"cle interdite: {key}")
    return key


def _freeze_value(value: object, field_name: str) -> Any:
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
        return _freeze_mapping(value, field_name, allow_empty=True)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item, field_name) for item in value)
    raise ValueError(f"{field_name} invalide")


def _to_payload_value(value: object) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _to_payload_value(child) for key, child in value.items()})
    if isinstance(value, tuple):
        return tuple(_to_payload_value(child) for child in value)
    return value


__all__ = [
    "CONVERSATION_CONTEXT_COMPACTION_POLICY_VERSION",
    "ConversationContextCompacted",
    "ConversationContextCompactionPolicy",
    "ConversationContextSnapshot",
]
