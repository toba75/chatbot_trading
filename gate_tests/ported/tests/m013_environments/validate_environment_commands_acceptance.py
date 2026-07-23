from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import sys
import tomllib
from types import SimpleNamespace


def test_validate_environment_commands_acceptance(monkeypatch, tmp_path, capsys) -> None:
    entrypoints_root = tmp_path / "entrypoints"
    errors_root = tmp_path / "errors"
    entrypoints_root.mkdir()
    errors_root.mkdir()
    _assert_uv_environment_entrypoints_launch_the_selected_stack(
        monkeypatch,
        entrypoints_root,
        capsys,
    )
    _assert_uv_environment_entrypoints_propagate_terminal_errors(
        monkeypatch,
        errors_root,
        capsys,
    )


def _assert_uv_environment_entrypoints_launch_the_selected_stack(monkeypatch, tmp_path, capsys) -> None:
    # Given les trois fichiers complets existent et chaque commande UV possède
    # une responsabilité explicite.
    # When l'opérateur invoque successivement les quatre entrypoints publiés.
    # Then development et production supervisent leur pile persistante tandis que
    # test exécute un cycle et test-isolation en exécute deux.
    import app.platform.environment_command as command

    scripts = tomllib.loads(
        (Path(__file__).resolve().parents[4] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["scripts"]
    expected_entrypoints = {
        "development": "app.platform.environment_command:development",
        "test": "app.platform.environment_command:test",
        "test-isolation": "app.platform.environment_command:test_isolation",
        "production": "app.platform.environment_command:production",
    }
    assert {profile: scripts.get(profile) for profile in expected_entrypoints} == expected_entrypoints
    assert "ui" not in scripts

    repository_root = Path(__file__).resolve().parents[4]
    for active_document in (
        "docs/runbooks/exploitation_locale.md",
        "docs/runbooks/ingestion_pdf.md",
        "docs/specs/m004_version_canonique_publiee.md",
        "docs/specs/ui.md",
    ):
        assert "uv run ui" not in (repository_root / active_document).read_text(encoding="utf-8")

    environments_root = tmp_path / "config" / "environments"
    environments_root.mkdir(parents=True)
    for profile in ("development", "test", "production"):
        (environments_root / f"{profile}.yaml").write_text(
            f"application:\n  environment: {profile}\n",
            encoding="utf-8",
        )

    prepared = []
    served = []
    qualified = []

    @contextmanager
    def supervised_stack(launch_configuration):
        prepared.append(launch_configuration)
        runtime_path = tmp_path / ".tmp" / f"{launch_configuration.environment}.yaml"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text("runtime\n", encoding="utf-8")
        yield replace(launch_configuration, config_path=str(runtime_path))

    def serve_http(*, service_id, port, config_path):
        served.append((service_id, port, config_path))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(command, "start_environment_compose_stack", supervised_stack)
    monkeypatch.setattr(command, "wait_environment_compose_stack", serve_http)
    monkeypatch.setattr(
        command,
        "run_test_environment_e2e",
        lambda **arguments: qualified.append(("test", arguments))
        or SimpleNamespace(
            to_mapping=lambda: {
                "environment": "test",
                "qualification_mode": "FUNCTIONAL",
                "runs": [1],
            }
        ),
    )
    monkeypatch.setattr(
        command,
        "run_test_environment_isolation_e2e",
        lambda **arguments: qualified.append(("test-isolation", arguments))
        or SimpleNamespace(
            to_mapping=lambda: {
                "environment": "test",
                "qualification_mode": "ISOLATION",
                "runs": [1, 2],
            }
        ),
    )
    if hasattr(command, "run_production_environment_e2e"):
        monkeypatch.setattr(
            command,
            "run_production_environment_e2e",
            lambda **arguments: qualified.append(("production", arguments))
            or SimpleNamespace(to_mapping=lambda: {"environment": "production"}),
        )
    original_argv = sys.argv[:]
    try:
        for profile in expected_entrypoints:
            sys.argv = [profile]
            assert getattr(command, profile.replace("-", "_"))() == 0
    finally:
        sys.argv = original_argv

    assert not hasattr(command, "_run_production_qualification")
    assert not hasattr(command, "run_production_environment_e2e")
    assert [launch.environment for launch in prepared] == ["development", "production"]
    assert [Path(launch.config_path) for launch in prepared] == [
        environments_root / "development.yaml",
        environments_root / "production.yaml",
    ]
    assert served == [
        ("ui", 8081, str(tmp_path / ".tmp" / "development.yaml")),
        ("ui", 8081, str(tmp_path / ".tmp" / "production.yaml")),
    ]
    assert qualified == [
        (
            profile,
            {
                "repository_root": tmp_path,
                "pdf_path": (
                    tmp_path
                    / "data/corpus/ostrading-environment-qualification-5-pages.pdf"
                ),
            },
        )
        for profile in ("test", "test-isolation")
    ]
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {
        "environment": "test",
        "qualification_mode": "FUNCTIONAL",
        "runs": [1],
    } in output
    assert {
        "environment": "test",
        "qualification_mode": "ISOLATION",
        "runs": [1, 2],
    } in output
    events = [event for event in output if event.get("event_type") == "environment_lifecycle"]
    assert [(event["environment"], event["state"]) for event in events] == [
        (profile, state)
        for profile in ("development", "production")
        for state in ("starting", "ready", "stopped")
    ]
    assert all(event["event_type"] == "environment_lifecycle" for event in events)


def _assert_uv_environment_entrypoints_propagate_terminal_errors(monkeypatch, tmp_path, capsys) -> None:
    # Given aucun fichier de profil n'est encore matérialisé par T-003.
    # When la commande dédiée est invoquée ou qu'une readiness réelle échoue.
    # Then elle s'arrête avec le code terminal 2, sans fallback ni service alternatif.
    import app.platform.environment_command as command

    calls = []

    @contextmanager
    def failing_stack(launch_configuration):
        calls.append(launch_configuration)
        raise ValueError("ENVIRONMENT_STACK_NOT_READY")
        yield launch_configuration

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(command, "start_environment_compose_stack", failing_stack)
    monkeypatch.setattr(
        command,
        "run_test_environment_e2e",
        lambda **_: (_ for _ in ()).throw(ValueError("CONFIG_FILE_UNREADABLE")),
    )
    monkeypatch.setattr(
        command,
        "run_test_environment_isolation_e2e",
        lambda **_: (_ for _ in ()).throw(ValueError("CONFIG_FILE_UNREADABLE")),
    )
    original_argv = sys.argv[:]
    try:
        sys.argv = ["test"]
        assert command.test() == 2
        assert "CONFIG_FILE_UNREADABLE" in capsys.readouterr().err
        assert calls == []

        sys.argv = ["test-isolation"]
        assert command.test_isolation() == 2
        assert "CONFIG_FILE_UNREADABLE" in capsys.readouterr().err
        assert calls == []

        config_path = tmp_path / "config" / "environments" / "development.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("application:\n  environment: development\n", encoding="utf-8")
        sys.argv = ["development", "--config", "config/application.yaml"]
        assert command.development() == 2
        assert "UV_ENVIRONMENT_ARGUMENTS_FORBIDDEN" in capsys.readouterr().err
        assert calls == []

        sys.argv = ["development"]
        assert command.development() == 2
        captured = capsys.readouterr()
        assert "ENVIRONMENT_STACK_NOT_READY" in captured.err
        events = [json.loads(line) for line in captured.out.splitlines()]
        assert [event["state"] for event in events] == ["starting", "failed"]
        assert len(calls) == 1
    finally:
        sys.argv = original_argv
