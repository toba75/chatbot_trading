from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_runbooks_user_docs_unit() -> None:
    assert_native_parity('gate_tests/ported/tests/m013/validate_runbooks_user_docs_unit.py', 'process')
