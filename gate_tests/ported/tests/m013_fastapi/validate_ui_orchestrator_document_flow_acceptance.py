from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_ui_orchestrator_document_flow_acceptance() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.py', 'process')
