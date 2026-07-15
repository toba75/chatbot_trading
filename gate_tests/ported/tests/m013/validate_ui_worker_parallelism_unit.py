from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import app.platform.ui_local_stack as ui_local_stack
from app.platform.ui_local_stack import build_local_ui_runtime_configuration


def test_uv_run_ui_uses_configured_worker_concurrency_for_document_and_projection_workers() -> None:
    # Given la configuration applicative déclare huit workers.
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        source_config = root / "config" / "application.yaml"
        source_config.parent.mkdir(parents=True)
        source_text = (repository_root / "config" / "application.example.yaml").read_text(encoding="utf-8")
        source_config.write_text(source_text.replace("concurrency: 2", "concurrency: 8"), encoding="utf-8")
        runtime_configuration = build_local_ui_runtime_configuration(
            repository_root=root,
            source_configuration_path=source_config,
        )

        assert ui_local_stack._configured_worker_concurrency(runtime_configuration) == 8

        calls: list[tuple[str, ...]] = []
        original_popen = ui_local_stack.subprocess.Popen

        class FakeProcess:
            def __init__(self, command, cwd):
                self.command = tuple(str(part) for part in command)
                self.cwd = cwd

            def poll(self):
                return None

        def fake_popen(command, cwd):
            calls.append(tuple(str(part) for part in command))
            return FakeProcess(command, cwd)

        ui_local_stack.subprocess.Popen = fake_popen
        try:
            document_workers = ui_local_stack._start_local_document_workers(
                repository_root=root,
                runtime_configuration=runtime_configuration,
                worker_count=8,
            )
            projection_workers = ui_local_stack._start_local_projection_workers(
                repository_root=root,
                runtime_configuration=runtime_configuration,
                worker_count=8,
            )
        finally:
            ui_local_stack.subprocess.Popen = original_popen

    # When `uv run ui` démarre les workers supervisés.
    # Then les huit processus documentaires et les huit processus projection ont des identifiants distincts.
    assert len(document_workers) == 8
    assert len(projection_workers) == 8
    document_ids = sorted(command[command.index("--worker-id") + 1] for command in calls[:8])
    projection_ids = sorted(command[command.index("--worker-id") + 1] for command in calls[8:])
    assert document_ids == [f"uv-run-ui-document-worker-{number:02d}" for number in range(1, 9)]
    assert projection_ids == [f"uv-run-ui-projection-worker-{number:02d}" for number in range(1, 9)]
