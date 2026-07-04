"""Cas d'usage SD de validation et de gestion des conflits de stratégie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidate,
    StrategyConflict,
)


class StrategyValidationRepository(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError

    def save(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class ValidateStrategyCandidateCommand:
    strategy_id: str
    expected_version: int

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)


@dataclass(frozen=True)
class RecordStrategyConflictCommand:
    strategy_id: str
    expected_version: int
    conflict_id: str
    description: str
    blocking: bool

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.conflict_id, "conflict_id")
        _ensure_text(self.description, "description")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking non booléen")


@dataclass(frozen=True)
class ResolveStrategyConflictCommand:
    strategy_id: str
    expected_version: int
    conflict_id: str
    resolution_summary: str

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.conflict_id, "conflict_id")
        _ensure_text(self.resolution_summary, "resolution_summary")


class ValidateStrategyCandidateHandler:
    def __init__(self, *, repository: StrategyValidationRepository) -> None:
        self._repository = repository

    def handle(self, command: ValidateStrategyCandidateCommand) -> StrategyCandidate:
        if not isinstance(command, ValidateStrategyCandidateCommand):
            raise ValueError("ValidateStrategyCandidateCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        updated_candidate = candidate.validate_candidate(
            expected_version=command.expected_version,
        )
        self._repository.save(
            updated_candidate,
            expected_version=command.expected_version,
        )
        return updated_candidate


class RecordStrategyConflictHandler:
    def __init__(self, *, repository: StrategyValidationRepository) -> None:
        self._repository = repository

    def handle(self, command: RecordStrategyConflictCommand) -> StrategyCandidate:
        if not isinstance(command, RecordStrategyConflictCommand):
            raise ValueError("RecordStrategyConflictCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        if not command.blocking:
            raise ValueError("conflit documentaire non bloquant hors périmètre T-007")
        conflict = StrategyConflict.blocking_documentary_conflict(
            conflict_id=command.conflict_id,
            description=command.description,
        )
        updated_candidate = candidate.record_conflict(
            conflict=conflict,
            expected_version=command.expected_version,
        )
        self._repository.save(
            updated_candidate,
            expected_version=command.expected_version,
        )
        return updated_candidate


class ResolveStrategyConflictHandler:
    def __init__(self, *, repository: StrategyValidationRepository) -> None:
        self._repository = repository

    def handle(self, command: ResolveStrategyConflictCommand) -> StrategyCandidate:
        if not isinstance(command, ResolveStrategyConflictCommand):
            raise ValueError("ResolveStrategyConflictCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        updated_candidate = candidate.resolve_conflict(
            conflict_id=command.conflict_id,
            resolution_summary=command.resolution_summary,
            expected_version=command.expected_version,
        )
        self._repository.save(
            updated_candidate,
            expected_version=command.expected_version,
        )
        return updated_candidate


def _ensure_strategy_id(value: str) -> None:
    try:
        DomainIdentifier.parse_with_prefix(value, "STRAT")
    except ValueError as exc:
        raise ValueError(f"strategy_id invalide: {exc}") from exc


def _ensure_expected_version(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("expected_version non entier")
    if value < 0:
        raise ValueError("expected_version négatif")


def _ensure_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value
