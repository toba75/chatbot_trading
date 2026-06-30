"""Agrégat RA de cas de recherche planifié."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from app.research_answering.domain.evidence_set import (
    EvidenceCollectionCompleted,
    EvidenceSet,
    EvidenceSetSealed,
)
from app.research_answering.domain.contradiction_assessment import (
    ContradictionAssessment,
    ContradictionDetected,
    KnowledgeGap,
    KnowledgeGapRecorded,
    ResearchEvidenceFoundConflicting,
    ResearchEvidenceFoundInsufficient,
    SupportStatus,
    ensure_assessments,
    ensure_knowledge_gaps,
    ensure_missing_obligations,
    ensure_reason_codes,
    ensure_relation_ids,
    ensure_support_status,
)


_HASH_HEX_LENGTH = 24
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")
_RESEARCH_PLAN_ID_PATTERN = re.compile(r"^RPLAN-[A-Z0-9][A-Z0-9-]*$")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ALLOWED_REQUESTING_CONTEXTS = frozenset({"API", "CV", "RA"})
_MANDATE_FIELDS = frozenset(
    {
        "allowed_universe",
        "horizon",
        "data_requirements",
        "exclusions",
        "language",
        "detail_level",
    }
)


class ResearchMode(str, Enum):
    """Mode de recherche demandé explicitement à RA."""

    DOCUMENTARY_SIMPLE = "DOCUMENTARY_SIMPLE"

    @classmethod
    def from_value(cls, value: object) -> "ResearchMode":
        text = _ensure_text(value, "requested_mode")
        for mode in cls:
            if text == mode.value:
                return mode
        raise ValueError(f"research_mode inconnu: {text}")


class ResearchCaseStatus(str, Enum):
    """État métier local du ResearchCase M-007."""

    CREATED = "CREATED"
    PLANNED = "PLANNED"
    EVIDENCE_ASSEMBLED = "EVIDENCE_ASSEMBLED"
    EVIDENCE_SET_SEALED = "EVIDENCE_SET_SEALED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


@dataclass(frozen=True)
class ResolvedQuestion:
    """Question autonome reçue par RA."""

    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_text(self.text, "resolved_question"))

    @property
    def question_hash(self) -> str:
        return _sha256_text(self.text)


@dataclass(frozen=True)
class ResearchMandate:
    """Mandat documentaire explicite bornant la réponse attendue."""

    allowed_universe: tuple[str, ...]
    horizon: str
    data_requirements: tuple[str, ...]
    exclusions: tuple[str, ...]
    language: str
    detail_level: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ResearchMandate":
        parsed_payload = _ensure_mapping(payload, "research_mandate")
        for field_name in parsed_payload:
            if field_name not in _MANDATE_FIELDS:
                raise ValueError(f"research_mandate champ interdit: {field_name}")
        return cls(
            allowed_universe=_required_text_tuple(parsed_payload, "allowed_universe"),
            horizon=_required_text(parsed_payload, "horizon"),
            data_requirements=_required_text_tuple(parsed_payload, "data_requirements"),
            exclusions=_required_text_tuple(parsed_payload, "exclusions"),
            language=_required_text(parsed_payload, "language"),
            detail_level=_required_text(parsed_payload, "detail_level"),
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_universe",
            _ensure_text_tuple(self.allowed_universe, "allowed_universe"),
        )
        object.__setattr__(self, "horizon", _ensure_text(self.horizon, "horizon"))
        object.__setattr__(
            self,
            "data_requirements",
            _ensure_text_tuple(self.data_requirements, "data_requirements"),
        )
        object.__setattr__(self, "exclusions", _ensure_text_tuple(self.exclusions, "exclusions"))
        object.__setattr__(self, "language", _ensure_text(self.language, "language"))
        object.__setattr__(self, "detail_level", _ensure_text(self.detail_level, "detail_level"))

    @property
    def mandate_hash(self) -> str:
        return _hash_payload(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "allowed_universe": self.allowed_universe,
            "horizon": self.horizon,
            "data_requirements": self.data_requirements,
            "exclusions": self.exclusions,
            "language": self.language,
            "detail_level": self.detail_level,
        }


@dataclass(frozen=True)
class CoverageObligation:
    """Obligation de couverture nommée avant toute collecte de preuves."""

    name: str
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _ensure_text(self.name, "coverage_obligation name"))
        object.__setattr__(
            self,
            "description",
            _ensure_text(self.description, "coverage_obligation description"),
        )

    def to_payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
        }


@dataclass(frozen=True)
class ResearchPlan:
    """Plan RA local publié dans le ResearchCase avant collecte."""

    plan_id: str
    mode: ResearchMode
    coverage_obligations: tuple[CoverageObligation, ...]
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _ensure_plan_id(self.plan_id))
        if not isinstance(self.mode, ResearchMode):
            raise ValueError("research_mode invalide")
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_coverage_obligations(self.coverage_obligations),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mode": self.mode.value,
            "coverage_obligations": [
                obligation.to_payload() for obligation in self.coverage_obligations
            ],
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class ResearchCaseOpened:
    """Événement RA d'ouverture d'un cas de recherche."""

    research_case_id: str
    resolved_question_hash: str
    mandate_hash: str
    requested_by_context: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ResearchCaseOpened"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "resolved_question_hash",
            _ensure_sha256(self.resolved_question_hash, "resolved_question_hash"),
        )
        object.__setattr__(self, "mandate_hash", _ensure_sha256(self.mandate_hash, "mandate_hash"))
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_requesting_context(self.requested_by_context),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "resolved_question_hash": self.resolved_question_hash,
                "mandate_hash": self.mandate_hash,
                "requested_by_context": self.requested_by_context,
            },
        }


@dataclass(frozen=True)
class ResearchPlanCreated:
    """Événement RA de planification d'un cas de recherche."""

    research_case_id: str
    coverage_obligations: tuple[str, ...]
    policy_version: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ResearchPlanCreated"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "coverage_obligations": self.coverage_obligations,
                "policy_version": self.policy_version,
            },
        }


@dataclass(frozen=True)
class ResearchCase:
    """Agrégat RA qui fige question, mandat et plan avant les preuves."""

    research_case_id: str
    resolved_question: ResolvedQuestion
    research_mandate: ResearchMandate
    requested_mode: ResearchMode
    status: ResearchCaseStatus
    research_plan: ResearchPlan | None
    evidence_set: EvidenceSet | None
    contradiction_assessments: tuple[ContradictionAssessment, ...]
    knowledge_gaps: tuple[KnowledgeGap, ...]
    requested_by_context: str
    opened_at: str
    events: tuple[
        ResearchCaseOpened
        | ResearchPlanCreated
        | EvidenceCollectionCompleted
        | EvidenceSetSealed
        | ContradictionDetected
        | KnowledgeGapRecorded
        | ResearchEvidenceFoundInsufficient
        | ResearchEvidenceFoundConflicting,
        ...,
    ]

    @classmethod
    def open(
        cls,
        *,
        research_case_id: str,
        resolved_question: ResolvedQuestion,
        research_mandate: ResearchMandate,
        requested_mode: ResearchMode,
        requested_by_context: str,
        occurred_at: str,
    ) -> "ResearchCase":
        question = _ensure_resolved_question(resolved_question)
        mandate = _ensure_research_mandate(research_mandate)
        mode = _ensure_research_mode(requested_mode)
        opened = ResearchCaseOpened(
            research_case_id=research_case_id,
            resolved_question_hash=question.question_hash,
            mandate_hash=mandate.mandate_hash,
            requested_by_context=requested_by_context,
            occurred_at=occurred_at,
        )
        return cls(
            research_case_id=research_case_id,
            resolved_question=question,
            research_mandate=mandate,
            requested_mode=mode,
            status=ResearchCaseStatus.CREATED,
            research_plan=None,
            evidence_set=None,
            contradiction_assessments=(),
            knowledge_gaps=(),
            requested_by_context=requested_by_context,
            opened_at=occurred_at,
            events=(opened,),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "resolved_question",
            _ensure_resolved_question(self.resolved_question),
        )
        object.__setattr__(
            self,
            "research_mandate",
            _ensure_research_mandate(self.research_mandate),
        )
        object.__setattr__(self, "requested_mode", _ensure_research_mode(self.requested_mode))
        if not isinstance(self.status, ResearchCaseStatus):
            raise ValueError("research_case status invalide")
        if self.research_plan is not None and not isinstance(self.research_plan, ResearchPlan):
            raise ValueError("research_plan invalide")
        if self.evidence_set is not None and not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        object.__setattr__(
            self,
            "contradiction_assessments",
            ensure_assessments(self.contradiction_assessments),
        )
        object.__setattr__(self, "knowledge_gaps", ensure_knowledge_gaps(self.knowledge_gaps))
        if self.status is ResearchCaseStatus.CREATED and self.research_plan is not None:
            raise ValueError("research_plan interdit pour CREATED")
        if self.status is ResearchCaseStatus.CREATED and self.evidence_set is not None:
            raise ValueError("evidence_set interdit pour CREATED")
        if self.status is ResearchCaseStatus.PLANNED and self.research_plan is None:
            raise ValueError("research_plan absent pour PLANNED")
        if self.status is ResearchCaseStatus.PLANNED and self.evidence_set is not None:
            raise ValueError("evidence_set interdit pour PLANNED")
        if self.status is ResearchCaseStatus.EVIDENCE_ASSEMBLED:
            if self.research_plan is None:
                raise ValueError("research_plan absent pour EVIDENCE_ASSEMBLED")
            if self.evidence_set is None:
                raise ValueError("evidence_set absent pour EVIDENCE_ASSEMBLED")
            if self.evidence_set.sealed:
                raise ValueError("evidence_set scelle pour EVIDENCE_ASSEMBLED")
        if self.status is ResearchCaseStatus.EVIDENCE_SET_SEALED:
            if self.research_plan is None:
                raise ValueError("research_plan absent pour EVIDENCE_SET_SEALED")
            if self.evidence_set is None:
                raise ValueError("evidence_set absent pour EVIDENCE_SET_SEALED")
            if not self.evidence_set.sealed:
                raise ValueError("evidence_set non scelle pour EVIDENCE_SET_SEALED")
        if self.status in {
            ResearchCaseStatus.CREATED,
            ResearchCaseStatus.PLANNED,
            ResearchCaseStatus.EVIDENCE_ASSEMBLED,
        } and (
            len(self.contradiction_assessments) > 0 or len(self.knowledge_gaps) > 0
        ):
            raise ValueError("diagnostics RA interdits avant evidence_set scelle")
        if self.status in {
            ResearchCaseStatus.INSUFFICIENT_EVIDENCE,
            ResearchCaseStatus.CONFLICTING_EVIDENCE,
        }:
            if self.research_plan is None:
                raise ValueError("research_plan absent pour statut terminal")
            if self.evidence_set is None or not self.evidence_set.sealed:
                raise ValueError("evidence_set non scelle pour statut terminal")
        if self.status is ResearchCaseStatus.INSUFFICIENT_EVIDENCE and len(self.knowledge_gaps) == 0:
            raise ValueError("knowledge_gap absent pour INSUFFICIENT_EVIDENCE")
        if self.status is ResearchCaseStatus.CONFLICTING_EVIDENCE and not any(
            assessment.blocks_publication for assessment in self.contradiction_assessments
        ):
            raise ValueError("contradiction bloquante absente pour CONFLICTING_EVIDENCE")
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_requesting_context(self.requested_by_context),
        )
        object.__setattr__(self, "opened_at", _ensure_utc_instant(self.opened_at, "opened_at"))
        object.__setattr__(self, "events", _ensure_events(self.events))

    def plan_research(self, plan: ResearchPlan) -> "ResearchCase":
        parsed_plan = _ensure_research_plan(plan)
        if self.status is ResearchCaseStatus.PLANNED or self.research_plan is not None:
            raise ValueError("research_case deja planifie")
        if self.status is not ResearchCaseStatus.CREATED:
            raise ValueError("transition research_case invalide")
        if parsed_plan.mode is not self.requested_mode:
            raise ValueError("research_plan mode incoherent")
        event = ResearchPlanCreated(
            research_case_id=self.research_case_id,
            coverage_obligations=tuple(
                obligation.name for obligation in parsed_plan.coverage_obligations
            ),
            policy_version=parsed_plan.policy_version,
            occurred_at=self.opened_at,
        )
        return replace(
            self,
            status=ResearchCaseStatus.PLANNED,
            research_plan=parsed_plan,
            events=self.events + (event,),
        )

    def ensure_evidence_collection_allowed(self) -> None:
        if self.status is not ResearchCaseStatus.PLANNED:
            raise ValueError("recherche non planifiee")

    def attach_evidence_set(
        self,
        evidence_set: EvidenceSet,
        *,
        occurred_at: str,
    ) -> tuple["ResearchCase", EvidenceCollectionCompleted]:
        self.ensure_evidence_collection_allowed()
        if not isinstance(evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        if evidence_set.research_case_id != self.research_case_id:
            raise ValueError("evidence_set hors research_case")
        if evidence_set.sealed:
            raise ValueError("evidence_set deja scelle")
        event = EvidenceCollectionCompleted(
            research_case_id=self.research_case_id,
            evidence_set_id=evidence_set.evidence_set_id,
            evidence_count=len(evidence_set.evidence_refs),
            verified_claim_count=len(evidence_set.verified_claim_refs),
            occurred_at=occurred_at,
        )
        return (
            replace(
                self,
                status=ResearchCaseStatus.EVIDENCE_ASSEMBLED,
                evidence_set=evidence_set,
                events=self.events + (event,),
            ),
            event,
        )

    def seal_evidence_set(
        self,
        *,
        evidence_set_id: str,
        citation_resolver: object,
        occurred_at: str,
    ) -> tuple["ResearchCase", EvidenceSetSealed]:
        if self.status is not ResearchCaseStatus.EVIDENCE_ASSEMBLED:
            raise ValueError("evidence_set non assemblé")
        if self.evidence_set is None:
            raise ValueError("evidence_set absent")
        if self.evidence_set.evidence_set_id != evidence_set_id:
            raise ValueError("evidence_set_id incoherent")
        sealed_set, event = self.evidence_set.seal(
            citation_resolver=citation_resolver,
            occurred_at=occurred_at,
        )
        return (
            replace(
                self,
                status=ResearchCaseStatus.EVIDENCE_SET_SEALED,
                evidence_set=sealed_set,
                events=self.events + (event,),
            ),
            event,
        )

    def ensure_contradiction_assessment_allowed(self) -> None:
        if self.status is not ResearchCaseStatus.EVIDENCE_SET_SEALED:
            raise ValueError("evidence_set non scelle")
        if self.evidence_set is None or not self.evidence_set.sealed:
            raise ValueError("evidence_set non scelle")

    def record_contradiction_assessments(
        self,
        assessments: tuple[ContradictionAssessment, ...],
        *,
        occurred_at: str,
    ) -> tuple["ResearchCase", tuple[ContradictionDetected, ...]]:
        self.ensure_contradiction_assessment_allowed()
        parsed_assessments = ensure_assessments(assessments)
        if len(parsed_assessments) == 0:
            raise ValueError("contradiction_assessments absents")
        existing_ids = {
            assessment.contradiction_id for assessment in self.contradiction_assessments
        }
        for assessment in parsed_assessments:
            if assessment.contradiction_id in existing_ids:
                raise ValueError("contradiction_assessment deja enregistre")
        events = tuple(
            ContradictionDetected.from_assessment(
                research_case_id=self.research_case_id,
                assessment=assessment,
                occurred_at=occurred_at,
            )
            for assessment in parsed_assessments
        )
        return (
            replace(
                self,
                contradiction_assessments=self.contradiction_assessments + parsed_assessments,
                events=self.events + events,
            ),
            events,
        )

    def declare_insufficient_evidence(
        self,
        *,
        missing_obligations: tuple[str, ...],
        reason_codes: tuple[str, ...],
        occurred_at: str,
    ) -> tuple[
        "ResearchCase",
        tuple[KnowledgeGap, ...],
        tuple[KnowledgeGapRecorded | ResearchEvidenceFoundInsufficient, ...],
    ]:
        self.ensure_contradiction_assessment_allowed()
        parsed_missing = ensure_missing_obligations(missing_obligations)
        parsed_reasons = ensure_reason_codes(reason_codes)
        if len(parsed_missing) != len(parsed_reasons):
            raise ValueError("reason_codes incoherents")
        self._ensure_missing_obligations_in_plan(parsed_missing)
        gaps = tuple(
            KnowledgeGap.for_missing_obligation(
                research_case_id=self.research_case_id,
                affected_obligation=obligation,
                reason_code=reason_code,
            )
            for obligation, reason_code in zip(parsed_missing, parsed_reasons, strict=True)
        )
        gap_events = tuple(
            KnowledgeGapRecorded(
                research_case_id=self.research_case_id,
                gap_type=gap.gap_type,
                affected_obligation=gap.affected_obligation,
                reason_code=gap.reason_code,
                occurred_at=occurred_at,
            )
            for gap in gaps
        )
        terminal_event = ResearchEvidenceFoundInsufficient(
            research_case_id=self.research_case_id,
            missing_obligations=parsed_missing,
            reason_codes=parsed_reasons,
            occurred_at=occurred_at,
        )
        events = gap_events + (terminal_event,)
        return (
            replace(
                self,
                status=ResearchCaseStatus.INSUFFICIENT_EVIDENCE,
                knowledge_gaps=self.knowledge_gaps + gaps,
                events=self.events + events,
            ),
            gaps,
            events,
        )

    def declare_conflicting_evidence(
        self,
        *,
        contradiction_ids: tuple[str, ...],
        reason_codes: tuple[str, ...],
        occurred_at: str,
    ) -> tuple["ResearchCase", ResearchEvidenceFoundConflicting]:
        self.ensure_contradiction_assessment_allowed()
        parsed_ids = ensure_relation_ids(
            contradiction_ids,
            "contradiction_ids",
            allow_empty=False,
        )
        parsed_reasons = ensure_reason_codes(reason_codes)
        if len(parsed_ids) != len(parsed_reasons):
            raise ValueError("reason_codes incoherents")
        assessments_by_id = {
            assessment.contradiction_id: assessment
            for assessment in self.contradiction_assessments
        }
        for contradiction_id in parsed_ids:
            assessment = assessments_by_id.get(contradiction_id)
            if assessment is None:
                raise ValueError("contradiction non enregistree")
            if not assessment.blocks_publication:
                raise ValueError("contradiction non bloquante")
        event = ResearchEvidenceFoundConflicting(
            research_case_id=self.research_case_id,
            contradiction_ids=parsed_ids,
            reason_codes=parsed_reasons,
            occurred_at=occurred_at,
        )
        return (
            replace(
                self,
                status=ResearchCaseStatus.CONFLICTING_EVIDENCE,
                events=self.events + (event,),
            ),
            event,
        )

    def ensure_support_status_allowed(self, support_status: SupportStatus) -> None:
        parsed_status = ensure_support_status(support_status)
        if parsed_status is not SupportStatus.SUPPORTED:
            return
        if any(assessment.blocks_general_supported_status for assessment in self.contradiction_assessments):
            raise ValueError("support_status SUPPORTED interdit par contradiction documentaire")
        if len(self.knowledge_gaps) > 0:
            raise ValueError("support_status SUPPORTED interdit par lacune documentaire")

    def to_payload(self) -> dict[str, Any]:
        return {
            "research_case_id": self.research_case_id,
            "resolved_question": {
                "text": self.resolved_question.text,
                "question_hash": self.resolved_question.question_hash,
            },
            "research_mandate": self.research_mandate.to_payload(),
            "requested_mode": self.requested_mode.value,
            "status": self.status.value,
            "research_plan": None if self.research_plan is None else self.research_plan.to_payload(),
            "evidence_set": None if self.evidence_set is None else self.evidence_set.to_payload(),
            "contradiction_assessments": [
                assessment.to_payload() for assessment in self.contradiction_assessments
            ],
            "knowledge_gaps": [gap.to_payload() for gap in self.knowledge_gaps],
            "requested_by_context": self.requested_by_context,
            "opened_at": self.opened_at,
            "events": [event.to_payload() for event in self.events],
        }

    def _ensure_missing_obligations_in_plan(self, missing_obligations: tuple[str, ...]) -> None:
        if self.research_plan is None:
            raise ValueError("research_plan absent")
        planned_obligations = {
            obligation.name for obligation in self.research_plan.coverage_obligations
        }
        for obligation in missing_obligations:
            if obligation not in planned_obligations:
                raise ValueError(f"coverage_obligation inconnue: {obligation}")


def research_case_id_for(
    *,
    idempotency_key: str,
    resolved_question: ResolvedQuestion,
    research_mandate: ResearchMandate,
) -> str:
    seed = "|".join(
        (
            _ensure_text(idempotency_key, "idempotency_key"),
            _ensure_resolved_question(resolved_question).question_hash,
            _ensure_research_mandate(research_mandate).mandate_hash,
        )
    )
    return f"RSC-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:_HASH_HEX_LENGTH].upper()}"


def _ensure_resolved_question(value: object) -> ResolvedQuestion:
    if not isinstance(value, ResolvedQuestion):
        raise ValueError("resolved_question absent")
    return value


def _ensure_research_mandate(value: object) -> ResearchMandate:
    if not isinstance(value, ResearchMandate):
        raise ValueError("research_mandate absent")
    return value


def _ensure_research_mode(value: object) -> ResearchMode:
    if not isinstance(value, ResearchMode):
        raise ValueError("research_mode invalide")
    return value


def _ensure_research_plan(value: object) -> ResearchPlan:
    if not isinstance(value, ResearchPlan):
        raise ValueError("research_plan invalide")
    return value


def _ensure_events(
    value: object,
) -> tuple[
    ResearchCaseOpened
    | ResearchPlanCreated
    | EvidenceCollectionCompleted
    | EvidenceSetSealed
    | ContradictionDetected
    | KnowledgeGapRecorded
    | ResearchEvidenceFoundInsufficient
    | ResearchEvidenceFoundConflicting,
    ...,
]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(
            event,
            (
                ResearchCaseOpened,
                ResearchPlanCreated,
                EvidenceCollectionCompleted,
                EvidenceSetSealed,
                ContradictionDetected,
                KnowledgeGapRecorded,
                ResearchEvidenceFoundInsufficient,
                ResearchEvidenceFoundConflicting,
            ),
        ):
            raise ValueError("event research_case invalide")
    return events


def _ensure_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return value


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text(payload[field_name], field_name)


def _required_text_tuple(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text_tuple(payload[field_name], field_name)


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


def _ensure_coverage_obligations(value: object) -> tuple[CoverageObligation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("coverage_obligations invalides")
    obligations = tuple(value)
    if len(obligations) == 0:
        raise ValueError("coverage_obligations absentes")
    for obligation in obligations:
        if not isinstance(obligation, CoverageObligation):
            raise ValueError("coverage_obligation invalide")
    names = tuple(obligation.name for obligation in obligations)
    if len(names) != len(set(names)):
        raise ValueError("coverage_obligation dupliquee")
    return obligations


def _ensure_requesting_context(value: object) -> str:
    context = _ensure_text(value, "requested_by_context")
    if context not in _ALLOWED_REQUESTING_CONTEXTS:
        raise ValueError(f"requested_by_context inconnu: {context}")
    return context


def _ensure_research_case_id(value: object) -> str:
    text = _ensure_text(value, "research_case_id")
    if _RESEARCH_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("research_case_id invalide")
    return text


def _ensure_plan_id(value: object) -> str:
    text = _ensure_text(value, "plan_id")
    if _RESEARCH_PLAN_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("plan_id invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisee")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_sha256(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _sha256_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "text").encode("utf-8")).hexdigest()


def _hash_payload(payload: Mapping[str, Any]) -> str:
    serialized_payload = json.dumps(
        _json_ready(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    if isinstance(value, Enum):
        return value.value
    return value


__all__ = [
    "CoverageObligation",
    "ResearchCase",
    "ResearchCaseOpened",
    "ResearchCaseStatus",
    "ResearchMandate",
    "ResearchMode",
    "ResearchPlan",
    "ResearchPlanCreated",
    "ResolvedQuestion",
    "research_case_id_for",
]
