from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory

import app.platform.ui_local_stack as ui_local_stack
from app.platform.ui_command import UILaunchConfiguration
from app.platform.ui_local_stack import build_local_ui_runtime_configuration


def test_validate_ui_local_stack_unit() -> None:
    # Given une configuration hôte qui désigne PostgreSQL par le DNS Compose.
    # When `uv run ui` prépare son runtime local.
    # Then seule la configuration temporaire désigne les dépendances loopback.
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        source_config = root / "config" / "application.yaml"
        source_config.parent.mkdir(parents=True)
        source_text = (
            "deployment:\n"
            "  hosts:\n"
            "    docker_local:\n"
            "      container_listen_host: 0.0.0.0\n"
            "services:\n"
            "  postgres:\n"
            "    url: postgresql+psycopg://app@postgres/app\n"
            "  api:\n"
            "    bind_host: 0.0.0.0\n"
            "    port: 8080\n"
        )
        source_config.write_text(source_text, encoding="utf-8")
        runtime_configuration = build_local_ui_runtime_configuration(
            repository_root=root,
            source_configuration_path=source_config,
        )
        assert runtime_configuration.path == root / ".tmp" / "ost-ui-runtime" / "application.yaml"
        assert "127.0.0.1:55432" in runtime_configuration.path.read_text(encoding="utf-8")
        assert source_config.read_text(encoding="utf-8") == source_text

    # Given PostgreSQL initialise encore son cluster local.
    # When `pg_isready` retourne un code transitoire avant la disponibilité.
    # Then le bootstrap réessaie explicitement.
    calls: list[frozenset[int]] = []
    original_run_docker = ui_local_stack._run_docker
    original_sleep = ui_local_stack.time.sleep

    def fake_run_docker(arguments, error_code, *, allowed_returncodes=frozenset((0,))):
        del arguments, error_code
        calls.append(allowed_returncodes)
        return CompletedProcess(
            args=(),
            returncode=1 if len(calls) == 1 else 0,
            stdout="",
            stderr="",
        )

    ui_local_stack._run_docker = fake_run_docker
    ui_local_stack.time.sleep = lambda _: None
    try:
        ui_local_stack._wait_for_postgres()
    finally:
        ui_local_stack._run_docker = original_run_docker
        ui_local_stack.time.sleep = original_sleep
    assert calls == [frozenset((0, 1, 2)), frozenset((0, 1, 2))]

    # Given `uv run ui` rend le diagnostic disponible.
    # When la stack locale est ouverte.
    # Then PostgreSQL, gateway, API et worker réel sont démarrés, puis arrêtés
    # dans l'ordre inverse sans chemin de remplacement.
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        source_config = root / "config" / "application.yaml"
        source_config.parent.mkdir(parents=True)
        source_config.write_text(
            "services:\n  postgres:\n    url: postgresql+psycopg://app@postgres/app\n",
            encoding="utf-8",
        )
        events: list[str] = []
        originals = {
            name: getattr(ui_local_stack, name)
            for name in (
                "_require_available_port",
                "_ensure_local_secret",
                "_start_local_postgres",
                "_wait_for_postgres",
                "_start_local_llm_gateway",
                "_wait_for_llm_gateway",
                "_start_orchestrator_api",
                "_wait_for_api",
                "_start_local_document_worker",
                "_wait_for_document_worker",
                "_stop_process",
                "_stop_local_postgres",
            )
        }
        ui_local_stack._require_available_port = lambda *, port, error_code: events.append(f"port:{port}")
        ui_local_stack._ensure_local_secret = lambda path: events.append(f"secret:{path.name}")
        ui_local_stack._start_local_postgres = lambda *, repository_root: events.append("postgres-start") or True
        ui_local_stack._wait_for_postgres = lambda: events.append("postgres-ready")
        ui_local_stack._start_local_llm_gateway = lambda **_: events.append("gateway-start") or "gateway"
        ui_local_stack._wait_for_llm_gateway = lambda _: events.append("gateway-ready")
        ui_local_stack._start_orchestrator_api = lambda **_: events.append("api-start") or "api"
        ui_local_stack._wait_for_api = lambda _: events.append("api-ready")
        ui_local_stack._start_local_document_worker = lambda **_: events.append("worker-start") or "worker"
        ui_local_stack._wait_for_document_worker = lambda _: events.append("worker-ready")
        ui_local_stack._stop_process = lambda process: events.append(f"stop:{process}")
        ui_local_stack._stop_local_postgres = lambda: events.append("postgres-stop")
        try:
            with ui_local_stack.start_local_ui_stack(
                UILaunchConfiguration(service_id="ui", port=8081, config_path=str(source_config))
            ) as runtime:
                assert runtime.config_path == str(root / ".tmp" / "ost-ui-runtime" / "application.yaml")
        finally:
            for name, original in originals.items():
                setattr(ui_local_stack, name, original)
        assert events == [
            "port:8080", "port:8090", "port:8081",
            "secret:postgres_password", "secret:local_api_token",
            "postgres-start", "postgres-ready", "gateway-start", "gateway-ready",
            "api-start", "api-ready", "worker-start", "worker-ready",
            "stop:worker", "stop:api", "stop:gateway", "postgres-stop",
        ]
