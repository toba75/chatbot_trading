"""Politique RA locale de planification de recherche documentaire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.research_answering.domain.research_case import (
    CoverageObligation,
    ResearchCase,
    ResearchCaseStatus,
    ResearchMode,
    ResearchPlan,
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


def _plan_id_for(research_case_id: str) -> str:
    return f"RPLAN-{research_case_id.removeprefix('RSC-')}"


__all__ = ["LocalDeterministicResearchPlanningPolicy", "ResearchPlanningPolicy"]
