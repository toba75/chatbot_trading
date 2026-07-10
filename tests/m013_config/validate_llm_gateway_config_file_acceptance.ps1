$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$runtimeStdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_no_config_" + [System.Guid]::NewGuid().ToString("N") + ".out.log")
$runtimeStderrPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_no_config_" + [System.Guid]::NewGuid().ToString("N") + ".err.log")
$runtimeProcess = Start-Process `
    -FilePath $pythonExecutable `
    -ArgumentList @("-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090") `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $runtimeStdoutPath `
    -RedirectStandardError $runtimeStderrPath `
    -WindowStyle Hidden `
    -PassThru
try {
    if (-not $runtimeProcess.WaitForExit(3000)) {
        Stop-Process -Id $runtimeProcess.Id -Force
        throw "CONFIG_FILE_REQUIRED attendu: le runtime sans --config est resté démarré."
    }

    $runtimeOutput = @()
    if (Test-Path -LiteralPath $runtimeStdoutPath) {
        $runtimeOutput += Get-Content -LiteralPath $runtimeStdoutPath
    }
    if (Test-Path -LiteralPath $runtimeStderrPath) {
        $runtimeOutput += Get-Content -LiteralPath $runtimeStderrPath
    }
    if ($runtimeProcess.ExitCode -eq 0) {
        throw "CONFIG_FILE_REQUIRED attendu: le runtime sans --config a réussi."
    }
    if (($runtimeOutput -join "`n") -notmatch "CONFIG_FILE_REQUIRED") {
        throw "CONFIG_FILE_REQUIRED absent de la sortie runtime sans --config: $($runtimeOutput -join "`n")"
    }
}
finally {
    if ($null -ne $runtimeProcess -and -not $runtimeProcess.HasExited) {
        Stop-Process -Id $runtimeProcess.Id -Force
    }
    Remove-Item -LiteralPath $runtimeStdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $runtimeStderrPath -Force -ErrorAction SilentlyContinue
}

$pythonCode = @'
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, sys.argv[1])

from app.evaluation.domain.llm_real_path_benchmark import REQUIRED_LLM_TASKS  # noqa: E402
from app.platform import local_runtime  # noqa: E402
from app.platform.configuration import (  # noqa: E402
    ApplicationConfigurationError,
    load_application_configuration,
)
from app.platform.llm_gateway import (  # noqa: E402
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceMessage,
    InferenceRequest,
    LLMGatewayInferenceError,
    OpenAICompatibleLocalLanguageModelGateway,
    SparkUnavailableError,
)
from app.platform.local_runtime import (  # noqa: E402
    _benchmark_marker_for_task,
    _build_gateway_configuration_from_application_configuration,
    _llm_real_path_benchmark_post_response,
    _product_chat_completions_post_response,
)
from app.platform.observability import InMemoryObservabilityCollector  # noqa: E402


class ManualClock:
    def monotonic_seconds(self) -> float:
        return 0.0


class FailingTransport:
    def post_chat_completion(
        self,
        *,
        base_url,
        headers,
        body,
        timeout_seconds,
        tls_ca_bundle_path,
    ):
        raise SparkUnavailableError("Spark indisponible test T-004.")


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_config(expected_code: str, action) -> None:
    try:
        action()
    except ApplicationConfigurationError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code CONFIG inattendu: {exc.code}. Attendu: {expected_code}.") from exc
        return
    raise AssertionError(f"Erreur CONFIG attendue absente: {expected_code}")


def inference_request() -> InferenceRequest:
    return InferenceRequest(
        messages=(InferenceMessage(role="user", content='Réponds uniquement {"answer":"OK"}.'),),
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        schema_name="m013_config_acceptance_answer",
        schema_version="1.0",
        trace_id="TRACE-M013-CONFIG-ACCEPTANCE-FAILURE",
        request_id="REQ-M013-CONFIG-ACCEPTANCE-FAILURE",
        idempotency_key="IDEMP-M013-CONFIG-ACCEPTANCE-FAILURE",
        prompt_id="PROMPT-M013-CONFIG-ACCEPTANCE-FAILURE",
        prompt_version="1.0",
        sampling_parameters={"max_tokens": 16, "temperature": 0},
    )


repo_root = Path(sys.argv[1])
example_path = repo_root / "config" / "application.example.yaml"
example_text = example_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
configuration = load_application_configuration(config_path=example_path, environment_snapshot={})

# Given config/application.yaml déclare Spark, le modèle servi et la provenance.
# When le chat produit exécute une inférence.
# Then les valeurs du fichier sont conservées et la provenance complète est publiée.
recorded_inference_bodies: list[dict[str, object]] = []


def fake_gateway_post(*, body, application_configuration):
    assert_equal(
        application_configuration.configuration_hash,
        configuration.configuration_hash,
        "Le hash de configuration doit être transmis au chemin gateway.",
    )
    recorded_inference_bodies.append(dict(body))
    schema_name = body["schema_name"]
    if schema_name == "m13_reality_product_chat":
        structured_output = {"answer": "Réponse produit issue du chemin configuré."}
    elif schema_name == "m13_reality_llm_benchmark_task":
        prompt_id = body["prompt_id"]
        task_name = prompt_id.removeprefix("PROMPT-M013-REALITY-LLM-TASK-")
        structured_output = {
            "task_name": task_name,
            "evaluation_marker": _benchmark_marker_for_task(task_name),
            "answer": f"Réponse benchmark {task_name}",
        }
    else:
        raise AssertionError(f"Schéma inference inattendu: {schema_name!r}")
    return (
        200,
        {
            "structured_output": structured_output,
            "provenance": {
                "model_id": configuration.models.llm.served_model_name,
                "model_revision": configuration.models.llm.model_revision,
                "runtime_version": configuration.models.llm.runtime_version,
                "prompt_id": body["prompt_id"],
                "prompt_version": body["prompt_version"],
                "schema_version": body["schema_version"],
                "input_hash": "a" * 64,
                "output_hash": "b" * 64,
                "started_at": "2026-07-10T00:00:00+00:00",
                "completed_at": "2026-07-10T00:00:01+00:00",
            },
            "raw_response_id": f"raw-{body['request_id']}",
        },
        12.5,
    )


original_gateway_post = local_runtime._post_local_gateway_inference
local_runtime._post_local_gateway_inference = fake_gateway_post
try:
    chat_status, chat_response = _product_chat_completions_post_response(
        body={
            "model": configuration.models.llm.served_model_name,
            "conversation_id": "CONV-M013-CONFIG-0001",
            "trace_id": "TRACE-M013-CONFIG-CHAT-0001",
            "request_id": "REQ-M013-CONFIG-CHAT-0001",
            "idempotency_key": "IDEMP-M013-CONFIG-CHAT-0001",
            "messages": [{"role": "user", "content": "Question produit configurée."}],
            "sampling_parameters": {"max_tokens": 32, "temperature": 0},
        },
        application_configuration=configuration,
    )
    assert_equal(chat_status, 200, "Le chat produit configuré doit réussir.")
    assert_equal(chat_response["model"], configuration.models.llm.served_model_name, "Modèle chat invalide.")
    product = chat_response["ost_product"]
    assert_equal(
        product["provenance"]["model_revision"],
        configuration.models.llm.model_revision,
        "Provenance chat incomplète.",
    )

    benchmark_status, benchmark_response = _llm_real_path_benchmark_post_response(
        body={
            "model": configuration.models.llm.served_model_name,
            "run_id": "LLMRUN-M013-CONFIG-0001",
            "trace_id": "TRACE-M013-CONFIG-BENCH-0001",
            "request_id": "REQ-M013-CONFIG-BENCH-0001",
            "idempotency_key": "IDEMP-M013-CONFIG-BENCH-0001",
            "sampling_parameters": {"max_tokens": 32, "temperature": 0},
        },
        application_configuration=configuration,
    )
    assert_equal(benchmark_status, 200, "Le benchmark LLM configuré doit réussir.")
    assert_equal(tuple(benchmark_response["task_names"]), REQUIRED_LLM_TASKS, "Tâches benchmark invalides.")
    assert_true(
        all(result["provenance"]["runtime_version"] == configuration.models.llm.runtime_version for result in benchmark_response["task_results"]),
        "Runtime déclaré absent des tâches benchmark.",
    )
finally:
    local_runtime._post_local_gateway_inference = original_gateway_post

assert_true(len(recorded_inference_bodies) == 1 + len(REQUIRED_LLM_TASKS), "Nombre d'inférences configurées invalide.")

# Given l'environnement de processus est pollué par une ancienne variable GEMMA_*.
# When la configuration applicative est chargée.
# Then le démarrage est refusé explicitement au lieu d'ignorer ou d'utiliser la variable.
assert_raises_config(
    "CONFIG_ENV_INPUT_REJECTED",
    lambda: load_application_configuration(
        config_path=example_path,
        environment_snapshot={"GEMMA_BASE_URL": "http://pollution.invalid/v1"},
    ),
)

with tempfile.TemporaryDirectory(prefix="ost_m013_llm_gateway_config_acceptance_") as temporary_directory_name:
    missing_provenance_path = Path(temporary_directory_name) / "provenance_absente.yaml"
    missing_provenance_path.write_text(
        example_text.replace(
            "    runtime_version: nim-1.7.0-variant-api-3.1.0\n",
            "",
            1,
        ),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_KEY_MISSING",
        lambda: load_application_configuration(config_path=missing_provenance_path, environment_snapshot={}),
    )

# Given le mode actuel Spark est auth_mode=none.
# When le gateway appelle le transport OpenAI compatible.
# Then aucune clé API ni header Authorization n'est injecté, et une panne Spark reste LLM_UNAVAILABLE.
gateway_configuration = _build_gateway_configuration_from_application_configuration(configuration)
collector = InMemoryObservabilityCollector()
gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=gateway_configuration,
    transport=FailingTransport(),
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(
            failure_threshold=configuration.services.llm_gateway.circuit_breaker_failure_threshold,
            open_seconds=configuration.services.llm_gateway.circuit_breaker_reset_seconds,
        ),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(observability_collector=collector),
)
try:
    gateway.infer(inference_request())
except LLMGatewayInferenceError as exc:
    assert_equal(exc.code, "LLM_UNAVAILABLE", "La panne Spark doit rester explicite.")
    assert_equal(exc.publishable, False, "Une panne Spark ne doit pas produire de réponse factuelle publiable.")
else:
    raise AssertionError("Panne Spark attendue absente.")

failure_log = collector.logs()[0].to_mapping()
assert_equal(failure_log["error_code"], "LLM_UNAVAILABLE", "Erreur LLM_UNAVAILABLE absente du log.")
assert_equal(
    failure_log["configuration_hash"],
    configuration.configuration_hash,
    "Hash de configuration absent du log de panne.",
)

print("Test d'acceptation T-004 gateway LLM configuré par fichier: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_config_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force -ErrorAction SilentlyContinue
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation T-004 gateway LLM configuré par fichier: OK"
