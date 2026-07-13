from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_network_boundary_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m002/validate_network_boundary_acceptance.py', 'process')
