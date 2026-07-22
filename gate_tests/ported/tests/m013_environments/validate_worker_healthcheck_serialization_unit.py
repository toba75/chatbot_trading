"""Régression de sérialisation du heartbeat réel des workers Compose."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType


def test_worker_healthcheck_serialise_le_heartbeat_reel(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Given un heartbeat prêt, When Compose le vérifie, Then son JSON reste exact."""

    import app.platform.environment_compose as module
    from app.platform.configuration import load_application_configuration
    from app.platform.worker_environment import (
        WorkerHealthFilePublisher,
        build_worker_environment_binding,
    )

    repository_root = Path(__file__).resolve().parents[4]
    configuration_path = repository_root / "config/environments/development.yaml"
    configuration = load_application_configuration(
        config_path=configuration_path,
        environment_snapshot={},
    )
    binding = build_worker_environment_binding(
        configuration,
        worker_id="worker-documents",
    )
    health_path = (tmp_path / "worker-documents.json").resolve()
    WorkerHealthFilePublisher(
        binding=binding,
        path=health_path,
        heartbeat_interval_seconds=5,
    ).publish_once()

    def load_configuration(*, config_path, environment_snapshot):
        assert config_path == configuration_path
        assert isinstance(environment_snapshot, dict)
        return configuration

    monkeypatch.setattr(module, "load_application_configuration", load_configuration)

    observed = module.configured_worker_healthcheck(
        worker_id="worker-documents",
        config_path=configuration_path,
        health_path=health_path,
    )
    expected = json.loads(health_path.read_text(encoding="utf-8"))
    assert type(observed) is MappingProxyType
    assert dict(observed) == expected
    assert json.loads(capsys.readouterr().out) == expected
