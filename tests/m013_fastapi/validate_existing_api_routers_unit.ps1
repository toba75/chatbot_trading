$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from fastapi import APIRouter
from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_contract_routers import (
    build_conversation_router,
    build_evaluation_router,
    build_health_router,
    build_indexing_router,
    build_search_router,
)
import app.platform.local_runtime as local_runtime
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="router-unit", status="ready")


async def asgi_post(application, path, raw_body, headers):
    sent_messages = []
    request_delivered = False

    async def receive():
        nonlocal request_delivered
        if request_delivered:
            return {"type": "http.disconnect"}
        request_delivered = True
        return {"type": "http.request", "body": raw_body, "more_body": False}

    async def send(message):
        sent_messages.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent_messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in sent_messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body.decode("utf-8"))


async def scenario(repo_root):
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    router_factories = (
        (build_health_router, ()),
        (build_conversation_router, (configuration,)),
        (build_evaluation_router, (configuration,)),
        (build_search_router, ()),
        (build_indexing_router, ()),
    )
    for factory, arguments in router_factories:
        router = factory(*arguments)
        if not isinstance(router, APIRouter):
            raise AssertionError(f"{factory.__name__} doit construire un APIRouter séparé.")
        assert_equal(len(router.routes), 1, f"{factory.__name__} doit posséder exactement une route de surface.")

    source = inspect.getsource(local_runtime._local_post_response)
    for migrated_path in (
        "/v1/chat/completions",
        "/v1/evaluation/llm-real-path-benchmark",
        "/v1/search",
        "/v1/documents/{document_id}/index",
    ):
        if migrated_path in source:
            raise AssertionError(f"Branche migrée encore présente dans _local_post_response: {migrated_path}")

    router_source = (repo_root / "app" / "platform" / "orchestrator_contract_routers.py").read_text(encoding="utf-8")
    if "except Exception" in router_source:
        raise AssertionError("Les routeurs ne doivent contenir aucun except Exception.")
    if "Depends(" in router_source:
        raise AssertionError("L'injection FastAPI ne doit pas devenir un service locator.")

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    async with application.router.lifespan_context(application):
        invalid_json = b"{"
        invalid_headers = [(b"content-type", b"application/json"), (b"content-length", b"1")]
        assert_equal(
            await asgi_post(application, "/v1/search", invalid_json, invalid_headers),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}),
            "Un JSON invalide doit être refusé avant toute délégation.",
        )
        assert_equal(
            await asgi_post(application, "/v1/search", b"{}", [(b"content-type", b"application/json")]),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}),
            "L'absence de Content-Length doit conserver le refus explicite.",
        )
        assert_equal(
            await asgi_post(
                application,
                "/v1/search",
                b"[]",
                [(b"content-type", b"application/json"), (b"content-length", b"2")],
            ),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}),
            "Un corps JSON non objet doit rester invalide.",
        )

    assert_equal(
        local_runtime._local_post_response(service_id="orchestrator-api", path="/v1/search", body={}, application_configuration=configuration),
        (404, {"error_code": "ENDPOINT_NOT_FOUND", "path": "/v1/search"}),
        "Une route migrée ne doit disposer d'aucun fallback vers le routeur artisanal.",
    )
    assert_equal(
        local_runtime._local_post_response(service_id="service-inconnu", path="/v1/search", body={}, application_configuration=configuration),
        (404, {"error_code": "ENDPOINT_NOT_FOUND", "path": "/v1/search"}),
        "Le comportement des autres services doit rester borné.",
    )


asyncio.run(scenario(Path(sys.argv[1])))
print("Tests unitaires des routeurs API existants: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_existing_routers_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires des routeurs API existants: OK"
