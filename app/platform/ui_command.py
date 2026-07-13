"""Commande locale `uv run ui` pour lancer l'interface utilisateur."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Protocol

from app.platform.local_runtime import HTTP_SERVICE_PORTS, serve_http_service
from app.platform.ui_local_stack import start_local_ui_stack


_UI_SERVICE_ID = "ui"
_UI_CONFIG_RELATIVE_PATH = Path("config") / "application.yaml"
_ARGUMENTS_FORBIDDEN = "UV_UI_ARGUMENTS_FORBIDDEN"


@dataclass(frozen=True)
class UILaunchConfiguration:
    service_id: str
    port: int
    config_path: str


class ServeHttp(Protocol):
    def __call__(self, *, service_id: str, port: int, config_path: str) -> None:
        pass


LocalStack = Callable[[UILaunchConfiguration], AbstractContextManager[UILaunchConfiguration]]


def build_ui_launch_configuration(*, repository_root: Path) -> UILaunchConfiguration:
    root = _ensure_repository_root(repository_root)
    config_path = root / _UI_CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        raise ValueError(f"CONFIG_FILE_UNREADABLE: configuration UI absente: {config_path}")
    return UILaunchConfiguration(
        service_id=_UI_SERVICE_ID,
        port=HTTP_SERVICE_PORTS[_UI_SERVICE_ID],
        config_path=str(config_path),
    )


def run_ui_command(
    *,
    argv: Sequence[str],
    repository_root: Path,
    serve_http: ServeHttp,
    local_stack: LocalStack | None = None,
) -> int:
    parsed_argv = tuple(argv)
    if len(parsed_argv) != 0:
        raise ValueError(f"{_ARGUMENTS_FORBIDDEN}: uv run ui ne prend aucun argument")
    launch_configuration = build_ui_launch_configuration(repository_root=repository_root)
    if local_stack is None:
        serve_http(
            service_id=launch_configuration.service_id,
            port=launch_configuration.port,
            config_path=launch_configuration.config_path,
        )
        return 0
    with local_stack(launch_configuration) as runtime_configuration:
        if not isinstance(runtime_configuration, UILaunchConfiguration):
            raise ValueError("UI_LOCAL_RUNTIME_CONFIGURATION_INVALID")
        serve_http(
            service_id=runtime_configuration.service_id,
            port=runtime_configuration.port,
            config_path=runtime_configuration.config_path,
        )
    return 0


def main() -> int:
    try:
        return run_ui_command(
            argv=tuple(sys.argv[1:]),
            repository_root=Path.cwd(),
            serve_http=serve_http_service,
            local_stack=start_local_ui_stack,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _ensure_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("UV_UI_REPOSITORY_ROOT_INVALID: chemin de dépôt invalide")
    root = value.resolve()
    if not root.is_dir():
        raise ValueError(f"UV_UI_REPOSITORY_ROOT_INVALID: chemin de dépôt absent: {root}")
    return root


__all__ = [
    "ServeHttp",
    "LocalStack",
    "UILaunchConfiguration",
    "build_ui_launch_configuration",
    "main",
    "run_ui_command",
]
