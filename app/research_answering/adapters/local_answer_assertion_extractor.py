"""Extracteur local déterministe des assertions importantes RA."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.research_answering.domain.answer import (
    AnswerAssertionCandidate,
    AnswerDraft,
    AssertionOrigin,
    AssertionOriginType,
)


_M007_EXTRACTOR_VERSION = "answer-assertion-extractor-m007-v1"
_ASSERTION_LINE_PATTERN = re.compile(r"\[(source|deduction|design):([^\]]*)\]\s(.+)")


@dataclass(frozen=True)
class LocalDeterministicAnswerAssertionExtractor:
    """Extracteur sans modèle: chaque ligne importante doit être balisée."""

    extractor_version: str

    @classmethod
    def for_m007(cls) -> "LocalDeterministicAnswerAssertionExtractor":
        return cls(extractor_version=_M007_EXTRACTOR_VERSION)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "extractor_version",
            _ensure_text(self.extractor_version, "extractor_version"),
        )

    def extract(self, draft: AnswerDraft) -> tuple[AnswerAssertionCandidate, ...]:
        parsed_draft = _ensure_answer_draft(draft)
        lines = tuple(line for line in parsed_draft.content.splitlines() if line.strip() != "")
        if len(lines) == 0:
            raise ValueError("answer_draft vide")
        candidates = tuple(self._candidate_from_line(line) for line in lines)
        if len(candidates) == 0:
            raise ValueError("answer_assertion_candidates absentes")
        return candidates

    def _candidate_from_line(self, line: str) -> AnswerAssertionCandidate:
        if line != line.strip():
            raise ValueError("assertion importante non extraite")
        match = _ASSERTION_LINE_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError("assertion importante non extraite")
        origin_kind = match.group(1)
        raw_basis_refs = match.group(2)
        assertion_text = match.group(3)
        origin = AssertionOrigin(
            origin_type=_origin_type_for_kind(origin_kind),
            basis_refs=_basis_refs_from_text(raw_basis_refs),
            rationale=_rationale_for_kind(origin_kind),
        )
        return AnswerAssertionCandidate.important_pending(
            text=assertion_text,
            origin=origin,
        )


def _origin_type_for_kind(value: str) -> AssertionOriginType:
    if value == "source":
        return AssertionOriginType.SOURCE
    if value == "deduction":
        return AssertionOriginType.DEDUCTION
    if value == "design":
        return AssertionOriginType.DESIGN_CHOICE
    raise ValueError(f"assertion_origin_type inconnu: {value}")


def _rationale_for_kind(value: str) -> str:
    if value == "source":
        return "Assertion issue d'une preuve ou d'un claim vérifié."
    if value == "deduction":
        return "Assertion déduite à partir de prémisses explicites."
    if value == "design":
        return "Assertion issue d'un choix de conception explicite."
    raise ValueError(f"assertion_origin_type inconnu: {value}")


def _basis_refs_from_text(value: str) -> tuple[str, ...]:
    if value is None:
        raise ValueError("basis_refs invalides")
    parts = tuple(part.strip() for part in value.split(",") if part.strip() != "")
    if len(parts) != len(set(parts)):
        raise ValueError("basis_refs dupliquees")
    return parts


def _ensure_answer_draft(value: object) -> AnswerDraft:
    if not isinstance(value, AnswerDraft):
        raise ValueError("answer_draft absent")
    return value


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["LocalDeterministicAnswerAssertionExtractor"]
