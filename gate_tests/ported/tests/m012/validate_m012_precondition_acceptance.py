from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m012_precondition_acceptance() -> None:
    assert_native_parity('tests/m012/validate_m012_precondition_acceptance.ps1', 'gate_tests/ported/tests/m012/validate_m012_precondition_acceptance.py', 'unit')
