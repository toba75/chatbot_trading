from __future__ import annotations

from gate_tests.ported_support import assert_native_parity


def test_validate_backup_restore_acceptance() -> None:
    assert_native_parity('tests/m013/validate_backup_restore_acceptance.ps1', 'gate_tests/ported/tests/m013/validate_backup_restore_acceptance.py', 'git')
