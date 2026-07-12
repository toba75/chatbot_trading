$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
import sys

from fastapi import APIRouter

sys.path.insert(0, sys.argv[1])

import app.platform.orchestrator_asgi as orchestrator_asgi_module
from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app, serve_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


def assert_required_parameter(callable_object, parameter_name):
    parameter = inspect.signature(callable_object).parameters[parameter_name]
    if parameter.default is not inspect.Parameter.empty:
        raise AssertionError(f"Valeur par défaut interdite pour {parameter_name}.")


class OrderedDependency:
    def __init__(self, name, events):
        self.name = name
        self.events = events
        self.readiness_count = 0

    async def open(self):
        self.events.append(f"open:{self.name}")

    async def close(self):
        self.events.append(f"close:{self.name}")

    def readiness(self):
        self.readiness_count += 1
        return DependencyReadiness(name=self.name, status="ready")


async def scenario(repo_root):
    for parameter_name in ("configuration", "composition_root_factory"):
        assert_required_parameter(create_orchestrator_app, parameter_name)
    for parameter_name in (
        "configuration",
        "dependencies",
        "document_command_router",
    ):
        assert_required_parameter(OrchestratorCompositionRoot, parameter_name)

    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    pyproject_content = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    uv_lock_content = (repo_root / "uv.lock").read_text(encoding="utf-8")
    for dependency_pin in ("fastapi==0.135.1", "uvicorn==0.41.0"):
        if dependency_pin not in pyproject_content:
            raise AssertionError(f"Dépendance exacte absente de pyproject.toml: {dependency_pin}")
    for locked_package in ('name = "fastapi"\nversion = "0.135.1"', 'name = "uvicorn"\nversion = "0.41.0"'):
        if locked_package not in uv_lock_content:
            raise AssertionError(f"Dépendance absente ou non verrouillée dans uv.lock: {locked_package!r}")

    events = []
    first = OrderedDependency("postgres", events)
    second = OrderedDependency("qdrant", events)
    root_factory_count = 0

    def root_factory(validated_configuration):
        nonlocal root_factory_count
        root_factory_count += 1
        assert_equal(validated_configuration, configuration, "La factory doit recevoir la configuration validée exacte.")
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(first, second),
            document_command_router=APIRouter(),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    assert_equal(root_factory_count, 0, "La factory ne doit pas être appelée à l'import ni à la création ASGI.")

    async with application.router.lifespan_context(application):
        assert_equal(root_factory_count, 1, "La factory doit être appelée exactement une fois par lifespan.")
        root = application.state.composition_root
        snapshot = root.readiness_snapshot()
        assert_equal(
            snapshot,
            (
                DependencyReadiness(name="postgres", status="ready"),
                DependencyReadiness(name="qdrant", status="ready"),
            ),
            "La composition root doit exposer la readiness réelle de chaque dépendance.",
        )
        assert_equal(first.readiness_count, 1, "La readiness PostgreSQL doit être interrogée une seule fois.")
        assert_equal(second.readiness_count, 1, "La readiness Qdrant doit être interrogée une seule fois.")

    assert_equal(
        events,
        ["open:postgres", "open:qdrant", "close:qdrant", "close:postgres"],
        "Le lifespan doit ouvrir dans l'ordre déclaré et fermer dans l'ordre inverse.",
    )

    uvicorn_calls = []
    original_uvicorn_run = orchestrator_asgi_module.uvicorn.run
    orchestrator_asgi_module.uvicorn.run = lambda application, **kwargs: uvicorn_calls.append((application, kwargs))
    try:
        serve_orchestrator_app(
            configuration=configuration,
            composition_root_factory=root_factory,
        )
    finally:
        orchestrator_asgi_module.uvicorn.run = original_uvicorn_run
    assert_equal(len(uvicorn_calls), 1, "Uvicorn doit être invoqué une seule fois.")
    assert_equal(
        uvicorn_calls[0][1],
        {"host": configuration.services.api.bind_host, "port": configuration.services.api.port},
        "Uvicorn doit recevoir exclusivement le bind et le port de la configuration validée.",
    )
    assert_equal(root_factory_count, 1, "Le serveur ne doit pas créer la composition avant le lifespan Uvicorn.")

    try:
        DependencyReadiness(name="postgres", status="unknown")
    except ValueError as exc:
        assert_equal(str(exc), "Statut de readiness invalide: unknown", "Le statut invalide doit rester explicite.")
    else:
        raise AssertionError("Un statut de readiness inconnu ne doit pas être accepté.")

    invalid_application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=lambda validated_configuration: object(),
    )
    try:
        async with invalid_application.router.lifespan_context(invalid_application):
            raise AssertionError("Un objet arbitraire ne doit pas devenir composition root.")
    except TypeError as exc:
        assert_equal(
            str(exc),
            "composition_root_factory doit construire OrchestratorCompositionRoot",
            "Une composition root invalide doit être refusée explicitement.",
        )
    else:
        raise AssertionError("Une composition root invalide ne doit pas démarrer l'application.")


asyncio.run(scenario(Path(sys.argv[1])))
print("Tests unitaires application factory orchestratrice: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_factory_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($exitCode -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires application factory orchestratrice: OK"
