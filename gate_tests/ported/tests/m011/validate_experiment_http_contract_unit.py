from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_experiment_http_contract_unit() -> None:
    assert_native_parity('tests/m011/validate_experiment_http_contract_unit.ps1', 'gate_tests/ported/tests/m011/validate_experiment_http_contract_unit.py', 'unit')
