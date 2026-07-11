"""Commande locale `uv run ui` pour lancer l'interface utilisateur."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Protocol

from app.platform.local_runtime import HTTP_SERVICE_PORTS, serve_http_service


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
) -> int:
    parsed_argv = tuple(argv)
    if len(parsed_argv) != 0:
        raise ValueError(f"{_ARGUMENTS_FORBIDDEN}: uv run ui ne prend aucun argument")
    launch_configuration = build_ui_launch_configuration(repository_root=repository_root)
    serve_http(
        service_id=launch_configuration.service_id,
        port=launch_configuration.port,
        config_path=launch_configuration.config_path,
    )
    return 0


def main() -> int:
    try:
        return run_ui_command(
            argv=tuple(sys.argv[1:]),
            repository_root=Path.cwd(),
            serve_http=serve_http_service,
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
    "UILaunchConfiguration",
    "build_ui_launch_configuration",
    "main",
    "run_ui_command",
]
