from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m009_specification_acceptance() -> None:
    assert_native_parity('tests/m009/validate_m009_specification_acceptance.ps1', 'gate_tests/ported/tests/m009/validate_m009_specification_acceptance.py', 'unit')
