"""Cas d'usage RA d'évaluation du support documentaire d'une réponse."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.domain.answer import (
    Answer,
    AnswerFreshnessPolicy,
    AnswerPartiallySupported,
    AnswerSupportEvaluated,
    AnswerSupportPolicy,
    AnswerSuperseded,
    AnswerVerified,
    CitationIntegrityPolicy,
    VerifiedAnswerVersion,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.research_case import ResearchCase


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ResearchCaseRepository(Protocol):
    """Port RA de lecture du ResearchCase."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne le cas de recherche existant."""


class AnswerRepository(Protocol):
    """Port RA de persistance d'Answer."""

    def update(self, answer: Answer) -> Answer:
        """Remplace un Answer par sa nouvelle version métier."""

    def answer_for_id(self, answer_id: str) -> Answer:
        """Retourne un Answer existant."""


@dataclass(frozen=True)
class EvaluateAnswerSupport:
    """Commande RA d'évaluation et publication du support documentaire."""

    research_case_id: str
    answer_id: str
    support_policy_version: str
    citation_policy_version: str
    freshness_policy_version: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "answer_id",
            _ensure_prefixed_text(self.answer_id, "answer_id", "ANS-"),
        )
        object.__setattr__(
            self,
            "support_policy_version",
            _ensure_text(self.support_policy_version, "support_policy_version"),
        )
        object.__setattr__(
            self,
            "citation_policy_version",
            _ensure_text(self.citation_policy_version, "citation_policy_version"),
        )
        object.__setattr__(
            self,
            "freshness_policy_version",
            _ensure_text(self.freshness_policy_version, "freshness_policy_version"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class SupersedeAnswer:
    """Commande RA de supersession explicite d'une réponse publiée."""

    answer_id: str
    new_answer_ref: str
    supersession_reason: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "answer_id",
            _ensure_prefixed_text(self.answer_id, "answer_id", "ANS-"),
        )
        object.__setattr__(self, "new_answer_ref", _ensure_answer_ref(self.new_answer_ref, "new_answer_ref"))
        object.__setattr__(
            self,
            "supersession_reason",
            _ensure_text(self.supersession_reason, "supersession_reason"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class EvaluateAnswerSupportResult:
    """Résultat observable de publication T-007."""

    support_status: SupportStatus
    answer: Answer
    verified_answer_version: VerifiedAnswerVersion
    verified_research_outcome: VerifiedResearchOutcome
    events: Sequence[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported]

    def __post_init__(self) -> None:
        if not isinstance(self.support_status, SupportStatus):
            raise ValueError("support_status invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        if not isinstance(self.verified_answer_version, VerifiedAnswerVersion):
            raise ValueError("verified_answer_version invalide")
        if not isinstance(self.verified_research_outcome, VerifiedResearchOutcome):
            raise ValueError("verified_research_outcome invalide")
        object.__setattr__(self, "events", _ensure_evaluation_events(self.events))


@dataclass(frozen=True)
class SupersedeAnswerResult:
    """Résultat observable de supersession T-007."""

    answer: Answer
    events: Sequence[AnswerSuperseded]

    def __post_init__(self) -> None:
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        object.__setattr__(self, "events", _ensure_superseded_events(self.events))


@dataclass(frozen=True)
class EvaluateAnswerSupportHandler:
    """Orchestre les politiques RA sans accès aux stockages internes KA ou EG."""

    research_case_repository: ResearchCaseRepository
    answer_repository: AnswerRepository
    citation_resolver: object

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.answer_repository, "answer_for_id", None)):
            raise ValueError("answer_repository sans answer_for_id")
        if not callable(getattr(self.answer_repository, "update", None)):
            raise ValueError("answer_repository sans update")
        if not callable(getattr(self.citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")

    def evaluate(self, command: EvaluateAnswerSupport) -> EvaluateAnswerSupportResult:
        parsed_command = _ensure_evaluate_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        answer = self.answer_repository.answer_for_id(parsed_command.answer_id)
        if not isinstance(answer, Answer):
            raise ValueError("answer invalide")
        if answer.research_case_id != research_case.research_case_id:
            raise ValueError("answer hors research_case")
        if research_case.evidence_set is None:
            raise ValueError("evidence_set absent")

        freshness_policy = AnswerFreshnessPolicy(
            policy_version=parsed_command.freshness_policy_version,
            current_support_policy_version=parsed_command.support_policy_version,
            accepted_canonical_version_ids=tuple(
                citation.source_locator.canonical_version_id
                for citation in research_case.evidence_set.citations
            ),
        )
        freshness_policy.ensure_fresh(
            evidence_set=research_case.evidence_set,
            support_policy_version=parsed_command.support_policy_version,
        )
        updated_answer, version, events = AnswerSupportPolicy(
            policy_version=parsed_command.support_policy_version,
        ).evaluate(
            answer=answer,
            research_case=research_case,
            citation_policy=CitationIntegrityPolicy(
                policy_version=parsed_command.citation_policy_version,
                citation_resolver=self.citation_resolver,
            ),
            occurred_at=parsed_command.occurred_at,
        )
        outcome = version.to_verified_research_outcome(
            question=research_case.resolved_question.text,
            mandate=research_case.research_mandate.to_payload(),
            unresolved_conflicts=tuple(
                assessment
                for assessment in research_case.contradiction_assessments
                if assessment.blocks_publication
            ),
            knowledge_gaps=research_case.knowledge_gaps,
            completed_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.update(updated_answer)
        return EvaluateAnswerSupportResult(
            support_status=version.support_status,
            answer=saved_answer,
            verified_answer_version=version,
            verified_research_outcome=outcome,
            events=events,
        )


@dataclass(frozen=True)
class SupersedeAnswerHandler:
    """Orchestre la supersession explicite d'une réponse publiée."""

    answer_repository: AnswerRepository

    def __post_init__(self) -> None:
        if not callable(getattr(self.answer_repository, "answer_for_id", None)):
            raise ValueError("answer_repository sans answer_for_id")
        if not callable(getattr(self.answer_repository, "update", None)):
            raise ValueError("answer_repository sans update")

    def supersede(self, command: SupersedeAnswer) -> SupersedeAnswerResult:
        parsed_command = _ensure_supersede_command(command)
        answer = self.answer_repository.answer_for_id(parsed_command.answer_id)
        if not isinstance(answer, Answer):
            raise ValueError("answer invalide")
        updated_answer, event = answer.supersede(
            new_answer_ref=parsed_command.new_answer_ref,
            supersession_reason=parsed_command.supersession_reason,
            occurred_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.update(updated_answer)
        return SupersedeAnswerResult(answer=saved_answer, events=(event,))


def _ensure_evaluate_command(value: object) -> EvaluateAnswerSupport:
    if not isinstance(value, EvaluateAnswerSupport):
        raise ValueError("commande EvaluateAnswerSupport invalide")
    return value


def _ensure_supersede_command(value: object) -> SupersedeAnswer:
    if not isinstance(value, SupersedeAnswer):
        raise ValueError("commande SupersedeAnswer invalide")
    return value


def _ensure_evaluation_events(
    value: Sequence[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported],
) -> tuple[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 2 or not isinstance(events[0], AnswerSupportEvaluated):
        raise ValueError("events evaluation invalides")
    if not isinstance(events[1], (AnswerVerified, AnswerPartiallySupported)):
        raise ValueError("event publication absent")
    return events


def _ensure_superseded_events(value: Sequence[AnswerSuperseded]) -> tuple[AnswerSuperseded, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1 or not isinstance(events[0], AnswerSuperseded):
        raise ValueError("event AnswerSuperseded absent")
    return events


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_prefixed_text(value: object, field_name: str, prefix: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_answer_ref(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"ANS-[A-Z0-9][A-Z0-9-]*@[1-9][0-9]*", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "AnswerRepository",
    "EvaluateAnswerSupport",
    "EvaluateAnswerSupportHandler",
    "EvaluateAnswerSupportResult",
    "ResearchCaseRepository",
    "SupersedeAnswer",
    "SupersedeAnswerHandler",
    "SupersedeAnswerResult",
]
