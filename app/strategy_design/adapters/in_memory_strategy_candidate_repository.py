"""Dépôt mémoire SD avec concurrence optimiste explicite."""

from __future__ import annotations

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidate,
    StrategyCandidateNotFoundError,
    StrategyConcurrencyError,
    _ensure_repository_expected_version,
)


class InMemoryStrategyCandidateRepository:
    def __init__(self, candidates: dict[str, StrategyCandidate]) -> None:
        self._candidates = dict(candidates)

    @classmethod
    def empty(cls) -> "InMemoryStrategyCandidateRepository":
        return cls({})

    def save_new(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        _ensure_candidate(candidate)
        _ensure_repository_expected_version(expected_version)

        current_candidate = self._candidates.get(candidate.strategy_id)
        if current_candidate is not None:
            if current_candidate.version != expected_version:
                raise StrategyConcurrencyError(
                    candidate.strategy_id,
                    expected_version,
                    current_candidate.version,
                )
            raise ValueError(f"identité stratégie déjà ouverte: {candidate.strategy_id}")

        if expected_version != 0:
            raise StrategyConcurrencyError(candidate.strategy_id, expected_version, 0)

        self._candidates[candidate.strategy_id] = candidate

    def save(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        _ensure_candidate(candidate)
        _ensure_repository_expected_version(expected_version)

        current_candidate = self._candidates.get(candidate.strategy_id)
        if current_candidate is None:
            raise StrategyCandidateNotFoundError(candidate.strategy_id)
        if current_candidate.version != expected_version:
            raise StrategyConcurrencyError(
                candidate.strategy_id,
                expected_version,
                current_candidate.version,
            )
        if candidate.version != current_candidate.version + 1:
            raise ValueError("version candidate invalide pour sauvegarde")

        self._candidates[candidate.strategy_id] = candidate

    def get(self, strategy_id: str) -> StrategyCandidate:
        _ensure_strategy_id(strategy_id)
        candidate = self._candidates.get(strategy_id)
        if candidate is None:
            raise StrategyCandidateNotFoundError(strategy_id)
        return candidate


def _ensure_candidate(candidate: StrategyCandidate) -> None:
    if not isinstance(candidate, StrategyCandidate):
        raise ValueError("StrategyCandidate attendu")


def _ensure_strategy_id(value: str) -> None:
    try:
        DomainIdentifier.parse_with_prefix(value, "STRAT")
    except ValueError as exc:
        raise ValueError(f"strategy_id SD invalide: {exc}") from exc
