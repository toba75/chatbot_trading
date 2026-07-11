$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import tomllib

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


# Given un utilisateur veut lancer l'interface locale sans connaitre le runtime interne.
# When il execute la commande projet `uv run ui`.
# Then le script `ui` pointe vers un point d'entree stable qui demarre le service local ui.
pyproject_path = repo_root / "pyproject.toml"
assert_true(pyproject_path.is_file(), "pyproject.toml doit declarer la commande `uv run ui`.")

pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
project = pyproject.get("project")
assert_true(isinstance(project, dict), "La section [project] est requise pour les scripts uv.")
scripts = project.get("scripts")
assert_true(isinstance(scripts, dict), "La section [project.scripts] est requise.")
assert_equal(
    scripts.get("ui"),
    "app.platform.ui_command:main",
    "La commande `uv run ui` doit cibler le point d'entree UI.",
)

module = importlib.import_module("app.platform.ui_command")
assert_true(callable(getattr(module, "main", None)), "Le point d'entree UI doit exposer main().")

launch_configuration = module.build_ui_launch_configuration(repository_root=repo_root)
assert_equal(launch_configuration.service_id, "ui", "La commande doit demarrer le service ui.")
assert_equal(launch_configuration.port, 8081, "La commande doit utiliser le port UI publie.")
assert_equal(
    Path(launch_configuration.config_path),
    repo_root / "config" / "application.yaml",
    "La commande doit utiliser la configuration locale explicite.",
)
assert_true(
    Path(launch_configuration.config_path).is_file(),
    "La configuration locale requise par `uv run ui` doit exister.",
)

print("Test d'acceptation commande uv run ui: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_uv_run_ui_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Test d'acceptation commande uv run ui invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
