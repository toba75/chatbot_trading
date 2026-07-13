from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_review3_ui_security_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_fastapi/validate_review3_ui_security_acceptance.py', 'unit')
