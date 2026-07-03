"""Cas d'usage RA de collecte et scellement d'un EvidenceSet."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.research_answering.domain.evidence_set import (
    DeepCoverageRequirement,
    DeepEvidenceCoveragePolicy,
    EvidenceCollectionCompleted,
    EvidenceSet,
    EvidenceSetSealed,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.research_case import ResearchCase
from app.research_answering.domain.research_case import DeepResearchPlan


_COVERAGE_POLICY_VERSION = "evidence-coverage-m007-v1"
_DIVERSIFICATION_POLICY_VERSION = "evidence-diversification-m007-v1"
_DEEP_COVERAGE_POLICY_VERSION = "deep-evidence-coverage-m009-v1"
_DEEP_DIVERSIFICATION_POLICY_VERSION = "deep-evidence-diversification-m009-v1"
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_DEEP_COVERAGE_REQUIREMENT_CONTRACT = {
    "methodes": {
        "critical": True,
        "required_polarity": "ANY",
        "requires_primary_source": True,
        "reason_code": "PRIMARY_SOURCE_MISSING",
        "public_reason": "Aucune source primaire admissible ne documente les methodes comparees.",
    },
    "preuves_favorables": {
        "critical": True,
        "required_polarity": "FAVORABLE",
        "requires_primary_source": False,
        "reason_code": "FAVORABLE_EVIDENCE_MISSING",
        "public_reason": "Aucune preuve favorable admissible n'est disponible.",
    },
    "preuves_defavorables": {
        "critical": True,
        "required_polarity": "UNFAVORABLE",
        "requires_primary_source": False,
        "reason_code": "UNFAVORABLE_EVIDENCE_MISSING",
        "public_reason": "Aucune preuve defavorable admissible ne couvre le mandat.",
    },
    "dependances": {
        "critical": True,
        "required_polarity": "ANY",
        "requires_primary_source": False,
        "reason_code": "DEPENDENCY_COVERAGE_MISSING",
        "public_reason": "Les dependances documentaires ne sont pas couvertes.",
    },
    "limites": {
        "critical": False,
        "required_polarity": "ANY",
        "requires_primary_source": False,
        "reason_code": "LIMIT_COVERAGE_MISSING",
        "public_reason": "Les limites documentaires doivent qualifier la synthese.",
    },
    "zones_non_documentees": {
        "critical": False,
        "required_polarity": "ANY",
        "requires_primary_source": False,
        "reason_code": "DOCUMENTARY_ZONE_UNCOVERED",
        "public_reason": "Les zones non documentees doivent rester visibles dans la reponse.",
    },
}


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


class DeepKnowledgeSearch(Protocol):
    """Port RA de recherche approfondie KA avec trace de projection publiée."""

    def search(self, request: "DeepEvidenceSearchRequest") -> "DeepEvidenceSearchResult":
        """Retourne les candidats et versions KA pour une sous-question M-009."""


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
    evidence_polarity: str
    source_kind: str

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
        object.__setattr__(
            self,
            "evidence_polarity",
            _ensure_deep_polarity(self.evidence_polarity),
        )
        object.__setattr__(self, "source_kind", _ensure_deep_source_kind(self.source_kind))

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_ref": self.evidence_ref.to_payload(),
            "search_trace_id": self.search_trace_id,
            "document_id": self.document_id,
            "covered_obligations": self.covered_obligations,
            "evidence_polarity": self.evidence_polarity,
            "source_kind": self.source_kind,
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
class DeepEvidenceSearchRequest:
    """Requête RA approfondie vers KA pour une sous-question planifiée."""

    research_case_id: str
    sub_question_id: str
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
        object.__setattr__(
            self,
            "sub_question_id",
            _ensure_prefixed_text(self.sub_question_id, "sub_question_id", "RSQ-"),
        )
        object.__setattr__(self, "query_text", _ensure_text(self.query_text, "query_text"))
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(self, "result_limit", _ensure_positive_integer(self.result_limit, "result_limit"))
        object.__setattr__(self, "requested_by_context", _ensure_text(self.requested_by_context, "requested_by_context"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DeepEvidenceSearchResult:
    """Résultat KA publié consommé par RA pour une sous-question approfondie."""

    projection_version_ref: str
    audit_trace_id: str
    candidates: Sequence[object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "projection_version_ref",
            _ensure_prefixed_text(self.projection_version_ref, "projection_version_ref", "PROJ-"),
        )
        object.__setattr__(
            self,
            "audit_trace_id",
            _ensure_prefixed_text(self.audit_trace_id, "audit_trace_id", "STRC-"),
        )
        object.__setattr__(self, "candidates", _ensure_deep_candidates(self.candidates))


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
class CollectDeepResearchEvidenceCommand:
    """Commande RA de collecte multi-requêtes pour un DeepResearchPlan."""

    research_case_id: str
    result_limit: int
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
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
class DeepResearchEvidenceCollected:
    """Événement RA de collecte approfondie avant synthèse multi-sources."""

    research_case_id: str
    evidence_set_id: str
    projection_version_refs: Sequence[str]
    audit_trace_ids: Sequence[str]
    evidence_count: int
    query_count: int
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "DeepResearchEvidenceCollected"

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
        object.__setattr__(
            self,
            "projection_version_refs",
            _ensure_text_sequence(self.projection_version_refs, "projection_version_refs"),
        )
        object.__setattr__(
            self,
            "audit_trace_ids",
            _ensure_prefixed_text_sequence(self.audit_trace_ids, "audit_trace_ids", "STRC-"),
        )
        object.__setattr__(self, "evidence_count", _ensure_positive_integer(self.evidence_count, "evidence_count"))
        object.__setattr__(self, "query_count", _ensure_positive_integer(self.query_count, "query_count"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "evidence_set_id": self.evidence_set_id,
                "projection_version_refs": self.projection_version_refs,
                "audit_trace_ids": self.audit_trace_ids,
                "evidence_count": self.evidence_count,
                "query_count": self.query_count,
            },
        }


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
class CollectDeepResearchEvidenceResult:
    """Résultat observable de collecte approfondie multi-requêtes."""

    status: str
    research_case: ResearchCase
    evidence_set: EvidenceSet
    projection_version_refs: Sequence[str]
    audit_trace_ids: Sequence[str]
    events: Sequence[DeepResearchEvidenceCollected]

    def __post_init__(self) -> None:
        if self.status != "DEEP_RESEARCH_EVIDENCE_COLLECTED":
            raise ValueError("status CollectDeepResearchEvidence invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        object.__setattr__(
            self,
            "projection_version_refs",
            _ensure_text_sequence(self.projection_version_refs, "projection_version_refs"),
        )
        object.__setattr__(
            self,
            "audit_trace_ids",
            _ensure_prefixed_text_sequence(self.audit_trace_ids, "audit_trace_ids", "STRC-"),
        )
        object.__setattr__(self, "events", _ensure_deep_collection_events(self.events))


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


@dataclass(frozen=True)
class CollectDeepResearchEvidenceHandler:
    """Orchestre la collecte RA approfondie sans exposer les internes KA."""

    research_case_repository: ResearchCaseRepository
    knowledge_search: DeepKnowledgeSearch
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

    def collect(self, command: CollectDeepResearchEvidenceCommand) -> CollectDeepResearchEvidenceResult:
        parsed_command = _ensure_deep_collect_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        research_case.ensure_evidence_collection_allowed()
        plan = _ensure_deep_research_plan(research_case.research_plan)

        collected_candidates: list[object] = []
        projection_version_refs: list[str] = []
        audit_trace_ids: list[str] = []

        for sub_question in plan.sub_questions:
            request = DeepEvidenceSearchRequest(
                research_case_id=research_case.research_case_id,
                sub_question_id=sub_question.sub_question_id,
                query_text=sub_question.text,
                coverage_obligations=sub_question.coverage_obligation_names,
                result_limit=parsed_command.result_limit,
                requested_by_context="RA",
                occurred_at=parsed_command.occurred_at,
            )
            search_result = _ensure_deep_search_result(
                self.knowledge_search.search(request),
                result_limit=parsed_command.result_limit,
            )
            _ensure_candidate_obligations_in_sub_question(
                candidates=search_result.candidates,
                sub_question_obligations=sub_question.coverage_obligation_names,
            )
            collected_candidates.extend(search_result.candidates)
            projection_version_refs.append(search_result.projection_version_ref)
            audit_trace_ids.append(search_result.audit_trace_id)

        candidates = tuple(collected_candidates)
        _ensure_deep_candidate_diversity(candidates)
        coverage_evaluation = DeepEvidenceCoveragePolicy(
            coverage_requirements=_deep_coverage_requirements_for_plan(plan),
            policy_version=_DEEP_COVERAGE_POLICY_VERSION,
        ).evaluate(candidates)
        if coverage_evaluation.support_status is SupportStatus.INSUFFICIENT_EVIDENCE:
            raise ValueError("COVERAGE_INSUFFICIENT")
        coverage_obligations = tuple(obligation.name for obligation in plan.coverage_obligations)
        evidence_refs = tuple(_deep_candidate_evidence_ref(candidate) for candidate in candidates)
        verified_claim_refs = self.verified_claim_catalog.verified_claims_for_evidence(evidence_refs)
        evidence_set = EvidenceSet.assemble(
            research_case_id=research_case.research_case_id,
            coverage_obligations=coverage_obligations,
            candidates=candidates,
            verified_claim_refs=verified_claim_refs,
            coverage_policy_version=_DEEP_COVERAGE_POLICY_VERSION,
            diversification_policy_version=_DEEP_DIVERSIFICATION_POLICY_VERSION,
        )
        updated_case, _collection_event = research_case.attach_evidence_set(
            evidence_set,
            occurred_at=parsed_command.occurred_at,
        )
        traced_case = updated_case.record_deep_collection_trace(
            evidence_set_id=evidence_set.evidence_set_id,
            projection_version_refs=tuple(projection_version_refs),
            audit_trace_ids=tuple(audit_trace_ids),
        )
        saved_case = self.research_case_repository.update(traced_case)
        deep_event = DeepResearchEvidenceCollected(
            research_case_id=research_case.research_case_id,
            evidence_set_id=evidence_set.evidence_set_id,
            projection_version_refs=tuple(projection_version_refs),
            audit_trace_ids=tuple(audit_trace_ids),
            evidence_count=len(evidence_set.evidence_refs),
            query_count=len(plan.sub_questions),
            occurred_at=parsed_command.occurred_at,
        )
        return CollectDeepResearchEvidenceResult(
            status="DEEP_RESEARCH_EVIDENCE_COLLECTED",
            research_case=saved_case,
            evidence_set=evidence_set,
            projection_version_refs=tuple(projection_version_refs),
            audit_trace_ids=tuple(audit_trace_ids),
            events=(deep_event,),
        )


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


def _ensure_deep_candidates(value: Sequence[object]) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_refs absentes")
    for candidate in candidates:
        _deep_candidate_evidence_ref(candidate)
        _deep_candidate_covered_obligations(candidate)
        _deep_candidate_document_id(candidate)
        _deep_candidate_evidence_polarity(candidate)
        _deep_candidate_source_kind(candidate)
    return candidates


def _ensure_deep_search_result(value: object, *, result_limit: int) -> DeepEvidenceSearchResult:
    if not isinstance(value, DeepEvidenceSearchResult):
        raise ValueError("deep_evidence_search_result invalide")
    if len(value.candidates) > _ensure_positive_integer(result_limit, "result_limit"):
        raise ValueError("evidence_candidates depassent result_limit")
    return value


def _ensure_collect_command(value: CollectEvidenceCommand) -> CollectEvidenceCommand:
    if not isinstance(value, CollectEvidenceCommand):
        raise ValueError("commande CollectEvidence invalide")
    return value


def _ensure_deep_collect_command(value: CollectDeepResearchEvidenceCommand) -> CollectDeepResearchEvidenceCommand:
    if not isinstance(value, CollectDeepResearchEvidenceCommand):
        raise ValueError("commande CollectDeepResearchEvidence invalide")
    return value


def _ensure_seal_command(value: SealEvidenceSetCommand) -> SealEvidenceSetCommand:
    if not isinstance(value, SealEvidenceSetCommand):
        raise ValueError("commande SealEvidenceSet invalide")
    return value


def _ensure_deep_research_plan(value: object) -> DeepResearchPlan:
    if not isinstance(value, DeepResearchPlan):
        raise ValueError("deep_research_plan absent")
    return value


def _deep_coverage_requirements_for_plan(plan: DeepResearchPlan) -> tuple[DeepCoverageRequirement, ...]:
    requirements: list[DeepCoverageRequirement] = []
    for obligation in plan.coverage_obligations:
        contract = _DEEP_COVERAGE_REQUIREMENT_CONTRACT.get(obligation.name)
        if contract is None:
            raise ValueError(f"coverage_obligation M-009 inconnue: {obligation.name}")
        requirements.append(
            DeepCoverageRequirement(
                obligation_name=obligation.name,
                critical=contract["critical"],
                required_polarity=contract["required_polarity"],
                requires_primary_source=contract["requires_primary_source"],
                reason_code=contract["reason_code"],
                public_reason=contract["public_reason"],
            )
        )
    return tuple(requirements)


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


def _ensure_deep_collection_events(
    value: Sequence[DeepResearchEvidenceCollected],
) -> tuple[DeepResearchEvidenceCollected, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, DeepResearchEvidenceCollected):
            raise ValueError("event DeepResearchEvidenceCollected invalide")
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


def _ensure_candidate_obligations_in_sub_question(
    *,
    candidates: Sequence[object],
    sub_question_obligations: Sequence[str],
) -> None:
    allowed = set(_ensure_text_tuple(sub_question_obligations, "coverage_obligations"))
    for candidate in _ensure_deep_candidates(candidates):
        for obligation in _deep_candidate_covered_obligations(candidate):
            if obligation not in allowed:
                raise ValueError(f"coverage_obligation hors sous-question: {obligation}")


def _ensure_deep_candidate_diversity(candidates: Sequence[object]) -> None:
    parsed_candidates = _ensure_deep_candidates(candidates)
    evidence_ids: set[str] = set()
    locator_keys: set[tuple[object, ...]] = set()
    document_ids: set[str] = set()
    for candidate in parsed_candidates:
        evidence_ref = _deep_candidate_evidence_ref(candidate)
        if evidence_ref.evidence_id in evidence_ids:
            raise ValueError("evidence_ref duplique")
        evidence_ids.add(evidence_ref.evidence_id)
        locator_key = _deep_source_locator_key(evidence_ref.source_locator)
        if locator_key in locator_keys:
            raise ValueError("source_locator duplique")
        locator_keys.add(locator_key)
        document_id = _deep_candidate_document_id(candidate)
        if document_id in document_ids:
            raise ValueError(f"document dominant: {document_id}")
        document_ids.add(document_id)


def _deep_candidate_evidence_ref(candidate: object) -> EvidenceRef:
    evidence_ref = getattr(candidate, "evidence_ref", None)
    if evidence_ref is None:
        raise ValueError("evidence_ref absent")
    if getattr(evidence_ref, "source_locator", None) is None:
        raise ValueError("source_locator absent")
    if not isinstance(evidence_ref, EvidenceRef):
        raise ValueError("evidence_ref invalide")
    return evidence_ref


def _deep_candidate_covered_obligations(candidate: object) -> tuple[str, ...]:
    return _ensure_text_tuple(
        getattr(candidate, "covered_obligations", None),
        "covered_obligations",
    )


def _deep_candidate_document_id(candidate: object) -> str:
    evidence_ref = _deep_candidate_evidence_ref(candidate)
    document_id = _ensure_prefixed_text(getattr(candidate, "document_id", None), "document_id", "DOC-")
    if evidence_ref.source_locator.document_id != document_id:
        raise ValueError("document_id incoherent avec SourceLocator")
    return document_id


def _deep_candidate_evidence_polarity(candidate: object) -> str:
    return _ensure_deep_polarity(getattr(candidate, "evidence_polarity", None))


def _deep_candidate_source_kind(candidate: object) -> str:
    return _ensure_deep_source_kind(getattr(candidate, "source_kind", None))


def _deep_source_locator_key(source_locator: object) -> tuple[object, ...]:
    if source_locator is None:
        raise ValueError("source_locator absent")
    return (
        source_locator.canonical_version_id,
        source_locator.document_id,
        source_locator.page_pdf,
        source_locator.item_id,
        source_locator.bbox,
        source_locator.content_hash,
    )


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


def _ensure_deep_polarity(value: object) -> str:
    text = _ensure_text(value, "evidence_polarity")
    if text not in {"ANY", "FAVORABLE", "UNFAVORABLE", "NEUTRAL"}:
        raise ValueError(f"evidence_polarity invalide: {text}")
    return text


def _ensure_deep_source_kind(value: object) -> str:
    text = _ensure_text(value, "source_kind")
    if text not in {"PRIMARY", "SECONDARY"}:
        raise ValueError(f"source_kind invalide: {text}")
    return text


def _ensure_text_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    return parsed


def _ensure_prefixed_text_sequence(value: object, field_name: str, prefix: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_prefixed_text(item, field_name, prefix) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
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
    "CollectDeepResearchEvidenceCommand",
    "CollectDeepResearchEvidenceHandler",
    "CollectDeepResearchEvidenceResult",
    "CollectEvidenceCommand",
    "CollectEvidenceHandler",
    "CollectEvidenceResult",
    "DeepEvidenceSearchRequest",
    "DeepEvidenceSearchResult",
    "DeepKnowledgeSearch",
    "DeepResearchEvidenceCollected",
    "EvidenceSearchRequest",
    "KnowledgeSearch",
    "ResearchCaseRepository",
    "SealEvidenceSetCommand",
    "SealEvidenceSetResult",
    "VerifiedClaimCatalog",
]
