"""Backend interne de compilation SD sans execution experimentale."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_design.domain.strategy_candidate import (
    CompiledStrategyRepresentation,
    RuleExpressionValidation,
    StrategyCandidate,
)


class DeterministicStrategyCompilerBackend:
    def __init__(self) -> None:
        self.compilation_call_count = 0
        self.backtest_call_count = 0

    def compile_representation(
        self,
        *,
        candidate: StrategyCandidate,
        rule_validations: Sequence[RuleExpressionValidation],
        compiler_version: str,
    ) -> CompiledStrategyRepresentation:
        self.compilation_call_count += 1
        return CompiledStrategyRepresentation.from_candidate(
            candidate=candidate,
            rule_validations=rule_validations,
            compiler_version=compiler_version,
        )
