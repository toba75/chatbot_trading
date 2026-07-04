"""Cas d'usage SD de déclaration et calibration des paramètres de stratégie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    ParameterDomain,
    RuleOriginType,
    StrategyCandidate,
    StrategyParameter,
    ValidationPlan,
)


class StrategyParameterRepository(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError

    def save(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class DeclareStrategyParameterCommand:
    strategy_id: str
    expected_version: int
    parameter_id: str
    name: str
    origin_type: RuleOriginType
    blocking: bool
    unresolved_reason: str

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.parameter_id, "parameter_id")
        _ensure_text(self.name, "name")
        if isinstance(self.origin_type, str) and not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type de parametre invalide")
        if not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type de parametre invalide")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking non booléen")
        _ensure_text(self.unresolved_reason, "unresolved_reason")


@dataclass(frozen=True)
class DefineCalibrationPlanCommand:
    strategy_id: str
    expected_version: int
    parameter_id: str
    lower_bound: int | float
    upper_bound: int | float
    unit: str
    calibration_protocol: str
    expected_sensitivity: str

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.parameter_id, "parameter_id")
        _ensure_number(self.lower_bound, "lower_bound")
        _ensure_number(self.upper_bound, "upper_bound")
        _ensure_text(self.unit, "unit")
        _ensure_text(self.calibration_protocol, "calibration_protocol")
        _ensure_text(self.expected_sensitivity, "expected_sensitivity")


class DeclareStrategyParameterHandler:
    def __init__(self, *, repository: StrategyParameterRepository) -> None:
        self._repository = repository

    def handle(self, command: DeclareStrategyParameterCommand) -> StrategyCandidate:
        if not isinstance(command, DeclareStrategyParameterCommand):
            raise ValueError("DeclareStrategyParameterCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        parameter = StrategyParameter.unresolved(
            parameter_id=command.parameter_id,
            name=command.name,
            origin_type=command.origin_type,
            blocking=command.blocking,
            unresolved_reason=command.unresolved_reason,
        )
        updated_candidate = candidate.add_parameter(
            parameter=parameter,
            expected_version=command.expected_version,
        )
        self._repository.save(
            updated_candidate,
            expected_version=command.expected_version,
        )
        return updated_candidate


class DefineCalibrationPlanHandler:
    def __init__(self, *, repository: StrategyParameterRepository) -> None:
        self._repository = repository

    def handle(self, command: DefineCalibrationPlanCommand) -> StrategyCandidate:
        if not isinstance(command, DefineCalibrationPlanCommand):
            raise ValueError("DefineCalibrationPlanCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        domain = ParameterDomain.from_bounds(
            lower_bound=command.lower_bound,
            upper_bound=command.upper_bound,
            unit=command.unit,
        )
        validation_plan = ValidationPlan(
            calibration_protocol=command.calibration_protocol,
            expected_sensitivity=command.expected_sensitivity,
        )
        updated_candidate = candidate.define_calibration_plan(
            parameter_id=command.parameter_id,
            domain=domain,
            validation_plan=validation_plan,
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


def _ensure_number(value: int | float, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    return value
