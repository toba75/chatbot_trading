from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_definition_of_done_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/governance/validate_definition_of_done_unit.py', 'git')
