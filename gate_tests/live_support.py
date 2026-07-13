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
    port = _free_loopback_port()
    container = f"ost-gate-m013-{int(time.time() * 1000)}"
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
        replaced = configuration.replace(
            "postgresql+psycopg://app@postgres/app",
            f"postgresql+psycopg://app@127.0.0.1:{port}/app",
        ).replace("config/secrets/local/postgres_password", postgres_secret_relative).replace(
            "config/secrets/local/local_api_token", token_secret_relative
        )
        if replaced == configuration:
            raise RuntimeError("M013_RUNTIME_CONFIG_POSTGRES_MAPPING_REQUIRED")
        with tempfile.TemporaryDirectory(prefix="ost_gate_m013_") as temporary_directory:
            runtime_config = Path(temporary_directory) / "application.yaml"
            runtime_config.write_text(replaced, encoding="utf-8")
            _run(("docker", "run", "--detach", "--name", container, "--env", "POSTGRES_DB=app", "--env", "POSTGRES_USER=app", "--env", f"POSTGRES_PASSWORD={password}", "--publish", f"127.0.0.1:{port}:5432", _POSTGRES_IMAGE), "M013_POSTGRES_DOCKER_START_FAILED")
            _wait_postgres(container)
            gateway = _start((sys.executable, "-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090", "--config", str(runtime_config)), repository_root)
            api = _start((sys.executable, "-m", "app.platform.orchestrator_command", "--config", str(runtime_config)), repository_root)
            yield runtime_config, token
    finally:
        _stop(api)
        _stop(gateway)
        subprocess.run(("docker", "rm", "--force", container), capture_output=True, check=False)
        postgres_secret.unlink(missing_ok=True)
        token_secret.unlink(missing_ok=True)


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _run(command: tuple[str, ...], error_code: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{error_code}:{detail}")


def _wait_postgres(container: str) -> None:
    for _ in range(120):
        completed = subprocess.run(("docker", "exec", container, "pg_isready", "-U", "app", "-d", "app"), capture_output=True, check=False)
        if completed.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("M013_POSTGRES_DOCKER_NOT_READY")


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
