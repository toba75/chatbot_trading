"""Repositories memoire append-only pour EX."""

from __future__ import annotations

import json
import threading

from app.contracts.strategy_experiments import StrategySnapshot
from app.experimentation.domain.experiment import Experiment


class StrategySnapshotNotFoundError(ValueError):
    pass


class ExperimentNotFoundError(ValueError):
    pass


class ExperimentResultNotFoundError(ValueError):
    pass


class InMemoryStrategySnapshotReader:
    def __init__(self, *, snapshots: tuple[StrategySnapshot, ...]) -> None:
        self._snapshots_by_id: dict[str, StrategySnapshot] = {}
        for snapshot in snapshots:
            if not isinstance(snapshot, StrategySnapshot):
                raise ValueError("StrategySnapshot attendu")
            if snapshot.strategy_version_id in self._snapshots_by_id:
                raise ValueError("snapshot_id duplique")
            self._snapshots_by_id[snapshot.strategy_version_id] = snapshot

    @classmethod
    def from_snapshots(
        cls,
        snapshots: tuple[StrategySnapshot, ...],
    ) -> "InMemoryStrategySnapshotReader":
        return cls(snapshots=snapshots)

    def get_strategy_snapshot(self, snapshot_id: str) -> StrategySnapshot:
        if snapshot_id not in self._snapshots_by_id:
            raise StrategySnapshotNotFoundError(f"snapshot absent: {snapshot_id}")
        return self._snapshots_by_id[snapshot_id]


class InMemoryExperimentRepository:
    def __init__(self, *, experiments: tuple[Experiment, ...]) -> None:
        self._lock = threading.Lock()
        self._versions_by_id: dict[str, list[Experiment]] = {}
        self._order: list[str] = []
        for experiment in experiments:
            self.save(experiment)

    @classmethod
    def empty(cls) -> "InMemoryExperimentRepository":
        return cls(experiments=())

    def save(self, experiment: Experiment) -> Experiment:
        if not isinstance(experiment, Experiment):
            raise ValueError("Experiment attendu")
        with self._lock:
            versions = self._versions_by_id.setdefault(experiment.experiment_id, [])
            if len(versions) == 0:
                versions.append(experiment)
                self._order.append(experiment.experiment_id)
                return experiment

            latest = versions[-1]
            if experiment.version == latest.version:
                if _experiment_signature(experiment) == _experiment_signature(latest):
                    return latest
                raise ValueError("registre append-only viole")
            if experiment.version < latest.version:
                raise ValueError("transition experiment non sequentielle")
            versions.append(experiment)
            return experiment

    def get(self, experiment_id: str) -> Experiment:
        with self._lock:
            if experiment_id not in self._versions_by_id:
                raise ExperimentNotFoundError(f"experience absente: {experiment_id}")
            return self._versions_by_id[experiment_id][-1]

    def history(self, experiment_id: str) -> tuple[Experiment, ...]:
        with self._lock:
            if experiment_id not in self._versions_by_id:
                raise ExperimentNotFoundError(f"experience absente: {experiment_id}")
            return tuple(self._versions_by_id[experiment_id])

    def all(self) -> tuple[Experiment, ...]:
        with self._lock:
            return tuple(self._versions_by_id[experiment_id][-1] for experiment_id in self._order)

    def delete(self, experiment_id: str) -> None:
        raise ValueError("registre append-only: suppression experience interdite")


class InMemoryExperimentResultRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results_by_experiment_id: dict[str, object] = {}
        self._result_signatures_by_experiment_id: dict[str, str] = {}
        self._order: list[str] = []

    @classmethod
    def empty(cls) -> "InMemoryExperimentResultRepository":
        return cls()

    def append(self, result: object) -> object:
        experiment_id = getattr(result, "experiment_id", None)
        result_hash = getattr(result, "result_hash", None)
        if not isinstance(experiment_id, str) or not isinstance(result_hash, str):
            raise ValueError("ExperimentResult attendu")
        signature = _result_signature(result)
        with self._lock:
            if experiment_id in self._results_by_experiment_id:
                if self._result_signatures_by_experiment_id[experiment_id] == signature:
                    return self._results_by_experiment_id[experiment_id]
                raise ValueError("resultat append-only viole")
            self._results_by_experiment_id[experiment_id] = result
            self._result_signatures_by_experiment_id[experiment_id] = signature
            self._order.append(experiment_id)
            return result

    def get(self, experiment_id: str) -> object:
        with self._lock:
            if experiment_id not in self._results_by_experiment_id:
                raise ExperimentResultNotFoundError(f"resultat absent: {experiment_id}")
            return self._results_by_experiment_id[experiment_id]

    def all(self) -> tuple[object, ...]:
        with self._lock:
            return tuple(self._results_by_experiment_id[experiment_id] for experiment_id in self._order)

    def delete(self, experiment_id: str) -> None:
        raise ValueError("suppression resultat interdite")


class InMemoryExperimentArtifactStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._artifacts_by_id: dict[str, dict[str, object]] = {}

    @classmethod
    def empty(cls) -> "InMemoryExperimentArtifactStore":
        return cls()

    def append(self, artifact: dict[str, object]) -> dict[str, object]:
        artifact_id = artifact.get("artifact_id")
        artifact_hash = artifact.get("artifact_hash")
        if not isinstance(artifact_id, str) or not isinstance(artifact_hash, str):
            raise ValueError("artifact invalide")
        with self._lock:
            if artifact_id in self._artifacts_by_id:
                if self._artifacts_by_id[artifact_id] != artifact:
                    raise ValueError("artifact append-only viole")
                return dict(self._artifacts_by_id[artifact_id])
            self._artifacts_by_id[artifact_id] = dict(artifact)
            return dict(artifact)


def _experiment_signature(experiment: Experiment) -> str:
    return json.dumps(experiment.to_payload(), sort_keys=True, separators=(",", ":"))


def _result_signature(result: object) -> str:
    payload = result.to_payload() if callable(getattr(result, "to_payload", None)) else vars(result)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


__all__ = [
    "ExperimentNotFoundError",
    "ExperimentResultNotFoundError",
    "InMemoryExperimentArtifactStore",
    "InMemoryExperimentRepository",
    "InMemoryExperimentResultRepository",
    "InMemoryStrategySnapshotReader",
    "StrategySnapshotNotFoundError",
]
