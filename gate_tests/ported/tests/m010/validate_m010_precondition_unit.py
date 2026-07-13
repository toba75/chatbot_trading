from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m010_precondition_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m010/validate_m010_precondition_unit.py', 'git')
