from __future__ import annotations

from pathlib import Path
import sys


def test_validate_uv_run_ui_local_stack_acceptance() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '''
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.platform.ui_command import UILaunchConfiguration, run_ui_command  # noqa: E402


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


# Given un utilisateur démarre l'UI sans avoir lancé l'API ni PostgreSQL.
# When il exécute `uv run ui`.
# Then le bootstrap local prépare les dépendances réelles avant que le serveur UI reçoive la configuration runtime.
with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    source_config = root / "config" / "application.yaml"
    source_config.parent.mkdir(parents=True)
    source_config.write_text("configuration locale\\n", encoding="utf-8")
    runtime_config = root / ".tmp" / "ost-ui-runtime" / "application.yaml"
    runtime_config.parent.mkdir(parents=True)
    runtime_config.write_text("configuration runtime\\n", encoding="utf-8")

    prepared = []
    served = []

    @contextmanager
    def local_stack(launch_configuration):
        prepared.append(launch_configuration)
        yield UILaunchConfiguration(
            service_id="ui",
            port=8081,
            config_path=str(runtime_config),
        )

    def serve_http(*, service_id, port, config_path):
        served.append((service_id, port, config_path))

    exit_code = run_ui_command(
        argv=(),
        repository_root=root,
        serve_http=serve_http,
        local_stack=local_stack,
    )

    assert_equal(exit_code, 0, "Le démarrage UI doit réussir après préparation des dépendances.")
    assert_equal(len(prepared), 1, "Le bootstrap local doit être appelé exactement une fois.")
    assert_equal(prepared[0].config_path, str(source_config), "Le bootstrap doit recevoir la configuration utilisateur explicite.")
    assert_equal(
        served,
        [("ui", 8081, str(runtime_config))],
        "Le serveur UI doit utiliser uniquement la configuration runtime préparée.",
    )

print("Test d'acceptation bootstrap local uv run ui: OK")
'''
        namespace = {"__name__": __name__, "__file__": str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), "exec"), namespace)
    finally:
        sys.argv = original_argv
