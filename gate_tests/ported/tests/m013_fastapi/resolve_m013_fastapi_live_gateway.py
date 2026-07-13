from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_resolve_m013_fastapi_live_gateway() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_fastapi/resolve_m013_fastapi_live_gateway.py', 'live')
