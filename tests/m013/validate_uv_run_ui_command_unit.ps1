$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.platform.ui_command import (  # noqa: E402
    build_ui_launch_configuration,
    run_ui_command,
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


with tempfile.TemporaryDirectory() as temporary_root:
    root = Path(temporary_root)
    config_dir = root / "config"
    config_dir.mkdir()
    config_path = config_dir / "application.yaml"
    config_path.write_text("configuration locale de test\n", encoding="utf-8")

    launch_configuration = build_ui_launch_configuration(repository_root=root)
    assert_equal(launch_configuration.service_id, "ui", "Le service cible doit etre ui.")
    assert_equal(launch_configuration.port, 8081, "Le port cible doit etre le port UI.")
    assert_equal(
        Path(launch_configuration.config_path),
        config_path,
        "La commande doit exiger config/application.yaml.",
    )

    calls: list[tuple[str, int, str]] = []

    def fake_serve_http(*, service_id: str, port: int, config_path: str) -> None:
        calls.append((service_id, port, config_path))

    exit_code = run_ui_command(
        argv=(),
        repository_root=root,
        serve_http=fake_serve_http,
    )
    assert_equal(exit_code, 0, "Le lancement doit retourner 0 apres delegation au runtime.")
    assert_equal(
        calls,
        [("ui", 8081, str(config_path))],
        "Le runtime local doit recevoir les parametres stricts de l'UI.",
    )

    assert_raises(
        "UV_UI_ARGUMENTS_FORBIDDEN",
        lambda: run_ui_command(
            argv=("--config", "config/application.example.yaml"),
            repository_root=root,
            serve_http=fake_serve_http,
        ),
    )

with tempfile.TemporaryDirectory() as temporary_root:
    assert_raises(
        "CONFIG_FILE_UNREADABLE",
        lambda: build_ui_launch_configuration(repository_root=Path(temporary_root)),
    )

print("Tests unitaires commande uv run ui: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_uv_run_ui_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires commande uv run ui invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
