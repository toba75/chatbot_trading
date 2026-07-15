"""Bootstrap local explicite des dépendances réelles de ``uv run ui``."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from typing import Any, Iterator
from urllib.error import URLError
from urllib.request import urlopen

from app.platform.configuration import load_application_configuration


LOCAL_POSTGRES_CONTAINER = "ostrading-ui-postgres"
LOCAL_QDRANT_CONTAINER = "ostrading-ui-qdrant"
LOCAL_POSTGRES_LABEL = "com.ostrading.managed-by"
LOCAL_POSTGRES_IMAGE = (
    "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
)
LOCAL_QDRANT_IMAGE = "qdrant/qdrant@sha256:318c11b72aaab96b36e9662ad244de3cabd0653a1b942d4e8191f18296c81af0"
LOCAL_POSTGRES_VOLUME = "ostrading-ui-postgres-data"
LOCAL_QDRANT_VOLUME = "ostrading-ui-qdrant-data"
LOCAL_POSTGRES_PORT = 55432
LOCAL_QDRANT_PORT = 56333
LOCAL_API_PORT = 8080
LOCAL_LLM_GATEWAY_PORT = 8090
_POSTGRES_SOURCE_URL = "postgresql+psycopg://app@postgres/app"
_POSTGRES_LOCAL_URL = f"postgresql+psycopg://app@127.0.0.1:{LOCAL_POSTGRES_PORT}/app"
_QDRANT_SOURCE_URL = "http://qdrant:6333"
_QDRANT_LOCAL_URL = f"http://127.0.0.1:{LOCAL_QDRANT_PORT}"
_CONTAINER_LISTEN_HOST_SOURCE = "      container_listen_host: 0.0.0.0\n"
_CONTAINER_LISTEN_HOST_LOCAL = "      container_listen_host: 127.0.0.1\n"
_API_BIND_HOST_SOURCE = "  api:\n    bind_host: 0.0.0.0\n"
_API_BIND_HOST_LOCAL = "  api:\n    bind_host: 127.0.0.1\n"
_RUNTIME_CONFIG_RELATIVE_PATH = Path(".tmp") / "ost-ui-runtime" / "application.yaml"
_POSTGRES_SECRET_RELATIVE_PATH = Path("config") / "secrets" / "local" / "postgres_password"
_API_TOKEN_SECRET_RELATIVE_PATH = Path("config") / "secrets" / "local" / "local_api_token"
_API_STARTUP_TIMEOUT_SECONDS = 60
_LLM_GATEWAY_STARTUP_TIMEOUT_SECONDS = 60
_POSTGRES_STARTUP_ATTEMPTS = 120
_DOCUMENT_WORKER_LEASE_SECONDS = 3600
_PROJECTION_WORKER_LEASE_SECONDS = 3600
_DOCUMENT_WORKER_POLL_SECONDS = 5.0
_DOCUMENT_WORKER_STARTUP_STABILITY_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class LocalUiRuntimeConfiguration:
    """Configuration éphémère servant l'UI et l'API hôte pendant une session."""

    path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_file():
            raise ValueError("UI_LOCAL_RUNTIME_CONFIG_UNREADABLE")


def build_local_ui_runtime_configuration(
    *,
    repository_root: Path,
    source_configuration_path: Path,
) -> LocalUiRuntimeConfiguration:
    """Écrit la seule adaptation réseau nécessaire au runtime hôte."""

    root = _require_repository_root(repository_root)
    source_path = _require_path_under_root(
        value=source_configuration_path,
        repository_root=root,
        error_code="UI_LOCAL_CONFIG_PATH_INVALID",
    )
    if not source_path.is_file():
        raise ValueError(f"CONFIG_FILE_UNREADABLE: configuration UI absente: {source_path}")
    source_text = source_path.read_text(encoding="utf-8-sig")
    runtime_text = source_text.replace(_POSTGRES_SOURCE_URL, _POSTGRES_LOCAL_URL)
    if runtime_text == source_text:
        raise ValueError("UI_LOCAL_POSTGRES_MAPPING_REQUIRED")
    runtime_text = runtime_text.replace(_QDRANT_SOURCE_URL, _QDRANT_LOCAL_URL)
    if _QDRANT_SOURCE_URL in runtime_text:
        raise ValueError("UI_LOCAL_QDRANT_MAPPING_REQUIRED")
    runtime_text = runtime_text.replace(
        _CONTAINER_LISTEN_HOST_SOURCE,
        _CONTAINER_LISTEN_HOST_LOCAL,
    ).replace(
        _API_BIND_HOST_SOURCE,
        _API_BIND_HOST_LOCAL,
    )
    runtime_path = root / _RUNTIME_CONFIG_RELATIVE_PATH
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(runtime_text, encoding="utf-8")
    return LocalUiRuntimeConfiguration(path=runtime_path)


@contextmanager
def start_local_ui_stack(launch_configuration: Any) -> Iterator[Any]:
    """Démarre PostgreSQL et l'API réels, puis fournit la configuration UI hôte."""

    source_config_path = _require_launch_configuration(launch_configuration)
    repository_root = _require_repository_root(source_config_path.parents[1])
    _require_available_port(port=LOCAL_API_PORT, error_code="UI_LOCAL_API_PORT_OCCUPIED")
    _require_available_port(
        port=LOCAL_LLM_GATEWAY_PORT,
        error_code="UI_LOCAL_LLM_GATEWAY_PORT_OCCUPIED",
    )
    _require_available_port(
        port=int(launch_configuration.port),
        error_code="UI_LOCAL_PORT_OCCUPIED",
    )
    _ensure_local_secret(repository_root / _POSTGRES_SECRET_RELATIVE_PATH)
    _ensure_local_secret(repository_root / _API_TOKEN_SECRET_RELATIVE_PATH)
    runtime_configuration = build_local_ui_runtime_configuration(
        repository_root=repository_root,
        source_configuration_path=source_config_path,
    )
    worker_count = _configured_worker_concurrency(runtime_configuration)
    api_process: subprocess.Popen[bytes] | None = None
    llm_gateway_process: subprocess.Popen[bytes] | None = None
    document_worker_processes: tuple[subprocess.Popen[bytes], ...] = ()
    projection_worker_processes: tuple[subprocess.Popen[bytes], ...] = ()
    postgres_started = False
    qdrant_started = False
    try:
        postgres_started = _start_local_postgres(repository_root=repository_root)
        _wait_for_postgres()
        qdrant_started = _start_local_qdrant()
        _wait_for_qdrant()
        llm_gateway_process = _start_local_llm_gateway(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
        )
        _wait_for_llm_gateway(llm_gateway_process)
        api_process = _start_orchestrator_api(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
        )
        _wait_for_api(api_process)
        document_worker_processes = _start_local_document_workers(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
            worker_count=worker_count,
        )
        _wait_for_document_workers(document_worker_processes)
        projection_worker_processes = _start_local_projection_workers(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
            worker_count=worker_count,
        )
        _wait_for_projection_workers(projection_worker_processes)
        yield replace(launch_configuration, config_path=str(runtime_configuration.path))
    finally:
        _stop_processes(projection_worker_processes)
        _stop_processes(document_worker_processes)
        _stop_process(api_process)
        _stop_process(llm_gateway_process)
        if qdrant_started:
            _stop_local_qdrant()
        if postgres_started:
            _stop_local_postgres()
        _remove_runtime_configuration(runtime_configuration)


def _require_launch_configuration(value: Any) -> Path:
    service_id = getattr(value, "service_id", None)
    config_path = getattr(value, "config_path", None)
    if service_id != "ui" or not isinstance(config_path, str) or config_path.strip() == "":
        raise ValueError("UI_LOCAL_LAUNCH_CONFIGURATION_INVALID")
    return Path(config_path).resolve()


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("UI_LOCAL_REPOSITORY_ROOT_INVALID")
    root = value.resolve()
    if not root.is_dir():
        raise ValueError(f"UI_LOCAL_REPOSITORY_ROOT_INVALID: dépôt absent: {root}")
    return root


def _require_path_under_root(*, repository_root: Path, error_code: str, value: Path) -> Path:
    root = _require_repository_root(repository_root)
    if not isinstance(value, Path):
        raise ValueError(error_code)
    path = value.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(error_code) from exc
    return path


def _require_available_port(*, port: int, error_code: str) -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65_535:
        raise ValueError(error_code)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(error_code) from exc


def _ensure_local_secret(path: Path) -> None:
    if not isinstance(path, Path):
        raise ValueError("UI_LOCAL_SECRET_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _require_secret_value(path)
        return
    value = secrets.token_urlsafe(48)
    try:
        with path.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(value)
    except FileExistsError:
        _require_secret_value(path)
        return
    print(f"UI_LOCAL_SECRET_PROVISIONED: {path}")


def _require_secret_value(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"UI_LOCAL_SECRET_UNREADABLE: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if len(value.encode("utf-8")) < 32:
        raise ValueError(f"UI_LOCAL_SECRET_INVALID: {path}")
    return value


def _start_local_postgres(*, repository_root: Path) -> bool:
    _run_docker(("version", "--format", "{{.Server.Version}}"), "UI_LOCAL_DOCKER_UNAVAILABLE")
    inspect = _run_docker(
        ("container", "inspect", "--format", "{{ index .Config.Labels \"com.ostrading.managed-by\" }}", LOCAL_POSTGRES_CONTAINER),
        "UI_LOCAL_POSTGRES_INSPECTION_FAILED",
        allowed_returncodes=frozenset((0, 1)),
    )
    if inspect.returncode == 0:
        if inspect.stdout.strip() != "uv-run-ui":
            raise ValueError("UI_LOCAL_POSTGRES_OWNERSHIP_INVALID")
        _run_docker(("start", LOCAL_POSTGRES_CONTAINER), "UI_LOCAL_POSTGRES_START_FAILED")
        _require_postgres_port_mapping()
        return True
    password = _require_secret_value(repository_root / _POSTGRES_SECRET_RELATIVE_PATH)
    _run_docker(
        (
            "run",
            "--detach",
            "--name",
            LOCAL_POSTGRES_CONTAINER,
            "--label",
            f"{LOCAL_POSTGRES_LABEL}=uv-run-ui",
            "--env",
            "POSTGRES_DB=app",
            "--env",
            "POSTGRES_USER=app",
            "--env",
            f"POSTGRES_PASSWORD={password}",
            "--mount",
            f"type=volume,source={LOCAL_POSTGRES_VOLUME},target=/var/lib/postgresql/data",
            "--publish",
            f"127.0.0.1:{LOCAL_POSTGRES_PORT}:5432",
            LOCAL_POSTGRES_IMAGE,
        ),
        "UI_LOCAL_POSTGRES_START_FAILED",
    )
    _require_postgres_port_mapping()
    return True


def _require_postgres_port_mapping() -> None:
    mapping = _run_docker(
        ("port", LOCAL_POSTGRES_CONTAINER, "5432/tcp"),
        "UI_LOCAL_POSTGRES_PORT_UNREADABLE",
    ).stdout.strip()
    if mapping != f"127.0.0.1:{LOCAL_POSTGRES_PORT}":
        raise ValueError("UI_LOCAL_POSTGRES_PORT_INVALID")


def _start_local_qdrant() -> bool:
    _run_docker(("version", "--format", "{{.Server.Version}}"), "UI_LOCAL_DOCKER_UNAVAILABLE")
    inspect = _run_docker(
        (
            "container", "inspect", "--format",
            "{{ index .Config.Labels \"com.ostrading.managed-by\" }}",
            LOCAL_QDRANT_CONTAINER,
        ),
        "UI_LOCAL_QDRANT_INSPECTION_FAILED",
        allowed_returncodes=frozenset((0, 1)),
    )
    if inspect.returncode == 0:
        if inspect.stdout.strip() != "uv-run-ui":
            raise ValueError("UI_LOCAL_QDRANT_OWNERSHIP_INVALID")
        _run_docker(("start", LOCAL_QDRANT_CONTAINER), "UI_LOCAL_QDRANT_START_FAILED")
        _require_qdrant_port_mapping()
        return True
    _run_docker(
        (
            "run", "--detach", "--name", LOCAL_QDRANT_CONTAINER,
            "--label", f"{LOCAL_POSTGRES_LABEL}=uv-run-ui",
            "--mount", f"type=volume,source={LOCAL_QDRANT_VOLUME},target=/qdrant/storage",
            "--publish", f"127.0.0.1:{LOCAL_QDRANT_PORT}:6333",
            LOCAL_QDRANT_IMAGE,
        ),
        "UI_LOCAL_QDRANT_START_FAILED",
    )
    _require_qdrant_port_mapping()
    return True


def _require_qdrant_port_mapping() -> None:
    mapping = _run_docker(
        ("port", LOCAL_QDRANT_CONTAINER, "6333/tcp"),
        "UI_LOCAL_QDRANT_PORT_UNREADABLE",
    ).stdout.strip()
    if mapping != f"127.0.0.1:{LOCAL_QDRANT_PORT}":
        raise ValueError("UI_LOCAL_QDRANT_PORT_INVALID")


def _wait_for_qdrant() -> None:
    deadline = time.monotonic() + _API_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{LOCAL_QDRANT_PORT}/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise ValueError("UI_LOCAL_QDRANT_STARTUP_TIMEOUT")


def _wait_for_postgres() -> None:
    for _ in range(_POSTGRES_STARTUP_ATTEMPTS):
        result = _run_docker(
            ("exec", LOCAL_POSTGRES_CONTAINER, "pg_isready", "-U", "app", "-d", "app"),
            "UI_LOCAL_POSTGRES_READINESS_FAILED",
            allowed_returncodes=frozenset((0, 1, 2)),
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise ValueError("UI_LOCAL_POSTGRES_STARTUP_TIMEOUT")


def _start_orchestrator_api(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        (
            sys.executable,
            "-m",
            "app.platform.orchestrator_command",
            "--config",
            str(runtime_configuration.path),
        ),
        cwd=repository_root,
    )


def _start_local_llm_gateway(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        (
            sys.executable,
            "-m",
            "app.platform.local_runtime",
            "serve-http",
            "llm-gateway",
            str(LOCAL_LLM_GATEWAY_PORT),
            "--config",
            str(runtime_configuration.path),
        ),
        cwd=repository_root,
    )


def _configured_worker_concurrency(
    runtime_configuration: LocalUiRuntimeConfiguration,
) -> int:
    configuration = load_application_configuration(
        config_path=runtime_configuration.path,
        environment_snapshot={},
    )
    return _require_worker_count(configuration.services.workers.concurrency)


def _require_worker_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("UI_LOCAL_WORKER_CONCURRENCY_INVALID")
    return value


def _start_local_document_workers(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
    worker_count: int,
) -> tuple[subprocess.Popen[bytes], ...]:
    count = _require_worker_count(worker_count)
    return tuple(
        _start_local_document_worker(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
            worker_id=f"uv-run-ui-document-worker-{number:02d}",
        )
        for number in range(1, count + 1)
    )


def _start_local_document_worker(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
    worker_id: str,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        (
            sys.executable,
            "-m",
            "app.source_processing.adapters.worker_runtime",
            "--config",
            str(runtime_configuration.path),
            "--worker-id",
            worker_id,
            "--lease-seconds",
            str(_DOCUMENT_WORKER_LEASE_SECONDS),
            "--poll-seconds",
            str(_DOCUMENT_WORKER_POLL_SECONDS),
        ),
        cwd=repository_root,
    )


def _start_local_projection_workers(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
    worker_count: int,
) -> tuple[subprocess.Popen[bytes], ...]:
    count = _require_worker_count(worker_count)
    return tuple(
        _start_local_projection_worker(
            repository_root=repository_root,
            runtime_configuration=runtime_configuration,
            worker_id=f"uv-run-ui-projection-worker-{number:02d}",
        )
        for number in range(1, count + 1)
    )


def _start_local_projection_worker(
    *,
    repository_root: Path,
    runtime_configuration: LocalUiRuntimeConfiguration,
    worker_id: str,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        (
            sys.executable,
            "-m",
            "app.knowledge_access.adapters.worker_runtime",
            "--config",
            str(runtime_configuration.path),
            "--worker-id",
            worker_id,
            "--lease-seconds",
            str(_PROJECTION_WORKER_LEASE_SECONDS),
            "--poll-seconds",
            str(_DOCUMENT_WORKER_POLL_SECONDS),
        ),
        cwd=repository_root,
    )


def _wait_for_llm_gateway(llm_gateway_process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + _LLM_GATEWAY_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if llm_gateway_process.poll() is not None:
            raise ValueError("UI_LOCAL_LLM_GATEWAY_START_FAILED")
        try:
            with urlopen(
                f"http://127.0.0.1:{LOCAL_LLM_GATEWAY_PORT}/health",
                timeout=1,
            ) as response:
                if response.status != 200:
                    time.sleep(0.25)
                    continue
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
            time.sleep(0.25)
            continue
        configuration_hash = payload.get("configuration_hash") if isinstance(payload, dict) else None
        if payload == {
            "service": "llm-gateway",
            "status": "ready",
            "configuration_hash": configuration_hash,
        } and isinstance(configuration_hash, str) and len(configuration_hash) == 64:
            return
        time.sleep(0.25)
    raise ValueError("UI_LOCAL_LLM_GATEWAY_STARTUP_TIMEOUT")


def _wait_for_api(api_process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + _API_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if api_process.poll() is not None:
            raise ValueError("UI_LOCAL_API_START_FAILED")
        try:
            with urlopen(f"http://127.0.0.1:{LOCAL_API_PORT}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise ValueError("UI_LOCAL_API_STARTUP_TIMEOUT")


def _wait_for_document_workers(
    document_worker_processes: tuple[subprocess.Popen[bytes], ...],
) -> None:
    time.sleep(_DOCUMENT_WORKER_STARTUP_STABILITY_SECONDS)
    if len(document_worker_processes) == 0:
        raise ValueError("UI_LOCAL_DOCUMENT_WORKER_START_FAILED")
    for process in document_worker_processes:
        if process.poll() is not None:
            raise ValueError("UI_LOCAL_DOCUMENT_WORKER_START_FAILED")


def _wait_for_projection_workers(
    projection_worker_processes: tuple[subprocess.Popen[bytes], ...],
) -> None:
    time.sleep(_DOCUMENT_WORKER_STARTUP_STABILITY_SECONDS)
    if len(projection_worker_processes) == 0:
        raise ValueError("UI_LOCAL_PROJECTION_WORKER_START_FAILED")
    for process in projection_worker_processes:
        if process.poll() is not None:
            raise ValueError("UI_LOCAL_PROJECTION_WORKER_START_FAILED")


def _run_docker(
    arguments: tuple[str, ...],
    error_code: str,
    *,
    allowed_returncodes: frozenset[int] = frozenset((0,)),
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ("docker", *arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in allowed_returncodes:
        raise ValueError(error_code)
    return result


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _stop_processes(processes: tuple[subprocess.Popen[bytes], ...]) -> None:
    for process in processes:
        _stop_process(process)


def _stop_local_postgres() -> None:
    _run_docker(
        ("stop", LOCAL_POSTGRES_CONTAINER),
        "UI_LOCAL_POSTGRES_STOP_FAILED",
    )


def _stop_local_qdrant() -> None:
    _run_docker(
        ("stop", LOCAL_QDRANT_CONTAINER),
        "UI_LOCAL_QDRANT_STOP_FAILED",
    )


def _remove_runtime_configuration(configuration: LocalUiRuntimeConfiguration) -> None:
    runtime_path = configuration.path
    if runtime_path.exists():
        runtime_path.unlink()
    if runtime_path.parent.exists() and not any(runtime_path.parent.iterdir()):
        runtime_path.parent.rmdir()


__all__ = [
    "LocalUiRuntimeConfiguration",
    "build_local_ui_runtime_configuration",
    "start_local_ui_stack",
]
