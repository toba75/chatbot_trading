$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from fastapi import APIRouter

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


async def asgi_get(application, path):
    sent_messages = []
    request_delivered = False

    async def receive():
        nonlocal request_delivered
        if request_delivered:
            return {"type": "http.disconnect"}
        request_delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent_messages.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )

    start_message = next(message for message in sent_messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in sent_messages
        if message["type"] == "http.response.body"
    )
    return start_message["status"], json.loads(body.decode("utf-8"))


class RecordingDependency:
    def __init__(self, name, status):
        self.name = name
        self.status = status
        self.open_count = 0
        self.close_count = 0

    async def open(self):
        self.open_count += 1

    async def close(self):
        self.close_count += 1

    def readiness(self):
        return DependencyReadiness(name=self.name, status=self.status)


class FailingDependency(RecordingDependency):
    async def open(self):
        self.open_count += 1
        raise RuntimeError("connexion PostgreSQL impossible")


async def scenario(repo_root):
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    dependency = RecordingDependency(name="document-store", status="not_wired")
    factory_calls = []

    def composition_root_factory(validated_configuration):
        factory_calls.append(validated_configuration)
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(dependency,),
            document_command_router=APIRouter(),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=composition_root_factory,
    )

    assert_equal(
        factory_calls,
        [configuration],
        "La composition doit enregistrer les routes avant le lifespan sans ouvrir ses dépendances.",
    )
    assert_equal(dependency.open_count, 0, "La construction ne doit ouvrir aucune dépendance.")

    async with application.router.lifespan_context(application):
        assert_equal(factory_calls, [configuration], "La composition root doit rester unique pendant le démarrage.")
        assert_equal(dependency.open_count, 1, "La dépendance doit être ouverte une seule fois par le lifespan.")

        health_status, health_body = await asgi_get(application, "/health")
        assert_equal(health_status, 200, "Le processus ASGI vivant doit répondre sur /health.")
        assert_equal(
            health_body,
            {"service": "orchestrator-api", "status": "healthy"},
            "Le contrat de santé doit rester borné à la vie du processus.",
        )

        ready_status, ready_body = await asgi_get(application, "/ready")
        assert_equal(ready_status, 503, "Une dépendance non câblée doit rendre l'API non prête.")
        assert_equal(
            ready_body,
            {
                "service": "orchestrator-api",
                "status": "not_ready",
                "dependencies": [{"name": "document-store", "status": "not_wired"}],
            },
            "La readiness doit nommer la dépendance non câblée sans fallback.",
        )

        dependency.status = "ready"
        ready_status, ready_body = await asgi_get(application, "/ready")
        assert_equal(ready_status, 200, "Toutes les dépendances prêtes doivent rendre l'API prête.")
        assert_equal(
            ready_body,
            {
                "service": "orchestrator-api",
                "status": "ready",
                "dependencies": [{"name": "document-store", "status": "ready"}],
            },
            "La readiness GREEN doit conserver le détail des dépendances obligatoires.",
        )

    assert_equal(dependency.close_count, 1, "La dépendance doit être fermée une seule fois à l'arrêt.")

    failing_dependency = FailingDependency(name="postgres", status="not_wired")

    def failing_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(failing_dependency,),
            document_command_router=APIRouter(),
        )

    failing_application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=failing_factory,
    )
    try:
        async with failing_application.router.lifespan_context(failing_application):
            raise AssertionError("Le lifespan ne doit pas démarrer après une erreur de connexion.")
    except RuntimeError as exc:
        assert_equal(str(exc), "connexion PostgreSQL impossible", "L'erreur de démarrage ne doit pas être masquée.")
    else:
        raise AssertionError("Une erreur de démarrage ne doit jamais être transformée en état healthy.")

    try:
        create_orchestrator_app(
            configuration=None,
            composition_root_factory=composition_root_factory,
        )
    except TypeError:
        pass
    else:
        raise AssertionError("Une configuration non validée doit être refusée explicitement.")


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation santé ASGI orchestratrice: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_health_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation santé ASGI orchestratrice: OK"
