from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_deterministic_backtest_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m011/validate_deterministic_backtest_unit.py', 'unit')
