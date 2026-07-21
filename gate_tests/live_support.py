"""Harness Python du pipeline réel M-013, sans substitution du Spark externe."""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_POSTGRES_IMAGE = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
_QDRANT_IMAGE = "qdrant/qdrant@sha256:318c11b72aaab96b36e9662ad244de3cabd0653a1b942d4e8191f18296c81af0"


@contextmanager
def m013_real_runtime(repository_root: Path) -> Iterator[tuple[Path, str]]:
    """Démarre les composants locaux; Spark reste obligatoirement externe et réel."""

    source_config = repository_root / "config" / "application.yaml"
    password_path = repository_root / "deploy" / "local-compose" / "secrets" / "postgres_password"
    if not source_config.is_file():
        raise RuntimeError(f"M013_RUNTIME_CONFIG_REQUIRED:{source_config}")
    if not password_path.is_file():
        raise RuntimeError(f"M013_POSTGRES_SECRET_REQUIRED:{password_path}")
    password = password_path.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("M013_POSTGRES_SECRET_EMPTY")
    postgres_port, qdrant_port = _two_free_loopback_ports()
    runtime_suffix = int(time.time() * 1000)
    postgres_container = f"ost-gate-m013-postgres-{runtime_suffix}"
    qdrant_container = f"ost-gate-m013-qdrant-{runtime_suffix}"
    postgres_secret_relative = "config/secrets/local/ost_gate_m013_postgres_password"
    token_secret_relative = "config/secrets/local/ost_gate_m013_local_api_token"
    postgres_secret = repository_root / postgres_secret_relative
    token_secret = repository_root / token_secret_relative
    postgres_secret.parent.mkdir(parents=True, exist_ok=True)
    token = "m013-gate-local-token-0123456789ab"
    postgres_secret.write_text(password, encoding="utf-8")
    token_secret.write_text(token, encoding="ascii")
    gateway: subprocess.Popen[bytes] | None = None
    api: subprocess.Popen[bytes] | None = None
    try:
        configuration = source_config.read_text(encoding="utf-8")
        replaced = _replace_required(
            configuration,
            "postgresql+psycopg://app@postgres/app",
            f"postgresql+psycopg://app@127.0.0.1:{postgres_port}/app",
        )
        replaced = _replace_required(
            replaced,
            "http://qdrant:6333",
            f"http://127.0.0.1:{qdrant_port}",
        )
        replaced = _replace_required(
            replaced,
            "config/secrets/local/postgres_password", postgres_secret_relative
        )
        replaced = _replace_required(
            replaced,
            "config/secrets/local/local_api_token", token_secret_relative
        )
        with tempfile.TemporaryDirectory(prefix="ost_gate_m013_") as temporary_directory:
            runtime_root = Path(temporary_directory).resolve()
            runtime_data_root = runtime_root / "data"
            runtime_reports_root = runtime_root / "reports"
            runtime_logs_root = runtime_root / "logs"
            path_replacements = {
                "  data_root: data": f"  data_root: {runtime_data_root.as_posix()}",
                "  corpus_root: data/corpus": (
                    f"  corpus_root: {(runtime_data_root / 'corpus').as_posix()}"
                ),
                "  canonical_sources_root: data/canonical_sources": (
                    "  canonical_sources_root: "
                    f"{(runtime_data_root / 'canonical_sources').as_posix()}"
                ),
                "  qdrant_storage_root: data/qdrant": (
                    f"  qdrant_storage_root: {(runtime_data_root / 'qdrant').as_posix()}"
                ),
                "  postgres_data_root: data/postgres": (
                    f"  postgres_data_root: {(runtime_data_root / 'postgres').as_posix()}"
                ),
                "  reports_root: docs/reports": (
                    f"  reports_root: {runtime_reports_root.as_posix()}"
                ),
                "  logs_root: logs": f"  logs_root: {runtime_logs_root.as_posix()}",
                "  experiments_root: data/experiments": (
                    f"  experiments_root: {(runtime_data_root / 'experiments').as_posix()}"
                ),
                "  cache_root: data/cache": (
                    f"  cache_root: {(runtime_data_root / 'cache').as_posix()}"
                ),
            }
            for configured_path, runtime_path in path_replacements.items():
                replaced = _replace_required(replaced, configured_path, runtime_path)
            runtime_config = Path(temporary_directory) / "application.yaml"
            runtime_config.write_text(replaced, encoding="utf-8")
            _run(("docker", "run", "--detach", "--name", postgres_container, "--env", "POSTGRES_DB=app", "--env", "POSTGRES_USER=app", "--env", f"POSTGRES_PASSWORD={password}", "--publish", f"127.0.0.1:{postgres_port}:5432", _POSTGRES_IMAGE), "M013_POSTGRES_DOCKER_START_FAILED")
            _run(("docker", "run", "--detach", "--name", qdrant_container, "--publish", f"127.0.0.1:{qdrant_port}:6333", _QDRANT_IMAGE), "M013_QDRANT_DOCKER_START_FAILED")
            _wait_postgres(postgres_container)
            _wait_qdrant(qdrant_port)
            gateway = _start((sys.executable, "-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090", "--config", str(runtime_config)), repository_root)
            api = _start((sys.executable, "-m", "app.platform.orchestrator_command", "--config", str(runtime_config)), repository_root)
            yield runtime_config, token
    finally:
        _stop(api)
        _stop(gateway)
        subprocess.run(("docker", "rm", "--force", postgres_container), capture_output=True, check=False)
        subprocess.run(("docker", "rm", "--force", qdrant_container), capture_output=True, check=False)
        postgres_secret.unlink(missing_ok=True)
        token_secret.unlink(missing_ok=True)


def _two_free_loopback_ports() -> tuple[int, int]:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as postgres_listener,
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as qdrant_listener,
    ):
        postgres_listener.bind(("127.0.0.1", 0))
        qdrant_listener.bind(("127.0.0.1", 0))
        return (
            int(postgres_listener.getsockname()[1]),
            int(qdrant_listener.getsockname()[1]),
        )


def _run(command: tuple[str, ...], error_code: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{error_code}:{detail}")


def _replace_required(document: str, configured_value: str, runtime_value: str) -> str:
    if document.count(configured_value) != 1:
        raise RuntimeError(f"M013_RUNTIME_CONFIG_MAPPING_REQUIRED:{configured_value}")
    return document.replace(configured_value, runtime_value)


def _wait_postgres(container: str) -> None:
    for _ in range(120):
        completed = subprocess.run(("docker", "exec", container, "pg_isready", "-U", "app", "-d", "app"), capture_output=True, check=False)
        if completed.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("M013_POSTGRES_DOCKER_NOT_READY")


def _wait_qdrant(port: int) -> None:
    import urllib.request

    for _ in range(120):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/collections", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("M013_QDRANT_DOCKER_NOT_READY")


def _start(command: tuple[str, ...], repository_root: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(command, cwd=repository_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
