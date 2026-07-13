from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m002_traceability_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m002/validate_m002_traceability_acceptance.py', 'unit')
