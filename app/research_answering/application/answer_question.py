"""Commande applicative RA de réponse documentaire publique."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.application.collect_evidence import (
    CollectEvidenceCommand,
    SealEvidenceSetCommand,
)
from app.research_answering.application.draft_answer import (
    DraftAnswer,
    ExtractAnswerAssertions,
)
from app.research_answering.application.open_research_case import OpenResearchCaseCommand
from app.research_answering.application.verify_answer import EvaluateAnswerSupport
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
_PUBLIC_SOURCE_LOCATOR_FIELDS = frozenset(
    {
        "schema_version",
        "canonical_version_id",
        "document_id",
        "page_pdf",
        "item_id",
        "bbox",
        "content_hash",
    }
)


class AnswerQuestionWorkflow(Protocol):
    """Port applicatif RA qui exécute le flux de réponse documentaire."""

    def answer(self, command: "AnswerQuestion") -> "AnswerQuestionResult":
        """Retourne la réponse documentaire vérifiée ou abstinente."""


class OpenResearchCaseHandlerPort(Protocol):
    """Port du workflow vers ouverture et planification de ResearchCase."""

    def open_and_plan(self, command: OpenResearchCaseCommand) -> object:
        """Ouvre et planifie un ResearchCase."""


class CollectEvidenceHandlerPort(Protocol):
    """Port du workflow vers collecte et scellement d'EvidenceSet."""

    def collect(self, command: CollectEvidenceCommand) -> object:
        """Collecte les preuves candidates bornées."""

    def seal(self, command: SealEvidenceSetCommand) -> object:
        """Scelle le jeu de preuves."""


class DraftAnswerHandlerPort(Protocol):
    """Port du workflow vers génération de brouillon."""

    def draft(self, command: DraftAnswer) -> object:
        """Produit un Answer en brouillon."""


class ExtractAnswerAssertionsHandlerPort(Protocol):
    """Port du workflow vers extraction d'assertions."""

    def extract(self, command: ExtractAnswerAssertions) -> object:
        """Extrait les assertions importantes."""


class EvaluateAnswerSupportHandlerPort(Protocol):
    """Port du workflow vers évaluation de support."""

    def evaluate(self, command: EvaluateAnswerSupport) -> object:
        """Évalue le support et publie la version RA."""


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
class DocumentaryAnswerWorkflow:
    """Workflow RA concret de réponse documentaire simple."""

    open_research_case_handler: OpenResearchCaseHandlerPort
    collect_evidence_handler: CollectEvidenceHandlerPort
    draft_answer_handler: DraftAnswerHandlerPort
    extract_answer_assertions_handler: ExtractAnswerAssertionsHandlerPort
    evaluate_answer_support_handler: EvaluateAnswerSupportHandlerPort
    coverage_obligations: Sequence[str]
    evidence_result_limit: int
    support_policy_version: str
    citation_policy_version: str
    freshness_policy_version: str

    def __post_init__(self) -> None:
        if not callable(getattr(self.open_research_case_handler, "open_and_plan", None)):
            raise ValueError("open_research_case_handler sans open_and_plan")
        if not callable(getattr(self.collect_evidence_handler, "collect", None)):
            raise ValueError("collect_evidence_handler sans collect")
        if not callable(getattr(self.collect_evidence_handler, "seal", None)):
            raise ValueError("collect_evidence_handler sans seal")
        if not callable(getattr(self.draft_answer_handler, "draft", None)):
            raise ValueError("draft_answer_handler sans draft")
        if not callable(getattr(self.extract_answer_assertions_handler, "extract", None)):
            raise ValueError("extract_answer_assertions_handler sans extract")
        if not callable(getattr(self.evaluate_answer_support_handler, "evaluate", None)):
            raise ValueError("evaluate_answer_support_handler sans evaluate")
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(
            self,
            "evidence_result_limit",
            _ensure_positive_integer(self.evidence_result_limit, "evidence_result_limit"),
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

    def answer(self, command: AnswerQuestion) -> AnswerQuestionResult:
        parsed_command = _ensure_answer_question(command)
        opened = self.open_research_case_handler.open_and_plan(
            OpenResearchCaseCommand(
                resolved_question=parsed_command.resolved_question,
                research_mandate=parsed_command.research_mandate,
                requested_mode=parsed_command.requested_mode,
                requested_by_context=parsed_command.requested_by_context,
                idempotency_key=parsed_command.idempotency_key,
                occurred_at=parsed_command.occurred_at,
            )
        )
        research_case_id = _ensure_text(
            getattr(opened, "research_case_id", None),
            "research_case_id",
        )
        collected = self.collect_evidence_handler.collect(
            CollectEvidenceCommand(
                research_case_id=research_case_id,
                coverage_obligations=self.coverage_obligations,
                result_limit=self.evidence_result_limit,
                occurred_at=parsed_command.occurred_at,
            )
        )
        collected_evidence_set = _required_attribute(collected, "evidence_set")
        evidence_set_id = _ensure_text(
            getattr(collected_evidence_set, "evidence_set_id", None),
            "evidence_set_id",
        )
        sealed = self.collect_evidence_handler.seal(
            SealEvidenceSetCommand(
                research_case_id=research_case_id,
                evidence_set_id=evidence_set_id,
                occurred_at=parsed_command.occurred_at,
            )
        )
        sealed_evidence_set = _required_attribute(sealed, "evidence_set")
        drafted = self.draft_answer_handler.draft(
            DraftAnswer(
                research_case_id=research_case_id,
                evidence_set_id=_ensure_text(
                    getattr(sealed_evidence_set, "evidence_set_id", None),
                    "evidence_set_id",
                ),
                occurred_at=parsed_command.occurred_at,
            )
        )
        drafted_answer = _required_attribute(drafted, "answer")
        extracted = self.extract_answer_assertions_handler.extract(
            ExtractAnswerAssertions(
                answer_id=_ensure_text(getattr(drafted_answer, "answer_id", None), "answer_id"),
                occurred_at=parsed_command.occurred_at,
            )
        )
        extracted_answer = _required_attribute(extracted, "answer")
        evaluated = self.evaluate_answer_support_handler.evaluate(
            EvaluateAnswerSupport(
                research_case_id=research_case_id,
                answer_id=_ensure_text(getattr(extracted_answer, "answer_id", None), "answer_id"),
                support_policy_version=self.support_policy_version,
                citation_policy_version=self.citation_policy_version,
                freshness_policy_version=self.freshness_policy_version,
                occurred_at=parsed_command.occurred_at,
            )
        )
        version = _required_attribute(evaluated, "verified_answer_version")
        outcome = _required_attribute(evaluated, "verified_research_outcome")
        if not isinstance(outcome, VerifiedResearchOutcome):
            raise ValueError("verified_research_outcome invalide")
        return AnswerQuestionResult(
            verified_research_outcome=outcome,
            answer_text=_ensure_text(getattr(version, "answer_text", None), "answer_text"),
            citations=tuple(citation.to_payload() for citation in getattr(version, "citations", ())),
            abstention_reason=(
                "CURRENT_DATA_REQUIRED"
                if outcome.support_status == "REQUIRES_CURRENT_DATA"
                else None
            ),
        )


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


def _required_attribute(value: object, field_name: str) -> Any:
    if not hasattr(value, field_name):
        raise ValueError(f"{field_name} absent")
    return getattr(value, field_name)


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _ensure_text(_required_value(payload, field_name), field_name)


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    return _ensure_utc_instant(_required_value(payload, field_name), field_name)


def _ensure_requested_by_context(value: object) -> str:
    context = _ensure_text(value, "requested_by_context")
    if context not in _ALLOWED_REQUESTING_CONTEXTS:
        raise ValueError("requested_by_context interdit")
    return context


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


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
    citation["source_locator"] = _ensure_public_source_locator(citation["source_locator"])
    return citation


def _ensure_public_source_locator(value: object) -> Mapping[str, Any]:
    source_locator = dict(_ensure_mapping(value, "source_locator"))
    unexpected_fields = frozenset(source_locator.keys()) - _PUBLIC_SOURCE_LOCATOR_FIELDS
    if len(unexpected_fields) > 0:
        raise ValueError(f"source_locator champ interdit: {sorted(unexpected_fields)[0]}")
    missing_fields = _PUBLIC_SOURCE_LOCATOR_FIELDS - frozenset(source_locator.keys())
    if len(missing_fields) > 0:
        raise ValueError(f"source_locator champ absent: {sorted(missing_fields)[0]}")
    return {
        "schema_version": _ensure_text(source_locator["schema_version"], "schema_version"),
        "canonical_version_id": _ensure_text(
            source_locator["canonical_version_id"],
            "canonical_version_id",
        ),
        "document_id": _ensure_text(source_locator["document_id"], "document_id"),
        "page_pdf": _ensure_positive_integer(source_locator["page_pdf"], "page_pdf"),
        "item_id": _ensure_text(source_locator["item_id"], "item_id"),
        "bbox": _ensure_bbox(source_locator["bbox"]),
        "content_hash": _ensure_text(source_locator["content_hash"], "content_hash"),
    }


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} non entier")
    if value <= 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_bbox(value: object) -> tuple[float, float, float, float]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("bbox invalide")
    parsed = tuple(value)
    if len(parsed) != 4:
        raise ValueError("bbox invalide")
    coordinates: list[float] = []
    for coordinate in parsed:
        if not isinstance(coordinate, (int, float)):
            raise ValueError("bbox invalide")
        coordinates.append(float(coordinate))
    return tuple(coordinates)


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
    "DocumentaryAnswerWorkflow",
]
