"""Cas d'usage SD d'ajout et d'attribution des règles de stratégie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.domain.strategy_candidate import (
    RuleExpression,
    RuleOrigin,
    StrategyCandidate,
    StrategyRule,
)


class StrategyRuleRepository(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError

    def save(self, candidate: StrategyCandidate, *, expected_version: int) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class AddStrategyRuleCommand:
    strategy_id: str
    expected_version: int
    rule_id: str
    rule_kind: str
    expression: str

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.rule_id, "rule_id")
        _ensure_text(self.rule_kind, "rule_kind")
        _ensure_text(self.expression, "expression")


@dataclass(frozen=True)
class AssignRuleOriginCommand:
    strategy_id: str
    expected_version: int
    rule_id: str
    origin: RuleOrigin

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        _ensure_expected_version(self.expected_version)
        _ensure_text(self.rule_id, "rule_id")
        if not isinstance(self.origin, RuleOrigin):
            raise ValueError("RuleOrigin attendue")


class AddStrategyRuleHandler:
    def __init__(self, *, repository: StrategyRuleRepository) -> None:
        self._repository = repository

    def handle(self, command: AddStrategyRuleCommand) -> StrategyCandidate:
        if not isinstance(command, AddStrategyRuleCommand):
            raise ValueError("AddStrategyRuleCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        rule = StrategyRule.without_origin(
            rule_id=command.rule_id,
            rule_kind=command.rule_kind,
            expression=RuleExpression.from_text(command.expression),
        )
        updated_candidate = candidate.add_rule(
            rule=rule,
            expected_version=command.expected_version,
        )
        self._repository.save(
            updated_candidate,
            expected_version=command.expected_version,
        )
        return updated_candidate


class AssignRuleOriginHandler:
    def __init__(self, *, repository: StrategyRuleRepository) -> None:
        self._repository = repository

    def handle(self, command: AssignRuleOriginCommand) -> StrategyCandidate:
        if not isinstance(command, AssignRuleOriginCommand):
            raise ValueError("AssignRuleOriginCommand attendue")

        candidate = self._repository.get(command.strategy_id)
        updated_candidate = candidate.assign_rule_origin(
            rule_id=command.rule_id,
            origin=command.origin,
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
