"""Contrats publics de santé et readiness de l'orchestrateur ASGI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient
import pytest

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)


class _RecordingDependency:
    def __init__(self, *, name: str, status: str) -> None:
        self.name = name
        self.status = status
        self.open_count = 0
        self.close_count = 0

    async def open(self) -> None:
        self.open_count += 1

    async def close(self) -> None:
        self.close_count += 1

    def readiness(self) -> DependencyReadiness:
        return DependencyReadiness(name=self.name, status=self.status)


class _FailingDependency(_RecordingDependency):
    async def open(self) -> None:
        self.open_count += 1
        raise RuntimeError("connexion PostgreSQL impossible")


def test_validate_orchestrator_asgi_health_acceptance() -> None:
    repository_root = next(
        parent for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    configuration = load_application_configuration(
        config_path=repository_root / "config/application.example.yaml",
        environment_snapshot={},
    )
    dependency = _RecordingDependency(name="document-store", status="not_wired")
    factory_calls = []

    def composition_root_factory(validated_configuration):
        factory_calls.append(validated_configuration)
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(dependency,),
            document_command_router=APIRouter(),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=composition_root_factory,
    )
    assert factory_calls == [configuration]
    assert dependency.open_count == 0

    with TestClient(application) as client:
        assert dependency.open_count == 1
        assert client.get("/health").json() == {
            "service": "orchestrator-api",
            "status": "healthy",
        }
        not_ready = client.get("/ready")
        assert not_ready.status_code == 503
        assert not_ready.json() == {
            "service": "orchestrator-api",
            "status": "not_ready",
            "environment": configuration.application.environment,
            "deployment_id": configuration.application.deployment_id,
            "configuration_hash": configuration.configuration_hash,
            "dependencies": [{"name": "document-store", "status": "not_wired"}],
        }

        dependency.status = "ready"
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {
            "service": "orchestrator-api",
            "status": "ready",
            "environment": configuration.application.environment,
            "deployment_id": configuration.application.deployment_id,
            "configuration_hash": configuration.configuration_hash,
            "dependencies": [{"name": "document-store", "status": "ready"}],
        }

    assert dependency.close_count == 1

    failing_dependency = _FailingDependency(name="postgres", status="not_wired")
    failing_application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=lambda validated: OrchestratorCompositionRoot(
            configuration=validated,
            dependencies=(failing_dependency,),
            document_command_router=APIRouter(),
        ),
    )
    with pytest.raises(RuntimeError, match="connexion PostgreSQL impossible"):
        with TestClient(failing_application):
            raise AssertionError("lifespan démarré malgré la dépendance en échec")

    with pytest.raises(TypeError):
        create_orchestrator_app(
            configuration=None,
            composition_root_factory=composition_root_factory,
        )
