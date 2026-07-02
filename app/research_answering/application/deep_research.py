"""Facade applicative RA pour la recherche approfondie publique M-009."""

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
_DEEP_RESEARCH_FIELDS = frozenset(
    {
        "resolved_question",
        "research_mandate",
        "research_mode",
        "selected_documents",
        "idempotency_key",
        "occurred_at",
    }
)
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
_FORBIDDEN_STORAGE_FIELDS = frozenset(
    {
        "eg_registry_table",
        "market_price_override",
        "prompt_override",
        "qdrant_collection",
        "qdrant_point_id",
        "ra_storage",
        "raw_projection_payload",
        "sp_table",
        "strategy_parameter",
        "support_status_override",
    }
)
_FORBIDDEN_CLIENT_FIELDS = frozenset({"support_status"})
_ALLOWED_REQUESTING_CONTEXTS = frozenset({"API", "CV", "RA"})


class DeepResearchWorkflow(Protocol):
    """Port RA qui execute une recherche approfondie sans fallback documentaire."""

    def research(self, command: "DeepResearchRequest") -> "DeepResearchResult":
        """Retourne un resultat public de recherche approfondie."""


@dataclass(frozen=True)
class DeepResearchRequest:
    """Commande publique stricte de `POST /v1/research/deep`."""

    resolved_question: ResolvedQuestion
    research_mandate: ResearchMandate
    research_mode: ResearchMode
    selected_document_ids: tuple[str, ...]
    requested_by_context: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        requested_by_context: str,
    ) -> "DeepResearchRequest":
        parsed_payload = _ensure_mapping(payload, "body")
        actual_fields = frozenset(parsed_payload.keys())
        forbidden_storage = actual_fields & _FORBIDDEN_STORAGE_FIELDS
        if len(forbidden_storage) > 0:
            raise ValueError(f"body champ stockage interdit: {sorted(forbidden_storage)[0]}")
        forbidden_client = actual_fields & _FORBIDDEN_CLIENT_FIELDS
        if len(forbidden_client) > 0:
            raise ValueError(f"body champ interdit: {sorted(forbidden_client)[0]}")
        unexpected_fields = actual_fields - _DEEP_RESEARCH_FIELDS
        if len(unexpected_fields) > 0:
            raise ValueError(f"body champ interdit: {sorted(unexpected_fields)[0]}")
        for field_name in sorted(_DEEP_RESEARCH_FIELDS):
            if field_name not in parsed_payload:
                raise ValueError(f"{field_name} absent")
        research_mandate_payload = _ensure_mapping(
            parsed_payload["research_mandate"],
            "research_mandate",
        )
        if len(research_mandate_payload) == 0:
            raise ValueError("research_mandate vide")
        try:
            research_mandate = ResearchMandate.from_payload(research_mandate_payload)
        except ValueError as exc:
            raise ValueError(f"research_mandate invalide: {exc}") from exc
        return cls(
            resolved_question=ResolvedQuestion(parsed_payload["resolved_question"]),
            research_mandate=research_mandate,
            research_mode=ResearchMode.from_value(parsed_payload["research_mode"]),
            selected_document_ids=_ensure_document_ids(
                parsed_payload["selected_documents"],
                "selected_documents",
            ),
            requested_by_context=requested_by_context,
            idempotency_key=_ensure_text(parsed_payload["idempotency_key"], "idempotency_key"),
            occurred_at=_ensure_utc_instant(parsed_payload["occurred_at"], "occurred_at"),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_question, ResolvedQuestion):
            raise ValueError("resolved_question absent")
        if not isinstance(self.research_mandate, ResearchMandate):
            raise ValueError("research_mandate absent")
        if self.research_mode is not ResearchMode.DEEP_RESEARCH:
            raise ValueError("research_mode approfondi requis")
        object.__setattr__(
            self,
            "selected_document_ids",
            _ensure_document_ids(self.selected_document_ids, "selected_documents"),
        )
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_requesting_context(self.requested_by_context),
        )
        object.__setattr__(self, "idempotency_key", _ensure_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DeepResearchResult:
    """Resultat public M-009 sans exposition des stockages internes."""

    verified_research_outcome: VerifiedResearchOutcome
    answer_text: str
    citations: Sequence[Mapping[str, Any]]
    plan_version: str
    coverage_summary: Mapping[str, Any]
    contradictions: Sequence[Mapping[str, Any]]
    gaps: Sequence[Mapping[str, Any]]
    synthesis_ref: str
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
        object.__setattr__(self, "plan_version", _ensure_ref(self.plan_version, "plan_version", "RPLAN-"))
        object.__setattr__(
            self,
            "coverage_summary",
            _ensure_public_mapping(self.coverage_summary, "coverage_summary", allow_empty=False),
        )
        object.__setattr__(
            self,
            "contradictions",
            _ensure_public_mapping_sequence(self.contradictions, "contradiction"),
        )
        object.__setattr__(self, "gaps", _ensure_public_mapping_sequence(self.gaps, "gap"))
        object.__setattr__(
            self,
            "synthesis_ref",
            _ensure_ref(self.synthesis_ref, "synthesis_ref", "SYN-"),
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
            "plan_version": self.plan_version,
            "coverage_summary": self.coverage_summary,
            "citations": self.citations,
            "contradictions": self.contradictions,
            "gaps": self.gaps,
            "synthesis_ref": self.synthesis_ref,
            "claim_refs": tuple(outcome["claim_refs"]),
            "abstention_reason": self.abstention_reason,
            "completed_at": outcome["completed_at"],
        }


@dataclass(frozen=True)
class DeepResearchHandler:
    """Facade RA mince qui delegue au workflow approfondi configure."""

    deep_research_workflow: DeepResearchWorkflow

    def __post_init__(self) -> None:
        if not callable(getattr(self.deep_research_workflow, "research", None)):
            raise ValueError("deep_research_workflow sans research")

    def research(self, command: DeepResearchRequest) -> DeepResearchResult:
        parsed_command = _ensure_deep_research_request(command)
        return _ensure_deep_research_result(self.deep_research_workflow.research(parsed_command))


def _ensure_deep_research_request(value: object) -> DeepResearchRequest:
    if not isinstance(value, DeepResearchRequest):
        raise ValueError("commande DeepResearchRequest invalide")
    return value


def _ensure_deep_research_result(value: object) -> DeepResearchResult:
    if not isinstance(value, DeepResearchResult):
        raise ValueError("deep_research_result invalide")
    return value


def _ensure_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return value


def _ensure_document_ids(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_ref(item, field_name, "DOC-") for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliques")
    return parsed


def _ensure_requesting_context(value: object) -> str:
    context = _ensure_text(value, "requested_by_context")
    if context not in _ALLOWED_REQUESTING_CONTEXTS:
        raise ValueError("requested_by_context interdit")
    return context


def _ensure_public_citations(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(_ensure_public_citation(citation) for citation in value)
    if len(citations) == 0 and not allow_empty:
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
    _ensure_no_forbidden_field(citation.keys(), "citation")
    unexpected_fields = frozenset(citation.keys()) - _PUBLIC_CITATION_FIELDS
    if len(unexpected_fields) > 0:
        raise ValueError(f"citation champ interdit: {sorted(unexpected_fields)[0]}")
    missing_fields = _PUBLIC_CITATION_FIELDS - frozenset(citation.keys())
    if len(missing_fields) > 0:
        raise ValueError(f"citation champ absent: {sorted(missing_fields)[0]}")
    return {
        "citation_id": _ensure_ref(citation["citation_id"], "citation_id", "CIT-"),
        "evidence_id": _ensure_ref(citation["evidence_id"], "evidence_id", "EVS-"),
        "source_locator": _ensure_public_source_locator(citation["source_locator"]),
        "quoted_span_hash": _ensure_text(citation["quoted_span_hash"], "quoted_span_hash"),
    }


def _ensure_public_source_locator(value: object) -> Mapping[str, Any]:
    source_locator = dict(_ensure_mapping(value, "source_locator"))
    _ensure_no_forbidden_field(source_locator.keys(), "source_locator")
    unexpected_fields = frozenset(source_locator.keys()) - _PUBLIC_SOURCE_LOCATOR_FIELDS
    if len(unexpected_fields) > 0:
        raise ValueError(f"source_locator champ interdit: {sorted(unexpected_fields)[0]}")
    missing_fields = _PUBLIC_SOURCE_LOCATOR_FIELDS - frozenset(source_locator.keys())
    if len(missing_fields) > 0:
        raise ValueError(f"source_locator champ absent: {sorted(missing_fields)[0]}")
    return {
        "schema_version": _ensure_text(source_locator["schema_version"], "schema_version"),
        "canonical_version_id": _ensure_ref(
            source_locator["canonical_version_id"],
            "canonical_version_id",
            "CVER-",
        ),
        "document_id": _ensure_ref(source_locator["document_id"], "document_id", "DOC-"),
        "page_pdf": _ensure_positive_integer(source_locator["page_pdf"], "page_pdf"),
        "item_id": _ensure_text(source_locator["item_id"], "item_id"),
        "bbox": _ensure_bbox(source_locator["bbox"]),
        "content_hash": _ensure_text(source_locator["content_hash"], "content_hash"),
    }


def _ensure_public_mapping_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(_ensure_public_mapping(item, field_name, allow_empty=False) for item in value)


def _ensure_public_mapping(
    value: object,
    field_name: str,
    *,
    allow_empty: bool,
) -> Mapping[str, Any]:
    parsed = dict(_ensure_mapping(value, field_name))
    if len(parsed) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    _ensure_no_forbidden_field(parsed.keys(), field_name)
    return {
        _ensure_text(key, "cle"): _freeze_public_value(child, field_name)
        for key, child in parsed.items()
    }


def _freeze_public_value(value: object, field_name: str) -> Any:
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value == value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Mapping):
        return _ensure_public_mapping(value, field_name, allow_empty=True)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_public_value(child, field_name) for child in value)
    raise ValueError(f"{field_name} invalide")


def _ensure_no_forbidden_field(keys: object, field_name: str) -> None:
    for key in keys:
        parsed_key = _ensure_text(key, "cle")
        if parsed_key in _FORBIDDEN_STORAGE_FIELDS or parsed_key in _FORBIDDEN_CLIENT_FIELDS:
            raise ValueError(f"{field_name} champ interdit: {parsed_key}")


def _ensure_abstention_reason(value: object, *, requires_current_data: bool) -> str | None:
    if requires_current_data:
        reason = _ensure_text(value, "abstention_reason")
        if reason != "CURRENT_DATA_REQUIRED":
            raise ValueError("abstention_reason CURRENT_DATA_REQUIRED requis")
        return reason
    if value is not None:
        raise ValueError("abstention_reason interdit")
    return None


def _ensure_bbox(value: object) -> tuple[float, float, float, float]:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("bbox invalide")
    parsed = tuple(value)
    if len(parsed) != 4:
        raise ValueError("bbox invalide")
    coordinates: list[float] = []
    for coordinate in parsed:
        if not isinstance(coordinate, (int, float)):
            raise ValueError("bbox invalide")
        parsed_coordinate = float(coordinate)
        if not parsed_coordinate == parsed_coordinate or parsed_coordinate in (
            float("inf"),
            float("-inf"),
        ):
            raise ValueError("bbox invalide")
        coordinates.append(parsed_coordinate)
    return tuple(coordinates)


def _ensure_ref(value: object, field_name: str, prefix: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} non entier")
    if value <= 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "DeepResearchHandler",
    "DeepResearchRequest",
    "DeepResearchResult",
    "DeepResearchWorkflow",
]
