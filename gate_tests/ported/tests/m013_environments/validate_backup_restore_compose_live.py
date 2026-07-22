from __future__ import annotations

from pathlib import Path


def test_backup_restore_compose_live() -> None:
    """Smoke Compose borné : archive réelle, restauration isolée et deux refus cryptographiques."""

    from ost_gate.operations.backup_restore_compose_smoke import run_backup_restore_compose_smoke

    report = run_backup_restore_compose_smoke(repository_root=Path.cwd())
    assert report["valid_restore"] == "GREEN"
    assert report["altered_archive"] == "RED"
    assert report["wrong_key"] == "RED"
    assert report["cleanup_complete"] is True
