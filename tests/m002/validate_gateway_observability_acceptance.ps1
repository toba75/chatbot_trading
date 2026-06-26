$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eAcute = [char] 0x00E9

$pythonCode = @'
from __future__ import annotations

import json
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.llm_gateway import (
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayConfiguration,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceMessage,
    InferenceRequest,
    LLMGatewayInferenceError,
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
    SparkFirstTokenTimeoutError,
    SparkStreamingInterruptedError,
    SparkTLSCertificateInvalidError,
    SparkUnavailableError,
)
from app.platform.observability import InMemoryObservabilityCollector


PROMPT_CANARY = "PROMPT_COMPLET_T010_NE_DOIT_PAS_SORTIR"
RESPONSE_CANARY = "REPONSE_COMPLETE_T010_NE_DOIT_PAS_SORTIR"
SECRET_CANARY = "secret-t010-ne-doit-pas-sortir"
PARTIAL_CANARY = "SORTIE_PARTIELLE_T010_NE_DOIT_PAS_SORTIR"


class ManualClock:
    def __init__(self) -> None:
        self.value = 100.0

    def monotonic_seconds(self) -> float:
        self.value += 0.125
        return self.value


class ControlledSparkDouble:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)

    def post_chat_completion(
        self,
        *,
        base_url,
        headers,
        body,
        timeout_seconds,
        tls_ca_bundle_path,
    ):
        if len(self.outcomes) == 0:
            raise AssertionError("Double Spark appelé sans événement prévu.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def configuration() -> GatewayConfiguration:
    return GatewayConfiguration(
        base_url="https://spark-inference.test:8443/v1",
        served_model="gemma-research-t010",
        api_key=SECRET_CANARY,
        tls_ca_bundle_path="C:/spark/ca-t010.pem",
        timeout_seconds=7,
    )


def request(trace_id: str) -> InferenceRequest:
    return InferenceRequest(
        messages=(
            InferenceMessage(role="system", content="Répondre en JSON strict."),
            InferenceMessage(role="user", content=f"{PROMPT_CANARY} avec preuve complète."),
        ),
        output_schema={
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string"}},
            "additionalProperties": False,
        },
        schema_name="answer_schema",
        schema_version="answer_schema.v1",
        trace_id=trace_id,
        request_id=f"request-{trace_id}",
        idempotency_key=f"idem-{trace_id}",
        prompt_id="prompt-answer-t010",
        prompt_version="1",
        sampling_parameters={"temperature": 0, "top_p": 1},
    )


def success_response() -> OpenAICompatibleResponse:
    return OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-t010",
            "model": "gemma-research-t010",
            "model_revision": "gemma-4-revision-t010",
            "runtime_version": "vllm-openai-t010",
            "choices": [{"message": {"content": json.dumps({"answer": RESPONSE_CANARY})}}],
        },
        headers={"x-request-id": "spark-request-t010", "x-ttft-ms": "12.5"},
    )


def gateway_for(outcomes, *, failure_threshold: int = 3):
    collector = InMemoryObservabilityCollector()
    recorder = GatewayFailureMetricRecorder(observability_collector=collector)
    gateway = OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration(),
        transport=ControlledSparkDouble(outcomes),
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=1),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(
                failure_threshold=failure_threshold,
                open_seconds=30,
            ),
            clock=ManualClock(),
        ),
        failure_metric_recorder=recorder,
    )
    return gateway, collector


def expect_failure(expected_code: str, callback) -> None:
    try:
        callback()
    except LLMGatewayInferenceError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code panne inattendu: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Panne attendue absente: {expected_code}")


def assert_observability_safe(collector: InMemoryObservabilityCollector, *, expected_status: str, trace_id: str) -> None:
    logs = collector.logs()
    metrics = collector.metrics()
    if len(logs) == 0:
        raise AssertionError("Aucun log structuré gateway n'a été émis.")
    if len(metrics) == 0:
        raise AssertionError("Aucune métrique gateway n'a été émise.")

    serialized = json.dumps(
        {
            "logs": [log.to_mapping() for log in logs],
            "metrics": [metric.to_mapping() for metric in metrics],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (PROMPT_CANARY, RESPONSE_CANARY, SECRET_CANARY, PARTIAL_CANARY):
        if forbidden in serialized:
            raise AssertionError(f"Payload ou secret exposé dans l'observabilité: {forbidden}")

    matching_logs = [
        log for log in logs
        if log.trace_id == trace_id and log.status == expected_status and log.phase == "spark_inference"
    ]
    if len(matching_logs) == 0:
        raise AssertionError(f"Log attendu absent pour {trace_id}/{expected_status}: {logs}")
    for log in matching_logs:
        if log.component != "llm-gateway":
            raise AssertionError(f"Composant log inattendu: {log}")
        if log.latency_ms <= 0:
            raise AssertionError(f"Latence non mesurée: {log}")
        if len(log.prompt_hash) != 64:
            raise AssertionError(f"Hash de prompt absent ou invalide: {log}")

    metric_names = {metric.name for metric in metrics if metric.trace_id == trace_id}
    required_metric_names = {"llm_gateway_request_total", "llm_gateway_request_latency_ms"}
    if not required_metric_names.issubset(metric_names):
        raise AssertionError(f"Métriques gateway obligatoires absentes: {metric_names}")


# Given un appel d'inférence réussit sur le Spark.
# When le gateway émet logs et métriques.
# Then la corrélation, la latence, TTFT, modèle et runtime sont visibles sans prompt ni réponse complète.
gateway, collector = gateway_for([success_response()])
result = gateway.infer(request("trace-t010-success"))
if result.structured_output != {"answer": RESPONSE_CANARY}:
    raise AssertionError(f"Résultat d'inférence inattendu: {result.structured_output}")
assert_observability_safe(collector, expected_status="SUCCEEDED", trace_id="trace-t010-success")
success_metric_names = {metric.name for metric in collector.metrics()}
for metric_name in ("llm_gateway_ttft_ms", "llm_gateway_payload_bytes"):
    if metric_name not in success_metric_names:
        raise AssertionError(f"Métrique succès absente: {metric_name}")

gateway, collector = gateway_for([
    OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-t010",
            "model": "gemma-research-t010",
            "model_revision": "gemma-4-revision-t010",
            "runtime_version": "vllm-openai-t010",
            "choices": [{"message": {"content": json.dumps({"answer": "ok"})}}],
        },
        headers={"x-request-id": "spark-request-t010"},
    )
])
gateway.infer(request("trace-t010-no-ttft"))
if "llm_gateway_ttft_ms" in {metric.name for metric in collector.metrics()}:
    raise AssertionError("TTFT ne doit pas être émis quand le transport ne le mesure pas explicitement.")


# Given un appel d'inférence échoue après validation TLS.
# When le gateway émet logs et métriques.
# Then l'erreur TLS, la phase et la latence sont visibles sans secret ni payload complet.
gateway, collector = gateway_for([SparkTLSCertificateInvalidError("certificat invalide avec secret local")])
expect_failure("LLM_TLS_CERTIFICATE_INVALID", lambda: gateway.infer(request("trace-t010-tls")))
assert_observability_safe(collector, expected_status="LLM_TLS_CERTIFICATE_INVALID", trace_id="trace-t010-tls")


# Given un timeout arrive avant le premier token puis le retry réussit.
# When le gateway émet logs et métriques.
# Then le retry avant premier token et le statut final sont auditables sans contenu complet.
gateway, collector = gateway_for([
    SparkFirstTokenTimeoutError("timeout avant premier token"),
    success_response(),
])
gateway.infer(request("trace-t010-timeout"))
assert_observability_safe(collector, expected_status="SUCCEEDED", trace_id="trace-t010-timeout")
retry_metric_values = [
    metric.value
    for metric in collector.metrics()
    if metric.trace_id == "trace-t010-timeout" and metric.name == "llm_gateway_retry_before_first_token_total"
]
if retry_metric_values != [1.0]:
    raise AssertionError("Métrique de retry avant premier token absente.")


# Given une sortie est interrompue après le premier token.
# When le gateway émet logs et métriques.
# Then le statut de sortie interrompue est visible sans fragment de réponse.
gateway, collector = gateway_for([
    SparkStreamingInterruptedError("flux interrompu", partial_output=PARTIAL_CANARY),
])
expect_failure("LLM_PARTIAL_OUTPUT", lambda: gateway.infer(request("trace-t010-partial")))
assert_observability_safe(collector, expected_status="LLM_PARTIAL_OUTPUT", trace_id="trace-t010-partial")
if "llm_gateway_output_interrupted_total" not in {metric.name for metric in collector.metrics()}:
    raise AssertionError("Métrique de sortie interrompue absente.")


# Given le Spark renvoie un contenu JSON invalide.
# When le gateway refuse la réponse.
# Then le refus reste observable sans payload complet.
gateway, collector = gateway_for([
    OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-t010",
            "model": "gemma-research-t010",
            "model_revision": "gemma-4-revision-t010",
            "runtime_version": "vllm-openai-t010",
            "choices": [{"message": {"content": "not-json"}}],
        },
        headers={"x-request-id": "spark-request-t010"},
    )
])
expect_failure("LLM_RESPONSE_INVALID_JSON", lambda: gateway.infer(request("trace-t010-invalid-json")))
assert_observability_safe(collector, expected_status="LLM_RESPONSE_INVALID_JSON", trace_id="trace-t010-invalid-json")


# Given le circuit breaker est ouvert après une panne Spark.
# When une nouvelle demande arrive.
# Then le refus circuit ouvert est observable et corrélé.
gateway, collector = gateway_for([SparkUnavailableError("spark indisponible")], failure_threshold=1)
expect_failure("LLM_UNAVAILABLE", lambda: gateway.infer(request("trace-t010-circuit")))
expect_failure("LLM_CIRCUIT_OPEN", lambda: gateway.infer(request("trace-t010-circuit-open")))
assert_observability_safe(collector, expected_status="LLM_CIRCUIT_OPEN", trace_id="trace-t010-circuit-open")
if "llm_gateway_circuit_breaker_open" not in {metric.name for metric in collector.metrics()}:
    raise AssertionError("Métrique circuit breaker ouvert absente.")

print("Test d'acceptation observabilité gateway M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_gateway_observability_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation observabilit$($eAcute) gateway M-002: OK"
