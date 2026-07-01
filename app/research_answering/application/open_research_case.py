"""Cas d'usage RA d'ouverture et de planification d'un ResearchCase."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.research_answering.domain.research_case import (
    ResearchCase,
    ResearchCaseOpened,
    ResearchMandate,
    ResearchMode,
    ResearchPlanCreated,
    ResolvedQuestion,
    research_case_id_for,
)
from app.research_answering.domain.research_planning import ResearchPlanningPolicy


_COMMAND_FIELDS = frozenset(
    {
        "resolved_question",
        "research_mandate",
        "requested_mode",
        "requested_by_context",
        "idempotency_key",
        "occurred_at",
    }
)
_FORBIDDEN_CONVERSATION_FIELDS = frozenset(
    {
        "conversation_history",
        "conversation_turns",
        "history_as_evidence",
        "raw_conversation",
    }
)
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ResearchCaseRepository(Protocol):
    """Port de persistance RA pour ResearchCase."""

    def save(self, research_case: ResearchCase) -> ResearchCase:
        """Persiste un ResearchCase."""


@dataclass(frozen=True)
class OpenResearchCaseCommand:
    """Commande applicative RA sans historique conversationnel brut."""

    resolved_question: ResolvedQuestion
    research_mandate: ResearchMandate
    requested_mode: ResearchMode
    requested_by_context: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "OpenResearchCaseCommand":
        parsed_payload = _ensure_mapping(payload, "OpenResearchCase")
        for field_name in parsed_payload:
            if field_name in _FORBIDDEN_CONVERSATION_FIELDS:
                raise ValueError("historique conversationnel interdit")
            if field_name not in _COMMAND_FIELDS:
                raise ValueError(f"OpenResearchCase champ interdit: {field_name}")
        return cls(
            resolved_question=ResolvedQuestion(_required_value(parsed_payload, "resolved_question")),
            research_mandate=ResearchMandate.from_payload(
                _required_value(parsed_payload, "research_mandate")
            ),
            requested_mode=ResearchMode.from_value(_required_value(parsed_payload, "requested_mode")),
            requested_by_context=_required_text(parsed_payload, "requested_by_context"),
            idempotency_key=_required_text(parsed_payload, "idempotency_key"),
            occurred_at=_required_utc_instant(parsed_payload, "occurred_at"),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_question, ResolvedQuestion):
            raise ValueError("resolved_question absent")
        if not isinstance(self.research_mandate, ResearchMandate):
            raise ValueError("research_mandate absent")
        if not isinstance(self.requested_mode, ResearchMode):
            raise ValueError("research_mode invalide")
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_text(self.requested_by_context, "requested_by_context"),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            _ensure_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant_value(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class OpenResearchCaseResult:
    """Résultat observable d'une ouverture planifiée."""

    status: str
    research_case_id: str
    research_case: ResearchCase
    events: tuple[ResearchCaseOpened | ResearchPlanCreated, ...]

    def __post_init__(self) -> None:
        if self.status != "RESEARCH_CASE_PLANNED":
            raise ValueError("status OpenResearchCase invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if self.research_case_id != self.research_case.research_case_id:
            raise ValueError("research_case_id incoherent")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class OpenResearchCaseHandler:
    """Orchestre ouverture, planification locale et persistance RA."""

    research_case_repository: ResearchCaseRepository
    planning_policy: ResearchPlanningPolicy

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "save", None)):
            raise ValueError("research_case_repository sans save")
        if not callable(getattr(self.planning_policy, "plan_for", None)):
            raise ValueError("planning_policy sans plan_for")

    def open_and_plan(self, command: OpenResearchCaseCommand) -> OpenResearchCaseResult:
        parsed_command = _ensure_command(command)
        research_case = ResearchCase.open(
            research_case_id=research_case_id_for(
                idempotency_key=parsed_command.idempotency_key,
                resolved_question=parsed_command.resolved_question,
                research_mandate=parsed_command.research_mandate,
            ),
            resolved_question=parsed_command.resolved_question,
            research_mandate=parsed_command.research_mandate,
            requested_mode=parsed_command.requested_mode,
            requested_by_context=parsed_command.requested_by_context,
            occurred_at=parsed_command.occurred_at,
        )
        planned_case = research_case.plan_research(self.planning_policy.plan_for(research_case))
        saved_case = self.research_case_repository.save(planned_case)
        return OpenResearchCaseResult(
            status="RESEARCH_CASE_PLANNED",
            research_case_id=saved_case.research_case_id,
            research_case=saved_case,
            events=saved_case.events,
        )


def _ensure_command(value: OpenResearchCaseCommand) -> OpenResearchCaseCommand:
    if not isinstance(value, OpenResearchCaseCommand):
        raise ValueError("commande OpenResearchCase invalide")
    return value


def _ensure_events(value: object) -> tuple[ResearchCaseOpened | ResearchPlanCreated, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    for event in events:
        if not isinstance(event, (ResearchCaseOpened, ResearchPlanCreated)):
            raise ValueError("event research_case invalide")
    return events


def _ensure_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return value


def _required_value(payload: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return payload[field_name]


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _ensure_text(_required_value(payload, field_name), field_name)


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    return _ensure_utc_instant_value(_required_value(payload, field_name), field_name)


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc_instant_value(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "OpenResearchCaseCommand",
    "OpenResearchCaseHandler",
    "OpenResearchCaseResult",
    "ResearchCaseRepository",
]
