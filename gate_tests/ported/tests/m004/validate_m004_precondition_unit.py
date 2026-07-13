from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m004_precondition_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m004/validate_m004_precondition_unit.py', 'git')
