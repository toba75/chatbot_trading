from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_postgres_migration_upgrade_live() -> None:
    assert_native_parity('gate_tests/ported/tests/m013_fastapi/validate_postgres_migration_upgrade_live.py', 'live')
