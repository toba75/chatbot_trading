"""Repository mémoire strict pour les Answer RA."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.research_answering.domain.answer import Answer
from app.research_answering.domain.answer import AnswerStatus


class InMemoryAnswerRepository:
    """Repository non durable utilisé par les tests RA."""

    def __init__(self, *, answers: Sequence[Answer]) -> None:
        self._lock = threading.Lock()
        self._answers_by_id: dict[str, Answer] = {}
        for answer in _ensure_answers(answers):
            self.save(answer)

    @classmethod
    def empty(cls) -> "InMemoryAnswerRepository":
        return cls(answers=())

    def save(self, answer: Answer) -> Answer:
        parsed_answer = _ensure_answer(answer)
        with self._lock:
            existing = self._answers_by_id.get(parsed_answer.answer_id)
            if existing is not None and existing != parsed_answer:
                raise ValueError("answer deja enregistre")
            self._answers_by_id[parsed_answer.answer_id] = parsed_answer
            return parsed_answer

    def update(self, answer: Answer) -> Answer:
        parsed_answer = _ensure_answer(answer)
        with self._lock:
            existing = self._answers_by_id.get(parsed_answer.answer_id)
            if existing is None:
                raise ValueError(f"answer inconnu: {parsed_answer.answer_id}")
            _ensure_same_answer_identity(existing, parsed_answer)
            _ensure_terminal_status_not_regressed(existing, parsed_answer)
            _ensure_event_history_extends(existing.events, parsed_answer.events)
            self._answers_by_id[parsed_answer.answer_id] = parsed_answer
            return parsed_answer

    def answer_for_id(self, answer_id: str) -> Answer:
        parsed_id = _ensure_answer_id(answer_id)
        with self._lock:
            answer = self._answers_by_id.get(parsed_id)
            if answer is None:
                raise ValueError(f"answer inconnu: {parsed_id}")
            return answer

    def answer_count(self) -> int:
        with self._lock:
            return len(self._answers_by_id)


def _ensure_answers(value: Sequence[Answer]) -> tuple[Answer, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answers invalides")
    answers = tuple(value)
    for answer in answers:
        _ensure_answer(answer)
    ids = tuple(answer.answer_id for answer in answers)
    if len(ids) != len(set(ids)):
        raise ValueError("answer duplique")
    return answers


def _ensure_answer(value: object) -> Answer:
    if not isinstance(value, Answer):
        raise ValueError("answer invalide")
    return value


def _ensure_same_answer_identity(existing: Answer, updated: Answer) -> None:
    if existing.answer_id != updated.answer_id:
        raise ValueError("answer_id incoherent")
    if existing.research_case_id != updated.research_case_id:
        raise ValueError("research_case_id incoherent")
    if existing.evidence_set_id != updated.evidence_set_id:
        raise ValueError("evidence_set_id incoherent")
    if existing.evidence_set_version != updated.evidence_set_version:
        raise ValueError("evidence_set_version incoherente")
    if existing.drafted_at != updated.drafted_at:
        raise ValueError("drafted_at incoherent")
    if existing.draft != updated.draft:
        raise ValueError("answer_draft incoherent")


def _ensure_event_history_extends(existing_events: tuple[object, ...], updated_events: tuple[object, ...]) -> None:
    if len(updated_events) < len(existing_events):
        raise ValueError("answer version obsolete")
    if updated_events[: len(existing_events)] != existing_events:
        raise ValueError("answer version obsolete")


def _ensure_terminal_status_not_regressed(existing: Answer, updated: Answer) -> None:
    terminal_statuses = {
        AnswerStatus.VERIFIED,
        AnswerStatus.PARTIALLY_SUPPORTED,
        AnswerStatus.INSUFFICIENT_EVIDENCE,
        AnswerStatus.CONFLICTING_EVIDENCE,
        AnswerStatus.ABSTAINED,
        AnswerStatus.REJECTED,
    }
    if existing.status in terminal_statuses and updated.status is not existing.status:
        raise ValueError("answer version obsolete")


def _ensure_answer_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("answer_id non textuel")
    if value.strip() == "":
        raise ValueError("answer_id vide")
    if value != value.strip():
        raise ValueError("answer_id non normalise")
    if not value.startswith("ANS-"):
        raise ValueError("answer_id invalide")
    return value


__all__ = ["InMemoryAnswerRepository"]
