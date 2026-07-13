from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_compose_config_file_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_config/validate_compose_config_file_acceptance.py', 'unit')
