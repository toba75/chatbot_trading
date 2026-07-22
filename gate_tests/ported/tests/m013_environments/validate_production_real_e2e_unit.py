"""Décisions unitaires du superviseur de parcours réel production."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def test_production_real_e2e_unit(monkeypatch, tmp_path: Path, capsys) -> None:
    from app.platform.production_e2e import (
        ProductionE2EError,
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
                        "limits": {"memory": str(8 * 1024**3), "cpus": 4}
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

    import app.platform.environment_command as command

    published: list[object] = []
    expected_report = SimpleNamespace(environment="production")
    assert (
        command._run_production_qualification(
            argv=(),
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            runner=lambda **_kwargs: expected_report,
            publish_report=published.append,
        )
        == 0
    )
    assert published == [expected_report]
    with pytest.raises(ValueError, match="UV_ENVIRONMENT_ARGUMENTS_FORBIDDEN"):
        command._run_production_qualification(
            argv=("--config",),
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            runner=lambda **_kwargs: expected_report,
            publish_report=published.append,
        )

    monkeypatch.setattr(
        command,
        "run_production_environment_e2e",
        lambda **_: (_ for _ in ()).throw(ProductionE2EError("PRODUCTION_RED")),
    )
    monkeypatch.setattr(command.sys, "argv", ["production"])
    assert command.production() == 1
    assert "PRODUCTION_RED" in capsys.readouterr().err

