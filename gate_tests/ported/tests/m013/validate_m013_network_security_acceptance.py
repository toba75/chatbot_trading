from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_m013_network_security_acceptance() -> None:
    assert_native_parity('tests/m013/validate_m013_network_security_acceptance.ps1', 'gate_tests/ported/tests/m013/validate_m013_network_security_acceptance.py', 'process')
