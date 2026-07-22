from __future__ import annotations

from pathlib import Path
import tomllib


def test_validate_uv_run_ui_command_acceptance() -> None:
    # Given ADR-046 ferme la sélection aux trois profils explicites.
    # When les scripts projet publiés sont inspectés.
    # Then l'ancien script ui est absent et aucun quatrième chemin n'est proposé.
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    scripts = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert "ui" not in scripts
    assert {
        profile: scripts.get(profile)
        for profile in ("development", "test", "production")
    } == {
        "development": "app.platform.environment_command:development",
        "test": "app.platform.environment_command:test",
        "production": "app.platform.environment_command:production",
    }
