from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m000_precondition_report_unit() -> None:
    assert_native_parity('tests/governance/validate_m000_precondition_report_unit.ps1', 'gate_tests/ported/tests/governance/validate_m000_precondition_report_unit.py', 'git')
