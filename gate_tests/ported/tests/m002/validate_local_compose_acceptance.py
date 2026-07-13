from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_local_compose_acceptance() -> None:
    assert_native_parity('tests/m002/validate_local_compose_acceptance.ps1', 'gate_tests/ported/tests/m002/validate_local_compose_acceptance.py', 'process')
