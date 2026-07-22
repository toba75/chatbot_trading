from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest


def test_validate_uv_run_ui_local_stack_acceptance() -> None:
    from app.platform.ui_command import run_ui_command

    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    events = []

    @contextmanager
    def forbidden_stack(_):
        events.append("stack-started")
        yield None

    with pytest.raises(ValueError, match="UV_UI_ENTRYPOINT_RETIRED"):
        run_ui_command(
            argv=(),
            repository_root=root,
            serve_http=lambda **_: events.append("ui-served"),
            local_stack=forbidden_stack,
        )
    assert events == []
