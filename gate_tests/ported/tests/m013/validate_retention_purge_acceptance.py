from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_retention_purge_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013/validate_retention_purge_acceptance.py', 'unit')
