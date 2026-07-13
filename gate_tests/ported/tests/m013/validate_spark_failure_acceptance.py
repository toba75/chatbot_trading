from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_spark_failure_acceptance() -> None:
    assert_native_parity('tests/m013/validate_spark_failure_acceptance.ps1', 'gate_tests/ported/tests/m013/validate_spark_failure_acceptance.py', 'unit')
