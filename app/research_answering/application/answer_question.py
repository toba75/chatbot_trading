"""Commande applicative RA de réponse documentaire publique."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.domain.research_case import (
    ResearchMandate,
    ResearchMode,
    ResolvedQuestion,
)


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ALLOWED_REQUESTING_CONTEXTS = frozenset({"API", "CV", "RA"})
_PUBLIC_CITATION_FIELDS = frozenset(
    {
        "citation_id",
        "evidence_id",
        "source_locator",
        "quoted_span_hash",
    }
)


class AnswerQuestionWorkflow(Protocol):
    """Port applicatif RA qui exécute le flux de réponse documentaire."""

    def answer(self, command: "AnswerQuestion") -> "AnswerQuestionResult":
        """Retourne la réponse documentaire vérifiée ou abstinente."""


@dataclass(frozen=True)
class AnswerQuestion:
    """Commande RA publique construite depuis `POST /v1/answer`."""

    resolved_question: ResolvedQuestion
    research_mandate: ResearchMandate
    requested_mode: ResearchMode
    requested_by_context: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        requested_by_context: str,
    ) -> "AnswerQuestion":
        parsed_payload = _ensure_mapping(payload, "answer_question")
        return cls(
            resolved_question=ResolvedQuestion(_required_value(parsed_payload, "resolved_question")),
            research_mandate=ResearchMandate.from_payload(
                _required_value(parsed_payload, "research_mandate")
            ),
            requested_mode=ResearchMode.from_value(_required_value(parsed_payload, "requested_mode")),
            requested_by_context=requested_by_context,
            idempotency_key=_required_text(parsed_payload, "idempotency_key"),
            occurred_at=_required_utc_instant(parsed_payload, "occurred_at"),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_question, ResolvedQuestion):
            raise ValueError("resolved_question absent")
        if not isinstance(self.research_mandate, ResearchMandate):
            raise ValueError("research_mandate absent")
        if not isinstance(self.requested_mode, ResearchMode):
            raise ValueError("requested_mode invalide")
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_requested_by_context(self.requested_by_context),
        )
        object.__setattr__(self, "idempotency_key", _ensure_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class AnswerQuestionResult:
    """Résultat public RA de réponse documentaire."""

    verified_research_outcome: VerifiedResearchOutcome
    answer_text: str
    citations: Sequence[Mapping[str, Any]]
    abstention_reason: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.verified_research_outcome, VerifiedResearchOutcome):
            raise ValueError("verified_research_outcome invalide")
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        requires_current_data = self.verified_research_outcome.support_status == "REQUIRES_CURRENT_DATA"
        object.__setattr__(
            self,
            "citations",
            _ensure_public_citations(self.citations, allow_empty=requires_current_data),
        )
        object.__setattr__(
            self,
            "abstention_reason",
            _ensure_abstention_reason(
                self.abstention_reason,
                requires_current_data=requires_current_data,
            ),
        )

    def to_public_payload(self) -> dict[str, Any]:
        outcome = self.verified_research_outcome.to_payload()
        return {
            "schema_version": outcome["schema_version"],
            "research_case_id": outcome["research_case_id"],
            "answer_id": outcome["answer_id"],
            "support_status": outcome["support_status"],
            "answer_text": self.answer_text,
            "citations": self.citations,
            "claim_refs": tuple(outcome["claim_refs"]),
            "unresolved_conflicts": tuple(outcome["unresolved_conflicts"]),
            "knowledge_gaps": tuple(outcome["knowledge_gaps"]),
            "abstention_reason": self.abstention_reason,
            "completed_at": outcome["completed_at"],
        }


@dataclass(frozen=True)
class AnswerQuestionHandler:
    """Délègue le flux RA complet sans exposer les stockages internes à l'API."""

    answer_workflow: AnswerQuestionWorkflow

    def __post_init__(self) -> None:
        if not callable(getattr(self.answer_workflow, "answer", None)):
            raise ValueError("answer_workflow sans AnswerQuestion")

    def answer(self, command: AnswerQuestion) -> AnswerQuestionResult:
        parsed_command = _ensure_answer_question(command)
        return _ensure_answer_question_result(self.answer_workflow.answer(parsed_command))


def _ensure_answer_question(value: object) -> AnswerQuestion:
    if not isinstance(value, AnswerQuestion):
        raise ValueError("commande AnswerQuestion invalide")
    return value


def _ensure_answer_question_result(value: object) -> AnswerQuestionResult:
    if not isinstance(value, AnswerQuestionResult):
        raise ValueError("answer_question_result invalide")
    return value


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
    return _ensure_utc_instant(_required_value(payload, field_name), field_name)


def _ensure_requested_by_context(value: object) -> str:
    context = _ensure_text(value, "requested_by_context")
    if context not in _ALLOWED_REQUESTING_CONTEXTS:
        raise ValueError("requested_by_context interdit")
    return context


def _ensure_abstention_reason(value: object, *, requires_current_data: bool) -> str | None:
    if requires_current_data:
        reason = _ensure_text(value, "abstention_reason")
        if reason != "CURRENT_DATA_REQUIRED":
            raise ValueError("abstention_reason CURRENT_DATA_REQUIRED requis")
        return reason
    if value is not None:
        raise ValueError("abstention_reason interdit")
    return None


def _ensure_public_citations(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(_ensure_public_citation(citation) for citation in value)
    if not allow_empty and len(citations) == 0:
        raise ValueError("citations absentes")
    citation_ids: list[str] = []
    for citation in citations:
        citation_id = citation["citation_id"]
        if citation_id in citation_ids:
            raise ValueError("citation dupliquee")
        citation_ids.append(citation_id)
    return citations


def _ensure_public_citation(value: object) -> Mapping[str, Any]:
    citation = dict(_ensure_mapping(value, "citation"))
    unexpected_fields = frozenset(citation.keys()) - _PUBLIC_CITATION_FIELDS
    if len(unexpected_fields) > 0:
        raise ValueError(f"citation champ interdit: {sorted(unexpected_fields)[0]}")
    missing_fields = _PUBLIC_CITATION_FIELDS - frozenset(citation.keys())
    if len(missing_fields) > 0:
        raise ValueError(f"citation champ absent: {sorted(missing_fields)[0]}")
    citation["citation_id"] = _ensure_text(citation["citation_id"], "citation_id")
    citation["evidence_id"] = _ensure_text(citation["evidence_id"], "evidence_id")
    citation["quoted_span_hash"] = _ensure_text(citation["quoted_span_hash"], "quoted_span_hash")
    source_locator = dict(_ensure_mapping(citation["source_locator"], "source_locator"))
    _ensure_text(source_locator.get("document_id"), "document_id")
    citation["source_locator"] = source_locator
    return citation


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "AnswerQuestion",
    "AnswerQuestionHandler",
    "AnswerQuestionResult",
    "AnswerQuestionWorkflow",
]
