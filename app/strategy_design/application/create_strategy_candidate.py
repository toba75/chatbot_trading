"""Cas d'usage SD d'ouverture de stratégie candidate depuis RA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.contracts.identity import DomainIdentifier
from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.strategy_design.domain.strategy_candidate import StrategyCandidate


class VerifiedResearchReader(Protocol):
    def read_verified_research(
        self,
        research_case_id: str,
        answer_id: str,
    ) -> VerifiedResearchOutcome:
        raise NotImplementedError


class ResearchOutcomeTranslator(Protocol):
    def translate(self, outcome: VerifiedResearchOutcome) -> Sequence[object]:
        raise NotImplementedError


class StrategyCandidateRepository(Protocol):
    def save_new(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class CreateStrategyCandidateCommand:
    strategy_id: str
    research_case_id: str
    answer_id: str
    expected_version: int

    def __post_init__(self) -> None:
        _ensure_identifier(self.strategy_id, "STRAT", "strategy_id")
        _ensure_identifier(self.research_case_id, "RSC", "research_case_id")
        _ensure_identifier(self.answer_id, "ANS", "answer_id")
        if not isinstance(self.expected_version, int) or isinstance(self.expected_version, bool):
            raise ValueError("expected_version non entier")
        if self.expected_version < 0:
            raise ValueError("expected_version négatif")


class CreateStrategyCandidateHandler:
    def __init__(
        self,
        *,
        verified_research_reader: VerifiedResearchReader,
        translator: ResearchOutcomeTranslator,
        repository: StrategyCandidateRepository,
    ) -> None:
        self._verified_research_reader = verified_research_reader
        self._translator = translator
        self._repository = repository

    def handle(self, command: CreateStrategyCandidateCommand) -> StrategyCandidate:
        if not isinstance(command, CreateStrategyCandidateCommand):
            raise ValueError("CreateStrategyCandidateCommand attendu")

        outcome = self._verified_research_reader.read_verified_research(
            command.research_case_id,
            command.answer_id,
        )
        if not isinstance(outcome, VerifiedResearchOutcome):
            raise ValueError("VerifiedResearchOutcome attendu")
        if outcome.research_case_id != command.research_case_id:
            raise ValueError("research_case_id lu incohérent")
        if outcome.answer_id != command.answer_id:
            raise ValueError("answer_id lu incohérent")

        translation_decisions = self._translator.translate(outcome)
        candidate = StrategyCandidate.create_from_verified_research(
            strategy_id=command.strategy_id,
            verified_research=outcome,
            translation_decisions=translation_decisions,
            expected_version=command.expected_version,
        )
        self._repository.save_new(candidate, expected_version=command.expected_version)
        return candidate


def _ensure_identifier(value: str, expected_prefix: str, field_name: str) -> None:
    try:
        DomainIdentifier.parse_with_prefix(value, expected_prefix)
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc
