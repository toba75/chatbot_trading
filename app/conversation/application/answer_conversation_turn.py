"""CV DTOs for public RA answers attached to conversation turns."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.contracts.identity import DomainIdentifier


@dataclass(frozen=True)
class PublicResearchAnswerResult:
    """Public RA answer result consumed by CV without owning RA proof."""

    verified_research_outcome: Any
    verified_answer_ref: str
    answer_text: str
    citations: Sequence[Mapping[str, Any]]
    abstention_reason: str | None

    @classmethod
    def from_answer_question_result(
        cls,
        result: object,
        *,
        verified_answer_ref: str,
    ) -> "PublicResearchAnswerResult":
        if not all(
            hasattr(result, attribute)
            for attribute in (
                "abstention_reason",
                "answer_text",
                "citations",
                "verified_research_outcome",
            )
        ):
            raise ValueError("answer_question_result invalide")
        return cls(
            verified_research_outcome=result.verified_research_outcome,
            verified_answer_ref=verified_answer_ref,
            answer_text=result.answer_text,
            citations=result.citations,
            abstention_reason=result.abstention_reason,
        )

    def __post_init__(self) -> None:
        verified_research_outcome = _ensure_verified_research_outcome(
            self.verified_research_outcome
        )
        object.__setattr__(self, "verified_research_outcome", verified_research_outcome)
        parsed_ref = _ensure_verified_answer_ref(self.verified_answer_ref)
        answer_id = parsed_ref.split("@", 1)[0]
        if answer_id != verified_research_outcome.answer_id:
            raise ValueError("verified_answer_ref incoherent")
        object.__setattr__(self, "verified_answer_ref", parsed_ref)
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        allow_empty_citations = (
            self.verified_research_outcome.support_status == "REQUIRES_CURRENT_DATA"
        )
        object.__setattr__(
            self,
            "citations",
            _ensure_public_citations(self.citations, allow_empty=allow_empty_citations),
        )
        object.__setattr__(
            self,
            "abstention_reason",
            _ensure_abstention_reason(
                self.abstention_reason,
                requires_current_data=allow_empty_citations,
            ),
        )

    @property
    def answer_id(self) -> str:
        return self.verified_research_outcome.answer_id

    @property
    def support_status(self) -> str:
        return self.verified_research_outcome.support_status

    def to_public_payload(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "abstention_reason": self.abstention_reason,
                "answer_id": self.answer_id,
                "answer_text": self.answer_text,
                "citations": tuple(self.citations),
                "support_status": self.support_status,
                "verified_answer_ref": self.verified_answer_ref,
            }
        )


def _ensure_verified_answer_ref(value: object) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    answer_id, separator, version = text.partition("@")
    if separator != "@" or not version.isdigit() or int(version) < 1:
        raise ValueError("verified_answer_ref invalide")
    try:
        DomainIdentifier.parse_with_prefix(answer_id, "ANS")
    except ValueError as exc:
        raise ValueError(f"verified_answer_ref invalide: {exc}") from exc
    return text


def _ensure_verified_research_outcome(value: object) -> object:
    required_attributes = ("answer_id", "question", "support_status", "to_payload")
    if not all(hasattr(value, attribute) for attribute in required_attributes):
        raise ValueError("verified_research_outcome invalide")
    if not callable(getattr(value, "to_payload")):
        raise ValueError("verified_research_outcome invalide")
    if hasattr(value, "answer_text") or hasattr(value, "citations"):
        raise ValueError("verified_research_outcome enrichi interdit")
    _ensure_answer_id(getattr(value, "answer_id"))
    _ensure_text(getattr(value, "question"), "question")
    _ensure_text(getattr(value, "support_status"), "support_status")
    return value


def _ensure_answer_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("answer_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "ANS"))
    except ValueError as exc:
        raise ValueError(f"answer_id invalide: {exc}") from exc


def _ensure_public_citations(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(_freeze_mapping(citation, "citation") for citation in value)
    if len(citations) == 0 and not allow_empty:
        raise ValueError("citations absentes")
    return citations


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return MappingProxyType(
        {
            _ensure_text(key, "cle"): _freeze_value(child, field_name)
            for key, child in value.items()
        }
    )


def _freeze_value(value: object, field_name: str) -> Any:
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_value(child, field_name) for child in value)
    raise ValueError(f"{field_name} invalide")


def _ensure_abstention_reason(value: object, *, requires_current_data: bool) -> str | None:
    if requires_current_data:
        return _ensure_text(value, "abstention_reason")
    if value is not None:
        raise ValueError("abstention_reason interdit")
    return None


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["PublicResearchAnswerResult"]
