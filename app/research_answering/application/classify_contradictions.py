"""Cas d'usage RA de classification des contradictions et lacunes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.evidence_claims import VerifiedClaimRef
from app.research_answering.domain.contradiction_assessment import (
    ConditionalContradictionDetected,
    ContradictionAssessment,
    ContradictionClassificationPolicy,
    ContradictionDetected,
    DeepContradictionAssessment,
    DeepContradictionClassificationPolicy,
    DeepRelationClassificationContext,
    KnowledgeGap,
    KnowledgeGapRecorded,
    ResearchEvidenceFoundConflicting,
    ResearchEvidenceFoundInsufficient,
    SupportStatus,
    claim_refs_for_relation,
    ensure_classification_basis,
    ensure_conflicting_decision_basis,
    ensure_insufficient_decision_basis,
    ensure_missing_obligations,
    ensure_reason_codes,
    ensure_relation_ids,
    ensure_relation_sequence,
    ensure_research_case_id,
    ensure_utc_instant,
)
from app.research_answering.domain.evidence_set import (
    DeepCoverageRequirement,
    DeepEvidenceCoverageEvaluation,
    DeepEvidenceCoveragePolicy,
    EvidenceCollectionCompleted,
    EvidenceSet,
    EvidenceSetSealed,
)
from app.research_answering.domain.research_case import ResearchCase


_CONTRADICTION_POLICY_VERSION = "contradiction-classification-m007-v1"
_DEEP_CONTRADICTION_POLICY_VERSION = "conditional-contradiction-m009-v1"


class ResearchCaseRepository(Protocol):
    """Port RA de mise à jour du ResearchCase."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne un cas de recherche existant."""

    def update(self, research_case: ResearchCase) -> ResearchCase:
        """Remplace le cas de recherche par sa nouvelle version métier."""


@dataclass(frozen=True)
class RecordContradictionAssessment:
    """Commande RA d'enregistrement des diagnostics de contradiction."""

    research_case_id: str
    claim_relations: Sequence[object]
    qualified_relation_ids: Sequence[str]
    classification_basis: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "claim_relations", ensure_relation_sequence(self.claim_relations))
        object.__setattr__(
            self,
            "qualified_relation_ids",
            ensure_relation_ids(
                self.qualified_relation_ids,
                "qualified_relation_ids",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "classification_basis",
            ensure_classification_basis(self.classification_basis),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))
        relation_ids = {
            getattr(relation, "relation_id")
            for relation in self.claim_relations
        }
        for relation_id in self.qualified_relation_ids:
            if relation_id not in relation_ids:
                raise ValueError("qualified_relation inconnue")


@dataclass(frozen=True)
class RecordDeepContradictionAssessment:
    """Commande RA M-009 de classification approfondie des relations EG publiques."""

    research_case_id: str
    claim_relations: Sequence[object]
    relation_contexts: Sequence[DeepRelationClassificationContext]
    classification_basis: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "claim_relations", ensure_relation_sequence(self.claim_relations))
        object.__setattr__(self, "relation_contexts", _ensure_deep_contexts(self.relation_contexts))
        object.__setattr__(
            self,
            "classification_basis",
            ensure_classification_basis(self.classification_basis),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))
        relation_ids = tuple(getattr(relation, "relation_id") for relation in self.claim_relations)
        context_ids = tuple(context.relation_id for context in self.relation_contexts)
        if set(relation_ids) != set(context_ids):
            raise ValueError("classification_context relation incoherente")


@dataclass(frozen=True)
class DeclareInsufficientEvidence:
    """Commande RA de declaration d'insuffisance documentaire."""

    research_case_id: str
    missing_obligations: Sequence[str]
    reason_codes: Sequence[str]
    decision_basis: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "missing_obligations",
            ensure_missing_obligations(self.missing_obligations),
        )
        object.__setattr__(self, "reason_codes", ensure_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "decision_basis",
            ensure_insufficient_decision_basis(self.decision_basis),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DeclareInsufficientDeepCoverage:
    """Commande RA M-009 de declaration d'une couverture approfondie insuffisante."""

    research_case_id: str
    candidates: Sequence[object]
    verified_claim_refs: Sequence[VerifiedClaimRef]
    coverage_requirements: Sequence[DeepCoverageRequirement]
    decision_basis: str
    coverage_policy_version: str
    diversification_policy_version: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "candidates", _ensure_deep_coverage_candidates(self.candidates))
        object.__setattr__(
            self,
            "verified_claim_refs",
            _ensure_verified_claim_refs(self.verified_claim_refs),
        )
        object.__setattr__(
            self,
            "coverage_requirements",
            _ensure_deep_coverage_requirements(self.coverage_requirements),
        )
        object.__setattr__(
            self,
            "decision_basis",
            ensure_insufficient_decision_basis(self.decision_basis),
        )
        object.__setattr__(
            self,
            "coverage_policy_version",
            _ensure_text(self.coverage_policy_version, "coverage_policy_version"),
        )
        object.__setattr__(
            self,
            "diversification_policy_version",
            _ensure_text(self.diversification_policy_version, "diversification_policy_version"),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DeclareConflictingEvidence:
    """Commande RA de declaration de conflit documentaire non resolu."""

    research_case_id: str
    contradiction_ids: Sequence[str]
    reason_codes: Sequence[str]
    decision_basis: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "contradiction_ids",
            ensure_relation_ids(
                self.contradiction_ids,
                "contradiction_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(self, "reason_codes", ensure_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "decision_basis",
            ensure_conflicting_decision_basis(self.decision_basis),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class RecordContradictionAssessmentResult:
    """Resultat observable d'enregistrement de diagnostics."""

    status: str
    research_case: ResearchCase
    assessments: Sequence[ContradictionAssessment]
    events: Sequence[ContradictionDetected]

    def __post_init__(self) -> None:
        if self.status != "CONTRADICTION_ASSESSMENT_RECORDED":
            raise ValueError("status RecordContradictionAssessment invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        object.__setattr__(self, "assessments", _ensure_assessments(self.assessments))
        object.__setattr__(self, "events", _ensure_contradiction_events(self.events))


@dataclass(frozen=True)
class RecordDeepContradictionAssessmentResult:
    """Résultat observable d'une classification approfondie M-009."""

    status: str
    research_case: ResearchCase
    assessments: Sequence[DeepContradictionAssessment]
    events: Sequence[ConditionalContradictionDetected]

    def __post_init__(self) -> None:
        if self.status != "DEEP_CONTRADICTION_CLASSIFICATION_RECORDED":
            raise ValueError("status RecordDeepContradictionAssessment invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        object.__setattr__(self, "assessments", _ensure_deep_assessments(self.assessments))
        object.__setattr__(self, "events", _ensure_conditional_events(self.events))


@dataclass(frozen=True)
class DeclareInsufficientEvidenceResult:
    """Resultat observable d'insuffisance documentaire."""

    status: str
    research_case: ResearchCase
    knowledge_gaps: Sequence[KnowledgeGap]
    events: Sequence[KnowledgeGapRecorded | ResearchEvidenceFoundInsufficient]

    def __post_init__(self) -> None:
        if self.status != "INSUFFICIENT_EVIDENCE":
            raise ValueError("status DeclareInsufficientEvidence invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        object.__setattr__(self, "knowledge_gaps", _ensure_knowledge_gaps(self.knowledge_gaps))
        object.__setattr__(self, "events", _ensure_insufficient_events(self.events))


@dataclass(frozen=True)
class DeclareInsufficientDeepCoverageResult:
    """Résultat observable d'insuffisance de couverture approfondie M-009."""

    status: str
    support_status: SupportStatus
    research_case: ResearchCase
    evidence_set: EvidenceSet
    coverage_evaluation: DeepEvidenceCoverageEvaluation
    knowledge_gaps: Sequence[KnowledgeGap]
    events: Sequence[
        EvidenceCollectionCompleted
        | EvidenceSetSealed
        | KnowledgeGapRecorded
        | ResearchEvidenceFoundInsufficient
    ]

    def __post_init__(self) -> None:
        if self.status != "INSUFFICIENT_EVIDENCE":
            raise ValueError("status DeclareInsufficientDeepCoverage invalide")
        if self.support_status is not SupportStatus.INSUFFICIENT_EVIDENCE:
            raise ValueError("support_status DeclareInsufficientDeepCoverage invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        if not isinstance(self.coverage_evaluation, DeepEvidenceCoverageEvaluation):
            raise ValueError("coverage_evaluation invalide")
        object.__setattr__(self, "knowledge_gaps", _ensure_knowledge_gaps(self.knowledge_gaps))
        object.__setattr__(self, "events", _ensure_deep_insufficient_events(self.events))


@dataclass(frozen=True)
class DeclareConflictingEvidenceResult:
    """Resultat observable de conflit documentaire."""

    status: str
    research_case: ResearchCase
    events: Sequence[ResearchEvidenceFoundConflicting]

    def __post_init__(self) -> None:
        if self.status != "CONFLICTING_EVIDENCE":
            raise ValueError("status DeclareConflictingEvidence invalide")
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        object.__setattr__(self, "events", _ensure_conflicting_events(self.events))


@dataclass(frozen=True)
class RecordContradictionAssessmentHandler:
    """Orchestre la politique RA sans lire de stockage EG interne."""

    research_case_repository: ResearchCaseRepository
    policy: ContradictionClassificationPolicy

    def __init__(self, *, research_case_repository: ResearchCaseRepository) -> None:
        if not callable(getattr(research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(research_case_repository, "update", None)):
            raise ValueError("research_case_repository sans update")
        object.__setattr__(self, "research_case_repository", research_case_repository)
        object.__setattr__(
            self,
            "policy",
            ContradictionClassificationPolicy(policy_version=_CONTRADICTION_POLICY_VERSION),
        )

    def record(
        self,
        command: RecordContradictionAssessment,
    ) -> RecordContradictionAssessmentResult:
        parsed_command = _ensure_record_command(command)
        research_case = self._case_for(parsed_command.research_case_id)
        self._ensure_relation_claim_refs_in_evidence_set(
            research_case=research_case,
            claim_relations=parsed_command.claim_relations,
        )
        assessments = tuple(
            self.policy.classify(
                relation,
                qualified_relation_ids=parsed_command.qualified_relation_ids,
            )
            for relation in parsed_command.claim_relations
        )
        updated_case, events = research_case.record_contradiction_assessments(
            assessments,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(updated_case)
        return RecordContradictionAssessmentResult(
            status="CONTRADICTION_ASSESSMENT_RECORDED",
            research_case=saved_case,
            assessments=assessments,
            events=events,
        )

    def declare_insufficient(
        self,
        command: DeclareInsufficientEvidence,
    ) -> DeclareInsufficientEvidenceResult:
        parsed_command = _ensure_insufficient_command(command)
        research_case = self._case_for(parsed_command.research_case_id)
        updated_case, gaps, events = research_case.declare_insufficient_evidence(
            missing_obligations=parsed_command.missing_obligations,
            reason_codes=parsed_command.reason_codes,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(updated_case)
        return DeclareInsufficientEvidenceResult(
            status="INSUFFICIENT_EVIDENCE",
            research_case=saved_case,
            knowledge_gaps=gaps,
            events=events,
        )

    def declare_conflicting(
        self,
        command: DeclareConflictingEvidence,
    ) -> DeclareConflictingEvidenceResult:
        parsed_command = _ensure_conflicting_command(command)
        research_case = self._case_for(parsed_command.research_case_id)
        updated_case, event = research_case.declare_conflicting_evidence(
            contradiction_ids=parsed_command.contradiction_ids,
            reason_codes=parsed_command.reason_codes,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(updated_case)
        return DeclareConflictingEvidenceResult(
            status="CONFLICTING_EVIDENCE",
            research_case=saved_case,
            events=(event,),
        )

    def _case_for(self, research_case_id: str) -> ResearchCase:
        research_case = self.research_case_repository.case_for_id(research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        return research_case

    def _ensure_relation_claim_refs_in_evidence_set(
        self,
        *,
        research_case: ResearchCase,
        claim_relations: Sequence[object],
    ) -> None:
        if research_case.evidence_set is None:
            raise ValueError("evidence_set absent")
        known_claim_refs = {
            (claim_ref.claim_id, claim_ref.claim_version)
            for claim_ref in research_case.evidence_set.verified_claim_refs
        }
        for relation in claim_relations:
            for claim_ref in claim_refs_for_relation(relation):
                if (claim_ref.claim_id, claim_ref.claim_version) not in known_claim_refs:
                    raise ValueError("claim_relation hors evidence_set")


@dataclass(frozen=True)
class DeclareInsufficientDeepCoverageHandler:
    """Orchestre la politique RA M-009 de couverture insuffisante explicite."""

    research_case_repository: ResearchCaseRepository
    citation_resolver: object

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.research_case_repository, "update", None)):
            raise ValueError("research_case_repository sans update")
        if not callable(getattr(self.citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")

    def declare(
        self,
        command: DeclareInsufficientDeepCoverage,
    ) -> DeclareInsufficientDeepCoverageResult:
        parsed_command = _ensure_deep_insufficient_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        coverage_policy = DeepEvidenceCoveragePolicy(
            coverage_requirements=parsed_command.coverage_requirements,
            policy_version=parsed_command.coverage_policy_version,
        )
        coverage_evaluation = coverage_policy.evaluate(parsed_command.candidates)
        if coverage_evaluation.support_status is not SupportStatus.INSUFFICIENT_EVIDENCE:
            raise ValueError("couverture critique suffisante")
        if len(coverage_evaluation.covered_obligations) == 0:
            raise ValueError("coverage_obligations couvertes absentes")
        evidence_set = EvidenceSet.assemble(
            research_case_id=research_case.research_case_id,
            coverage_obligations=coverage_evaluation.covered_obligations,
            candidates=parsed_command.candidates,
            verified_claim_refs=parsed_command.verified_claim_refs,
            coverage_policy_version=parsed_command.coverage_policy_version,
            diversification_policy_version=parsed_command.diversification_policy_version,
        )
        assembled_case, collection_event = research_case.attach_evidence_set(
            evidence_set,
            occurred_at=parsed_command.occurred_at,
        )
        sealed_case, sealed_event = assembled_case.seal_evidence_set(
            evidence_set_id=evidence_set.evidence_set_id,
            citation_resolver=self.citation_resolver,
            occurred_at=parsed_command.occurred_at,
        )
        terminal_case, gaps, insufficient_events = sealed_case.declare_insufficient_deep_coverage(
            missing_obligations=coverage_evaluation.missing_obligations,
            reason_codes=coverage_evaluation.reason_codes,
            public_reasons=coverage_evaluation.public_reasons,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.research_case_repository.update(terminal_case)
        if saved_case.evidence_set is None:
            raise ValueError("evidence_set absent")
        return DeclareInsufficientDeepCoverageResult(
            status="INSUFFICIENT_EVIDENCE",
            support_status=coverage_evaluation.support_status,
            research_case=saved_case,
            evidence_set=saved_case.evidence_set,
            coverage_evaluation=coverage_evaluation,
            knowledge_gaps=gaps,
            events=(collection_event, sealed_event) + insufficient_events,
        )


@dataclass(frozen=True)
class RecordDeepContradictionAssessmentHandler:
    """Orchestre la classification approfondie M-009 sans accès au stockage EG interne."""

    research_case_repository: ResearchCaseRepository
    policy: DeepContradictionClassificationPolicy

    def __init__(self, *, research_case_repository: ResearchCaseRepository) -> None:
        if not callable(getattr(research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(research_case_repository, "update", None)):
            raise ValueError("research_case_repository sans update")
        object.__setattr__(self, "research_case_repository", research_case_repository)
        object.__setattr__(
            self,
            "policy",
            DeepContradictionClassificationPolicy(policy_version=_DEEP_CONTRADICTION_POLICY_VERSION),
        )

    def record(
        self,
        command: RecordDeepContradictionAssessment,
    ) -> RecordDeepContradictionAssessmentResult:
        parsed_command = _ensure_deep_record_command(command)
        research_case = self._case_for(parsed_command.research_case_id)
        self._ensure_relation_claim_refs_in_evidence_set(
            research_case=research_case,
            claim_relations=parsed_command.claim_relations,
        )
        contexts_by_relation_id = {
            context.relation_id: context
            for context in parsed_command.relation_contexts
        }
        assessments = tuple(
            self.policy.classify(
                relation,
                classification_context=contexts_by_relation_id[getattr(relation, "relation_id")],
            )
            for relation in parsed_command.claim_relations
        )
        events = tuple(
            ConditionalContradictionDetected.from_assessment(
                research_case_id=parsed_command.research_case_id,
                assessment=assessment,
                occurred_at=parsed_command.occurred_at,
            )
            for assessment in assessments
        )
        saved_case = self.research_case_repository.update(research_case)
        return RecordDeepContradictionAssessmentResult(
            status="DEEP_CONTRADICTION_CLASSIFICATION_RECORDED",
            research_case=saved_case,
            assessments=assessments,
            events=events,
        )

    def _case_for(self, research_case_id: str) -> ResearchCase:
        research_case = self.research_case_repository.case_for_id(research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        return research_case

    def _ensure_relation_claim_refs_in_evidence_set(
        self,
        *,
        research_case: ResearchCase,
        claim_relations: Sequence[object],
    ) -> None:
        if research_case.evidence_set is None:
            raise ValueError("evidence_set absent")
        known_claim_refs = {
            (claim_ref.claim_id, claim_ref.claim_version)
            for claim_ref in research_case.evidence_set.verified_claim_refs
        }
        for relation in claim_relations:
            for claim_ref in claim_refs_for_relation(relation):
                if (claim_ref.claim_id, claim_ref.claim_version) not in known_claim_refs:
                    raise ValueError("claim_relation hors evidence_set")


def _ensure_record_command(value: object) -> RecordContradictionAssessment:
    if not isinstance(value, RecordContradictionAssessment):
        raise ValueError("commande RecordContradictionAssessment invalide")
    return value


def _ensure_deep_record_command(value: object) -> RecordDeepContradictionAssessment:
    if not isinstance(value, RecordDeepContradictionAssessment):
        raise ValueError("commande RecordDeepContradictionAssessment invalide")
    return value


def _ensure_insufficient_command(value: object) -> DeclareInsufficientEvidence:
    if not isinstance(value, DeclareInsufficientEvidence):
        raise ValueError("commande DeclareInsufficientEvidence invalide")
    return value


def _ensure_deep_insufficient_command(value: object) -> DeclareInsufficientDeepCoverage:
    if not isinstance(value, DeclareInsufficientDeepCoverage):
        raise ValueError("commande DeclareInsufficientDeepCoverage invalide")
    return value


def _ensure_conflicting_command(value: object) -> DeclareConflictingEvidence:
    if not isinstance(value, DeclareConflictingEvidence):
        raise ValueError("commande DeclareConflictingEvidence invalide")
    return value


def _ensure_assessments(value: Sequence[ContradictionAssessment]) -> tuple[ContradictionAssessment, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("contradiction_assessments invalides")
    assessments = tuple(value)
    if len(assessments) == 0:
        raise ValueError("contradiction_assessments absents")
    for assessment in assessments:
        if not isinstance(assessment, ContradictionAssessment):
            raise ValueError("contradiction_assessment invalide")
    return assessments


def _ensure_deep_contexts(
    value: Sequence[DeepRelationClassificationContext],
) -> tuple[DeepRelationClassificationContext, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("relation_contexts invalides")
    contexts = tuple(value)
    if len(contexts) == 0:
        raise ValueError("relation_contexts absents")
    relation_ids: list[str] = []
    for context in contexts:
        if not isinstance(context, DeepRelationClassificationContext):
            raise ValueError("classification_context invalide")
        if context.relation_id in relation_ids:
            raise ValueError("classification_context duplique")
        relation_ids.append(context.relation_id)
    return contexts


def _ensure_deep_assessments(
    value: Sequence[DeepContradictionAssessment],
) -> tuple[DeepContradictionAssessment, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("deep_contradiction_assessments invalides")
    assessments = tuple(value)
    if len(assessments) == 0:
        raise ValueError("deep_contradiction_assessments absents")
    relation_ids: list[str] = []
    for assessment in assessments:
        if not isinstance(assessment, DeepContradictionAssessment):
            raise ValueError("deep_contradiction_assessment invalide")
        if assessment.relation_id in relation_ids:
            raise ValueError("deep_contradiction_assessment duplique")
        relation_ids.append(assessment.relation_id)
    return assessments


def _ensure_knowledge_gaps(value: Sequence[KnowledgeGap]) -> tuple[KnowledgeGap, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("knowledge_gaps invalides")
    gaps = tuple(value)
    if len(gaps) == 0:
        raise ValueError("knowledge_gaps absents")
    for gap in gaps:
        if not isinstance(gap, KnowledgeGap):
            raise ValueError("knowledge_gap invalide")
    return gaps


def _ensure_deep_coverage_candidates(value: Sequence[object]) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_refs absentes")
    return candidates


def _ensure_verified_claim_refs(value: Sequence[VerifiedClaimRef]) -> tuple[VerifiedClaimRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verified_claim_refs invalides")
    verified_claim_refs = tuple(value)
    if len(verified_claim_refs) == 0:
        raise ValueError("verified_claim_refs absents")
    claim_keys: list[tuple[str, int]] = []
    for verified_claim_ref in verified_claim_refs:
        if not isinstance(verified_claim_ref, VerifiedClaimRef):
            raise ValueError("verified_claim_ref invalide")
        claim_key = (verified_claim_ref.claim_id, verified_claim_ref.claim_version)
        if claim_key in claim_keys:
            raise ValueError("verified_claim_ref duplique")
        claim_keys.append(claim_key)
    return verified_claim_refs


def _ensure_deep_coverage_requirements(
    value: Sequence[DeepCoverageRequirement],
) -> tuple[DeepCoverageRequirement, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("coverage_requirements invalides")
    requirements = tuple(value)
    if len(requirements) == 0:
        raise ValueError("coverage_requirements absentes")
    obligation_names: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, DeepCoverageRequirement):
            raise ValueError("coverage_requirement invalide")
        if requirement.obligation_name in obligation_names:
            raise ValueError("coverage_requirement dupliquee")
        obligation_names.append(requirement.obligation_name)
    return requirements


def _ensure_contradiction_events(value: Sequence[ContradictionDetected]) -> tuple[ContradictionDetected, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ContradictionDetected):
            raise ValueError("event ContradictionDetected invalide")
    return events


def _ensure_conditional_events(
    value: Sequence[ConditionalContradictionDetected],
) -> tuple[ConditionalContradictionDetected, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ConditionalContradictionDetected):
            raise ValueError("event ConditionalContradictionDetected invalide")
    return events


def _ensure_insufficient_events(
    value: Sequence[KnowledgeGapRecorded | ResearchEvidenceFoundInsufficient],
) -> tuple[KnowledgeGapRecorded | ResearchEvidenceFoundInsufficient, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) < 2:
        raise ValueError("events insuffisance absents")
    for event in events:
        if not isinstance(event, (KnowledgeGapRecorded, ResearchEvidenceFoundInsufficient)):
            raise ValueError("event insuffisance invalide")
    if not isinstance(events[-1], ResearchEvidenceFoundInsufficient):
        raise ValueError("ResearchEvidenceFoundInsufficient absent")
    return events


def _ensure_deep_insufficient_events(
    value: Sequence[
        EvidenceCollectionCompleted
        | EvidenceSetSealed
        | KnowledgeGapRecorded
        | ResearchEvidenceFoundInsufficient
    ],
) -> tuple[
    EvidenceCollectionCompleted
    | EvidenceSetSealed
    | KnowledgeGapRecorded
    | ResearchEvidenceFoundInsufficient,
    ...,
]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) < 4:
        raise ValueError("events insuffisance approfondie absents")
    if not isinstance(events[0], EvidenceCollectionCompleted):
        raise ValueError("EvidenceCollectionCompleted absent")
    if not isinstance(events[1], EvidenceSetSealed):
        raise ValueError("EvidenceSetSealed absent")
    for event in events[2:]:
        if not isinstance(event, (KnowledgeGapRecorded, ResearchEvidenceFoundInsufficient)):
            raise ValueError("event insuffisance approfondie invalide")
    if not isinstance(events[-1], ResearchEvidenceFoundInsufficient):
        raise ValueError("ResearchEvidenceFoundInsufficient absent")
    return events


def _ensure_conflicting_events(
    value: Sequence[ResearchEvidenceFoundConflicting],
) -> tuple[ResearchEvidenceFoundConflicting, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1:
        raise ValueError("ResearchEvidenceFoundConflicting absent")
    if not isinstance(events[0], ResearchEvidenceFoundConflicting):
        raise ValueError("event conflit invalide")
    return events


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "DeclareConflictingEvidence",
    "DeclareConflictingEvidenceResult",
    "DeclareInsufficientDeepCoverage",
    "DeclareInsufficientDeepCoverageHandler",
    "DeclareInsufficientDeepCoverageResult",
    "DeclareInsufficientEvidence",
    "DeclareInsufficientEvidenceResult",
    "RecordDeepContradictionAssessment",
    "RecordDeepContradictionAssessmentHandler",
    "RecordDeepContradictionAssessmentResult",
    "RecordContradictionAssessment",
    "RecordContradictionAssessmentHandler",
    "RecordContradictionAssessmentResult",
    "ResearchCaseRepository",
]
