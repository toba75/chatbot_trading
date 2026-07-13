from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_runbooks_user_docs_acceptance() -> None:
    assert_native_parity('tests/m013/validate_runbooks_user_docs_acceptance.ps1', 'gate_tests/ported/tests/m013/validate_runbooks_user_docs_acceptance.py', 'unit')
