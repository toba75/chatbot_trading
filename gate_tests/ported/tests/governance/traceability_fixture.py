from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_traceability_fixture() -> None:
    assert_native_parity('gate_tests/ported/tests/governance/traceability_fixture.py', 'git')
