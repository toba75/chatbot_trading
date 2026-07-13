from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m001_specification_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m001/validate_m001_specification_acceptance.py', 'unit')
