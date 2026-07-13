from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_cost_environment_freeze_acceptance() -> None:
    assert_native_parity('tests/m011/validate_cost_environment_freeze_acceptance.ps1', 'gate_tests/ported/tests/m011/validate_cost_environment_freeze_acceptance.py', 'unit')
