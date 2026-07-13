from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_context_registry_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m001/validate_context_registry_unit.py', 'unit')
