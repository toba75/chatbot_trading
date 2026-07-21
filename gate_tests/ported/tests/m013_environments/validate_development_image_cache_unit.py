"""Régression du cache de dépendances de l'image d'environnement."""

from __future__ import annotations

from pathlib import Path


def test_environment_image_keeps_dependencies_cached_across_application_commits() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    dockerfile = (repository_root / "deploy" / "local-compose" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    dependency_sync = "RUN uv sync --frozen --no-dev --no-install-project"
    project_sync = "RUN uv sync --frozen --no-dev --offline --no-build-isolation"
    assert dependency_sync in dockerfile
    assert project_sync in dockerfile
    assert dockerfile.index(dependency_sync) < dockerfile.index("COPY app ./app")
    assert dockerfile.index("COPY app ./app") < dockerfile.index(project_sync)
