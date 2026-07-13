from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_local_monitoring_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013/validate_local_monitoring_acceptance.py', 'process')
