"""Cas d'usage SD de creation de snapshot immuable de strategie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidate,
    StrategyCompilationResult,
    StrategyCompilationStatus,
    StrategySnapshotPolicy,
    StrategySnapshotPublication,
)


class StrategySnapshotRepository(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError


class StrategySnapshotStore(Protocol):
    def append_publication(self, publication: StrategySnapshotPublication) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class CreateStrategySnapshotCommand:
    strategy_id: str
    expected_version: int
    compilation_result: StrategyCompilationResult | None
    created_at: str
    correlation_id: str
    causation_id: str
    supersedes_snapshot_id: str | None

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        if not isinstance(self.compilation_result, StrategyCompilationResult):
            raise ValueError("compilation disponible requise")
        if self.compilation_result.compilation_status != StrategyCompilationStatus.COMPILED:
            raise ValueError("compilation disponible requise")
        if self.compilation_result.representation is None:
            raise ValueError("compilation disponible requise")
        _ensure_text(self.created_at, "created_at")
        _ensure_text(self.correlation_id, "correlation_id")
        _ensure_text(self.causation_id, "causation_id")
        if self.supersedes_snapshot_id is not None:
            _ensure_text(self.supersedes_snapshot_id, "supersedes_snapshot_id")


@dataclass(frozen=True)
class CreateStrategySnapshotResult:
    strategy: StrategyCandidate
    snapshot_id: str
    snapshot_hash: str
    snapshot: object
    created_event: object
    superseded_event: object | None
    stored_record: object


class CreateStrategySnapshotHandler:
    def __init__(
        self,
        *,
        repository: StrategySnapshotRepository,
        snapshot_store: StrategySnapshotStore,
    ) -> None:
        self._repository = repository
        self._snapshot_store = snapshot_store
        self._policy = StrategySnapshotPolicy()

    def handle(self, command: CreateStrategySnapshotCommand) -> CreateStrategySnapshotResult:
        if not isinstance(command, CreateStrategySnapshotCommand):
            raise ValueError("CreateStrategySnapshotCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        publication = self._policy.create_snapshot(
            candidate=candidate,
            compiled_representation=command.compilation_result.representation,
            created_at=command.created_at,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            supersedes_snapshot_id=command.supersedes_snapshot_id,
        )
        strategy = candidate.mark_snapshotted(
            snapshot_id=publication.snapshot_id,
            snapshot_hash=publication.snapshot_hash,
            expected_version=command.expected_version,
        )
        stored_record = self._snapshot_store.append_publication(publication)
        return CreateStrategySnapshotResult(
            strategy=strategy,
            snapshot_id=publication.snapshot_id,
            snapshot_hash=publication.snapshot_hash,
            snapshot=publication.snapshot,
            created_event=publication.created_event,
            superseded_event=publication.superseded_event,
            stored_record=stored_record,
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


def _ensure_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value
