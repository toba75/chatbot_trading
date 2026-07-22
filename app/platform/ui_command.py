"""Refus explicite du point d'entrée local retiré par ADR-046."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Protocol

from app.platform.local_runtime import serve_http_service
from app.platform.ui_local_stack import start_local_ui_stack


_ENTRYPOINT_RETIRED = "UV_UI_ENTRYPOINT_RETIRED"


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
    _ensure_repository_root(repository_root)
    raise ValueError(
        f"{_ENTRYPOINT_RETIRED}: utiliser uv run development, uv run test ou uv run production"
    )


def run_ui_command(
    *,
    argv: Sequence[str],
    repository_root: Path,
    serve_http: ServeHttp,
    local_stack: LocalStack | None = None,
) -> int:
    tuple(argv)
    _ensure_repository_root(repository_root)
    if not callable(serve_http):
        raise TypeError("serveur UI invalide")
    if local_stack is not None and not callable(local_stack):
        raise TypeError("stack UI locale invalide")
    raise ValueError(
        f"{_ENTRYPOINT_RETIRED}: utiliser uv run development, uv run test ou uv run production"
    )


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
