"""Cas d'usage RA de brouillon et extraction d'assertions de réponse."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.research_answering.domain.answer import (
    Answer,
    AnswerAssertion,
    AnswerAssertionCandidate,
    AnswerAssertionsExtracted,
    AnswerDraft,
    AnswerDrafted,
    answer_id_for,
)
from app.research_answering.domain.research_case import ResearchCase


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ResearchCaseRepository(Protocol):
    """Port RA de lecture du ResearchCase."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne le cas de recherche existant."""


class AnswerRepository(Protocol):
    """Port RA de persistance d'Answer."""

    def save(self, answer: Answer) -> Answer:
        """Persiste un Answer nouveau."""

    def update(self, answer: Answer) -> Answer:
        """Remplace un Answer par sa nouvelle version métier."""

    def answer_for_id(self, answer_id: str) -> Answer:
        """Retourne un Answer existant."""


class AnswerGenerator(Protocol):
    """Port RA de génération de brouillon sans autorité de support."""

    def draft(self, request: "DraftAnswerRequest") -> object:
        """Produit un brouillon structuré."""


class AnswerAssertionExtractor(Protocol):
    """Port RA d'extraction des assertions importantes."""

    @property
    def extractor_version(self) -> str:
        """Version explicite de l'extracteur."""

    def extract(self, draft: AnswerDraft) -> Sequence[AnswerAssertionCandidate]:
        """Retourne les assertions candidates extraites."""


@dataclass(frozen=True)
class GeneratedAnswerDraft:
    """Sortie autorisée du port AnswerGenerator."""

    content: str
    model_provenance: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _ensure_text(self.content, "answer_draft"))
        object.__setattr__(
            self,
            "model_provenance",
            _ensure_text(self.model_provenance, "model_provenance"),
        )


@dataclass(frozen=True)
class DraftAnswerRequest:
    """Requête transmise au générateur via port RA."""

    research_case_id: str
    resolved_question: str
    evidence_set_id: str
    evidence_set_version: int
    verified_claim_count: int
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "resolved_question",
            _ensure_text(self.resolved_question, "resolved_question"),
        )
        object.__setattr__(
            self,
            "evidence_set_id",
            _ensure_prefixed_text(self.evidence_set_id, "evidence_set_id", "EVS-"),
        )
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        object.__setattr__(
            self,
            "verified_claim_count",
            _ensure_positive_integer(self.verified_claim_count, "verified_claim_count"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DraftAnswer:
    """Commande RA de génération d'un brouillon Answer."""

    research_case_id: str
    evidence_set_id: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "evidence_set_id",
            _ensure_prefixed_text(self.evidence_set_id, "evidence_set_id", "EVS-"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ExtractAnswerAssertions:
    """Commande RA d'extraction des assertions importantes."""

    answer_id: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "answer_id",
            _ensure_prefixed_text(self.answer_id, "answer_id", "ANS-"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DraftAnswerResult:
    """Résultat observable de génération du brouillon."""

    status: str
    answer: Answer
    events: Sequence[AnswerDrafted]

    def __post_init__(self) -> None:
        if self.status != "ANSWER_DRAFTED":
            raise ValueError("status DraftAnswer invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        object.__setattr__(self, "events", _ensure_draft_events(self.events))


@dataclass(frozen=True)
class ExtractAnswerAssertionsResult:
    """Résultat observable d'extraction des assertions."""

    status: str
    answer: Answer
    assertions: Sequence[AnswerAssertion]
    events: Sequence[AnswerAssertionsExtracted]

    def __post_init__(self) -> None:
        if self.status != "ANSWER_ASSERTIONS_EXTRACTED":
            raise ValueError("status ExtractAnswerAssertions invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        object.__setattr__(self, "assertions", _ensure_answer_assertions(self.assertions))
        object.__setattr__(self, "events", _ensure_extraction_events(self.events))


@dataclass(frozen=True)
class DraftAnswerHandler:
    """Orchestre ResearchCase scellé, générateur et AnswerRepository."""

    research_case_repository: ResearchCaseRepository
    answer_repository: AnswerRepository
    answer_generator: AnswerGenerator

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.answer_repository, "save", None)):
            raise ValueError("answer_repository sans save")
        if not callable(getattr(self.answer_generator, "draft", None)):
            raise ValueError("answer_generator sans draft")

    def draft(self, command: DraftAnswer) -> DraftAnswerResult:
        parsed_command = _ensure_draft_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if research_case.evidence_set is None or not research_case.evidence_set.sealed:
            raise ValueError("evidence_set non scelle")
        if research_case.evidence_set.evidence_set_id != parsed_command.evidence_set_id:
            raise ValueError("evidence_set_id incoherent")
        request = DraftAnswerRequest(
            research_case_id=research_case.research_case_id,
            resolved_question=research_case.resolved_question.text,
            evidence_set_id=research_case.evidence_set.evidence_set_id,
            evidence_set_version=research_case.evidence_set.version.value,
            verified_claim_count=len(research_case.evidence_set.verified_claim_refs),
            occurred_at=parsed_command.occurred_at,
        )
        generated = _ensure_generated_draft(self.answer_generator.draft(request))
        draft = AnswerDraft(
            draft_version=1,
            content=generated.content,
            model_provenance=generated.model_provenance,
        )
        answer = Answer.create_draft(
            answer_id=answer_id_for(
                research_case_id=research_case.research_case_id,
                evidence_set_id=research_case.evidence_set.evidence_set_id,
                draft_hash=draft.draft_hash,
            ),
            research_case_id=research_case.research_case_id,
            evidence_set_id=research_case.evidence_set.evidence_set_id,
            evidence_set_version=research_case.evidence_set.version.value,
            draft=draft,
            occurred_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.save(answer)
        return DraftAnswerResult(
            status="ANSWER_DRAFTED",
            answer=saved_answer,
            events=(saved_answer.events[-1],),
        )


@dataclass(frozen=True)
class ExtractAnswerAssertionsHandler:
    """Orchestre extraction d'assertions et transition de l'Answer."""

    answer_repository: AnswerRepository
    answer_assertion_extractor: AnswerAssertionExtractor

    def __post_init__(self) -> None:
        if not callable(getattr(self.answer_repository, "answer_for_id", None)):
            raise ValueError("answer_repository sans answer_for_id")
        if not callable(getattr(self.answer_repository, "update", None)):
            raise ValueError("answer_repository sans update")
        if not callable(getattr(self.answer_assertion_extractor, "extract", None)):
            raise ValueError("answer_assertion_extractor sans extract")
        _ensure_text(
            getattr(self.answer_assertion_extractor, "extractor_version", None),
            "extractor_version",
        )

    def extract(self, command: ExtractAnswerAssertions) -> ExtractAnswerAssertionsResult:
        parsed_command = _ensure_extract_command(command)
        answer = self.answer_repository.answer_for_id(parsed_command.answer_id)
        if not isinstance(answer, Answer):
            raise ValueError("answer invalide")
        candidates = _ensure_assertion_candidates(
            self.answer_assertion_extractor.extract(answer.draft)
        )
        updated_answer, event = answer.extract_assertions(
            assertions=candidates,
            extractor_version=self.answer_assertion_extractor.extractor_version,
            occurred_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.update(updated_answer)
        return ExtractAnswerAssertionsResult(
            status="ANSWER_ASSERTIONS_EXTRACTED",
            answer=saved_answer,
            assertions=saved_answer.assertions,
            events=(event,),
        )


def _ensure_generated_draft(value: object) -> GeneratedAnswerDraft:
    for forbidden_field in ("support_status", "final_status", "answer_status"):
        if hasattr(value, forbidden_field):
            raise ValueError("support_status fourni par le generateur")
    if isinstance(value, GeneratedAnswerDraft):
        return value
    return GeneratedAnswerDraft(
        content=getattr(value, "content", None),
        model_provenance=getattr(value, "model_provenance", None),
    )


def _ensure_draft_command(value: object) -> DraftAnswer:
    if not isinstance(value, DraftAnswer):
        raise ValueError("commande DraftAnswer invalide")
    return value


def _ensure_extract_command(value: object) -> ExtractAnswerAssertions:
    if not isinstance(value, ExtractAnswerAssertions):
        raise ValueError("commande ExtractAnswerAssertions invalide")
    return value


def _ensure_assertion_candidates(value: object) -> tuple[AnswerAssertionCandidate, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertion_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("answer_assertion_candidates absentes")
    for candidate in candidates:
        if not isinstance(candidate, AnswerAssertionCandidate):
            raise ValueError("answer_assertion_candidate invalide")
    return candidates


def _ensure_answer_assertions(value: object) -> tuple[AnswerAssertion, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertions invalides")
    assertions = tuple(value)
    if len(assertions) == 0:
        raise ValueError("answer_assertions absentes")
    for assertion in assertions:
        if not isinstance(assertion, AnswerAssertion):
            raise ValueError("answer_assertion invalide")
    return assertions


def _ensure_draft_events(value: object) -> tuple[AnswerDrafted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1 or not isinstance(events[0], AnswerDrafted):
        raise ValueError("event AnswerDrafted absent")
    return events


def _ensure_extraction_events(value: object) -> tuple[AnswerAssertionsExtracted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1 or not isinstance(events[0], AnswerAssertionsExtracted):
        raise ValueError("event AnswerAssertionsExtracted absent")
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


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "AnswerAssertionExtractor",
    "AnswerGenerator",
    "AnswerRepository",
    "DraftAnswer",
    "DraftAnswerHandler",
    "DraftAnswerRequest",
    "DraftAnswerResult",
    "ExtractAnswerAssertions",
    "ExtractAnswerAssertionsHandler",
    "ExtractAnswerAssertionsResult",
    "GeneratedAnswerDraft",
    "ResearchCaseRepository",
]
