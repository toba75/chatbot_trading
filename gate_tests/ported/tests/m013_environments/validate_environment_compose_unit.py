from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest


def test_environment_compose_unit(tmp_path: Path) -> None:
    from app.platform.environment_compose import (
        ENVIRONMENTS,
        REQUIRED_SERVICE_IDS,
        EnvironmentContainerState,
        aggregate_environment_readiness,
        environment_stack_definition,
        _parse_compose_ps,
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

    definition = definitions["development"]
    ready_states = tuple(
        EnvironmentContainerState(
            service=service_id,
            container_name=f"{definition.project_name}-{service_id}-1",
            state="running",
            health="healthy",
        )
        for service_id in REQUIRED_SERVICE_IDS
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

    with pytest.raises(ValueError, match="ENVIRONMENT_STACK_SERVICE_MISSING"):
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
