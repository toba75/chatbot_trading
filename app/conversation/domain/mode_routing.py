"""Conversation mode routing value objects and policy."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.contracts.identity import DomainIdentifier


CONVERSATION_MODE_ROUTING_POLICY_VERSION = "mode-routing-m008-v1"


class ConversationMode(str, Enum):
    """Explicit CV processing mode."""

    CHAT_DOCUMENTAIRE = "CHAT_DOCUMENTAIRE"
    RECHERCHE_APPROFONDIE = "RECHERCHE_APPROFONDIE"
    COMPARAISON = "COMPARAISON"
    CONCEPTION_STRATEGIE = "CONCEPTION_STRATEGIE"
    CALCUL = "CALCUL"
    BACKTEST = "BACKTEST"
    CLARIFICATION_INTERNE = "CLARIFICATION_INTERNE"


@dataclass(frozen=True)
class ModeClassificationResult:
    """Classifier proposal before policy validation."""

    mode: ConversationMode
    justification: str
    classifier_label: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _ensure_mode(self.mode))
        object.__setattr__(
            self,
            "justification",
            _ensure_text(self.justification, "justification mode"),
        )
        object.__setattr__(
            self,
            "classifier_label",
            _ensure_text(self.classifier_label, "classifier_label"),
        )


@dataclass(frozen=True)
class ConversationModeSelection:
    """Mode selected for one CV turn."""

    conversation_id: str
    turn_id: str
    mode: ConversationMode
    justification: str
    policy_version: str
    classifier_label: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "mode", _ensure_mode(self.mode))
        object.__setattr__(
            self,
            "justification",
            _ensure_text(self.justification, "justification mode"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "classifier_label",
            _ensure_text(self.classifier_label, "classifier_label"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ConversationModeSelected:
    """Event emitted after explicit mode selection."""

    conversation_id: str
    turn_id: str
    mode: ConversationMode
    justification_hash: str
    policy_version: str

    @property
    def event_type(self) -> str:
        return "ConversationModeSelected"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "mode", _ensure_mode(self.mode))
        object.__setattr__(
            self,
            "justification_hash",
            _ensure_hash(self.justification_hash, "justification_hash"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )


class ConversationModeRoutingPolicy:
    """Selects an explicit mode and refuses unavailable modes."""

    def select(
        self,
        *,
        conversation_id: str,
        turn_id: str,
        requested_mode: str | ConversationMode | None,
        classifier_result: ModeClassificationResult,
        available_modes: Sequence[str | ConversationMode],
        occurred_at: str,
    ) -> ConversationModeSelection:
        parsed_conversation_id = _ensure_conversation_id(conversation_id)
        parsed_turn_id = _ensure_turn_id(turn_id)
        available = _ensure_available_modes(available_modes)
        if requested_mode is not None:
            forced_mode = _ensure_mode(requested_mode)
            if forced_mode not in available:
                raise ValueError("mode conversation indisponible")
            return ConversationModeSelection(
                conversation_id=parsed_conversation_id,
                turn_id=parsed_turn_id,
                mode=forced_mode,
                justification=f"Mode force par utilisateur: {forced_mode.value}.",
                policy_version=CONVERSATION_MODE_ROUTING_POLICY_VERSION,
                classifier_label="user-forced",
                occurred_at=occurred_at,
            )
        if not isinstance(classifier_result, ModeClassificationResult):
            raise ValueError("classifier_result invalide")
        if classifier_result.mode not in available:
            raise ValueError("mode conversation indisponible")
        return ConversationModeSelection(
            conversation_id=parsed_conversation_id,
            turn_id=parsed_turn_id,
            mode=classifier_result.mode,
            justification=classifier_result.justification,
            policy_version=CONVERSATION_MODE_ROUTING_POLICY_VERSION,
            classifier_label=classifier_result.classifier_label,
            occurred_at=occurred_at,
        )


def make_mode_selected_event(selection: ConversationModeSelection) -> ConversationModeSelected:
    return ConversationModeSelected(
        conversation_id=selection.conversation_id,
        turn_id=selection.turn_id,
        mode=selection.mode,
        justification_hash=hash_justification(selection.justification),
        policy_version=selection.policy_version,
    )


def hash_justification(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "justification mode").encode("utf-8")).hexdigest()


def _ensure_available_modes(value: object) -> frozenset[ConversationMode]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("available_modes invalides")
    modes = frozenset(_ensure_mode(item) for item in value)
    if len(modes) == 0:
        raise ValueError("available_modes vides")
    return modes


def _ensure_mode(value: object) -> ConversationMode:
    if isinstance(value, ConversationMode):
        return value
    if not isinstance(value, str):
        raise ValueError("mode conversation invalide")
    try:
        return ConversationMode(value)
    except ValueError as exc:
        raise ValueError("mode conversation invalide") from exc


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


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "CONVERSATION_MODE_ROUTING_POLICY_VERSION",
    "ConversationMode",
    "ConversationModeRoutingPolicy",
    "ConversationModeSelected",
    "ConversationModeSelection",
    "ModeClassificationResult",
    "hash_justification",
    "make_mode_selected_event",
]
