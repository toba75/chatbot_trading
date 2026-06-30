"""Repository mémoire strict pour les ResearchCase RA."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.research_answering.domain.research_case import ResearchCase


class InMemoryResearchCaseRepository:
    """Repository non durable utilisé par les tests RA."""

    def __init__(self, *, research_cases: Sequence[ResearchCase]) -> None:
        self._lock = threading.Lock()
        self._cases_by_id: dict[str, ResearchCase] = {}
        for research_case in _ensure_research_cases(research_cases):
            self.save(research_case)

    @classmethod
    def empty(cls) -> "InMemoryResearchCaseRepository":
        return cls(research_cases=())

    def save(self, research_case: ResearchCase) -> ResearchCase:
        parsed_case = _ensure_research_case(research_case)
        with self._lock:
            existing = self._cases_by_id.get(parsed_case.research_case_id)
            if existing is not None and existing != parsed_case:
                raise ValueError("research_case deja enregistre")
            self._cases_by_id[parsed_case.research_case_id] = parsed_case
            return parsed_case

    def update(self, research_case: ResearchCase) -> ResearchCase:
        parsed_case = _ensure_research_case(research_case)
        with self._lock:
            existing = self._cases_by_id.get(parsed_case.research_case_id)
            if existing is None:
                raise ValueError(f"research_case inconnu: {parsed_case.research_case_id}")
            _ensure_same_case_identity(existing, parsed_case)
            self._cases_by_id[parsed_case.research_case_id] = parsed_case
            return parsed_case

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        parsed_id = _ensure_research_case_id(research_case_id)
        with self._lock:
            research_case = self._cases_by_id.get(parsed_id)
            if research_case is None:
                raise ValueError(f"research_case inconnu: {parsed_id}")
            return research_case

    def case_count(self) -> int:
        with self._lock:
            return len(self._cases_by_id)


def _ensure_research_cases(value: Sequence[ResearchCase]) -> tuple[ResearchCase, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("research_cases invalides")
    research_cases = tuple(value)
    for research_case in research_cases:
        _ensure_research_case(research_case)
    ids = tuple(research_case.research_case_id for research_case in research_cases)
    if len(ids) != len(set(ids)):
        raise ValueError("research_case duplique")
    return research_cases


def _ensure_research_case(value: object) -> ResearchCase:
    if not isinstance(value, ResearchCase):
        raise ValueError("research_case invalide")
    return value


def _ensure_same_case_identity(existing: ResearchCase, updated: ResearchCase) -> None:
    if existing.research_case_id != updated.research_case_id:
        raise ValueError("research_case_id incoherent")
    if existing.resolved_question != updated.resolved_question:
        raise ValueError("resolved_question incoherente")
    if existing.research_mandate != updated.research_mandate:
        raise ValueError("research_mandate incoherent")
    if existing.requested_mode != updated.requested_mode:
        raise ValueError("research_mode incoherent")
    if existing.requested_by_context != updated.requested_by_context:
        raise ValueError("requested_by_context incoherent")
    if existing.opened_at != updated.opened_at:
        raise ValueError("opened_at incoherent")


def _ensure_research_case_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("research_case_id non textuel")
    if value.strip() == "":
        raise ValueError("research_case_id vide")
    if value != value.strip():
        raise ValueError("research_case_id non normalise")
    if not value.startswith("RSC-"):
        raise ValueError("research_case_id invalide")
    return value


__all__ = ["InMemoryResearchCaseRepository"]
