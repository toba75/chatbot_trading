"""Cas d'usage EX pour experiences reproductibles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from app.contracts.strategy_experiments import StrategySnapshot
from app.experimentation.domain.experiment import (
    CostModelSnapshot,
    DataSnapshotRef,
    ExecutionEnvironment,
    Experiment,
    ExperimentComparisonResult,
    compare_experiments,
)


class StrategySnapshotReaderPort(Protocol):
    def get_strategy_snapshot(self, snapshot_id: str) -> StrategySnapshot:
        raise NotImplementedError


class ExperimentRepositoryPort(Protocol):
    def save(self, experiment: Experiment) -> Experiment:
        raise NotImplementedError

    def get(self, experiment_id: str) -> Experiment:
        raise NotImplementedError


class ExperimentResultRepositoryPort(Protocol):
    def get(self, experiment_id: str) -> object:
        raise NotImplementedError


@dataclass(frozen=True)
class PlanExperimentCommand:
    experiment_id: str
    strategy_snapshot_id: str
    mandate: Mapping[str, Any]
    created_at: str


class PlanExperimentHandler:
    def __init__(
        self,
        *,
        snapshot_reader: StrategySnapshotReaderPort,
        repository: ExperimentRepositoryPort,
    ) -> None:
        if not callable(getattr(snapshot_reader, "get_strategy_snapshot", None)):
            raise ValueError("snapshot_reader sans get_strategy_snapshot")
        if not callable(getattr(repository, "save", None)):
            raise ValueError("repository sans save")
        self._snapshot_reader = snapshot_reader
        self._repository = repository

    def handle(self, command: PlanExperimentCommand) -> Experiment:
        snapshot = self._snapshot_reader.get_strategy_snapshot(command.strategy_snapshot_id)
        experiment = Experiment.plan(
            experiment_id=command.experiment_id,
            strategy_snapshot=snapshot,
            mandate=command.mandate,
            created_at=command.created_at,
        )
        return self._repository.save(experiment)


@dataclass(frozen=True)
class AttachDataSnapshotCommand:
    experiment_id: str
    expected_version: int
    data_snapshot: DataSnapshotRef


class AttachDataSnapshotHandler:
    def __init__(self, *, repository: ExperimentRepositoryPort) -> None:
        self._repository = repository

    def handle(self, command: AttachDataSnapshotCommand) -> Experiment:
        experiment = self._repository.get(command.experiment_id)
        updated = experiment.attach_data_snapshot(
            data_snapshot=command.data_snapshot,
            expected_version=command.expected_version,
        )
        return self._repository.save(updated)


@dataclass(frozen=True)
class AttachCostEnvironmentCommand:
    experiment_id: str
    expected_version: int
    cost_model: CostModelSnapshot
    execution_environment: ExecutionEnvironment
    frozen_at: str


class AttachCostEnvironmentHandler:
    def __init__(self, *, repository: ExperimentRepositoryPort) -> None:
        self._repository = repository

    def handle(self, command: AttachCostEnvironmentCommand) -> Experiment:
        experiment = self._repository.get(command.experiment_id)
        updated = experiment.attach_cost_environment(
            cost_model=command.cost_model,
            execution_environment=command.execution_environment,
            frozen_at=command.frozen_at,
            expected_version=command.expected_version,
        )
        return self._repository.save(updated)


@dataclass(frozen=True)
class ScheduleExperimentCommand:
    experiment_id: str
    expected_version: int
    scheduled_at: str


class ScheduleExperimentHandler:
    def __init__(self, *, repository: ExperimentRepositoryPort) -> None:
        self._repository = repository

    def handle(self, command: ScheduleExperimentCommand) -> Experiment:
        experiment = self._repository.get(command.experiment_id)
        updated = experiment.schedule(
            scheduled_at=command.scheduled_at,
            expected_version=command.expected_version,
        )
        return self._repository.save(updated)


@dataclass(frozen=True)
class RepeatExperimentCommand:
    source_experiment_id: str
    new_experiment_id: str
    created_at: str


class RepeatExperimentHandler:
    def __init__(self, *, repository: ExperimentRepositoryPort) -> None:
        self._repository = repository

    def handle(self, command: RepeatExperimentCommand) -> Experiment:
        source = self._repository.get(command.source_experiment_id)
        repeated = source.repeat_as(
            new_experiment_id=command.new_experiment_id,
            created_at=command.created_at,
        )
        return self._repository.save(repeated)


@dataclass(frozen=True)
class CompareExperimentsCommand:
    left_experiment_id: str
    right_experiment_id: str
    comparison_id: str


class CompareExperimentsHandler:
    def __init__(
        self,
        *,
        experiment_repository: ExperimentRepositoryPort,
        result_repository: ExperimentResultRepositoryPort,
    ) -> None:
        self._experiment_repository = experiment_repository
        self._result_repository = result_repository

    def handle(self, command: CompareExperimentsCommand) -> ExperimentComparisonResult:
        left = self._experiment_repository.get(command.left_experiment_id)
        right = self._experiment_repository.get(command.right_experiment_id)
        self._result_repository.get(left.experiment_id)
        self._result_repository.get(right.experiment_id)
        return compare_experiments(
            comparison_id=command.comparison_id,
            left=left,
            right=right,
        )


__all__ = [
    "AttachCostEnvironmentCommand",
    "AttachCostEnvironmentHandler",
    "AttachDataSnapshotCommand",
    "AttachDataSnapshotHandler",
    "CompareExperimentsCommand",
    "CompareExperimentsHandler",
    "ExperimentRepositoryPort",
    "PlanExperimentCommand",
    "PlanExperimentHandler",
    "RepeatExperimentCommand",
    "RepeatExperimentHandler",
    "ScheduleExperimentCommand",
    "ScheduleExperimentHandler",
    "StrategySnapshotReaderPort",
]
