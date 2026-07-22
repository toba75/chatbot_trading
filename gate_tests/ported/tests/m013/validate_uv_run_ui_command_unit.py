from __future__ import annotations

from pathlib import Path

import pytest


def test_validate_uv_run_ui_command_unit() -> None:
    from app.platform.ui_command import build_ui_launch_configuration, run_ui_command

    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    calls = []
    with pytest.raises(ValueError, match="UV_UI_ENTRYPOINT_RETIRED"):
        build_ui_launch_configuration(repository_root=root)
    with pytest.raises(ValueError, match="UV_UI_ENTRYPOINT_RETIRED"):
        run_ui_command(
            argv=(),
            repository_root=root,
            serve_http=lambda **arguments: calls.append(arguments),
        )
    assert calls == []
