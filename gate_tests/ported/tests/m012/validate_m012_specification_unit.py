from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m012_specification_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m012/validate_m012_specification_unit.py', 'unit')
