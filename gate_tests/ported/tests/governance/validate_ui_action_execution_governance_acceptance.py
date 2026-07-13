from __future__ import annotations

from pathlib import Path


def test_validate_ui_action_execution_governance_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    definition_of_done = (repository_root / "docs/governance/definition_of_done.md").read_text(
        encoding="utf-8"
    )
    ui_specification = (repository_root / "docs/specs/ui.md").read_text(encoding="utf-8")
    task = (
        repository_root
        / "docs/tasks/milestone_013-fastapi/0012_executer_actions_ui_avec_progression.md"
    ).read_text(encoding="utf-8")

    # Given une action UI asynchrone.
    # When sa clôture est contrôlée par la gouvernance.
    # Then la chaîne réelle et la progression publique sont des preuves obligatoires.
    assert "API -> outbox -> relais -> worker -> état public" in definition_of_done
    assert "progression publique" in definition_of_done
    assert "UI-019 - Action réellement exécutable et observable" in ui_specification
    assert "QUEUED` ou `RUNNING" in task
