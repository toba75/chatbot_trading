from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_experiment_reproducibility_unit() -> None:
    assert_native_parity('tests/m011/validate_experiment_reproducibility_unit.ps1', 'gate_tests/ported/tests/m011/validate_experiment_reproducibility_unit.py', 'unit')
