"""Cas d'usage SD de compilation deterministe d'une strategie candidate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidate,
    StrategyCompilationResult,
    StrategyCompiler,
)


class StrategyCompilationRepository(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError


@dataclass(frozen=True)
class CompileStrategyCandidateCommand:
    strategy_id: str
    expected_version: int

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)


class CompileStrategyCandidateHandler:
    def __init__(
        self,
        *,
        repository: StrategyCompilationRepository,
        compiler: StrategyCompiler,
    ) -> None:
        self._repository = repository
        self._compiler = compiler

    def handle(self, command: CompileStrategyCandidateCommand) -> StrategyCompilationResult:
        if not isinstance(command, CompileStrategyCandidateCommand):
            raise ValueError("CompileStrategyCandidateCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        return self._compiler.compile(
            candidate,
            expected_version=command.expected_version,
        )


def _ensure_strategy_id(value: str) -> None:
    try:
        DomainIdentifier.parse_with_prefix(value, "STRAT")
    except ValueError as exc:
        raise ValueError(f"strategy_id invalide: {exc}") from exc


def _ensure_expected_version(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("expected_version non entier")
    if value < 0:
        raise ValueError("expected_version negatif")
