from __future__ import annotations

from pathlib import Path
import sys


def test_validate_uv_run_ui_command_unit() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '\nfrom pathlib import Path\nimport sys\nimport tempfile\n\nrepo_root = Path(sys.argv[1])\nif str(repo_root) not in sys.path:\n    sys.path.insert(0, str(repo_root))\n\nfrom app.platform.ui_command import (  # noqa: E402\n    build_ui_launch_configuration,\n    run_ui_command,\n)\n\n\ndef assert_equal(actual: object, expected: object, message: str) -> None:\n    if actual != expected:\n        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")\n\n\ndef assert_raises(expected_fragment: str, action) -> None:\n    try:\n        action()\n    except ValueError as exc:\n        if expected_fragment not in str(exc):\n            raise AssertionError(f"Erreur inattendue: {exc}") from exc\n        return\n    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")\n\n\nwith tempfile.TemporaryDirectory() as temporary_root:\n    root = Path(temporary_root)\n    config_dir = root / "config"\n    config_dir.mkdir()\n    config_path = config_dir / "application.yaml"\n    config_path.write_text("configuration locale de test\\n", encoding="utf-8")\n\n    launch_configuration = build_ui_launch_configuration(repository_root=root)\n    assert_equal(launch_configuration.service_id, "ui", "Le service cible doit etre ui.")\n    assert_equal(launch_configuration.port, 8081, "Le port cible doit etre le port UI.")\n    assert_equal(\n        Path(launch_configuration.config_path),\n        config_path,\n        "La commande doit exiger config/application.yaml.",\n    )\n\n    calls: list[tuple[str, int, str]] = []\n\n    def fake_serve_http(*, service_id: str, port: int, config_path: str) -> None:\n        calls.append((service_id, port, config_path))\n\n    exit_code = run_ui_command(\n        argv=(),\n        repository_root=root,\n        serve_http=fake_serve_http,\n    )\n    assert_equal(exit_code, 0, "Le lancement doit retourner 0 apres delegation au runtime.")\n    assert_equal(\n        calls,\n        [("ui", 8081, str(config_path))],\n        "Le runtime local doit recevoir les parametres stricts de l\'UI.",\n    )\n\n    assert_raises(\n        "UV_UI_ARGUMENTS_FORBIDDEN",\n        lambda: run_ui_command(\n            argv=("--config", "config/application.example.yaml"),\n            repository_root=root,\n            serve_http=fake_serve_http,\n        ),\n    )\n\nwith tempfile.TemporaryDirectory() as temporary_root:\n    assert_raises(\n        "CONFIG_FILE_UNREADABLE",\n        lambda: build_ui_launch_configuration(repository_root=Path(temporary_root)),\n    )\n\nprint("Tests unitaires commande uv run ui: OK")'
        namespace = {'__name__': __name__, '__file__': str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), 'exec'), namespace)
    finally:
        sys.argv = original_argv
