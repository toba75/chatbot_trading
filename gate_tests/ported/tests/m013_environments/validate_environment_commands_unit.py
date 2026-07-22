from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import inspect

import pytest


def test_validate_environment_commands_unit(monkeypatch, tmp_path) -> None:
    mapping_root = tmp_path / "mapping"
    failure_root = tmp_path / "failure"
    stack_root = tmp_path / "stack"
    mapping_root.mkdir()
    failure_root.mkdir()
    stack_root.mkdir()
    _assert_environment_mapping_is_closed_and_non_configurable(mapping_root)
    _assert_environment_launcher_stops_the_supervised_stack_after_failure(failure_root)
    _assert_local_stack_accepts_the_explicit_environment_configuration_path(
        monkeypatch,
        stack_root,
    )


def _assert_environment_mapping_is_closed_and_non_configurable(tmp_path) -> None:
    from app.platform.environment_command import (
        EnvironmentLaunchConfiguration,
        configuration_relative_path_for_environment,
        run_environment_command,
    )

    expected = {
        "development": Path("config/environments/development.yaml"),
        "test": Path("config/environments/test.yaml"),
        "production": Path("config/environments/production.yaml"),
    }
    assert {
        profile: configuration_relative_path_for_environment(profile)
        for profile in expected
    } == expected
    for unknown in ("", "local", "Development", None):
        with pytest.raises(ValueError, match="CONFIG_ENVIRONMENT_UNKNOWN"):
            configuration_relative_path_for_environment(unknown)  # type: ignore[arg-type]

    signature = inspect.signature(run_environment_command)
    assert signature.parameters["environment"].default is inspect.Parameter.empty
    assert signature.parameters["argv"].default is inspect.Parameter.empty

    config_path = tmp_path / expected["development"]
    config_path.parent.mkdir(parents=True)
    config_path.write_text("application:\n  environment: development\n", encoding="utf-8")
    with pytest.raises(ValueError, match="UV_ENVIRONMENT_ARGUMENTS_FORBIDDEN"):
        run_environment_command(
            environment="development",
            argv=("--config", "config/environments/test.yaml"),
            repository_root=tmp_path,
            serve_http=lambda **_: None,
            local_stack=lambda _: None,  # type: ignore[arg-type]
            publish_state=lambda _: None,
        )

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    with pytest.raises(ValueError, match="CONFIG_FILE_UNREADABLE"):
        run_environment_command(
            environment="production",
            argv=(),
            repository_root=missing_root,
            serve_http=lambda **_: None,
            local_stack=lambda _: None,  # type: ignore[arg-type]
            publish_state=lambda _: None,
        )

    source = inspect.getsource(inspect.getmodule(EnvironmentLaunchConfiguration))
    assert "config/application.yaml" not in source
    assert "os.environ" not in source
    assert "getenv" not in source


def _assert_environment_launcher_stops_the_supervised_stack_after_failure(tmp_path) -> None:
    from app.platform.environment_command import run_environment_command

    config_path = tmp_path / "config" / "environments" / "test.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("application:\n  environment: test\n", encoding="utf-8")
    states = []
    events = []

    @contextmanager
    def supervised_stack(launch_configuration):
        events.append(("enter", launch_configuration.environment, launch_configuration.config_path))
        try:
            yield launch_configuration
        finally:
            events.append(("exit", launch_configuration.environment, launch_configuration.config_path))

    def failing_server(**_):
        raise ValueError("UI_SERVER_FAILED")

    with pytest.raises(ValueError, match="UI_SERVER_FAILED"):
        run_environment_command(
            environment="test",
            argv=(),
            repository_root=tmp_path,
            serve_http=failing_server,
            local_stack=supervised_stack,
            publish_state=states.append,
        )

    assert [event.state for event in states] == ["starting", "ready", "failed"]
    assert all(event.environment == "test" for event in states)
    assert [event[0] for event in events] == ["enter", "exit"]

    states.clear()
    events.clear()

    def interrupted_server(**_):
        raise KeyboardInterrupt

    assert run_environment_command(
        environment="test",
        argv=(),
        repository_root=tmp_path,
        serve_http=interrupted_server,
        local_stack=supervised_stack,
        publish_state=states.append,
    ) == 0
    assert [event.state for event in states] == ["starting", "ready", "stopped"]
    assert [event[0] for event in events] == ["enter", "exit"]


def _assert_local_stack_accepts_the_explicit_environment_configuration_path(monkeypatch, tmp_path) -> None:
    import app.platform.ui_local_stack as local_stack
    from app.platform.environment_command import EnvironmentLaunchConfiguration

    config_path = tmp_path / "config" / "environments" / "development.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("configuration complète\n", encoding="utf-8")
    runtime_path = tmp_path / ".tmp" / "ost-ui-runtime" / "application.yaml"
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_text("configuration runtime\n", encoding="utf-8")
    events = []

    monkeypatch.setattr(local_stack, "_require_available_port", lambda **_: None)
    monkeypatch.setattr(local_stack, "_ensure_local_secret", lambda path: events.append(("secret", path)))
    monkeypatch.setattr(
        local_stack,
        "build_local_ui_runtime_configuration",
        lambda **kwargs: events.append(("build", kwargs["repository_root"]))
        or local_stack.LocalUiRuntimeConfiguration(path=runtime_path),
    )
    monkeypatch.setattr(local_stack, "_configured_worker_concurrency", lambda _: 1)
    monkeypatch.setattr(
        local_stack,
        "_start_local_postgres",
        lambda *, repository_root: events.append(("postgres", repository_root)) or True,
    )
    monkeypatch.setattr(local_stack, "_wait_for_postgres", lambda: None)
    monkeypatch.setattr(local_stack, "_start_local_qdrant", lambda: True)
    monkeypatch.setattr(local_stack, "_wait_for_qdrant", lambda: None)
    monkeypatch.setattr(local_stack, "_start_local_llm_gateway", lambda **_: None)
    monkeypatch.setattr(local_stack, "_wait_for_llm_gateway", lambda _: None)
    monkeypatch.setattr(local_stack, "_start_orchestrator_api", lambda **_: None)
    monkeypatch.setattr(local_stack, "_wait_for_api", lambda _: None)
    monkeypatch.setattr(local_stack, "_start_local_document_workers", lambda **_: (object(),))
    monkeypatch.setattr(local_stack, "_wait_for_document_workers", lambda _: None)
    monkeypatch.setattr(local_stack, "_start_local_projection_workers", lambda **_: (object(),))
    monkeypatch.setattr(local_stack, "_wait_for_projection_workers", lambda _: None)
    monkeypatch.setattr(local_stack, "_stop_processes", lambda _: None)
    monkeypatch.setattr(local_stack, "_stop_process", lambda _: None)
    monkeypatch.setattr(local_stack, "_stop_local_qdrant", lambda: None)
    monkeypatch.setattr(local_stack, "_stop_local_postgres", lambda: None)
    monkeypatch.setattr(local_stack, "_remove_runtime_configuration", lambda _: None)

    launch = EnvironmentLaunchConfiguration(
        environment="development",
        service_id="ui",
        port=8081,
        config_path=str(config_path),
    )
    with local_stack.start_local_ui_stack(launch) as runtime:
        assert runtime.environment == "development"
        assert runtime.config_path == str(runtime_path)

    assert ("build", tmp_path) in events
    assert ("postgres", tmp_path) in events
    assert all(tmp_path in path.parents for kind, path in events if kind == "secret")
