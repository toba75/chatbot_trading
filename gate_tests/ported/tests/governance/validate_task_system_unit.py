from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_task_system_unit() -> None:
    assert_native_parity('tests/governance/validate_task_system_unit.ps1', 'gate_tests/ported/tests/governance/validate_task_system_unit.py', 'unit')
