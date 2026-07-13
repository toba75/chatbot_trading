from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_run_m011_case() -> None:
    assert_native_parity('tests/m011/run_m011_case.ps1', 'gate_tests/ported/tests/m011/run_m011_case.py', 'unit')
