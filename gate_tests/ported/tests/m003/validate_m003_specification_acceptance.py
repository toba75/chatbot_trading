from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m003_specification_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m003/validate_m003_specification_acceptance.py', 'unit')
