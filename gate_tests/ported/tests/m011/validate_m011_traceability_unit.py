from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m011_traceability_unit() -> None:
    assert_native_parity('tests/m011/validate_m011_traceability_unit.ps1', 'gate_tests/ported/tests/m011/validate_m011_traceability_unit.py', 'unit')
