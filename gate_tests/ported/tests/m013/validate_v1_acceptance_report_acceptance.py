from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_v1_acceptance_report_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013/validate_v1_acceptance_report_acceptance.py', 'unit')
