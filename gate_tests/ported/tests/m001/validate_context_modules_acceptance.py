from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_context_modules_acceptance() -> None:
    assert_native_parity('tests/m001/validate_context_modules_acceptance.ps1', 'gate_tests/ported/tests/m001/validate_context_modules_acceptance.py', 'unit')
