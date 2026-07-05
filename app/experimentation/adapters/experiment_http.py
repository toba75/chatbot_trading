"""Adaptateur HTTP public EX pour backtests et experiences."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.experimentation.adapters.in_memory_experiment_repository import (
    ExperimentNotFoundError,
    StrategySnapshotNotFoundError,
)
from app.experimentation.application.experiment_workflow import (
    AttachCostEnvironmentCommand,
    AttachCostEnvironmentHandler,
    AttachDataSnapshotCommand,
    AttachDataSnapshotHandler,
    PlanExperimentCommand,
    PlanExperimentHandler,
    ScheduleExperimentCommand,
    ScheduleExperimentHandler,
)
from app.experimentation.domain.experiment import (
    CostModelSnapshot,
    DataSnapshotRef,
    ExecutionEnvironment,
    Experiment,
)


_POST_BACKTEST_FIELDS = frozenset(
    {
        "experiment_id",
        "strategy_snapshot_id",
        "mandate",
        "data_snapshot",
        "cost_model",
        "execution_environment",
        "frozen_at",
        "scheduled_at",
    }
)
_GET_FIELDS = frozenset()
_FORBIDDEN_FIELDS = frozenset(
    {
        "experiment_registry_table",
        "raw_engine_payload",
        "prompt",
        "prompt_text",
        "current_strategy_ref",
        "latest_data_ref",
        "market_data_payload",
        "strategy_internal_payload",
    }
)


@dataclass(frozen=True)
class HttpRequest:
    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body", allow_empty=True))


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise ValueError("status_code invalide")
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("status_code invalide")
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body", allow_empty=False))


class ExperimentHttpAdapter:
    def __init__(
        self,
        *,
        plan_handler: PlanExperimentHandler,
        attach_data_snapshot_handler: AttachDataSnapshotHandler,
        attach_cost_environment_handler: AttachCostEnvironmentHandler,
        schedule_handler: ScheduleExperimentHandler,
        repository: Any,
    ) -> None:
        self._plan_handler = plan_handler
        self._attach_data_snapshot_handler = attach_data_snapshot_handler
        self._attach_cost_environment_handler = attach_cost_environment_handler
        self._schedule_handler = schedule_handler
        self._repository = repository

    def handle(self, request: HttpRequest) -> HttpResponse:
        if not isinstance(request, HttpRequest):
            raise ValueError("HttpRequest attendu")
        strategy_id = _strategy_backtest_path(request.path)
        if request.method == "POST" and strategy_id is not None:
            return self._handle_post_backtest(strategy_id, request)
        experiment_id = _experiment_get_path(request.path)
        if request.method == "GET" and experiment_id is not None:
            return self._handle_get_experiment(experiment_id, request)
        return HttpResponse(status_code=404, body={"error_code": "ENDPOINT_NOT_FOUND"})

    def _handle_post_backtest(self, strategy_id: str, request: HttpRequest) -> HttpResponse:
        validation_error = _validate_fields(request.body, _POST_BACKTEST_FIELDS)
        if validation_error is not None:
            return validation_error
        try:
            planned = self._plan_handler.handle(
                PlanExperimentCommand(
                    experiment_id=request.body["experiment_id"],
                    strategy_snapshot_id=request.body["strategy_snapshot_id"],
                    mandate=request.body["mandate"],
                    created_at=request.body["frozen_at"],
                )
            )
            if planned.strategy_id != strategy_id:
                return HttpResponse(status_code=409, body={"error_code": "STRATEGY_SNAPSHOT_MISMATCH"})
            with_data = self._attach_data_snapshot_handler.handle(
                AttachDataSnapshotCommand(
                    experiment_id=planned.experiment_id,
                    expected_version=planned.version,
                    data_snapshot=DataSnapshotRef.from_payload(request.body["data_snapshot"]),
                )
            )
            locked = self._attach_cost_environment_handler.handle(
                AttachCostEnvironmentCommand(
                    experiment_id=with_data.experiment_id,
                    expected_version=with_data.version,
                    cost_model=CostModelSnapshot.from_payload(request.body["cost_model"]),
                    execution_environment=ExecutionEnvironment.from_payload(
                        request.body["execution_environment"]
                    ),
                    frozen_at=request.body["frozen_at"],
                )
            )
            scheduled = self._schedule_handler.handle(
                ScheduleExperimentCommand(
                    experiment_id=locked.experiment_id,
                    expected_version=locked.version,
                    scheduled_at=request.body["scheduled_at"],
                )
            )
        except StrategySnapshotNotFoundError:
            return HttpResponse(status_code=404, body={"error_code": "STRATEGY_SNAPSHOT_NOT_FOUND"})
        except ValueError as exc:
            return HttpResponse(status_code=400, body={"error_code": "HTTP_REQUEST_INVALID", "message": str(exc)})
        return HttpResponse(status_code=202, body=_public_experiment_payload(scheduled))

    def _handle_get_experiment(self, experiment_id: str, request: HttpRequest) -> HttpResponse:
        validation_error = _validate_fields(request.body, _GET_FIELDS)
        if validation_error is not None:
            return validation_error
        try:
            experiment = self._repository.get(experiment_id)
        except ExperimentNotFoundError:
            return HttpResponse(status_code=404, body={"error_code": "EXPERIMENT_NOT_FOUND"})
        return HttpResponse(status_code=200, body=_public_experiment_payload(experiment))


def _public_experiment_payload(experiment: Experiment) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_id": experiment.experiment_id,
        "status": experiment.status,
        "strategy_id": experiment.strategy_id,
        "strategy_version_id": experiment.strategy_version_id,
        "diagnostics": dict(experiment.diagnostics),
        "frozen_inputs": None,
        "result": None,
    }
    if experiment.frozen_inputs is not None:
        payload["frozen_inputs"] = experiment.frozen_inputs.to_payload()
    if experiment.result is not None:
        payload["result"] = {
            "status": experiment.result.status,
            "result_hash": experiment.result.result_hash,
            "metrics": dict(experiment.result.metrics),
            "diagnostics": dict(experiment.result.diagnostics),
            "artifacts": tuple(dict(artifact) for artifact in experiment.result.artifacts),
        }
    return payload


def _validate_fields(body: Mapping[str, Any], allowed_fields: frozenset[str]) -> HttpResponse | None:
    actual_fields = frozenset(str(key) for key in body.keys())
    if len(actual_fields & _FORBIDDEN_FIELDS) > 0:
        return HttpResponse(status_code=400, body={"error_code": "PUBLIC_STORAGE_FIELD_FORBIDDEN"})
    if actual_fields != allowed_fields:
        return HttpResponse(status_code=400, body={"error_code": "HTTP_REQUEST_INVALID"})
    return None


def _strategy_backtest_path(path: str) -> str | None:
    prefix = "/v1/strategies/"
    suffix = "/backtest"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    strategy_id = path[len(prefix) : -len(suffix)]
    if strategy_id == "" or "/" in strategy_id:
        return None
    return strategy_id


def _experiment_get_path(path: str) -> str | None:
    prefix = "/v1/experiments/"
    if not path.startswith(prefix):
        return None
    experiment_id = path[len(prefix) :]
    if experiment_id == "" or "/" in experiment_id:
        return None
    return experiment_id


def _ensure_method(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.upper():
        raise ValueError("method invalide")
    return value


def _ensure_path(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "" or not value.startswith("/"):
        raise ValueError("path invalide")
    return value


def _ensure_mapping(value: object, field_name: str, *, allow_empty: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")
    return dict(value)


__all__ = ["ExperimentHttpAdapter", "HttpRequest", "HttpResponse"]
