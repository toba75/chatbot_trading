"""Décisions unitaires du superviseur de parcours réel production."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx


def test_production_real_e2e_unit(monkeypatch, tmp_path: Path) -> None:
    from app.platform.production_e2e import (
        ProductionE2EError,
        _production_red_report_guard,
        _run_production_stack_twice,
        _verify_production_compose_document,
    )

    # Given une preuve production qui doit redémarrer la même installation.
    starts: list[str] = []

    def run_stack(*, phase: str):
        starts.append(phase)
        return phase

    # When le superviseur exécute le parcours puis sa relecture.
    phases = _run_production_stack_twice(stack_runner=run_stack)

    # Then les deux phases obligatoires sont ordonnées et aucune purge n'existe.
    assert phases == ("product", "restart-read")
    assert starts == ["product", "restart-read"]

    production_document = {
        "name": "ostrading-production",
        "services": {
            "worker-documents": {
                "volumes": [
                    {
                        "source": "C:/repo/config/secrets/production",
                        "target": "/workspace/config/secrets/production",
                    }
                ],
                "deploy": {
                    "resources": {
                        "limits": {"memory": str(2 * 1024**3), "cpus": 4}
                    }
                },
                "healthcheck": {"timeout": "30s"},
            }
        },
        "volumes": {"postgres-data": {"name": "ostrading-production-postgres-data"}},
        "networks": {"core": {"name": "ostrading-production-core"}},
    }
    assert _verify_production_compose_document(production_document) is production_document

    contaminated = {
        **production_document,
        "services": {
            "worker-documents": {
                **production_document["services"]["worker-documents"],
                "volumes": [
                    {
                        "source": "C:/repo/config/secrets/test",
                        "target": "/workspace/config/secrets/test",
                    }
                ],
            }
        },
    }
    with pytest.raises(ProductionE2EError, match="NON_PRODUCTION_RESOURCE_VISIBLE"):
        _verify_production_compose_document(contaminated)

    import app.platform.production_e2e as production_e2e

    teardown_events: list[str] = []

    @contextmanager
    def stack():
        teardown_events.append("enter")
        try:
            yield
        finally:
            teardown_events.append("exit")

    monkeypatch.setattr(
        production_e2e,
        "_write_secret_free_payload",
        lambda **arguments: teardown_events.append(
            f"report:{arguments['payload']['status']}"
        ),
    )
    with pytest.raises(ProductionE2EError, match="PRODUCTION_E2E_NETWORK_FAILED"):
        with stack(), _production_red_report_guard(
            proof_id="A" * 32,
            phase="product",
            checkpoint_path=tmp_path / "production-red.json",
            configuration=SimpleNamespace(),
            repository_root=tmp_path,
        ):
            raise httpx.ConnectError("network red")
    assert teardown_events == ["enter", "report:RED", "exit"]

    import app.platform.environment_command as command

    launched: list[str] = []
    monkeypatch.setattr(
        command,
        "_run_entrypoint",
        lambda environment: launched.append(environment) or 0,
    )
    monkeypatch.setattr(command.sys, "argv", ["production"])
    assert command.production() == 0
    assert launched == ["production"]
    assert not hasattr(command, "_run_production_qualification")
