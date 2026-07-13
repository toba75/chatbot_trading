from __future__ import annotations

from pathlib import Path
import sys


def test_validate_ui_local_stack_unit() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '''
from pathlib import Path
import sys
import tempfile

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.platform.ui_local_stack import build_local_ui_runtime_configuration  # noqa: E402
import app.platform.ui_local_stack as ui_local_stack  # noqa: E402
from subprocess import CompletedProcess


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


# Given une configuration hôte qui désigne PostgreSQL par le DNS Compose.
# When `uv run ui` prépare son runtime local.
# Then seule la configuration temporaire désigne PostgreSQL local ; la configuration utilisateur reste inchangée.
with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    source_config = root / "config" / "application.yaml"
    source_config.parent.mkdir(parents=True)
    source_text = "services:\\n  postgres:\\n    url: postgresql+psycopg://app@postgres/app\\n"
    source_config.write_text(source_text, encoding="utf-8")

    runtime_configuration = build_local_ui_runtime_configuration(
        repository_root=root,
        source_configuration_path=source_config,
    )

    assert_equal(
        runtime_configuration.path,
        root / ".tmp" / "ost-ui-runtime" / "application.yaml",
        "Le runtime doit utiliser une configuration temporaire dédiée.",
    )
    assert_equal(
        runtime_configuration.path.read_text(encoding="utf-8"),
        "services:\\n  postgres:\\n    url: postgresql+psycopg://app@127.0.0.1:55432/app\\n",
        "Le runtime doit rendre PostgreSQL hôte explicitement adressable.",
    )
    assert_equal(
        source_config.read_text(encoding="utf-8"),
        source_text,
        "La configuration utilisateur ne doit pas être modifiée.",
    )

    source_config.write_text("services:\\n  postgres:\\n    url: postgresql://invalide\\n", encoding="utf-8")
    assert_raises(
        "UI_LOCAL_POSTGRES_MAPPING_REQUIRED",
        lambda: build_local_ui_runtime_configuration(
            repository_root=root,
            source_configuration_path=source_config,
        ),
    )


# Given PostgreSQL initialise encore son cluster local.
# When `pg_isready` retourne son code transitoire 1 avant un code 0.
# Then le bootstrap attend la readiness au lieu de présenter une panne prématurée.
calls = []
original_run_docker = ui_local_stack._run_docker
original_sleep = ui_local_stack.time.sleep

def fake_run_docker(arguments, error_code, *, allowed_returncodes=frozenset((0,))):
    calls.append(allowed_returncodes)
    if len(calls) == 1:
        assert_equal(
            allowed_returncodes,
            frozenset((0, 1, 2)),
            "Le code transitoire pg_isready doit être explicitement accepté.",
        )
        return CompletedProcess(args=arguments, returncode=1, stdout="", stderr="")
    return CompletedProcess(args=arguments, returncode=0, stdout="", stderr="")

ui_local_stack._run_docker = fake_run_docker
ui_local_stack.time.sleep = lambda _: None
try:
    ui_local_stack._wait_for_postgres()
finally:
    ui_local_stack._run_docker = original_run_docker
    ui_local_stack.time.sleep = original_sleep
assert_equal(len(calls), 2, "Le bootstrap doit réessayer jusqu'à readiness PostgreSQL.")

print("Tests unitaires bootstrap local uv run ui: OK")
'''
        namespace = {"__name__": __name__, "__file__": str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), "exec"), namespace)
    finally:
        sys.argv = original_argv
