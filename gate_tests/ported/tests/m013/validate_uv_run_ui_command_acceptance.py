from __future__ import annotations

from pathlib import Path
import sys


def test_validate_uv_run_ui_command_acceptance() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = '\nimport importlib\nfrom pathlib import Path\nimport sys\nimport tomllib\n\nrepo_root = Path(sys.argv[1])\nif str(repo_root) not in sys.path:\n    sys.path.insert(0, str(repo_root))\n\n\ndef assert_equal(actual: object, expected: object, message: str) -> None:\n    if actual != expected:\n        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")\n\n\ndef assert_true(value: bool, message: str) -> None:\n    if not value:\n        raise AssertionError(message)\n\n\n# Given un utilisateur veut lancer l\'interface locale sans connaitre le runtime interne.\n# When il execute la commande projet `uv run ui`.\n# Then le script `ui` pointe vers un point d\'entree stable qui demarre le service local ui.\npyproject_path = repo_root / "pyproject.toml"\nassert_true(pyproject_path.is_file(), "pyproject.toml doit declarer la commande `uv run ui`.")\n\npyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))\nproject = pyproject.get("project")\nassert_true(isinstance(project, dict), "La section [project] est requise pour les scripts uv.")\nscripts = project.get("scripts")\nassert_true(isinstance(scripts, dict), "La section [project.scripts] est requise.")\nassert_equal(\n    scripts.get("ui"),\n    "app.platform.ui_command:main",\n    "La commande `uv run ui` doit cibler le point d\'entree UI.",\n)\n\nmodule = importlib.import_module("app.platform.ui_command")\nassert_true(callable(getattr(module, "main", None)), "Le point d\'entree UI doit exposer main().")\n\nlaunch_configuration = module.build_ui_launch_configuration(repository_root=repo_root)\nassert_equal(launch_configuration.service_id, "ui", "La commande doit demarrer le service ui.")\nassert_equal(launch_configuration.port, 8081, "La commande doit utiliser le port UI publie.")\nassert_equal(\n    Path(launch_configuration.config_path),\n    repo_root / "config" / "application.yaml",\n    "La commande doit utiliser la configuration locale explicite.",\n)\nassert_true(\n    Path(launch_configuration.config_path).is_file(),\n    "La configuration locale requise par `uv run ui` doit exister.",\n)\n\nprint("Test d\'acceptation commande uv run ui: OK")'
        namespace = {'__name__': __name__, '__file__': str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), 'exec'), namespace)
    finally:
        sys.argv = original_argv
