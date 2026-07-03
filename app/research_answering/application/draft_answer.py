"""Cas d'usage RA de brouillon et extraction d'assertions de réponse."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.research_answering.domain.answer import (
    Answer,
    AnswerAssertion,
    AnswerAssertionCandidate,
    AnswerAssertionsExtracted,
    AnswerDraft,
    AnswerDrafted,
    DeepResearchReport,
    DeepResearchReportSection,
    DeepResearchReportSectionName,
    answer_id_for,
)
from app.research_answering.application.verify_answer import (
    EvaluateAnswerSupport,
    EvaluateAnswerSupportHandler,
)
from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.domain.evidence_set import EvidenceSet
from app.research_answering.domain.research_case import ResearchCase
from app.research_answering.domain.research_case import DeepResearchPlan
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_case import ResearchMode


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ResearchCaseRepository(Protocol):
    """Port RA de lecture du ResearchCase."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne le cas de recherche existant."""


class AnswerRepository(Protocol):
    """Port RA de persistance d'Answer."""

    def save(self, answer: Answer) -> Answer:
        """Persiste un Answer nouveau."""

    def update(self, answer: Answer) -> Answer:
        """Remplace un Answer par sa nouvelle version métier."""

    def answer_for_id(self, answer_id: str) -> Answer:
        """Retourne un Answer existant."""


class AnswerGenerator(Protocol):
    """Port RA de génération de brouillon sans autorité de support."""

    def draft(self, request: "DraftAnswerRequest") -> object:
        """Produit un brouillon structuré."""


class DeepSynthesisGenerator(Protocol):
    """Port RA de génération de synthèse approfondie sans autorité de support."""

    def draft(self, request: "DeepSynthesisDraftRequest") -> object:
        """Produit une proposition de synthèse multi-sources."""


class AnswerAssertionExtractor(Protocol):
    """Port RA d'extraction des assertions importantes."""

    @property
    def extractor_version(self) -> str:
        """Version explicite de l'extracteur."""

    def extract(self, draft: AnswerDraft) -> Sequence[AnswerAssertionCandidate]:
        """Retourne les assertions candidates extraites."""


@dataclass(frozen=True)
class GeneratedAnswerDraft:
    """Sortie autorisée du port AnswerGenerator."""

    content: str
    model_provenance: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _ensure_text(self.content, "answer_draft"))
        object.__setattr__(
            self,
            "model_provenance",
            _ensure_text(self.model_provenance, "model_provenance"),
        )


@dataclass(frozen=True)
class GeneratedDeepResearchDraft:
    """Sortie autorisée du port de synthèse RA approfondie."""

    sections: Mapping[str, str]
    assertion_lines: Sequence[str]
    section_citation_ids: Mapping[str, Sequence[str]]
    model_provenance: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", _ensure_deep_section_texts(self.sections))
        object.__setattr__(
            self,
            "assertion_lines",
            _ensure_text_sequence(self.assertion_lines, "assertion_lines", allow_empty=False),
        )
        object.__setattr__(
            self,
            "section_citation_ids",
            _ensure_deep_section_citation_ids(self.section_citation_ids),
        )
        object.__setattr__(
            self,
            "model_provenance",
            _ensure_text(self.model_provenance, "model_provenance"),
        )

    @property
    def answer_draft_content(self) -> str:
        return "\n".join(self.assertion_lines)


@dataclass(frozen=True)
class DraftAnswerRequest:
    """Requête transmise au générateur via port RA."""

    research_case_id: str
    resolved_question: str
    evidence_set_id: str
    evidence_set_version: int
    verified_claim_count: int
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "resolved_question",
            _ensure_text(self.resolved_question, "resolved_question"),
        )
        object.__setattr__(
            self,
            "evidence_set_id",
            _ensure_prefixed_text(self.evidence_set_id, "evidence_set_id", "EVS-"),
        )
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        object.__setattr__(
            self,
            "verified_claim_count",
            _ensure_positive_integer(self.verified_claim_count, "verified_claim_count"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DeepSynthesisDraftRequest:
    """Requête transmise au générateur de synthèse approfondie."""

    research_case_id: str
    resolved_question: str
    research_mandate: Mapping[str, Any]
    research_plan: DeepResearchPlan
    evidence_set_id: str
    evidence_set_version: int
    verified_claim_refs: Sequence[object]
    citations: Sequence[object]
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "research_case_id",
            _ensure_prefixed_text(self.research_case_id, "research_case_id", "RSC-"),
        )
        object.__setattr__(
            self,
            "resolved_question",
            _ensure_text(self.resolved_question, "resolved_question"),
        )
        if not isinstance(self.research_mandate, Mapping) or len(self.research_mandate) == 0:
            raise ValueError("research_mandate invalide")
        object.__setattr__(self, "research_mandate", dict(self.research_mandate))
        if not isinstance(self.research_plan, DeepResearchPlan):
            raise ValueError("deep_research_plan absent")
        object.__setattr__(
            self,
            "evidence_set_id",
            _ensure_prefixed_text(self.evidence_set_id, "evidence_set_id", "EVS-"),
        )
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        object.__setattr__(
            self,
            "verified_claim_refs",
            _ensure_object_sequence(self.verified_claim_refs, "verified_claim_refs"),
        )
        object.__setattr__(
            self,
            "citations",
            _ensure_object_sequence(self.citations, "citations"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DraftAnswer:
    """Commande RA de génération d'un brouillon Answer."""

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
class ExtractAnswerAssertions:
    """Commande RA d'extraction des assertions importantes."""

    answer_id: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "answer_id",
            _ensure_prefixed_text(self.answer_id, "answer_id", "ANS-"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ProduceMultiSourceSynthesis:
    """Commande RA M-009 de production d'une synthèse multi-sources."""

    research_case_id: str
    evidence_set_id: str
    synthesis_policy_version: str
    support_policy_version: str
    citation_policy_version: str
    freshness_policy_version: str
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
        object.__setattr__(
            self,
            "synthesis_policy_version",
            _ensure_text(self.synthesis_policy_version, "synthesis_policy_version"),
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
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class DraftAnswerResult:
    """Résultat observable de génération du brouillon."""

    status: str
    answer: Answer
    events: Sequence[AnswerDrafted]

    def __post_init__(self) -> None:
        if self.status != "ANSWER_DRAFTED":
            raise ValueError("status DraftAnswer invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        object.__setattr__(self, "events", _ensure_draft_events(self.events))


@dataclass(frozen=True)
class ExtractAnswerAssertionsResult:
    """Résultat observable d'extraction des assertions."""

    status: str
    answer: Answer
    assertions: Sequence[AnswerAssertion]
    events: Sequence[AnswerAssertionsExtracted]

    def __post_init__(self) -> None:
        if self.status != "ANSWER_ASSERTIONS_EXTRACTED":
            raise ValueError("status ExtractAnswerAssertions invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        object.__setattr__(self, "assertions", _ensure_answer_assertions(self.assertions))
        object.__setattr__(self, "events", _ensure_extraction_events(self.events))


@dataclass(frozen=True)
class ProduceMultiSourceSynthesisResult:
    """Résultat observable de publication d'une synthèse approfondie."""

    status: str
    answer: Answer
    deep_research_report: DeepResearchReport
    verified_research_outcome: VerifiedResearchOutcome
    events: Sequence[object]

    def __post_init__(self) -> None:
        if self.status != "MULTI_SOURCE_SYNTHESIS_PUBLISHED":
            raise ValueError("status ProduceMultiSourceSynthesis invalide")
        if not isinstance(self.answer, Answer):
            raise ValueError("answer invalide")
        if not isinstance(self.deep_research_report, DeepResearchReport):
            raise ValueError("deep_research_report invalide")
        if not isinstance(self.verified_research_outcome, VerifiedResearchOutcome):
            raise ValueError("verified_research_outcome invalide")
        object.__setattr__(self, "events", _ensure_object_sequence(self.events, "events"))


@dataclass(frozen=True)
class ProduceMultiSourceSynthesisFailedResult:
    """Résultat explicite d'échec du générateur de synthèse."""

    status: str
    failure_reason_code: str
    failure_detail: str
    research_case: ResearchCase
    research_plan: DeepResearchPlan
    evidence_set: EvidenceSet

    def __post_init__(self) -> None:
        if self.status != "SYNTHESIS_DRAFT_FAILED":
            raise ValueError("status ProduceMultiSourceSynthesisFailed invalide")
        object.__setattr__(
            self,
            "failure_reason_code",
            _ensure_text(self.failure_reason_code, "failure_reason_code"),
        )
        if self.failure_reason_code != "DEEP_RESEARCH_DRAFT_GENERATION_FAILED":
            raise ValueError("failure_reason_code synthese invalide")
        object.__setattr__(self, "failure_detail", _ensure_text(self.failure_detail, "failure_detail"))
        if not isinstance(self.research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if not isinstance(self.research_plan, DeepResearchPlan):
            raise ValueError("deep_research_plan absent")
        if not isinstance(self.evidence_set, EvidenceSet) or not self.evidence_set.sealed:
            raise ValueError("evidence_set scelle absent")


@dataclass(frozen=True)
class DraftAnswerHandler:
    """Orchestre ResearchCase scellé, générateur et AnswerRepository."""

    research_case_repository: ResearchCaseRepository
    answer_repository: AnswerRepository
    answer_generator: AnswerGenerator

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.answer_repository, "save", None)):
            raise ValueError("answer_repository sans save")
        if not callable(getattr(self.answer_generator, "draft", None)):
            raise ValueError("answer_generator sans draft")

    def draft(self, command: DraftAnswer) -> DraftAnswerResult:
        parsed_command = _ensure_draft_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if research_case.evidence_set is None or not research_case.evidence_set.sealed:
            raise ValueError("evidence_set non scelle")
        if research_case.evidence_set.evidence_set_id != parsed_command.evidence_set_id:
            raise ValueError("evidence_set_id incoherent")
        request = DraftAnswerRequest(
            research_case_id=research_case.research_case_id,
            resolved_question=research_case.resolved_question.text,
            evidence_set_id=research_case.evidence_set.evidence_set_id,
            evidence_set_version=research_case.evidence_set.version.value,
            verified_claim_count=len(research_case.evidence_set.verified_claim_refs),
            occurred_at=parsed_command.occurred_at,
        )
        generated = _ensure_generated_draft(self.answer_generator.draft(request))
        draft = AnswerDraft(
            draft_version=1,
            content=generated.content,
            model_provenance=generated.model_provenance,
        )
        answer = Answer.create_draft(
            answer_id=answer_id_for(
                research_case_id=research_case.research_case_id,
                evidence_set_id=research_case.evidence_set.evidence_set_id,
                draft_hash=draft.draft_hash,
            ),
            research_case_id=research_case.research_case_id,
            evidence_set_id=research_case.evidence_set.evidence_set_id,
            evidence_set_version=research_case.evidence_set.version.value,
            draft=draft,
            occurred_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.save(answer)
        return DraftAnswerResult(
            status="ANSWER_DRAFTED",
            answer=saved_answer,
            events=(saved_answer.events[-1],),
        )


@dataclass(frozen=True)
class ExtractAnswerAssertionsHandler:
    """Orchestre extraction d'assertions et transition de l'Answer."""

    answer_repository: AnswerRepository
    answer_assertion_extractor: AnswerAssertionExtractor

    def __post_init__(self) -> None:
        if not callable(getattr(self.answer_repository, "answer_for_id", None)):
            raise ValueError("answer_repository sans answer_for_id")
        if not callable(getattr(self.answer_repository, "update", None)):
            raise ValueError("answer_repository sans update")
        if not callable(getattr(self.answer_assertion_extractor, "extract", None)):
            raise ValueError("answer_assertion_extractor sans extract")
        _ensure_text(
            getattr(self.answer_assertion_extractor, "extractor_version", None),
            "extractor_version",
        )

    def extract(self, command: ExtractAnswerAssertions) -> ExtractAnswerAssertionsResult:
        parsed_command = _ensure_extract_command(command)
        answer = self.answer_repository.answer_for_id(parsed_command.answer_id)
        if not isinstance(answer, Answer):
            raise ValueError("answer invalide")
        candidates = _ensure_assertion_candidates(
            self.answer_assertion_extractor.extract(answer.draft)
        )
        updated_answer, event = answer.extract_assertions(
            assertions=candidates,
            extractor_version=self.answer_assertion_extractor.extractor_version,
            occurred_at=parsed_command.occurred_at,
        )
        saved_answer = self.answer_repository.update(updated_answer)
        return ExtractAnswerAssertionsResult(
            status="ANSWER_ASSERTIONS_EXTRACTED",
            answer=saved_answer,
            assertions=saved_answer.assertions,
            events=(event,),
        )


@dataclass(frozen=True)
class ProduceMultiSourceSynthesisHandler:
    """Orchestre une synthèse RA approfondie sans fallback vers réponse simple."""

    research_case_repository: ResearchCaseRepository
    answer_repository: AnswerRepository
    deep_synthesis_generator: DeepSynthesisGenerator
    answer_assertion_extractor: AnswerAssertionExtractor
    citation_resolver: object

    def __post_init__(self) -> None:
        if not callable(getattr(self.research_case_repository, "case_for_id", None)):
            raise ValueError("research_case_repository sans case_for_id")
        if not callable(getattr(self.research_case_repository, "update", None)):
            raise ValueError("research_case_repository sans update")
        if not callable(getattr(self.answer_repository, "save", None)):
            raise ValueError("answer_repository sans save")
        if not callable(getattr(self.answer_repository, "update", None)):
            raise ValueError("answer_repository sans update")
        if not callable(getattr(self.answer_repository, "answer_for_id", None)):
            raise ValueError("answer_repository sans answer_for_id")
        if not callable(getattr(self.deep_synthesis_generator, "draft", None)):
            raise ValueError("deep_synthesis_generator sans draft")
        if not callable(getattr(self.answer_assertion_extractor, "extract", None)):
            raise ValueError("answer_assertion_extractor sans extract")
        _ensure_text(
            getattr(self.answer_assertion_extractor, "extractor_version", None),
            "extractor_version",
        )
        if not callable(getattr(self.citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")

    def produce(
        self,
        command: ProduceMultiSourceSynthesis,
    ) -> ProduceMultiSourceSynthesisResult | ProduceMultiSourceSynthesisFailedResult:
        parsed_command = _ensure_produce_multi_source_command(command)
        research_case = self.research_case_repository.case_for_id(parsed_command.research_case_id)
        research_case = _ensure_deep_synthesis_case(
            research_case=research_case,
            evidence_set_id=parsed_command.evidence_set_id,
        )
        evidence_set = research_case.evidence_set
        if evidence_set is None:
            raise ValueError("evidence_set absent")
        plan = research_case.research_plan
        if not isinstance(plan, DeepResearchPlan):
            raise ValueError("deep_research_plan absent")
        request = DeepSynthesisDraftRequest(
            research_case_id=research_case.research_case_id,
            resolved_question=research_case.resolved_question.text,
            research_mandate=research_case.research_mandate.to_payload(),
            research_plan=plan,
            evidence_set_id=evidence_set.evidence_set_id,
            evidence_set_version=evidence_set.version.value,
            verified_claim_refs=evidence_set.verified_claim_refs,
            citations=evidence_set.citations,
            occurred_at=parsed_command.occurred_at,
        )
        try:
            generated = _ensure_generated_deep_draft(self.deep_synthesis_generator.draft(request))
        except Exception as exc:
            return ProduceMultiSourceSynthesisFailedResult(
                status="SYNTHESIS_DRAFT_FAILED",
                failure_reason_code="DEEP_RESEARCH_DRAFT_GENERATION_FAILED",
                failure_detail=_failure_detail_for(exc),
                research_case=research_case,
                research_plan=plan,
                evidence_set=evidence_set,
            )

        draft = AnswerDraft(
            draft_version=1,
            content=generated.answer_draft_content,
            model_provenance=generated.model_provenance,
        )
        answer = Answer.create_draft(
            answer_id=answer_id_for(
                research_case_id=research_case.research_case_id,
                evidence_set_id=evidence_set.evidence_set_id,
                draft_hash=draft.draft_hash,
            ),
            research_case_id=research_case.research_case_id,
            evidence_set_id=evidence_set.evidence_set_id,
            evidence_set_version=evidence_set.version.value,
            draft=draft,
            occurred_at=parsed_command.occurred_at,
        )
        try:
            candidates = _ensure_assertion_candidates(
                self.answer_assertion_extractor.extract(answer.draft)
            )
            extracted_answer, extraction_event = answer.extract_assertions(
                assertions=candidates,
                extractor_version=self.answer_assertion_extractor.extractor_version,
                occurred_at=parsed_command.occurred_at,
            )
        except Exception as exc:
            raise ValueError("DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED") from exc
        saved_answer = self.answer_repository.save(extracted_answer)
        evaluated = EvaluateAnswerSupportHandler(
            research_case_repository=self.research_case_repository,
            answer_repository=self.answer_repository,
            citation_resolver=self.citation_resolver,
        ).evaluate(
            EvaluateAnswerSupport(
                research_case_id=research_case.research_case_id,
                answer_id=saved_answer.answer_id,
                support_policy_version=parsed_command.support_policy_version,
                citation_policy_version=parsed_command.citation_policy_version,
                freshness_policy_version=parsed_command.freshness_policy_version,
                occurred_at=parsed_command.occurred_at,
            )
        )
        report = DeepResearchReport(
            answer_id=evaluated.answer.answer_id,
            research_case_id=evaluated.answer.research_case_id,
            evidence_set_id=evaluated.answer.evidence_set_id,
            evidence_set_version=evaluated.answer.evidence_set_version,
            evidence_hash=evidence_set.evidence_hash,
            support_status=evaluated.support_status,
            sections=_sections_from_generated(generated),
            final_assertions=evaluated.answer.assertions,
            final_assertion_decisions=evaluated.verified_answer_version.assertion_decisions,
            citations=evidence_set.citations,
            claim_refs=evidence_set.verified_claim_refs,
            policy_version=parsed_command.synthesis_policy_version,
            published_at=parsed_command.occurred_at,
        )
        return ProduceMultiSourceSynthesisResult(
            status="MULTI_SOURCE_SYNTHESIS_PUBLISHED",
            answer=evaluated.answer,
            deep_research_report=report,
            verified_research_outcome=evaluated.verified_research_outcome,
            events=(saved_answer.events[0], extraction_event) + tuple(evaluated.events),
        )


def _ensure_generated_deep_draft(value: object) -> GeneratedDeepResearchDraft:
    for forbidden_field in (
        "support_status",
        "final_status",
        "answer_status",
        "strategy_parameter",
        "strategy_parameters",
        "candidate_strategy",
        "kelly_fraction",
        "volatility_target",
        "rebalance_rule",
    ):
        if hasattr(value, forbidden_field):
            if "strategy" in forbidden_field or forbidden_field in {
                "kelly_fraction",
                "volatility_target",
                "rebalance_rule",
            }:
                raise ValueError("parametre de strategie interdit")
            raise ValueError("support_status fourni par le generateur")
    if isinstance(value, GeneratedDeepResearchDraft):
        return value
    return GeneratedDeepResearchDraft(
        sections=getattr(value, "sections", None),
        assertion_lines=getattr(value, "assertion_lines", None),
        section_citation_ids=getattr(value, "section_citation_ids", None),
        model_provenance=getattr(value, "model_provenance", None),
    )


def _ensure_produce_multi_source_command(value: object) -> ProduceMultiSourceSynthesis:
    if not isinstance(value, ProduceMultiSourceSynthesis):
        raise ValueError("commande ProduceMultiSourceSynthesis invalide")
    return value


def _ensure_deep_synthesis_case(
    *,
    research_case: object,
    evidence_set_id: str,
) -> ResearchCase:
    if not isinstance(research_case, ResearchCase):
        raise ValueError("research_case invalide")
    if research_case.requested_mode is not ResearchMode.DEEP_RESEARCH:
        raise ValueError("research_mode approfondi requis")
    if not isinstance(research_case.research_plan, DeepResearchPlan):
        raise ValueError("deep_research_plan absent")
    if research_case.status is not ResearchCaseStatus.EVIDENCE_SET_SEALED:
        raise ValueError("evidence_set non scelle")
    if research_case.evidence_set is None or not research_case.evidence_set.sealed:
        raise ValueError("evidence_set non scelle")
    if research_case.evidence_set.evidence_set_id != evidence_set_id:
        raise ValueError("evidence_set_id incoherent")
    research_case.ensure_deep_collection_trace_recorded(evidence_set_id=evidence_set_id)
    research_case.ensure_claim_dependencies_resolved(evidence_set_id=evidence_set_id)
    return research_case


def _sections_from_generated(generated: GeneratedDeepResearchDraft) -> tuple[DeepResearchReportSection, ...]:
    return tuple(
        DeepResearchReportSection(
            section_name=section_name,
            content=generated.sections[section_name.value],
            citation_ids=generated.section_citation_ids[section_name.value],
        )
        for section_name in DeepResearchReportSectionName
    )


def _ensure_generated_draft(value: object) -> GeneratedAnswerDraft:
    for forbidden_field in ("support_status", "final_status", "answer_status"):
        if hasattr(value, forbidden_field):
            raise ValueError("support_status fourni par le generateur")
    if isinstance(value, GeneratedAnswerDraft):
        return value
    return GeneratedAnswerDraft(
        content=getattr(value, "content", None),
        model_provenance=getattr(value, "model_provenance", None),
    )


def _ensure_draft_command(value: object) -> DraftAnswer:
    if not isinstance(value, DraftAnswer):
        raise ValueError("commande DraftAnswer invalide")
    return value


def _ensure_extract_command(value: object) -> ExtractAnswerAssertions:
    if not isinstance(value, ExtractAnswerAssertions):
        raise ValueError("commande ExtractAnswerAssertions invalide")
    return value


def _ensure_assertion_candidates(value: object) -> tuple[AnswerAssertionCandidate, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertion_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("answer_assertion_candidates absentes")
    for candidate in candidates:
        if not isinstance(candidate, AnswerAssertionCandidate):
            raise ValueError("answer_assertion_candidate invalide")
    return candidates


def _ensure_answer_assertions(value: object) -> tuple[AnswerAssertion, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertions invalides")
    assertions = tuple(value)
    if len(assertions) == 0:
        raise ValueError("answer_assertions absentes")
    for assertion in assertions:
        if not isinstance(assertion, AnswerAssertion):
            raise ValueError("answer_assertion invalide")
    return assertions


def _ensure_draft_events(value: object) -> tuple[AnswerDrafted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1 or not isinstance(events[0], AnswerDrafted):
        raise ValueError("event AnswerDrafted absent")
    return events


def _ensure_extraction_events(value: object) -> tuple[AnswerAssertionsExtracted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) != 1 or not isinstance(events[0], AnswerAssertionsExtracted):
        raise ValueError("event AnswerAssertionsExtracted absent")
    return events


def _ensure_deep_section_texts(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("deep_report_sections invalides")
    expected_keys = {section_name.value for section_name in DeepResearchReportSectionName}
    actual_keys = {str(key) for key in value}
    missing_keys = expected_keys.difference(actual_keys)
    if len(missing_keys) > 0:
        raise ValueError(f"section obligatoire absente: {sorted(missing_keys)[0]}")
    extra_keys = actual_keys.difference(expected_keys)
    if len(extra_keys) > 0:
        raise ValueError(f"deep_report_section inattendue: {sorted(extra_keys)[0]}")
    return {
        section_name.value: _ensure_text(value[section_name.value], "deep_report_section")
        for section_name in DeepResearchReportSectionName
    }


def _ensure_deep_section_citation_ids(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise ValueError("section_citation_ids invalides")
    expected_keys = {section_name.value for section_name in DeepResearchReportSectionName}
    actual_keys = {str(key) for key in value}
    missing_keys = expected_keys.difference(actual_keys)
    if len(missing_keys) > 0:
        raise ValueError(f"section_citation_ids absents: {sorted(missing_keys)[0]}")
    extra_keys = actual_keys.difference(expected_keys)
    if len(extra_keys) > 0:
        raise ValueError(f"section_citation_ids inattendus: {sorted(extra_keys)[0]}")
    return {
        section_name.value: _ensure_text_sequence(
            value[section_name.value],
            "section_citation_ids",
            allow_empty=False,
        )
        for section_name in DeepResearchReportSectionName
    }


def _ensure_text_sequence(value: object, field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if not allow_empty and len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


def _ensure_object_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    return parsed


def _failure_detail_for(exc: Exception) -> str:
    return "DEEP_RESEARCH_DRAFT_GENERATION_FAILED"


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
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "AnswerAssertionExtractor",
    "AnswerGenerator",
    "AnswerRepository",
    "DeepSynthesisDraftRequest",
    "DeepSynthesisGenerator",
    "DraftAnswer",
    "DraftAnswerHandler",
    "DraftAnswerRequest",
    "DraftAnswerResult",
    "ExtractAnswerAssertions",
    "ExtractAnswerAssertionsHandler",
    "ExtractAnswerAssertionsResult",
    "GeneratedAnswerDraft",
    "GeneratedDeepResearchDraft",
    "ProduceMultiSourceSynthesis",
    "ProduceMultiSourceSynthesisFailedResult",
    "ProduceMultiSourceSynthesisHandler",
    "ProduceMultiSourceSynthesisResult",
    "ResearchCaseRepository",
]
