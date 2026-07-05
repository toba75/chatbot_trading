"""Domaine EX pour experiences de backtest reproductibles."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.contracts.strategy_experiments import ExperimentResult, StrategySnapshot


PLANNED = "PLANNED"
SCHEDULED = "SCHEDULED"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
TERMINAL_STATUSES = frozenset({COMPLETED, FAILED, CANCELLED})

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_FORBIDDEN_REFERENCE_FRAGMENTS = (
    "/current",
    "/latest",
    ":latest",
    "strategy_candidate:",
    "live_reference",
)


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", _ensure_text(self.event_type, "event_type"))
        object.__setattr__(self, "aggregate_id", _ensure_experiment_id(self.aggregate_id))
        object.__setattr__(
            self,
            "aggregate_version",
            _ensure_positive_integer(self.aggregate_version, "aggregate_version"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))


@dataclass(frozen=True)
class DataSnapshotRef:
    data_snapshot_id: str
    data_snapshot_hash: str
    universe: tuple[str, ...]
    period_start: str
    period_end: str
    frequency: str
    point_in_time: bool
    validation_slice_declared_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_snapshot_id", _ensure_data_snapshot_id(self.data_snapshot_id))
        object.__setattr__(
            self,
            "data_snapshot_hash",
            _ensure_hash(self.data_snapshot_hash, "data_snapshot_hash"),
        )
        object.__setattr__(
            self,
            "universe",
            _ensure_text_tuple(self.universe, "universe", allow_empty=False),
        )
        object.__setattr__(self, "period_start", _ensure_date(self.period_start, "period_start"))
        object.__setattr__(self, "period_end", _ensure_date(self.period_end, "period_end"))
        object.__setattr__(self, "frequency", _ensure_text(self.frequency, "frequency"))
        if not isinstance(self.point_in_time, bool):
            raise ValueError("point_in_time non booleen")
        if not self.point_in_time:
            raise ValueError("snapshot point-in-time requis")
        object.__setattr__(
            self,
            "validation_slice_declared_at",
            _ensure_utc_instant(self.validation_slice_declared_at, "validation_slice_declared_at"),
        )
        if self.period_start > self.period_end:
            raise ValueError("periode snapshot incoherente")
        _ensure_no_mutable_reference(self.to_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DataSnapshotRef":
        parsed = _ensure_mapping(payload, "data_snapshot")
        return cls(
            data_snapshot_id=parsed.get("data_snapshot_id"),
            data_snapshot_hash=parsed.get("data_snapshot_hash"),
            universe=tuple(parsed.get("universe", ())),
            period_start=parsed.get("period_start"),
            period_end=parsed.get("period_end"),
            frequency=parsed.get("frequency"),
            point_in_time=parsed.get("point_in_time"),
            validation_slice_declared_at=parsed.get("validation_slice_declared_at"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "data_snapshot_id": self.data_snapshot_id,
            "data_snapshot_hash": self.data_snapshot_hash,
            "universe": list(self.universe),
            "period_start": self.period_start,
            "period_end": self.period_end,
            "frequency": self.frequency,
            "point_in_time": self.point_in_time,
            "validation_slice_declared_at": self.validation_slice_declared_at,
        }

    def with_reference(self, reference: str) -> "DataSnapshotRef":
        _ensure_no_mutable_reference({"reference": reference})
        return self


@dataclass(frozen=True)
class CostModelSnapshot:
    cost_model_id: str
    cost_model_hash: str
    commission_bps: float
    slippage_bps: float
    currency: str
    assumptions: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cost_model_id", _ensure_prefixed_text(self.cost_model_id, "COST-", "cost_model_id"))
        object.__setattr__(self, "cost_model_hash", _ensure_hash(self.cost_model_hash, "cost_model_hash"))
        object.__setattr__(self, "commission_bps", _ensure_non_negative_number(self.commission_bps, "commission_bps"))
        object.__setattr__(self, "slippage_bps", _ensure_non_negative_number(self.slippage_bps, "slippage_bps"))
        object.__setattr__(self, "currency", _ensure_text(self.currency, "currency"))
        object.__setattr__(self, "assumptions", _freeze_mapping(self.assumptions, "assumptions"))
        _ensure_no_mutable_reference(self.to_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CostModelSnapshot":
        parsed = _ensure_mapping(payload, "cost_model")
        return cls(
            cost_model_id=parsed.get("cost_model_id"),
            cost_model_hash=parsed.get("cost_model_hash"),
            commission_bps=parsed.get("commission_bps"),
            slippage_bps=parsed.get("slippage_bps"),
            currency=parsed.get("currency"),
            assumptions=parsed.get("assumptions"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "cost_model_id": self.cost_model_id,
            "cost_model_hash": self.cost_model_hash,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "currency": self.currency,
            "assumptions": _json_ready(self.assumptions),
        }


@dataclass(frozen=True)
class ExecutionEnvironment:
    environment_id: str
    execution_environment_hash: str
    code_version: str
    engine_version: str
    seed: int
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment_id", _ensure_prefixed_text(self.environment_id, "ENV-", "environment_id"))
        object.__setattr__(
            self,
            "execution_environment_hash",
            _ensure_hash(self.execution_environment_hash, "execution_environment_hash"),
        )
        object.__setattr__(self, "code_version", _ensure_text(self.code_version, "code_version"))
        object.__setattr__(self, "engine_version", _ensure_text(self.engine_version, "engine_version"))
        object.__setattr__(self, "seed", _ensure_non_negative_integer(self.seed, "seed"))
        object.__setattr__(self, "created_at", _ensure_utc_instant(self.created_at, "created_at"))

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutionEnvironment":
        parsed = _ensure_mapping(payload, "execution_environment")
        return cls(
            environment_id=parsed.get("environment_id"),
            execution_environment_hash=parsed.get("execution_environment_hash"),
            code_version=parsed.get("code_version"),
            engine_version=parsed.get("engine_version"),
            seed=parsed.get("seed"),
            created_at=parsed.get("created_at"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "execution_environment_hash": self.execution_environment_hash,
            "code_version": self.code_version,
            "engine_version": self.engine_version,
            "seed": self.seed,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class FrozenInputs:
    strategy_snapshot_hash: str
    strategy_parameter_hash: str
    data_snapshot_ref: DataSnapshotRef
    cost_model_snapshot: CostModelSnapshot
    execution_environment: ExecutionEnvironment
    frozen_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "strategy_snapshot_hash",
            _ensure_hash(self.strategy_snapshot_hash, "strategy_snapshot_hash"),
        )
        object.__setattr__(
            self,
            "strategy_parameter_hash",
            _ensure_hash(self.strategy_parameter_hash, "strategy_parameter_hash"),
        )
        if not isinstance(self.data_snapshot_ref, DataSnapshotRef):
            raise ValueError("data_snapshot_ref invalide")
        if not isinstance(self.cost_model_snapshot, CostModelSnapshot):
            raise ValueError("cost_model_snapshot invalide")
        if not isinstance(self.execution_environment, ExecutionEnvironment):
            raise ValueError("execution_environment invalide")
        object.__setattr__(self, "frozen_at", _ensure_utc_instant(self.frozen_at, "frozen_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "strategy_snapshot_hash": self.strategy_snapshot_hash,
            "strategy_parameter_hash": self.strategy_parameter_hash,
            "data_snapshot_id": self.data_snapshot_ref.data_snapshot_id,
            "data_snapshot_hash": self.data_snapshot_ref.data_snapshot_hash,
            "cost_model_hash": self.cost_model_snapshot.cost_model_hash,
            "execution_environment_hash": self.execution_environment.execution_environment_hash,
            "frozen_at": self.frozen_at,
        }

    def full_payload(self) -> dict[str, Any]:
        payload = self.to_payload()
        payload["data_snapshot"] = self.data_snapshot_ref.to_payload()
        payload["cost_model"] = self.cost_model_snapshot.to_payload()
        payload["execution_environment"] = self.execution_environment.to_payload()
        return payload


@dataclass(frozen=True)
class BacktestEngineResult:
    result_hash: str
    metrics: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]
    controls: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_hash", _ensure_hash(self.result_hash, "result_hash"))
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics, "metrics"))
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics, "diagnostics"))
        object.__setattr__(self, "artifacts", _ensure_artifacts(self.artifacts))
        object.__setattr__(self, "controls", _freeze_mapping(self.controls, "controls"))


@dataclass(frozen=True)
class ExperimentComparisonResult:
    comparison_id: str
    event_type: str
    left_experiment_id: str
    right_experiment_id: str
    inputs_match: bool
    metrics_match: bool
    diagnostics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparison_id", _ensure_prefixed_text(self.comparison_id, "CMP-", "comparison_id"))
        object.__setattr__(self, "event_type", _ensure_expected_text(self.event_type, "ExperimentComparisonCompleted", "event_type"))
        object.__setattr__(self, "left_experiment_id", _ensure_experiment_id(self.left_experiment_id))
        object.__setattr__(self, "right_experiment_id", _ensure_experiment_id(self.right_experiment_id))
        if self.left_experiment_id == self.right_experiment_id:
            raise ValueError("experiences distinctes requises")
        if not isinstance(self.inputs_match, bool):
            raise ValueError("inputs_match non booleen")
        if not isinstance(self.metrics_match, bool):
            raise ValueError("metrics_match non booleen")
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics, "diagnostics"))


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    version: int
    status: str
    strategy_id: str
    strategy_version_id: str
    strategy_snapshot_hash: str
    strategy_parameter_hash: str
    spec_hash: str
    mandate: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    data_snapshot_ref: DataSnapshotRef | None
    cost_model_snapshot: CostModelSnapshot | None
    execution_environment: ExecutionEnvironment | None
    frozen_inputs: FrozenInputs | None
    result: ExperimentResult | None
    events: tuple[DomainEvent, ...]
    repeats_experiment_id: str | None
    invalidated_by_experiment_id: str | None
    archived: bool
    created_at: str

    @classmethod
    def plan(
        cls,
        *,
        experiment_id: str,
        strategy_snapshot: StrategySnapshot,
        mandate: Mapping[str, Any],
        created_at: str,
    ) -> "Experiment":
        parsed_experiment_id = _ensure_experiment_id(experiment_id)
        if not isinstance(strategy_snapshot, StrategySnapshot):
            raise ValueError("StrategySnapshot requis")
        _ensure_no_mutable_reference(strategy_snapshot.to_payload())
        parsed_created_at = _ensure_utc_instant(created_at, "created_at")
        parsed_mandate = _freeze_mapping(mandate, "mandate")
        strategy_parameter_hash = _stable_hash(
            {"parameters": strategy_snapshot.to_payload()["parameters"]}
        )
        event = DomainEvent(
            event_type="ExperimentPlanned",
            aggregate_id=parsed_experiment_id,
            aggregate_version=1,
            occurred_at=parsed_created_at,
            payload={
                "strategy_id": strategy_snapshot.strategy_id,
                "strategy_version_id": strategy_snapshot.strategy_version_id,
                "spec_hash": strategy_snapshot.spec_hash,
                "strategy_parameter_hash": strategy_parameter_hash,
            },
        )
        return cls(
            experiment_id=parsed_experiment_id,
            version=1,
            status=PLANNED,
            strategy_id=strategy_snapshot.strategy_id,
            strategy_version_id=strategy_snapshot.strategy_version_id,
            strategy_snapshot_hash=strategy_snapshot.spec_hash,
            strategy_parameter_hash=strategy_parameter_hash,
            spec_hash=strategy_snapshot.spec_hash,
            mandate=parsed_mandate,
            diagnostics={"planning_status": "READY_FOR_INPUT_FREEZE"},
            data_snapshot_ref=None,
            cost_model_snapshot=None,
            execution_environment=None,
            frozen_inputs=None,
            result=None,
            events=(event,),
            repeats_experiment_id=None,
            invalidated_by_experiment_id=None,
            archived=False,
            created_at=parsed_created_at,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "experiment_id", _ensure_experiment_id(self.experiment_id))
        object.__setattr__(self, "version", _ensure_positive_integer(self.version, "version"))
        object.__setattr__(self, "status", _ensure_experiment_status(self.status))
        object.__setattr__(self, "strategy_id", _ensure_strategy_id(self.strategy_id))
        object.__setattr__(self, "strategy_version_id", _ensure_strategy_version_id(self.strategy_version_id))
        object.__setattr__(self, "strategy_snapshot_hash", _ensure_hash(self.strategy_snapshot_hash, "strategy_snapshot_hash"))
        object.__setattr__(self, "strategy_parameter_hash", _ensure_hash(self.strategy_parameter_hash, "strategy_parameter_hash"))
        object.__setattr__(self, "spec_hash", _ensure_hash(self.spec_hash, "spec_hash"))
        object.__setattr__(self, "mandate", _freeze_mapping(self.mandate, "mandate"))
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics, "diagnostics"))
        if self.data_snapshot_ref is not None and not isinstance(self.data_snapshot_ref, DataSnapshotRef):
            raise ValueError("data_snapshot_ref invalide")
        if self.cost_model_snapshot is not None and not isinstance(self.cost_model_snapshot, CostModelSnapshot):
            raise ValueError("cost_model_snapshot invalide")
        if self.execution_environment is not None and not isinstance(self.execution_environment, ExecutionEnvironment):
            raise ValueError("execution_environment invalide")
        if self.frozen_inputs is not None and not isinstance(self.frozen_inputs, FrozenInputs):
            raise ValueError("frozen_inputs invalide")
        if self.result is not None and not isinstance(self.result, ExperimentResult):
            raise ValueError("ExperimentResult invalide")
        object.__setattr__(self, "events", _ensure_events(self.events, self.experiment_id))
        if self.repeats_experiment_id is not None:
            object.__setattr__(self, "repeats_experiment_id", _ensure_experiment_id(self.repeats_experiment_id))
        if self.invalidated_by_experiment_id is not None:
            object.__setattr__(self, "invalidated_by_experiment_id", _ensure_experiment_id(self.invalidated_by_experiment_id))
        if not isinstance(self.archived, bool):
            raise ValueError("archived non booleen")
        object.__setattr__(self, "created_at", _ensure_utc_instant(self.created_at, "created_at"))

    def with_mutable_strategy_reference(self, reference: str) -> "Experiment":
        _ensure_no_mutable_reference({"strategy_reference": reference})
        return self

    def attach_data_snapshot(
        self,
        *,
        data_snapshot: DataSnapshotRef,
        expected_version: int,
    ) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(PLANNED)
        if self.data_snapshot_ref is not None:
            raise ValueError("snapshot donnees deja fige")
        if not isinstance(data_snapshot, DataSnapshotRef):
            raise ValueError("data_snapshot invalide")
        return self._replace_with_event(
            event_type="ExperimentDataSnapshotFrozen",
            occurred_at=data_snapshot.validation_slice_declared_at,
            payload=data_snapshot.to_payload(),
            data_snapshot_ref=data_snapshot,
            diagnostics={"data_snapshot_status": "POINT_IN_TIME_LOCKED"},
        )

    def attach_cost_environment(
        self,
        *,
        cost_model: CostModelSnapshot,
        execution_environment: ExecutionEnvironment,
        frozen_at: str,
        expected_version: int,
    ) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(PLANNED)
        if self.data_snapshot_ref is None:
            raise ValueError("snapshot donnees requis")
        if self.frozen_inputs is not None:
            raise ValueError("entrees deja verrouillees")
        frozen_inputs = FrozenInputs(
            strategy_snapshot_hash=self.strategy_snapshot_hash,
            strategy_parameter_hash=self.strategy_parameter_hash,
            data_snapshot_ref=self.data_snapshot_ref,
            cost_model_snapshot=cost_model,
            execution_environment=execution_environment,
            frozen_at=frozen_at,
        )
        return self._replace_with_event(
            event_type="ExperimentInputsFrozen",
            occurred_at=frozen_inputs.frozen_at,
            payload=frozen_inputs.full_payload(),
            cost_model_snapshot=cost_model,
            execution_environment=execution_environment,
            frozen_inputs=frozen_inputs,
            diagnostics={"input_lock_status": "LOCKED"},
        )

    def schedule(self, *, scheduled_at: str, expected_version: int) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(PLANNED)
        if self.frozen_inputs is None:
            raise ValueError("entrees verrouillees requises")
        return self._replace_with_event(
            event_type="ExperimentScheduled",
            occurred_at=scheduled_at,
            payload={"previous_status": self.status, "next_status": SCHEDULED},
            status=SCHEDULED,
            diagnostics={"schedule_status": "READY_TO_RUN"},
        )

    def cancel(self, *, cancelled_at: str, reason: str, expected_version: int) -> "Experiment":
        self._ensure_expected_version(expected_version)
        if self.status not in {PLANNED, SCHEDULED}:
            raise ValueError("transition interdite")
        parsed_reason = _ensure_text(reason, "reason")
        return self._replace_with_event(
            event_type="ExperimentCancelled",
            occurred_at=cancelled_at,
            payload={"reason": parsed_reason, "previous_status": self.status, "next_status": CANCELLED},
            status=CANCELLED,
            diagnostics={"cancellation_reason": parsed_reason},
        )

    def start(self, *, started_at: str, expected_version: int) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(SCHEDULED)
        if self.frozen_inputs is None:
            raise ValueError("entrees verrouillees requises")
        return self._replace_with_event(
            event_type="ExperimentStarted",
            occurred_at=started_at,
            payload={"previous_status": self.status, "next_status": RUNNING},
            status=RUNNING,
            diagnostics={"run_status": "RUNNING_WITH_LOCKED_INPUTS"},
        )

    def complete(
        self,
        *,
        engine_result: BacktestEngineResult,
        completed_at: str,
        expected_version: int,
    ) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(RUNNING)
        if not isinstance(engine_result, BacktestEngineResult):
            raise ValueError("BacktestEngineResult requis")
        result = self._to_contract_result(
            engine_result=engine_result,
            status=COMPLETED,
            completed_at=completed_at,
            diagnostics=dict(engine_result.diagnostics),
        )
        return self._replace_with_event(
            event_type="ExperimentResultRecorded",
            occurred_at=completed_at,
            payload={"result_hash": result.result_hash, "status": result.status},
            status=COMPLETED,
            result=result,
            diagnostics={"result_status": "COMPLETED_IMMUTABLE"},
        )

    def fail(
        self,
        *,
        failure_reason: str,
        completed_at: str,
        expected_version: int,
    ) -> "Experiment":
        self._ensure_expected_version(expected_version)
        self._ensure_status(RUNNING)
        if not isinstance(failure_reason, str) or failure_reason.strip() == "":
            raise ValueError("failure_reason requis")
        parsed_failure_reason = _ensure_text(failure_reason, "failure_reason")
        engine_result = BacktestEngineResult(
            result_hash=_stable_hash(
                {
                    "experiment_id": self.experiment_id,
                    "failure_reason": parsed_failure_reason,
                    "frozen_inputs": self.frozen_inputs.full_payload(),
                }
            ),
            metrics={"return_pct": 0.0, "trade_count": 0},
            diagnostics={"failure_reason": parsed_failure_reason},
            artifacts=(
                {
                    "artifact_id": f"{self.experiment_id}-FAILURE-LOG",
                    "artifact_type": "run_log",
                    "artifact_hash": _stable_hash({"failure_reason": parsed_failure_reason}),
                },
            ),
            controls={"failure_retained": "PASS"},
        )
        result = self._to_contract_result(
            engine_result=engine_result,
            status=FAILED,
            completed_at=completed_at,
            diagnostics={"failure_reason": parsed_failure_reason},
        )
        return self._replace_with_event(
            event_type="ExperimentFailedResultRecorded",
            occurred_at=completed_at,
            payload={"result_hash": result.result_hash, "failure_reason": parsed_failure_reason},
            status=FAILED,
            result=result,
            diagnostics={"failure_reason": parsed_failure_reason, "result_retention": "RETAINED"},
        )

    def invalidate(
        self,
        *,
        invalidated_by_experiment_id: str,
        reason: str,
        invalidated_at: str,
        expected_version: int,
    ) -> "Experiment":
        self._ensure_expected_version(expected_version)
        if self.result is None:
            raise ValueError("resultat absent")
        parsed_replacement_id = _ensure_experiment_id(invalidated_by_experiment_id)
        if parsed_replacement_id == self.experiment_id:
            raise ValueError("nouvelle experience liee requise")
        parsed_reason = _ensure_text(reason, "reason")
        return self._replace_with_event(
            event_type="ExperimentResultInvalidated",
            occurred_at=invalidated_at,
            payload={
                "invalidated_by_experiment_id": parsed_replacement_id,
                "reason": parsed_reason,
                "retained_result_hash": self.result.result_hash,
            },
            invalidated_by_experiment_id=parsed_replacement_id,
            diagnostics={
                **dict(self.diagnostics),
                "invalidated_after_audit": True,
                "invalidation_reason": parsed_reason,
            },
        )

    def repeat_as(self, *, new_experiment_id: str, created_at: str) -> "Experiment":
        if self.status != COMPLETED or self.result is None or self.frozen_inputs is None:
            raise ValueError("experience terminee requise")
        parsed_experiment_id = _ensure_experiment_id(new_experiment_id)
        if parsed_experiment_id == self.experiment_id:
            raise ValueError("nouvel experiment_id requis")
        parsed_created_at = _ensure_utc_instant(created_at, "created_at")
        event = DomainEvent(
            event_type="ExperimentRepeated",
            aggregate_id=parsed_experiment_id,
            aggregate_version=1,
            occurred_at=parsed_created_at,
            payload={
                "repeats_experiment_id": self.experiment_id,
                "strategy_parameter_hash": self.strategy_parameter_hash,
                "data_snapshot_hash": self.frozen_inputs.data_snapshot_ref.data_snapshot_hash,
                "cost_model_hash": self.frozen_inputs.cost_model_snapshot.cost_model_hash,
                "execution_environment_hash": self.frozen_inputs.execution_environment.execution_environment_hash,
            },
        )
        return Experiment(
            experiment_id=parsed_experiment_id,
            version=1,
            status=SCHEDULED,
            strategy_id=self.strategy_id,
            strategy_version_id=self.strategy_version_id,
            strategy_snapshot_hash=self.strategy_snapshot_hash,
            strategy_parameter_hash=self.strategy_parameter_hash,
            spec_hash=self.spec_hash,
            mandate=self.mandate,
            diagnostics={"repeat_status": "SAME_INPUTS_LOCKED"},
            data_snapshot_ref=self.data_snapshot_ref,
            cost_model_snapshot=self.cost_model_snapshot,
            execution_environment=self.execution_environment,
            frozen_inputs=self.frozen_inputs,
            result=None,
            events=(event,),
            repeats_experiment_id=self.experiment_id,
            invalidated_by_experiment_id=None,
            archived=False,
            created_at=parsed_created_at,
        )

    def event_types(self) -> tuple[str, ...]:
        return tuple(event.event_type for event in self.events)

    def to_payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "version": self.version,
            "status": self.status,
            "strategy_id": self.strategy_id,
            "strategy_version_id": self.strategy_version_id,
            "strategy_snapshot_hash": self.strategy_snapshot_hash,
            "strategy_parameter_hash": self.strategy_parameter_hash,
            "spec_hash": self.spec_hash,
            "mandate": _json_ready(self.mandate),
            "diagnostics": _json_ready(self.diagnostics),
            "data_snapshot_ref": None if self.data_snapshot_ref is None else self.data_snapshot_ref.to_payload(),
            "frozen_inputs": None if self.frozen_inputs is None else self.frozen_inputs.full_payload(),
            "result_hash": None if self.result is None else self.result.result_hash,
            "events": tuple(event.event_type for event in self.events),
            "repeats_experiment_id": self.repeats_experiment_id,
            "invalidated_by_experiment_id": self.invalidated_by_experiment_id,
            "archived": self.archived,
            "created_at": self.created_at,
        }

    def _to_contract_result(
        self,
        *,
        engine_result: BacktestEngineResult,
        status: str,
        completed_at: str,
        diagnostics: Mapping[str, Any],
    ) -> ExperimentResult:
        if self.frozen_inputs is None:
            raise ValueError("frozen_inputs requis")
        return ExperimentResult.from_payload(
            {
                "schema_version": "1.0",
                "experiment_id": self.experiment_id,
                "strategy_version_id": self.strategy_version_id,
                "data_snapshot_id": self.frozen_inputs.data_snapshot_ref.data_snapshot_id,
                "result_hash": engine_result.result_hash,
                "code_version": self.frozen_inputs.execution_environment.code_version,
                "status": status,
                "frozen_inputs": self.frozen_inputs.to_payload(),
                "metrics": dict(engine_result.metrics),
                "diagnostics": dict(diagnostics),
                "artifacts": tuple(dict(artifact) for artifact in engine_result.artifacts),
                "started_at": _started_at_for(self.events),
                "completed_at": completed_at,
            }
        )

    def _replace_with_event(self, *, event_type: str, occurred_at: str, payload: Mapping[str, Any], **changes: Any) -> "Experiment":
        next_version = self.version + 1
        event = DomainEvent(
            event_type=event_type,
            aggregate_id=self.experiment_id,
            aggregate_version=next_version,
            occurred_at=occurred_at,
            payload=payload,
        )
        return replace(
            self,
            version=next_version,
            events=self.events + (event,),
            **changes,
        )

    def _ensure_expected_version(self, expected_version: int) -> None:
        parsed_expected_version = _ensure_positive_integer(expected_version, "expected_version")
        if parsed_expected_version != self.version:
            raise ValueError("expected_version incoherent")

    def _ensure_status(self, expected_status: str) -> None:
        if self.status != expected_status:
            raise ValueError("transition interdite")


def compare_experiments(
    *,
    comparison_id: str,
    left: Experiment,
    right: Experiment,
) -> ExperimentComparisonResult:
    if not isinstance(left, Experiment) or not isinstance(right, Experiment):
        raise ValueError("experiences requises")
    if left.result is None or right.result is None:
        raise ValueError("resultat absent")
    if left.frozen_inputs is None or right.frozen_inputs is None:
        raise ValueError("frozen_inputs absent")
    left_inputs = left.frozen_inputs.to_payload()
    right_inputs = right.frozen_inputs.to_payload()
    inputs_match = left_inputs == right_inputs
    metrics_match = dict(left.result.metrics) == dict(right.result.metrics)
    return ExperimentComparisonResult(
        comparison_id=comparison_id,
        event_type="ExperimentComparisonCompleted",
        left_experiment_id=left.experiment_id,
        right_experiment_id=right.experiment_id,
        inputs_match=inputs_match,
        metrics_match=metrics_match,
        diagnostics={
            "strategy_parameter_hash_match": left.strategy_parameter_hash == right.strategy_parameter_hash,
            "data_snapshot_hash_match": left_inputs["data_snapshot_hash"] == right_inputs["data_snapshot_hash"],
            "cost_model_hash_match": left_inputs["cost_model_hash"] == right_inputs["cost_model_hash"],
            "execution_environment_hash_match": (
                left_inputs["execution_environment_hash"] == right_inputs["execution_environment_hash"]
            ),
            "multiple_testing_disclosure": "comparison_descriptive_only",
        },
    )


def _started_at_for(events: tuple[DomainEvent, ...]) -> str:
    for event in events:
        if event.event_type == "ExperimentStarted":
            return event.occurred_at
    raise ValueError("ExperimentStarted absent")


def _ensure_experiment_id(value: object) -> str:
    text = _ensure_text(value, "experiment_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "EXP"))
    except ValueError as exc:
        raise ValueError(f"experiment_id invalide: {exc}") from exc


def _ensure_strategy_id(value: object) -> str:
    text = _ensure_text(value, "strategy_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "STRAT"))
    except ValueError as exc:
        raise ValueError(f"strategy_id invalide: {exc}") from exc


def _ensure_strategy_version_id(value: object) -> str:
    text = _ensure_text(value, "strategy_version_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "SVER"))
    except ValueError as exc:
        raise ValueError(f"strategy_version_id invalide: {exc}") from exc


def _ensure_data_snapshot_id(value: object) -> str:
    text = _ensure_text(value, "data_snapshot_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "DATA"))
    except ValueError as exc:
        raise ValueError(f"data_snapshot_id invalide: {exc}") from exc


def _ensure_prefixed_text(value: object, prefix: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_expected_text(value: object, expected: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if text != expected:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _HASH_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text.lower()


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_date(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    datetime.strptime(text, "%Y-%m-%d")
    return text


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _ensure_text_tuple(value: Sequence[str], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} duplique")
    return parsed


def _ensure_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return dict(value)


def _freeze_mapping(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    return _json_ready(_ensure_mapping(value, field_name))


def _ensure_artifacts(value: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("artifacts invalides")
    parsed = tuple(_freeze_mapping(artifact, "artifact") for artifact in value)
    if len(parsed) == 0:
        raise ValueError("artifacts absents")
    for artifact in parsed:
        _ensure_text(artifact.get("artifact_id"), "artifact_id")
        _ensure_text(artifact.get("artifact_type"), "artifact_type")
        _ensure_hash(artifact.get("artifact_hash"), "artifact_hash")
    return parsed


def _ensure_events(value: Sequence[DomainEvent], experiment_id: str) -> tuple[DomainEvent, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, DomainEvent):
            raise ValueError("event invalide")
        if event.aggregate_id != experiment_id:
            raise ValueError("event hors aggregate")
    return events


def _ensure_experiment_status(value: object) -> str:
    text = _ensure_text(value, "status")
    if text not in {PLANNED, SCHEDULED, RUNNING, COMPLETED, FAILED, CANCELLED}:
        raise ValueError("status experience invalide")
    return text


def _ensure_no_mutable_reference(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in {"current_strategy_ref", "latest_data_ref", "live_reference", "mutable_reference"}:
                raise ValueError("reference mutable interdite")
            _ensure_no_mutable_reference(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            _ensure_no_mutable_reference(child)
    elif isinstance(value, str):
        lowered = value.lower()
        for fragment in _FORBIDDEN_REFERENCE_FRAGMENTS:
            if fragment in lowered:
                raise ValueError("reference mutable interdite")


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "BacktestEngineResult",
    "CANCELLED",
    "COMPLETED",
    "CostModelSnapshot",
    "DataSnapshotRef",
    "DomainEvent",
    "ExecutionEnvironment",
    "Experiment",
    "ExperimentComparisonResult",
    "FAILED",
    "FrozenInputs",
    "PLANNED",
    "RUNNING",
    "SCHEDULED",
    "compare_experiments",
]
