from __future__ import annotations

from pathlib import Path


def test_precondition_m013() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert (repository_root / 'docs' / 'tasks').is_dir()
    assert (repository_root / 'docs' / 'specs').is_dir()
