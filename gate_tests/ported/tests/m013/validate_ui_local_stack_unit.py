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
from app.platform.ui_command import UILaunchConfiguration  # noqa: E402
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


# Given aucun conteneur PostgreSQL de développement n'existe encore.
# When `uv run ui` crée son conteneur local.
# Then son marqueur de propriété est exactement `com.ostrading.managed-by=uv-run-ui`.
with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    secret_path = root / "config" / "secrets" / "local" / "postgres_password"
    secret_path.parent.mkdir(parents=True)
    secret_path.write_text("a" * 32, encoding="ascii")
    docker_calls = []
    original_run_docker = ui_local_stack._run_docker

    def fake_docker_creation(arguments, error_code, *, allowed_returncodes=frozenset((0,))):
        docker_calls.append(arguments)
        if arguments[0] == "version":
            return CompletedProcess(args=arguments, returncode=0, stdout="16.0", stderr="")
        if arguments[:2] == ("container", "inspect"):
            return CompletedProcess(args=arguments, returncode=1, stdout="", stderr="")
        if arguments[0] == "run":
            label_index = arguments.index("--label")
            assert_equal(
                arguments[label_index + 1],
                "com.ostrading.managed-by=uv-run-ui",
                "Le conteneur local doit porter un marqueur de propriété non ambigu.",
            )
            return CompletedProcess(args=arguments, returncode=0, stdout="container-id", stderr="")
        if arguments[0] == "port":
            return CompletedProcess(
                args=arguments,
                returncode=0,
                stdout="127.0.0.1:55432",
                stderr="",
            )
        raise AssertionError(f"Commande Docker inattendue: {arguments}")

    ui_local_stack._run_docker = fake_docker_creation
    try:
        assert_equal(
            ui_local_stack._start_local_postgres(repository_root=root),
            True,
            "Le bootstrap doit créer le conteneur PostgreSQL local géré.",
        )
    finally:
        ui_local_stack._run_docker = original_run_docker


# Given `uv run ui` doit rendre l'API orchestratrice réellement prête.
# When la stack locale est ouverte.
# Then PostgreSQL, le llm-gateway réel et l'API démarrent dans cet ordre, puis sont arrêtés en sens inverse.
with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    source_config = root / "config" / "application.yaml"
    source_config.parent.mkdir(parents=True)
    source_config.write_text(
        "services:\\n  postgres:\\n    url: postgresql+psycopg://app@postgres/app\\n",
        encoding="utf-8",
    )
    events = []
    originals = {
        name: getattr(ui_local_stack, name)
        for name in (
            "_require_available_port",
            "_ensure_local_secret",
            "_start_local_postgres",
            "_wait_for_postgres",
            "_start_local_llm_gateway",
            "_wait_for_llm_gateway",
            "_start_orchestrator_api",
            "_wait_for_api",
            "_stop_process",
            "_stop_local_postgres",
        )
    }
    ui_local_stack._require_available_port = lambda *, port, error_code: events.append(f"port:{port}")
    ui_local_stack._ensure_local_secret = lambda path: events.append(f"secret:{path.name}")
    ui_local_stack._start_local_postgres = lambda *, repository_root: events.append("postgres-start") or True
    ui_local_stack._wait_for_postgres = lambda: events.append("postgres-ready")
    ui_local_stack._start_local_llm_gateway = (
        lambda *, repository_root, runtime_configuration: events.append("gateway-start") or "gateway"
    )
    ui_local_stack._wait_for_llm_gateway = lambda gateway_process: events.append("gateway-ready")
    ui_local_stack._start_orchestrator_api = (
        lambda *, repository_root, runtime_configuration: events.append("api-start") or "api"
    )
    ui_local_stack._wait_for_api = lambda api_process: events.append("api-ready")
    ui_local_stack._stop_process = lambda process: events.append(f"stop:{process}")
    ui_local_stack._stop_local_postgres = lambda: events.append("postgres-stop")
    try:
        with ui_local_stack.start_local_ui_stack(
            UILaunchConfiguration(service_id="ui", port=8081, config_path=str(source_config))
        ) as runtime_configuration:
            assert_equal(
                runtime_configuration.config_path,
                str(root / ".tmp" / "ost-ui-runtime" / "application.yaml"),
                "L'UI doit utiliser la configuration runtime après readiness des dépendances.",
            )
    finally:
        for name, original in originals.items():
            setattr(ui_local_stack, name, original)
    assert_equal(
        events,
        [
            "port:8080",
            "port:8090",
            "port:8081",
            "secret:postgres_password",
            "secret:local_api_token",
            "postgres-start",
            "postgres-ready",
            "gateway-start",
            "gateway-ready",
            "api-start",
            "api-ready",
            "stop:api",
            "stop:gateway",
            "postgres-stop",
        ],
        "Le bootstrap doit encadrer toutes les dépendances réelles de l'UI.",
    )

print("Tests unitaires bootstrap local uv run ui: OK")
'''
        namespace = {"__name__": __name__, "__file__": str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), "exec"), namespace)
    finally:
        sys.argv = original_argv
