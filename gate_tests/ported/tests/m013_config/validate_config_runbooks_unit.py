from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_config_runbooks_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_config/validate_config_runbooks_unit.py', 'git')
