$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$python = Get-RequiredPythonExecutable
$env:PYTHONPATH = $repoRoot
$env:PYTHONIOENCODING = "utf-8"

$scenario = @'
from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
from dataclasses import replace
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types
import urllib.error

from fastapi import APIRouter

from app.platform.configuration import load_application_configuration
import app.platform.orchestrator_asgi as asgi_module
from app.platform.orchestrator_asgi import create_orchestrator_app, serve_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.platform.orchestrator_runtime import build_orchestrator_composition_root
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import PostgresMigrationRunner
from app.platform.ui_document_api import (
    ORCHESTRATOR_API_UNAVAILABLE,
    UiDocumentApiUnavailableError,
    UrllibUiDocumentApiTransport,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


class Dependency:
    def __init__(self, name, events, *, open_error=None, close_error=None, delay=0):
        self.name = name
        self.events = events
        self.open_error = open_error
        self.close_error = close_error
        self.delay = delay
        self.ready = True

    async def open(self):
        self.events.append(f"open:{self.name}")
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.open_error:
            raise self.open_error

    async def close(self):
        self.events.append(f"close:{self.name}")
        if self.close_error:
            raise self.close_error

    def readiness(self):
        return DependencyReadiness(name=self.name, status="ready" if self.ready else "unavailable")


async def asgi_request(application, path, *, headers=()):
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await application(
        {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "GET", "scheme": "http", "path": path,
            "raw_path": path.encode("ascii"), "query_string": b"", "root_path": "",
            "headers": list(headers), "client": ("test", 50000), "server": ("api", 8080), "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    response_headers = {name.decode().lower(): value.decode() for name, value in start["headers"]}
    return start["status"], response_headers, json.loads(body)


async def main(repo_root):
    configuration = load_application_configuration(repo_root / "config/application.example.yaml", {})

    # Given deux ressources sont ouvertes puis la suivante échoue.
    # When la composition est ouverte.
    # Then toutes les ressources déjà ouvertes sont fermées sans masquer l'erreur primaire.
    events = []
    primary = RuntimeError("PRIMARY_OPEN_FAILURE")
    root = OrchestratorCompositionRoot(
        configuration=configuration,
        dependencies=(
            Dependency("first", events, close_error=RuntimeError("FIRST_CLOSE_FAILURE")),
            Dependency("second", events),
            Dependency("third", events, open_error=primary),
        ),
        document_command_router=APIRouter(),
    )
    try:
        await root.open()
    except RuntimeError as exc:
        assert exc is primary
        assert any("FIRST_CLOSE_FAILURE" in note for note in getattr(exc, "__notes__", ()))
    else:
        raise AssertionError("L'ouverture partielle devait échouer.")
    assert_equal(events, ["open:first", "open:second", "open:third", "close:second", "close:first"], "Rollback d'ouverture invalide.")

    events = []
    root = OrchestratorCompositionRoot(
        configuration=configuration,
        dependencies=(
            Dependency("first", events, close_error=RuntimeError("FIRST_CLOSE_FAILURE")),
            Dependency("second", events, close_error=RuntimeError("SECOND_CLOSE_FAILURE")),
        ),
        document_command_router=APIRouter(),
    )
    await root.open()
    try:
        await root.close()
    except RuntimeError as exc:
        assert_equal(str(exc), "SECOND_CLOSE_FAILURE", "La première erreur de fermeture en ordre inverse doit rester primaire.")
        assert any("FIRST_CLOSE_FAILURE" in note for note in getattr(exc, "__notes__", ()))
    else:
        raise AssertionError("Les erreurs de fermeture ne doivent pas être ignorées.")
    assert_equal(events[-2:], ["close:second", "close:first"], "Toutes les ressources doivent être fermées.")

    # Le connect_timeout PostgreSQL provient du budget startup validé.
    connect_calls = []
    fake_psycopg = types.SimpleNamespace(connect=lambda url, **kwargs: connect_calls.append((url, kwargs)) or object())
    previous_psycopg = sys.modules.get("psycopg")
    sys.modules["psycopg"] = fake_psycopg
    try:
        with TemporaryDirectory() as temporary_directory:
            password_path = Path(temporary_directory) / "postgres_password"
            password_path.write_text("test-password", encoding="utf-8")
            PsycopgConnectionFactory(
                connection_url="postgresql://app@postgres/app",
                password_path=password_path,
                connect_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
            ).connect()
    finally:
        if previous_psycopg is None:
            del sys.modules["psycopg"]
        else:
            sys.modules["psycopg"] = previous_psycopg
    assert_equal(
        connect_calls,
        [(
            "postgresql://app@postgres/app",
            {"password": "test-password", "connect_timeout": configuration.runtime.timeouts.startup_seconds},
        )],
        "Psycopg doit recevoir le connect_timeout validé.",
    )

    runtime_root = build_orchestrator_composition_root(configuration)
    postgres_dependency = runtime_root.dependencies[0]
    assert isinstance(postgres_dependency.migration_runner, PostgresMigrationRunner)
    assert_equal(
        postgres_dependency.connection_factory.connect_timeout_seconds,
        configuration.runtime.timeouts.startup_seconds,
        "Le timeout de connexion PostgreSQL doit être propagé.",
    )

    # Uvicorn reçoit les budgets request/shutdown et le lifespan borne startup.
    calls = []
    previous_run = asgi_module.uvicorn.run
    asgi_module.uvicorn.run = lambda application, **kwargs: calls.append(kwargs)
    try:
        serve_orchestrator_app(configuration=configuration, composition_root_factory=lambda _: runtime_root)
    finally:
        asgi_module.uvicorn.run = previous_run
    assert_equal(
        calls,
        [{
            "host": configuration.services.api.bind_host,
            "port": configuration.services.api.port,
            "timeout_keep_alive": configuration.runtime.timeouts.request_seconds,
            "timeout_graceful_shutdown": configuration.runtime.timeouts.shutdown_seconds,
        }],
        "Propagation Uvicorn invalide.",
    )

    short_runtime = replace(
        configuration.runtime,
        timeouts=replace(configuration.runtime.timeouts, startup_seconds=1, request_seconds=1),
    )
    short_configuration = replace(configuration, runtime=short_runtime)
    slow = Dependency("slow", [], delay=2)
    slow_app = create_orchestrator_app(
        configuration=short_configuration,
        composition_root_factory=lambda _: OrchestratorCompositionRoot(
            configuration=short_configuration, dependencies=(slow,), document_command_router=APIRouter()
        ),
    )
    try:
        async with slow_app.router.lifespan_context(slow_app):
            raise AssertionError("Le démarrage hors budget ne doit pas réussir.")
    except TimeoutError as exc:
        assert_equal(str(exc), "ORCHESTRATOR_STARTUP_TIMEOUT", "Timeout startup public invalide.")

    router = APIRouter()
    @router.get("/boom")
    async def boom():
        raise RuntimeError("SECRET_PAYLOAD_MUST_NOT_LEAK")
    @router.get("/slow")
    async def slow_route():
        await asyncio.sleep(2)
        return {"status": "unexpected"}

    app = create_orchestrator_app(
        configuration=short_configuration,
        composition_root_factory=lambda _: OrchestratorCompositionRoot(
            configuration=short_configuration,
            dependencies=(Dependency("postgres", []),),
            document_command_router=router,
        ),
    )
    logs = StringIO()
    with redirect_stdout(logs):
        async with app.router.lifespan_context(app):
            invalid = await asgi_request(app, "/health", headers=((b"x-trace-id", b" invalid "),))
            assert_equal(invalid[0], 400, "Une trace invalide doit produire 400.")
            assert_equal(invalid[2], {"error_code": "TRACE_ID_INVALID"}, "Erreur trace publique invalide.")
            assert invalid[1]["x-trace-id"].startswith("TRACE-")
            not_found = await asgi_request(app, "/route-absente", headers=((b"x-trace-id", b"TRACE-404"),))
            assert_equal(not_found[0], 404, "Une route absente doit conserver 404.")
            assert_equal(
                not_found[2],
                {"error_code": "ENDPOINT_NOT_FOUND", "path": "/route-absente"},
                "Erreur 404 publique invalide.",
            )
            assert_equal(not_found[1]["x-trace-id"], "TRACE-404", "Trace de l'erreur 404 absente.")
            failed = await asgi_request(app, "/boom", headers=((b"x-trace-id", b"TRACE-FAIL"),))
            assert_equal(failed[0], 500, "Une exception infrastructure doit produire 500.")
            assert_equal(failed[2], {"error_code": "ORCHESTRATOR_INTERNAL_ERROR"}, "Erreur infrastructure publique invalide.")
            assert_equal(failed[1]["x-trace-id"], "TRACE-FAIL", "Trace de l'erreur absente.")
            timed_out = await asgi_request(app, "/slow", headers=((b"x-trace-id", b"TRACE-TIMEOUT"),))
            assert_equal(timed_out[0], 504, "Une requête hors budget doit produire 504.")
            assert_equal(timed_out[2], {"error_code": "ORCHESTRATOR_REQUEST_TIMEOUT"}, "Erreur timeout publique invalide.")
    log_text = logs.getvalue()
    assert "SECRET_PAYLOAD_MUST_NOT_LEAK" not in log_text
    records = [json.loads(line) for line in log_text.splitlines()]
    request_records = [
        record for record in records
        if record["event_type"] == "orchestrator_http_request"
    ]
    assert_equal(
        [record["status_code"] for record in request_records],
        [400, 404, 500, 504],
        "Un log JSON est requis pour chaque erreur.",
    )
    internal_records = [
        record for record in records
        if record["event_type"] == "orchestrator_internal_error"
    ]
    assert_equal(len(internal_records), 1, "L'erreur interne sûre doit être observée une fois.")
    assert_equal(internal_records[0]["trace_id"], "TRACE-FAIL", "Trace interne absente.")

    # Un timeout pendant HTTPError.read() est une indisponibilité explicite.
    class TimedOutHttpError(urllib.error.HTTPError):
        def read(self, size=-1):
            del size
            raise TimeoutError("read timed out with secret")

    previous_urlopen = asgi_module.uvicorn.run  # sentinelle locale pour éviter tout fallback implicite
    import app.platform.ui_document_api as ui_module
    original_urlopen = ui_module.urllib.request.urlopen
    ui_module.urllib.request.urlopen = lambda request, timeout: (_ for _ in ()).throw(
        TimedOutHttpError(request.full_url, 503, "Unavailable", {}, BytesIO())
    )
    try:
        transport = UrllibUiDocumentApiTransport(orchestrator_origin="http://orchestrator-api:8080", timeout_seconds=1, token_path="config/secrets/local/local_api_token")
        try:
            transport.request(method="GET", path="/v1/documents", body=None, content_type=None)
        except UiDocumentApiUnavailableError as exc:
            assert_equal(str(exc), ORCHESTRATOR_API_UNAVAILABLE, "Traduction timeout HTTPError invalide.")
        else:
            raise AssertionError("Le timeout de lecture HTTPError devait être traduit.")
    finally:
        ui_module.urllib.request.urlopen = original_urlopen


asyncio.run(main(Path(sys.argv[1])))
print("Test d'acceptation runtime/opérations M13-FastAPI: OK")
'@

$scenario | & $python -B - $repoRoot
if ($LASTEXITCODE -ne 0) { throw "Test d'acceptation runtime/opérations M13-FastAPI RED." }
