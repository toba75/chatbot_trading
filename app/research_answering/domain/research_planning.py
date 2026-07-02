"""Politique RA locale de planification de recherche documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.research_answering.domain.research_case import (
    CoverageObligation,
    DeepResearchPlan,
    ResearchCase,
    ResearchCaseStatus,
    ResearchMandate,
    ResearchMode,
    ResearchPlan,
    ResearchSubQuestion,
)


_M007_POLICY_VERSION = "research-planning-m007-documentary-simple-v1"
_M007_OBLIGATIONS = (
    CoverageObligation(
        name="question_autonome",
        description="Valider que la question RA est autonome et stable.",
    ),
    CoverageObligation(
        name="mandat_documentaire",
        description="Respecter le ResearchMandate explicite sans mode implicite.",
    ),
    CoverageObligation(
        name="preuves_documentaires",
        description="Préparer la collecte via les ports KA et EG publiés, sans stockage interne direct.",
    ),
)
_M009_POLICY_VERSION = "deep-research-planning-m009-v1"
_M009_REQUIRED_COVERAGE_NAMES = (
    "methodes",
    "preuves_favorables",
    "preuves_defavorables",
    "dependances",
    "limites",
    "zones_non_documentees",
)
_M009_OBLIGATIONS = (
    CoverageObligation(
        name="methodes",
        description="Comparer les méthodes déclarées dans le mandat.",
    ),
    CoverageObligation(
        name="preuves_favorables",
        description="Chercher les preuves favorables autorisées par le mandat.",
    ),
    CoverageObligation(
        name="preuves_defavorables",
        description="Chercher les preuves défavorables autorisées par le mandat.",
    ),
    CoverageObligation(
        name="dependances",
        description="Identifier les dépendances et répétitions documentaires.",
    ),
    CoverageObligation(
        name="limites",
        description="Nommer les limites et conditions de portée.",
    ),
    CoverageObligation(
        name="zones_non_documentees",
        description="Nommer les lacunes et zones non documentées.",
    ),
)
_M009_SUB_QUESTIONS = (
    ResearchSubQuestion(
        sub_question_id="RSQ-METHODES",
        text="Quelles méthodes du mandat comparent Kelly et volatility targeting ?",
        coverage_obligation_names=("methodes", "dependances"),
        mandate_terms=("methodes", "Kelly", "volatility targeting"),
    ),
    ResearchSubQuestion(
        sub_question_id="RSQ-PREUVES-FAVORABLES",
        text="Quelles preuves favorables documentent Kelly et volatility targeting ?",
        coverage_obligation_names=("preuves_favorables",),
        mandate_terms=("preuves favorables", "Kelly", "volatility targeting"),
    ),
    ResearchSubQuestion(
        sub_question_id="RSQ-PREUVES-DEFAVORABLES",
        text="Quelles preuves défavorables documentent Kelly et volatility targeting ?",
        coverage_obligation_names=("preuves_defavorables",),
        mandate_terms=("preuves defavorables", "Kelly", "volatility targeting"),
    ),
    ResearchSubQuestion(
        sub_question_id="RSQ-LIMITES-LACUNES",
        text="Quelles limites et zones non documentées bornent la synthèse ?",
        coverage_obligation_names=("limites", "zones_non_documentees"),
        mandate_terms=("limites", "zones non documentees", "synthese approfondie multi-sources"),
    ),
)


class ResearchPlanningPolicy(Protocol):
    """Port de politique de planification RA."""

    def plan_for(self, research_case: ResearchCase) -> ResearchPlan:
        """Retourne un plan local pour le cas de recherche."""


@dataclass(frozen=True)
class LocalDeterministicResearchPlanningPolicy:
    """Planificateur local déterministe limité à M-007."""

    policy_version: str
    documentary_simple_obligations: tuple[CoverageObligation, ...]

    @classmethod
    def for_m007_documentary_simple(cls) -> "LocalDeterministicResearchPlanningPolicy":
        return cls(
            policy_version=_M007_POLICY_VERSION,
            documentary_simple_obligations=_M007_OBLIGATIONS,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or self.policy_version.strip() == "":
            raise ValueError("policy_version vide")
        if self.policy_version != self.policy_version.strip():
            raise ValueError("policy_version non normalisee")
        obligations = self.documentary_simple_obligations
        if not isinstance(obligations, tuple) or len(obligations) == 0:
            raise ValueError("coverage_obligations absentes")
        for obligation in obligations:
            if not isinstance(obligation, CoverageObligation):
                raise ValueError("coverage_obligation invalide")

    def plan_for(self, research_case: ResearchCase) -> ResearchPlan:
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if research_case.status is not ResearchCaseStatus.CREATED:
            raise ValueError("research_case deja planifie")
        if research_case.requested_mode is not ResearchMode.DOCUMENTARY_SIMPLE:
            raise ValueError("research_mode non supporte par politique")
        return ResearchPlan(
            plan_id=_plan_id_for(research_case.research_case_id),
            mode=research_case.requested_mode,
            coverage_obligations=self.documentary_simple_obligations,
            policy_version=self.policy_version,
        )


@dataclass(frozen=True)
class DeepResearchPlanningPolicy:
    """Planificateur déterministe de recherche approfondie M-009."""

    policy_version: str
    coverage_obligations: tuple[CoverageObligation, ...]
    sub_questions: tuple[ResearchSubQuestion, ...]

    @classmethod
    def for_m009_deep_research(cls) -> "DeepResearchPlanningPolicy":
        return cls(
            policy_version=_M009_POLICY_VERSION,
            coverage_obligations=_M009_OBLIGATIONS,
            sub_questions=_M009_SUB_QUESTIONS,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _ensure_policy_version(self.policy_version))
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_policy_obligations(self.coverage_obligations),
        )
        object.__setattr__(
            self,
            "sub_questions",
            _ensure_policy_sub_questions(self.sub_questions),
        )

    def plan_for(self, research_case: ResearchCase) -> DeepResearchPlan:
        if not isinstance(research_case, ResearchCase):
            raise ValueError("research_case invalide")
        if research_case.status is not ResearchCaseStatus.CREATED:
            raise ValueError("research_case deja planifie")
        if research_case.requested_mode is not ResearchMode.DEEP_RESEARCH:
            raise ValueError("research_mode approfondi requis")
        _ensure_obligation_contract(self.coverage_obligations)
        _ensure_sub_questions_in_mandate(
            research_mandate=research_case.research_mandate,
            sub_questions=self.sub_questions,
        )
        return DeepResearchPlan(
            plan_id=_plan_id_for(research_case.research_case_id),
            mode=research_case.requested_mode,
            coverage_obligations=self.coverage_obligations,
            policy_version=self.policy_version,
            sub_questions=self.sub_questions,
        )


def _plan_id_for(research_case_id: str) -> str:
    return f"RPLAN-{research_case_id.removeprefix('RSC-')}"


def _ensure_policy_version(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("policy_version non textuelle")
    if value.strip() == "":
        raise ValueError("policy_version vide")
    if value != value.strip():
        raise ValueError("policy_version non normalisee")
    return value


def _ensure_policy_obligations(value: object) -> tuple[CoverageObligation, ...]:
    if not isinstance(value, tuple) or len(value) == 0:
        raise ValueError("coverage_obligations absentes")
    for obligation in value:
        if not isinstance(obligation, CoverageObligation):
            raise ValueError("coverage_obligation invalide")
    names = tuple(obligation.name for obligation in value)
    if len(names) != len(set(names)):
        raise ValueError("coverage_obligation dupliquee")
    return value


def _ensure_policy_sub_questions(value: object) -> tuple[ResearchSubQuestion, ...]:
    if not isinstance(value, tuple) or len(value) == 0:
        raise ValueError("research_sub_questions absentes")
    for sub_question in value:
        if not isinstance(sub_question, ResearchSubQuestion):
            raise ValueError("research_sub_question invalide")
    ids = tuple(sub_question.sub_question_id for sub_question in value)
    if len(ids) != len(set(ids)):
        raise ValueError("research_sub_question dupliquee")
    return value


def _ensure_obligation_contract(coverage_obligations: tuple[CoverageObligation, ...]) -> None:
    names = tuple(obligation.name for obligation in coverage_obligations)
    for required_name in _M009_REQUIRED_COVERAGE_NAMES:
        if required_name not in names:
            raise ValueError(f"coverage_obligation obligatoire absente: {required_name}")
    if names != _M009_REQUIRED_COVERAGE_NAMES:
        raise ValueError("coverage_obligations non deterministes")


def _ensure_sub_questions_in_mandate(
    *,
    research_mandate: ResearchMandate,
    sub_questions: tuple[ResearchSubQuestion, ...],
) -> None:
    mandate_values = (
        research_mandate.allowed_universe
        + research_mandate.data_requirements
        + research_mandate.exclusions
        + (
            research_mandate.horizon,
            research_mandate.language,
            research_mandate.detail_level,
        )
    )
    mandate_text = "\n".join(mandate_values).casefold()
    for sub_question in sub_questions:
        for mandate_term in sub_question.mandate_terms:
            if mandate_term.casefold() not in mandate_text:
                raise ValueError(f"mandate_term hors mandat: {mandate_term}")


__all__ = [
    "DeepResearchPlanningPolicy",
    "LocalDeterministicResearchPlanningPolicy",
    "ResearchPlanningPolicy",
]
