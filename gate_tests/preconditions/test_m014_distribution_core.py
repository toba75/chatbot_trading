from __future__ import annotations

from pathlib import Path


def test_precondition_m014_distribution_core() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert (
        repository_root / "docs" / "tasks" / "milestone_014-distribution-core"
    ).is_dir()
    assert (repository_root / "docs" / "specs" / "plan_distribution.md").is_file()
    assert (
        repository_root / "docs" / "adr" / "ADR-051-execution-granite-cuda-stricte.md"
    ).is_file()
