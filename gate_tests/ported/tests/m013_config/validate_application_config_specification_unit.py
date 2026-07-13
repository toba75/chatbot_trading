from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_application_config_specification_unit() -> None:
    assert_native_parity('tests/m013_config/validate_application_config_specification_unit.ps1', 'gate_tests/ported/tests/m013_config/validate_application_config_specification_unit.py', 'git')
