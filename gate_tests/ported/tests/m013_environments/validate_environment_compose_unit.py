from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_environment_compose_unit(tmp_path: Path) -> None:
    from app.platform.environment_compose import (
        ENVIRONMENTS,
        EXPECTED_SERVICE_REPLICAS,
        REQUIRED_SERVICE_IDS,
        EnvironmentContainerState,
        aggregate_environment_readiness,
        environment_stack_definition,
        _first_environment_service_has_stopped,
        _parse_compose_ps,
        _provision_environment_secrets,
        _require_launch_profile_identity,
        _stop_environment_stack,
    )

    repository_root = tmp_path.resolve()
    expected_projects = {
        "development": "ostrading-development",
        "test": "ostrading-test",
        "production": "ostrading-production",
    }
    definitions = {
        environment: environment_stack_definition(
            environment,
            repository_root=repository_root,
        )
        for environment in ENVIRONMENTS
    }
    assert {key: value.project_name for key, value in definitions.items()} == expected_projects
    assert [definition.edge_port for definition in definitions.values()] == [18443, 19443, 20443]
    for unknown in ("", "local", "Development", None):
        with pytest.raises(ValueError, match="CONFIG_ENVIRONMENT_UNKNOWN"):
            environment_stack_definition(unknown, repository_root=repository_root)  # type: ignore[arg-type]

    # Given les neuf permutations commande/fichier des trois profils.
    # When leur identité est contrôlée avant tout effet.
    # Then seuls les trois couples diagonaux sont acceptés.
    for command_environment in ENVIRONMENTS:
        for file_environment in ENVIRONMENTS:
            selected_definition = definitions[command_environment]
            selected_path = definitions[file_environment].configuration_path
            configuration = SimpleNamespace(
                application=SimpleNamespace(environment=file_environment)
            )
            if command_environment == file_environment:
                assert _require_launch_profile_identity(
                    environment=command_environment,
                    configuration_path=selected_path,
                    definition=selected_definition,
                    configuration=configuration,
                ) is configuration
            else:
                with pytest.raises(ValueError, match="CONFIG_ENVIRONMENT_MISMATCH"):
                    _require_launch_profile_identity(
                        environment=command_environment,
                        configuration_path=selected_path,
                        definition=selected_definition,
                        configuration=configuration,
                    )

    # Un secret absent est une erreur sans création de répertoire ni fichier.
    secret_definition = definitions["test"]
    for required_path in (
        secret_definition.base_compose_path,
        secret_definition.compose_path,
        secret_definition.configuration_path,
        secret_definition.caddyfile_path,
    ):
        required_path.parent.mkdir(parents=True, exist_ok=True)
        required_path.write_text("versionné\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ENVIRONMENT_SECRET_UNREADABLE"):
        _provision_environment_secrets(secret_definition)
    assert not secret_definition.secrets_path.exists()

    # Un arrêt Compose code 1 est terminal : aucune réussite n'est présumée.
    compose_calls = []

    def strict_compose(*args, **kwargs):
        compose_calls.append((args, kwargs))
        assert kwargs.get("allowed_returncodes", frozenset({0})) == frozenset({0})

    import app.platform.environment_compose as environment_compose

    original_run_compose = environment_compose._run_compose
    environment_compose._run_compose = strict_compose
    try:
        _stop_environment_stack(
            definition=definitions["development"],
            technical_environment={
                "OSTRADING_IMAGE_REVISION": "a" * 40,
                "OSTRADING_POSTGRES_SCHEMA_VERSION": "020",
            },
        )
    finally:
        environment_compose._run_compose = original_run_compose
    assert len(compose_calls) == 1

    definition = definitions["development"]
    ready_states = tuple(
        EnvironmentContainerState(
            service=service_id,
            container_name=f"{definition.project_name}-{service_id}-{replica}",
            state="running",
            health="healthy",
        )
        for service_id in REQUIRED_SERVICE_IDS
        for replica in range(1, EXPECTED_SERVICE_REPLICAS[service_id] + 1)
    )
    readiness = aggregate_environment_readiness(
        definition,
        container_states=ready_states,
    )
    assert readiness.environment == "development"
    assert readiness.project_name == "ostrading-development"
    assert readiness.is_ready is True
    assert readiness.ready_services == REQUIRED_SERVICE_IDS

    ndjson = "\n".join(
        json.dumps(
            {
                "Service": state.service,
                "Name": state.container_name,
                "State": state.state,
                "Health": state.health,
            }
        )
        for state in ready_states
    )
    assert _parse_compose_ps(ndjson) == ready_states
    supervised_rows = [json.loads(line) | {"ExitCode": 0} for line in ndjson.splitlines()]
    supervised_document = "\n".join(json.dumps(row) for row in supervised_rows)
    assert not _first_environment_service_has_stopped(
        supervised_document,
        project_name=definition.project_name,
    )
    stopped_edge_rows = [
        row | {"State": "exited", "Health": "", "ExitCode": 0}
        if row["Service"] == "edge-gateway"
        else row
        for row in supervised_rows
    ]
    assert _first_environment_service_has_stopped(
        "\n".join(json.dumps(row) for row in stopped_edge_rows),
        project_name=definition.project_name,
    )
    stopped_worker_rows = [
        row | {"State": "exited", "Health": "", "ExitCode": 0}
        if row["Service"] == "worker-documents"
        else row
        for row in supervised_rows
    ]
    with pytest.raises(ValueError, match="ENVIRONMENT_STACK_SERVICE_EXITED.*worker-documents"):
        _first_environment_service_has_stopped(
            "\n".join(json.dumps(row) for row in stopped_worker_rows),
            project_name=definition.project_name,
        )

    with pytest.raises(ValueError, match="ENVIRONMENT_STACK_REPLICA_COUNT_INVALID"):
        aggregate_environment_readiness(
            definition,
            container_states=ready_states[:-1],
        )

    unhealthy = tuple(
        replace(state, health="unhealthy") if state.service == "worker-projection" else state
        for state in ready_states
    )
    with pytest.raises(ValueError, match="ENVIRONMENT_STACK_NOT_READY.*worker-projection"):
        aggregate_environment_readiness(
            definition,
            container_states=unhealthy,
        )

    foreign = (
        replace(ready_states[0], container_name="ostrading-production-edge-gateway-1"),
        *ready_states[1:],
    )
    with pytest.raises(ValueError, match="ENVIRONMENT_STACK_CONTAINER_MISMATCH"):
        aggregate_environment_readiness(
            definition,
            container_states=foreign,
        )

    import app.platform.environment_command as environment_command
    from app.platform.environment_compose import start_environment_compose_stack

    assert environment_command.start_environment_compose_stack is start_environment_compose_stack

    # Given le serveur PostgreSQL temporaire puis le serveur final de docker-entrypoint.
    # When Compose qualifie la disponibilité de chaque profil avant les migrations.
    # Then seul PID 1 postgres répondant réellement à SELECT 1 est déclaré sain.
    import yaml

    actual_repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    expected_databases = {
        "development": "ostrading_development",
        "test": "ostrading_test",
        "production": "ostrading_production",
    }
    for environment, database in expected_databases.items():
        compose_document = yaml.safe_load(
            (actual_repository_root / "deploy" / "environments" / f"{environment}.compose.yaml")
            .read_text(encoding="utf-8")
        )
        postgres_healthcheck = compose_document["services"]["postgres"]["healthcheck"]["test"]
        assert postgres_healthcheck == [
            "CMD-SHELL",
            (
                'test "$$(cat /proc/1/comm)" = "postgres" '
                f'&& test "$$(psql -U {database} -d {database} -Atqc \'SELECT 1\')" = "1"'
            ),
        ]
