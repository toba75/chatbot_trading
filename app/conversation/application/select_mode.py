"""Application command for explicit CV mode selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.conversation.application.resolve_followup_question import ResolvedQuestion
from app.conversation.domain.mode_routing import (
    ConversationMode,
    ConversationModeRoutingPolicy,
    ConversationModeSelected,
    ConversationModeSelection,
    ModeClassificationResult,
    make_mode_selected_event,
)


class ModeClassifier(Protocol):
    """Port used before CV mode policy validation."""

    def classify(self, resolved_question: ResolvedQuestion) -> ModeClassificationResult:
        """Return a proposed mode with an explicit justification."""


@dataclass(frozen=True)
class SelectConversationModeCommand:
    """Command selecting a mode for a resolved CV question."""

    conversation_id: str
    turn_id: str
    resolved_question: ResolvedQuestion
    requested_mode: str | ConversationMode | None
    available_modes: Sequence[str | ConversationMode]
    occurred_at: str


@dataclass(frozen=True)
class SelectConversationModeResult:
    """Application result for mode selection."""

    status: str
    selection: ConversationModeSelection
    downstream_context: str
    events: tuple[ConversationModeSelected, ...]


class DeterministicModeClassifier:
    """Local keyword classifier for M-008 deterministic scenarios."""

    def classify(self, resolved_question: ResolvedQuestion) -> ModeClassificationResult:
        question = _ensure_resolved_question(resolved_question)
        text = question.text.lower()
        if "clarifie" in text or "clarifier" in text or "ambigue" in text:
            return ModeClassificationResult(
                mode=ConversationMode.CLARIFICATION_INTERNE,
                justification="Demande de clarification conversationnelle explicite.",
                classifier_label="clarification",
            )
        if "backtest" in text or ("tester" in text and "strategie" in text):
            return ModeClassificationResult(
                mode=ConversationMode.BACKTEST,
                justification="La question demande un backtest ou un test de strategie.",
                classifier_label="backtest",
            )
        if "calcule" in text or "calcul" in text or "drawdown" in text or "volatilite" in text:
            return ModeClassificationResult(
                mode=ConversationMode.CALCUL,
                justification="La question demande un calcul quantitatif explicite.",
                classifier_label="calculation",
            )
        if "compare" in text or "comparaison" in text or "versus" in text:
            return ModeClassificationResult(
                mode=ConversationMode.COMPARAISON,
                justification="La question demande de comparer plusieurs objets.",
                classifier_label="comparison",
            )
        if "approfondi" in text or "approfondie" in text or "recherche" in text:
            return ModeClassificationResult(
                mode=ConversationMode.RECHERCHE_APPROFONDIE,
                justification="La question demande une recherche approfondie.",
                classifier_label="deep-research",
            )
        if "strategie" in text or "concois" in text or "conçois" in text:
            return ModeClassificationResult(
                mode=ConversationMode.CONCEPTION_STRATEGIE,
                justification="La question demande de concevoir une strategie.",
                classifier_label="strategy-design",
            )
        if "documentaire" in text or "citation" in text or "explique" in text:
            return ModeClassificationResult(
                mode=ConversationMode.CHAT_DOCUMENTAIRE,
                justification="La question demande une reponse documentaire avec citations.",
                classifier_label="documentary-chat",
            )
        raise ValueError("mode conversation non classable")


class SelectConversationModeHandler:
    """Application handler selecting mode without downstream execution."""

    def __init__(
        self,
        *,
        mode_classifier: ModeClassifier,
        policy: ConversationModeRoutingPolicy | None = None,
    ) -> None:
        if not callable(getattr(mode_classifier, "classify", None)):
            raise ValueError("mode_classifier sans classify")
        self._mode_classifier = mode_classifier
        self._policy = policy if policy is not None else ConversationModeRoutingPolicy()

    def select(self, command: SelectConversationModeCommand) -> SelectConversationModeResult:
        parsed = _ensure_command(command)
        classifier_result = self._mode_classifier.classify(parsed.resolved_question)
        selection = self._policy.select(
            conversation_id=parsed.conversation_id,
            turn_id=parsed.turn_id,
            requested_mode=parsed.requested_mode,
            classifier_result=classifier_result,
            available_modes=parsed.available_modes,
            occurred_at=parsed.occurred_at,
        )
        event = make_mode_selected_event(selection)
        return SelectConversationModeResult(
            status="MODE_SELECTED",
            selection=selection,
            downstream_context=_downstream_context(selection.mode),
            events=(event,),
        )


def _ensure_command(command: object) -> SelectConversationModeCommand:
    if not isinstance(command, SelectConversationModeCommand):
        raise ValueError("commande SelectConversationMode invalide")
    question = _ensure_resolved_question(command.resolved_question)
    if command.conversation_id != question.conversation_id:
        raise ValueError("resolved_question conversation incoherente")
    if command.turn_id != question.turn_id:
        raise ValueError("resolved_question turn incoherent")
    return command


def _ensure_resolved_question(value: object) -> ResolvedQuestion:
    if not isinstance(value, ResolvedQuestion):
        raise ValueError("resolved_question invalide")
    return value


def _downstream_context(mode: ConversationMode) -> str:
    if mode in (
        ConversationMode.CHAT_DOCUMENTAIRE,
        ConversationMode.RECHERCHE_APPROFONDIE,
        ConversationMode.COMPARAISON,
    ):
        return "RA"
    if mode is ConversationMode.CONCEPTION_STRATEGIE:
        return "SD"
    if mode is ConversationMode.BACKTEST:
        return "EX"
    return "CV"


__all__ = [
    "DeterministicModeClassifier",
    "ModeClassificationResult",
    "ModeClassifier",
    "SelectConversationModeCommand",
    "SelectConversationModeHandler",
    "SelectConversationModeResult",
]
