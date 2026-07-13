$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
from io import StringIO
import inspect
import json
from pathlib import Path
import sys

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

sys.path.insert(0, sys.argv[1])

from app.contracts.llm_inference import LlmInferenceResponse
from app.conversation.application.public_chat import ProductConversationHandler
from app.evaluation.application.llm_real_path import LlmRealPathBenchmarkHandler
from app.platform.configuration import load_application_configuration
from app.platform.job_runtime.relay import ClaimedRelayMessage, JobOutboxRelay, RelayedJobMessage
from app.platform.orchestrator_api_models import (
    DocumentConversionResponse,
    DocumentCorpusItemResponse,
    KnowledgeProjectionResponse,
)
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.platform.orchestrator_contract_routers import build_public_contract_router
from app.platform.orchestrator_public_services import build_public_contract_services


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


class FakeInferenceGateway:
    def __init__(self):
        self.requests = []

    def infer(self, request):
        self.requests.append(request)
        if request.schema_name == "m13_reality_product_chat":
            structured = {"answer": "Réponse corrélée"}
            raw_response_id = "RAW-CHAT-REVIEW3"
        else:
            task_name = request.prompt_id.removeprefix("PROMPT-M013-REALITY-LLM-TASK-")
            structured = {
                "task_name": task_name,
                "evaluation_marker": f"M013-REALITY-{task_name}",
                "answer": f"Résultat {task_name}",
            }
            raw_response_id = f"RAW-{task_name}"
        return LlmInferenceResponse(
            status_code=200,
            payload={
                "structured_output": structured,
                "raw_response_id": raw_response_id,
                "provenance": {"provider": "vllm-spark"},
            },
            latency_ms=12.5,
        )


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="review3-api", status="ready", error_code=None)


async def asgi_request(application, method, path, body=None, *, trace_id=None):
    raw_body = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = []
    if body is not None:
        headers.extend([
            (b"content-type", b"application/json"),
            (b"content-length", str(len(raw_body)).encode("ascii")),
        ])
    if trace_id is not None:
        headers.append((b"x-trace-id", trace_id.encode("ascii")))
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": raw_body, "more_body": False}

    async def send(message):
        sent.append(message)

    caught = None
    try:
        await application(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"",
                "root_path": "",
                "headers": headers,
                "client": ("review3", 50000),
                "server": ("orchestrator-api", 8080),
                "state": {},
            },
            receive,
            send,
        )
    except BaseException as error:
        caught = error
    start = next((message for message in sent if message["type"] == "http.response.start"), None)
    raw_response = b"".join(
        message.get("body", b"") for message in sent if message["type"] == "http.response.body"
    )
    return start, raw_response, caught


def chat_body(configuration):
    return {
        "model": configuration.models.llm.served_model_name,
        "conversation_id": "CONV-M013-REVIEW3",
        "messages": [{"role": "user", "content": "Question"}],
        "trace_id": "TRACE-BODY-DIVERGENT",
        "request_id": "REQ-M013-REVIEW3",
        "idempotency_key": "IDEMP-M013-REVIEW3",
        "sampling_parameters": {"temperature": 0},
    }


async def scenario(repo_root: Path):
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    gateway = FakeInferenceGateway()
    services = build_public_contract_services(
        configuration,
        inference_gateway=gateway,
    )
    assert isinstance(services.conversation, ProductConversationHandler)
    assert isinstance(services.evaluation, LlmRealPathBenchmarkHandler)

    custom = APIRouter()

    @custom.get("/review3/internal-error")
    async def internal_error():
        raise RuntimeError("SECRET_PAYLOAD_MUST_NOT_LEAK")

    @custom.get("/review3/stream-error")
    async def stream_error():
        async def content():
            yield b"%PDF"
            raise RuntimeError("SECRET_STREAM_PAYLOAD_MUST_NOT_LEAK")
        return StreamingResponse(content(), media_type="application/pdf")

    route_bundle = APIRouter()
    route_bundle.include_router(build_public_contract_router(services))
    route_bundle.include_router(custom)
    root_factory_calls = 0

    def root_factory(validated_configuration):
        nonlocal root_factory_calls
        root_factory_calls += 1
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=route_bundle,
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    assert_equal(root_factory_calls, 1, "La composition doit enregistrer les routes avant le lifespan.")
    before = application.openapi()
    for path in (
        "/v1/chat/completions",
        "/v1/evaluation/llm-real-path-benchmark",
        "/v1/search",
        "/v1/documents/{document_id}/index",
    ):
        if path not in before["paths"]:
            raise AssertionError(f"Contrat OpenAPI absent avant lifespan: {path}")
        operation = before["paths"][path]["post"]
        if "requestBody" not in operation or "503" not in operation["responses"]:
            raise AssertionError(f"Requête ou erreur 503 non générable: {path}")

    async with application.router.lifespan_context(application):
        after = application.openapi()
        assert_equal(after, before, "OpenAPI doit rester stable avant et pendant le lifespan.")
        start, raw, error = await asgi_request(
            application,
            "POST",
            "/v1/chat/completions",
            chat_body(configuration),
            trace_id="TRACE-HTTP-REVIEW3",
        )
        assert error is None
        assert_equal(start["status"], 200, "Le contrat conversationnel doit rester nominal.")
        assert json.loads(raw.decode("utf-8"))["choices"][0]["message"]["content"] == "Réponse corrélée"
        assert_equal(gateway.requests[0].trace_id, "TRACE-HTTP-REVIEW3", "Le trace HTTP courant doit atteindre le gateway.")

        start, raw, error = await asgi_request(application, "GET", "/route-absente")
        assert error is None
        assert_equal(
            (start["status"], json.loads(raw.decode("utf-8"))),
            (404, {"error_code": "ENDPOINT_NOT_FOUND", "path": "/route-absente"}),
            "La compatibilité historique 404 doit être préservée.",
        )

        internal_logs = StringIO()
        with redirect_stdout(internal_logs):
            start, raw, error = await asgi_request(application, "GET", "/review3/internal-error", trace_id="TRACE-INTERNAL")
        assert error is None
        assert_equal(start["status"], 500, "L'erreur interne doit être sanitizée.")
        assert_equal(json.loads(raw.decode("utf-8")), {"error_code": "ORCHESTRATOR_INTERNAL_ERROR"}, "Payload interne interdit.")
        log_text = internal_logs.getvalue()
        for marker in ('"exception_type": "RuntimeError"', '"error_code": "ORCHESTRATOR_INTERNAL_ERROR"', '"trace_id": "TRACE-INTERNAL"'):
            if marker not in log_text:
                raise AssertionError(f"Contexte interne sûr absent: {marker}")
        if "SECRET_PAYLOAD_MUST_NOT_LEAK" in log_text:
            raise AssertionError("Le message sensible ne doit pas être journalisé.")

        stream_logs = StringIO()
        with redirect_stdout(stream_logs):
            start, raw, error = await asgi_request(application, "GET", "/review3/stream-error", trace_id="TRACE-STREAM")
        assert start["status"] == 200 and raw == b"%PDF" and error is not None
        stream_text = stream_logs.getvalue()
        for marker in ('"error_code": "HTTP_STREAM_INTERRUPTED"', '"response_volume_bytes": 4', '"trace_id": "TRACE-STREAM"'):
            if marker not in stream_text:
                raise AssertionError(f"Observation de flux interrompu absente: {marker}")
        if '"success_count": 1' in stream_text or "SECRET_STREAM_PAYLOAD_MUST_NOT_LEAK" in stream_text:
            raise AssertionError("Un flux interrompu ne doit être ni succès ni fuite de payload.")

    # Les invariants documentaires publics sont exprimés par les modèles et refusent les états partiels.
    invalid_models = (
        lambda: DocumentCorpusItemResponse(
            document_id="DOC-M013-REVIEW3", title="Document", document_status="REGISTERED",
            diagnostic_status="DIAGNOSTIC_NOT_REQUESTED", conversion_status="CANONICAL_ACCEPTED",
            canonical_version_id=None, projection_status="PROJECTION_NOT_REQUESTED",
        ),
        lambda: DocumentConversionResponse(
            document_id="DOC-M013-REVIEW3", conversion_status="QA_REJECTED",
            qa_rejection_error_code=None, canonical_version_id=None,
        ),
        lambda: KnowledgeProjectionResponse(
            document_id="DOC-M013-REVIEW3", projection_id="PROJ-M013-REVIEW3",
            canonical_version_id="CVER-M013-REVIEW3", projection_status="SEARCHABLE",
            profile={"projection_profile_id": "P", "chunking_profile": "C", "embedding_model": "E", "sparse_profile": "S", "index_schema": "I"},
            freshness={"status": "CURRENT", "observed_at": "2026-07-13T00:00:00Z"},
            chunk_count=0, chunk_samples=[],
        ),
    )
    for invalid_model in invalid_models:
        try:
            invalid_model()
        except ValidationError:
            pass
        else:
            raise AssertionError("Un modèle documentaire partiel ne doit pas être accepté.")


def architecture(repo_root: Path):
    platform_public = repo_root / "app" / "platform" / "application" / "public_contract_use_cases.py"
    compatibility_source = platform_public.read_text(encoding="utf-8")
    for forbidden in (
        "import urllib",
        "class ConversationUseCase",
        "class EvaluationUseCase",
        "_TASKS =",
        "_METRICS =",
    ):
        if forbidden in compatibility_source:
            raise AssertionError(f"La délégation platform n'est pas mince: {forbidden}")
    local_runtime = (repo_root / "app" / "platform" / "local_runtime.py").read_text(encoding="utf-8")
    if "def _legacy_" in local_runtime or "import urllib" in local_runtime:
        raise AssertionError("Les implémentations legacy et l'I/O urllib doivent quitter local_runtime.")
    sp_application = repo_root / "app" / "source_processing" / "application"
    for source in sp_application.glob("*.py"):
        if "app.platform" in source.read_text(encoding="utf-8"):
            raise AssertionError(f"SP/application dépend encore de platform: {source.name}")


class OneClaimOutbox:
    def __init__(self, claim):
        self.claim = claim

    def claim_next(self, *, owner_id, lease_seconds):
        claim, self.claim = self.claim, None
        return claim

    def acknowledge(self, claim, *, platform_job_id):
        raise AssertionError("ACK interdit après conflit")


class ConflictConsumer:
    def consume_relay_message(self, message):
        raise RuntimeError("JOB_RELAY_MESSAGE_CONFLICT")


def relay_observability():
    message = RelayedJobMessage(
        message_id="OUTBOX-SP-REVIEW3", job_name="DIAGNOSE", priority="P1",
        input_hash="a" * 64, configuration_hash="b" * 64, code_version="review3",
        model_version="none", payload={"document_id": "DOC-M013-REVIEW3"}, trace_id="TRACE-RELAY-REVIEW3",
    )
    claim = ClaimedRelayMessage(
        message=message, owner_id="RELAY-REVIEW3", claim_generation=1,
        claim_token="00000000-0000-4000-8000-000000000001",
    )
    logs = StringIO()
    try:
        with redirect_stdout(logs):
            JobOutboxRelay(outbox=OneClaimOutbox(claim), consumer=ConflictConsumer()).relay_pending(
                limit=1, owner_id="RELAY-REVIEW3", lease_seconds=5,
            )
    except RuntimeError as error:
        assert str(error) == "JOB_RELAY_MESSAGE_CONFLICT"
    else:
        raise AssertionError("Le conflit relais doit rester visible.")
    text = logs.getvalue()
    for marker in (
        '"event_type": "job_outbox_relay"', '"error_code": "JOB_RELAY_MESSAGE_CONFLICT"',
        '"message_id": "OUTBOX-SP-REVIEW3"', '"trace_id": "TRACE-RELAY-REVIEW3"', '"relayed_count": 0',
    ):
        if marker not in text:
            raise AssertionError(f"Observation de conflit relais absente: {marker}")
    if "DOC-M013-REVIEW3" in text:
        raise AssertionError("Le payload métier du relais ne doit pas être journalisé.")


repo_root = Path(sys.argv[1])
architecture(repo_root)
asyncio.run(scenario(repo_root))
relay_observability()
print("Test d'acceptation architecture API et observabilité revue 3: OK")
'@

$scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_review3_api_" + [Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $scriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    & $pythonExecutable -B $scriptPath $repoRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Test d'acceptation architecture API et observabilité revue 3: OK"
