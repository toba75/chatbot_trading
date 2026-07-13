from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_architecture_boundaries_unit() -> None:
    assert_native_parity('tests/m001/validate_architecture_boundaries_unit.ps1', 'gate_tests/ported/tests/m001/validate_architecture_boundaries_unit.py', 'unit')
