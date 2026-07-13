from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_v1_antipatterns_unit() -> None:
    assert_native_parity('tests/m013/validate_v1_antipatterns_unit.ps1', 'gate_tests/ported/tests/m013/validate_v1_antipatterns_unit.py', 'process')
