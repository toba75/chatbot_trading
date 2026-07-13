from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_document_http_live_acceptance() -> None:
    assert_native_parity('tests/m013_fastapi/validate_document_http_live_acceptance.ps1', 'gate_tests/ported/tests/m013_fastapi/validate_document_http_live_acceptance.py', 'live')
