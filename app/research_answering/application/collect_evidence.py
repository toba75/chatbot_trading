"""Cas d'usage RA de collecte et scellement d'un EvidenceSet."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.research_answering.domain.evidence_set import (
    EvidenceCollectionCompleted,
    EvidenceSet,
    EvidenceSetSealed,
)
from app.research_answering.domain.research_case import ResearchCase


_COVERAGE_POLICY_VERSION = "evidence-coverage-m007-v1"
_DIVERSIFICATION_POLICY_VERSION = "evidence-diversification-m007-v1"
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ResearchCaseRepository(Protocol):
    """Port RA de mise à jour du ResearchCase."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne le cas de recherche existant."""

    def update(self, research_case: ResearchCase) -> ResearchCase:
        """Remplace un ResearchCase par sa nouvelle version métier."""


class KnowledgeSearch(Protocol):
    """Port RA de recherche de preuves candidates KA."""

    def search(self, request: "EvidenceSearchRequest") -> Sequence["CandidateEvidence"]:
        """Retourne des preuves candidates sans exposer Qdrant."""


class VerifiedClaimCatalog(Protocol):
    """Port RA de lecture des claims vérifiés publiés par EG."""

    def verified_claims_for_evidence(
        self,
        evidence_refs: Sequence[EvidenceRef],
    ) -> Sequence[VerifiedClaimRef]:
        """Retourne les claims vérifiés couvrant les preuves retenues."""


class CitationResolver(Protocol):
    """Port RA de vérification d'ouverture des citations."""

    def resolve(self, citation: object) -> object:
        """Ouvre une citation ou échoue explicitement."""


@dataclass(frozen=True)
class CandidateEvidence:
    """Preuve candidate traduite dans le langage RA."""

    evidence_ref: EvidenceRef
    source_text: str
    search_trace_id: str
    document_id: str
    covered_obligations: Sequence[str]

    def __post_init__(self) -> None:
        if getattr(self.evidence_ref, "source_locator", None) is None:
            raise ValueError("source_locator absent")
        if not isinstance(self.evidence_ref, EvidenceRef):
            raise ValueError("evidence_ref invalide")
        object.__setattr__(self, "source_text", _ensure_text(self.source_text, "source_text"))
        object.__setattr__(
            self,
            "search_trace_id",
            _ensure_prefixed_text(self.search_trace_id, "search_trace_id", "STRC-"),
        )
        object.__setattr__(
            self,
            "document_id",
            _ensure_prefixed_text(self.document_id, "document_id", "DOC-"),
        )
        if self.evidence_ref.source_locator.document_id != self.document_id:
            raise ValueError("document_id incoherent avec SourceLocator")
        object.__setattr__(
            self,
            "covered_obligations",
            _ensure_text_tuple(self.covered_obligations, "covered_obligations"),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_ref": self.evidence_ref.to_payload(),
            "search_trace_id": self.search_trace_id,
            "document_id": self.document_id,
            "covered_obligations": self.covered_obligations,
        }


@dataclass(frozen=True)
class EvidenceSearchRequest:
    """Requête RA vers le port KA, sans détail d'index technique."""

    research_case_id: str
    query_text: str
    coverage_obligations: Sequence[str]
    result_limit: int
    requested_by_context: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(self, "query_text", _ensure_text(self.query_text, "query_text"))
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(self, "result_limit", _ensure_positive_integer(self.result_limit, "result_limit"))
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_text(self.requested_by_context, "requested_by_context"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class CollectEvidenceCommand:
    """Commande RA de collecte de preuves avant rédaction."""

    research_case_id: str
    coverage_obligations: Sequence[str]
    result_limit: int
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(self, "result_limit", _ensure_positive_integer(self.result_limit, "result_limit"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class SealEvidenceSetCommand:
    """Commande RA de scellement d'un EvidenceSet assemblé."""

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
class CollectEvidenceResult:
    """Résultat observable de collecte de preuves."""

    status: str
    research_case: ResearchCase
    evidence_set: EvidenceSet
    events: Sequence[EvidenceCollectionCompleted]

    def __post_init__(self) -> None:
        if self.status != "EVIDENCE_SET_COLLECTED":
            raise ValueError("status CollectEvidence invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        object.__setattr__(self, "events", _ensure_collection_events(self.events))


@dataclass(frozen=True)
class SealEvidenceSetResult:
    """Résultat observable de scellement de preuves."""

    status: str
    research_case: ResearchCase
    evidence_set: EvidenceSet
    events: Sequence[EvidenceSetSealed]

    def __post_init__(self) -> None:
        if self.status != "EVIDENCE_SET_SEALED":
            raise ValueError("status SealEvidenceSet invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        if not self.evidence_set.sealed:
            raise ValueError("evidence_set non scelle")
        object.__setattr__(self, "events", _ensure_sealed_events(self.events))


@dataclass(frozen=True)
class CollectEvidenceHandler:
    """Orchestre ports KA/EG et invariants RA pour l'EvidenceSet."""

    research_case_repository: ResearchCaseRepository
    knowledge_search: KnowledgeSearch
    verified_claim_catalog: VerifiedClaimCatalog
    citation_resolver: CitationResolver

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.research_case_repository, "update", None)):
            raise ValueError("research_case_repository sans update")
        if not callable(getattr(self.knowledge_search, "search", None)):
            raise ValueError("knowledge_search sans search")
        if not callable(getattr(self.verified_claim_catalog, "verified_claims_for_evidence", None)):
            raise ValueError("verified_claim_catalog sans verified_claims_for_evidence")
        if not callable(getattr(self.citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")

    def collect(self, command: CollectEvidenceCommand) -> CollectEvidenceResult:
        parsed_command = _ensure_collect_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        research_case.ensure_evidence_collection_allowed()
        self._ensure_requested_obligations_in_plan(research_case, parsed_command.coverage_obligations)
        request = EvidenceSearchRequest(
            research_case_id=research_case.research_case_id,
            query_text=research_case.resolved_question.text,
            coverage_obligations=parsed_command.coverage_obligations,
            result_limit=parsed_command.result_limit,
            requested_by_context="RA",
            occurred_at=parsed_command.occurred_at,
        )
        candidates = _ensure_candidate_evidences(
            self.knowledge_search.search(request),
            result_limit=parsed_command.result_limit,
        )
        evidence_refs = tuple(candidate.evidence_ref for candidate in candidates)
        verified_claim_refs = self.verified_claim_catalog.verified_claims_for_evidence(evidence_refs)
        evidence_set = EvidenceSet.assemble(
            research_case_id=research_case.research_case_id,
            coverage_obligations=parsed_command.coverage_obligations,
            candidates=candidates,
            verified_claim_refs=verified_claim_refs,
            coverage_policy_version=_COVERAGE_POLICY_VERSION,
            diversification_policy_version=_DIVERSIFICATION_POLICY_VERSION,
        )
        updated_case, event = research_case.attach_evidence_set(
            evidence_set,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(updated_case)
        return CollectEvidenceResult(
            status="EVIDENCE_SET_COLLECTED",
            research_case=saved_case,
            evidence_set=evidence_set,
            events=(event,),
        )

    def seal(self, command: SealEvidenceSetCommand) -> SealEvidenceSetResult:
        parsed_command = _ensure_seal_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        sealed_case, event = research_case.seal_evidence_set(
            evidence_set_id=parsed_command.evidence_set_id,
            citation_resolver=self.citation_resolver,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(sealed_case)
        if saved_case.evidence_set is None:
            raise ValueError("evidence_set absent")
        return SealEvidenceSetResult(
            status="EVIDENCE_SET_SEALED",
            research_case=saved_case,
            evidence_set=saved_case.evidence_set,
            events=(event,),
        )

    def _ensure_requested_obligations_in_plan(
        self,
        research_case: ResearchCase,
        coverage_obligations: Sequence[str],
    ) -> None:
        if research_case.research_plan is None:
            raise ValueError("research_plan absent")
        planned = {obligation.name for obligation in research_case.research_plan.coverage_obligations}
        for obligation in coverage_obligations:
            if obligation not in planned:
                raise ValueError(f"coverage_obligation inconnue: {obligation}")


def _ensure_candidate_evidences(
    value: Sequence[CandidateEvidence],
    *,
    result_limit: int,
) -> tuple[CandidateEvidence, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_refs absentes")
    if len(candidates) > _ensure_positive_integer(result_limit, "result_limit"):
        raise ValueError("evidence_candidates depassent result_limit")
    for candidate in candidates:
        if not isinstance(candidate, CandidateEvidence):
            raise ValueError("candidate_evidence invalide")
    return candidates


def _ensure_collect_command(value: CollectEvidenceCommand) -> CollectEvidenceCommand:
    if not isinstance(value, CollectEvidenceCommand):
        raise ValueError("commande CollectEvidence invalide")
    return value


def _ensure_seal_command(value: SealEvidenceSetCommand) -> SealEvidenceSetCommand:
    if not isinstance(value, SealEvidenceSetCommand):
        raise ValueError("commande SealEvidenceSet invalide")
    return value


def _ensure_collection_events(value: Sequence[EvidenceCollectionCompleted]) -> tuple[EvidenceCollectionCompleted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, EvidenceCollectionCompleted):
            raise ValueError("event EvidenceCollectionCompleted invalide")
    return events


def _ensure_sealed_events(value: Sequence[EvidenceSetSealed]) -> tuple[EvidenceSetSealed, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, EvidenceSetSealed):
            raise ValueError("event EvidenceSetSealed invalide")
    return events


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


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
    if not isinstance(value, int):
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
    "CandidateEvidence",
    "CitationResolver",
    "CollectEvidenceCommand",
    "CollectEvidenceHandler",
    "CollectEvidenceResult",
    "EvidenceSearchRequest",
    "KnowledgeSearch",
    "ResearchCaseRepository",
    "SealEvidenceSetCommand",
    "SealEvidenceSetResult",
    "VerifiedClaimCatalog",
]
