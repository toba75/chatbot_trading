from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m008_precondition_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m008/validate_m008_precondition_acceptance.py', 'unit')
