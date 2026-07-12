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
import app.platform.local_runtime as legacy_runtime
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.platform.orchestrator_contract_routers import build_public_contract_router
from app.platform.orchestrator_public_services import build_public_contract_services


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="contract-parity", status="ready")


async def asgi_request(application, method, path, body=None):
    raw_body = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [] if body is None else [(b"content-type", b"application/json"), (b"content-length", str(len(raw_body)).encode("ascii"))]
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
            "method": method,
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
    response_body = b"".join(
        message.get("body", b"")
        for message in sent_messages
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(response_body.decode("utf-8"))


def chat_body(configuration):
    return {
        "model": configuration.models.llm.served_model_name,
        "conversation_id": "CONV-M013-FASTAPI-PARITY",
        "messages": [{"role": "user", "content": "Question de parité"}],
        "trace_id": "TRACE-M013-FASTAPI-PARITY",
        "request_id": "REQ-M013-FASTAPI-PARITY",
        "idempotency_key": "IDEMP-M013-FASTAPI-PARITY",
        "sampling_parameters": {"temperature": 0},
    }


def benchmark_body(configuration):
    return {
        "model": configuration.models.llm.served_model_name,
        "run_id": "LLMRUN-M013-FASTAPI-PARITY",
        "trace_id": "TRACE-M013-FASTAPI-BENCHMARK",
        "request_id": "REQ-M013-FASTAPI-BENCHMARK",
        "idempotency_key": "IDEMP-M013-FASTAPI-BENCHMARK",
        "sampling_parameters": {"temperature": 0},
    }


def fake_gateway_response(*, body, application_configuration):
    if body["schema_name"] == "m13_reality_product_chat":
        structured_output = {"answer": "Réponse stable"}
        raw_response_id = "RAW-CHAT-PARITY"
    else:
        task_name = body["prompt_id"].removeprefix("PROMPT-M013-REALITY-LLM-TASK-")
        structured_output = {
            "task_name": task_name,
            "evaluation_marker": f"M013-REALITY-{task_name}",
            "answer": f"Résultat {task_name}",
        }
        raw_response_id = f"RAW-{task_name}"
    return 200, {
        "structured_output": structured_output,
        "raw_response_id": raw_response_id,
        "provenance": {"provider": "vllm-spark"},
    }, 12.5


async def scenario(repo_root):
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    services = build_public_contract_services(configuration)

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=build_public_contract_router(services),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )

    original_gateway = legacy_runtime._post_local_gateway_inference
    original_time = legacy_runtime.time.time
    legacy_runtime._post_local_gateway_inference = fake_gateway_response
    legacy_runtime.time.time = lambda: 1_720_000_000
    try:
        direct_chat = legacy_runtime._product_chat_completions_post_response(
            body=chat_body(configuration),
            application_configuration=configuration,
        )
        direct_benchmark = legacy_runtime._llm_real_path_benchmark_post_response(
            body=benchmark_body(configuration),
            application_configuration=configuration,
        )
        direct_search = legacy_runtime._search_post_response()
        direct_index = legacy_runtime._index_post_response(document_id="DOC-M013-FASTAPI-PARITY")

        async with application.router.lifespan_context(application):
            assert_equal(
                await asgi_request(application, "GET", "/health"),
                (200, {"service": "orchestrator-api", "status": "healthy"}),
                "La santé ASGI doit préserver son contrat public.",
            )
            assert_equal(
                await asgi_request(application, "POST", "/v1/chat/completions", chat_body(configuration)),
                direct_chat,
                "Le routeur conversation doit préserver le succès publié par l'adaptateur borné.",
            )
            assert_equal(
                await asgi_request(application, "POST", "/v1/evaluation/llm-real-path-benchmark", benchmark_body(configuration)),
                direct_benchmark,
                "Le routeur d'évaluation doit préserver le succès publié par l'adaptateur borné.",
            )
            assert_equal(
                await asgi_request(application, "POST", "/v1/search", {"query_text": "volatilité"}),
                direct_search,
                "La recherche non configurée doit rester explicitement indisponible.",
            )
            assert_equal(
                await asgi_request(application, "POST", "/v1/documents/DOC-M013-FASTAPI-PARITY/index", {}),
                direct_index,
                "L'indexation non configurée doit préserver document_id et son erreur publique.",
            )

            invalid_model = {**chat_body(configuration), "model": "modele-inattendu"}
            assert_equal(
                await asgi_request(application, "POST", "/v1/chat/completions", invalid_model),
                (
                    400,
                    {
                        "error_code": "LOCAL_RUNTIME_MODEL_MISMATCH",
                        "message": f"Modele local attendu {configuration.models.llm.served_model_name}, obtenu modele-inattendu.",
                    },
                ),
                "Le refus conversationnel doit conserver statut, code et message.",
            )
            assert_equal(
                await asgi_request(application, "POST", "/v1/documents/id-invalide/index", {}),
                (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}),
                "L'identifiant d'indexation invalide doit conserver son contrat public.",
            )
    finally:
        legacy_runtime._post_local_gateway_inference = original_gateway
        legacy_runtime.time.time = original_time


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation de parité des contrats API existants: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_contract_parity_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation de parité des contrats API existants: OK"
