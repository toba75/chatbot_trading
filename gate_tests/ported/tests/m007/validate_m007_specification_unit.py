from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m007_specification_unit() -> None:
    assert_native_parity('tests/m007/validate_m007_specification_unit.ps1', 'gate_tests/ported/tests/m007/validate_m007_specification_unit.py', 'unit')
