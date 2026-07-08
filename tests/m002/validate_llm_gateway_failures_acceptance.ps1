$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

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


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic_seconds(self) -> float:
        return self.value


class ControlledSparkDouble:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    def post_chat_completion(
        self,
        *,
        base_url,
        headers,
        body,
        timeout_seconds,
        tls_ca_bundle_path,
    ):
        self.calls.append(
            {
                "base_url": base_url,
                "headers": dict(headers),
                "body": dict(body),
                "timeout_seconds": timeout_seconds,
                "tls_ca_bundle_path": tls_ca_bundle_path,
            }
        )
        if len(self.outcomes) == 0:
            raise AssertionError("Double Spark appelé sans événement prévu.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def configuration() -> GatewayConfiguration:
    return GatewayConfiguration(
        base_url="https://spark-inference.test:8443/v1",
        served_model="gemma-research",
        auth_mode="api_key_file",
        api_key="secret-t006",
        tls_mode="ca_bundle",
        tls_ca_bundle_path="C:/spark/ca.pem",
        timeout_seconds=7,
    )


def request() -> InferenceRequest:
    return InferenceRequest(
        messages=(InferenceMessage(role="user", content="Synthétiser le fait vérifié."),),
        output_schema={
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string"}},
            "additionalProperties": False,
        },
        schema_name="answer_schema",
        schema_version="answer_schema.v1",
        trace_id="trace-t006",
        request_id="request-t006",
        idempotency_key="idem-t006",
        prompt_id="prompt-answer",
        prompt_version="1",
        sampling_parameters={"temperature": 0, "top_p": 1},
    )


def success_response() -> OpenAICompatibleResponse:
    return OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-t006",
            "model": "gemma-research",
            "model_revision": "gemma-4-revision-t006",
            "runtime_version": "vllm-openai-t006",
            "choices": [{"message": {"content": '{"answer":"publication refusée sans preuve"}'}}],
        },
        headers={"x-request-id": "spark-request-t006"},
    )


def gateway_for(outcomes, *, max_retries_before_first_token, failure_threshold=3):
    transport = ControlledSparkDouble(outcomes)
    recorder = GatewayFailureMetricRecorder(
        observability_collector=InMemoryObservabilityCollector(),
    )
    breaker = GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(
            failure_threshold=failure_threshold,
            open_seconds=30,
        ),
        clock=ManualClock(),
    )
    gateway = OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration(),
        transport=transport,
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=max_retries_before_first_token),
        circuit_breaker=breaker,
        failure_metric_recorder=recorder,
    )
    return gateway, transport, recorder


def assert_no_fallback_model(transport) -> None:
    if len(transport.calls) == 0:
        return
    models = {call["body"].get("model") for call in transport.calls}
    if models != {"gemma-research"}:
        raise AssertionError(f"Fallback modèle détecté: {models}")


def assert_same_idempotency_key(transport) -> None:
    keys = {call["headers"].get("Idempotency-Key") for call in transport.calls}
    if keys != {"idem-t006"}:
        raise AssertionError(f"Idempotency key perdue pendant le retry: {keys}")


def expect_failure(expected_code, callback):
    try:
        callback()
    except LLMGatewayInferenceError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code panne inattendu: {exc.code}, attendu: {expected_code}")
        if exc.business_state_changed:
            raise AssertionError("Une panne gateway ne doit pas muter d'état métier.")
        if "secret-t006" in str(exc) or "secret-t006" in exc.message:
            raise AssertionError(f"Secret exposé dans l'erreur: {exc}")
        return exc
    else:
        raise AssertionError(f"Panne attendue absente: {expected_code}")


# Given une demande d'inférence nécessite Gemma sur spark-inference.
# When le Spark est indisponible avant le premier token.
# Then LLM_UNAVAILABLE est retourné sans fallback, avec retry borné et sans changement métier.
gateway, transport, recorder = gateway_for(
    [SparkUnavailableError("spark-inference indisponible"), SparkUnavailableError("spark-inference indisponible")],
    max_retries_before_first_token=1,
)
failure = expect_failure("LLM_UNAVAILABLE", lambda: gateway.infer(request()))
if failure.retry_pending:
    raise AssertionError("La panne finale ne doit plus être marquée RETRY_PENDING.")
if len(transport.calls) != 2:
    raise AssertionError(f"Retry borné indisponibilité incorrect: {len(transport.calls)}")
assert_no_fallback_model(transport)
assert_same_idempotency_key(transport)
if [event.status for event in recorder.events] != ["RETRY_PENDING", "LLM_UNAVAILABLE"]:
    raise AssertionError(f"Métriques indisponibilité inattendues: {recorder.events}")


# When le certificat Spark est invalide.
# Then l'erreur TLS explicite est retournée sans retry et sans désactivation TLS.
gateway, transport, recorder = gateway_for(
    [SparkTLSCertificateInvalidError("certificat invalide")],
    max_retries_before_first_token=1,
)
failure = expect_failure("LLM_TLS_CERTIFICATE_INVALID", lambda: gateway.infer(request()))
if failure.retryable:
    raise AssertionError("Un certificat invalide ne doit pas être retenté.")
if len(transport.calls) != 1:
    raise AssertionError(f"Retry interdit sur TLS invalide: {len(transport.calls)}")
assert_no_fallback_model(transport)
if recorder.events[-1].status != "LLM_TLS_CERTIFICATE_INVALID":
    raise AssertionError(f"Métrique TLS inattendue: {recorder.events}")


# When le timeout arrive avant le premier token puis Spark répond.
# Then le retry conserve l'idempotency key et le résultat final reste publiable.
gateway, transport, recorder = gateway_for(
    [SparkFirstTokenTimeoutError("timeout avant premier token"), success_response()],
    max_retries_before_first_token=1,
)
result = gateway.infer(request())
if result.structured_output != {"answer": "publication refusée sans preuve"}:
    raise AssertionError(f"Résultat après retry inattendu: {result.structured_output}")
if len(transport.calls) != 2:
    raise AssertionError(f"Retry borné timeout incorrect: {len(transport.calls)}")
assert_same_idempotency_key(transport)
if recorder.events[0].status != "RETRY_PENDING":
    raise AssertionError(f"Métrique retry timeout absente: {recorder.events}")


# When le flux est interrompu après le premier token.
# Then la sortie partielle est non publiable et aucun retry n'est tenté.
gateway, transport, recorder = gateway_for(
    [SparkStreamingInterruptedError("flux interrompu après le premier token", partial_output="réponse partielle")],
    max_retries_before_first_token=1,
)
failure = expect_failure("LLM_PARTIAL_OUTPUT", lambda: gateway.infer(request()))
if failure.publishable:
    raise AssertionError("Une sortie partielle ne doit pas être publiable.")
if failure.retryable:
    raise AssertionError("Aucun retry n'est autorisé après émission de token.")
if len(transport.calls) != 1:
    raise AssertionError(f"Retry interdit après premier token: {len(transport.calls)}")
if "réponse partielle" in str(failure):
    raise AssertionError("La sortie partielle ne doit pas être exposée dans le message d'erreur.")


# When les pannes transitoires ouvrent le circuit breaker.
# Then l'appel suivant retourne LLM_CIRCUIT_OPEN sans contacter Spark.
gateway, transport, recorder = gateway_for(
    [
        SparkUnavailableError("spark-inference indisponible"),
        SparkUnavailableError("spark-inference indisponible"),
        success_response(),
    ],
    max_retries_before_first_token=0,
    failure_threshold=2,
)
expect_failure("LLM_UNAVAILABLE", lambda: gateway.infer(request()))
expect_failure("LLM_UNAVAILABLE", lambda: gateway.infer(request()))
failure = expect_failure("LLM_CIRCUIT_OPEN", lambda: gateway.infer(request()))
if failure.retryable:
    raise AssertionError("Un circuit ouvert doit refuser l'appel sans retry immédiat.")
if len(transport.calls) != 2:
    raise AssertionError(f"Le circuit ouvert ne doit pas contacter Spark: {len(transport.calls)}")
if recorder.events[-1].status != "LLM_CIRCUIT_OPEN":
    raise AssertionError(f"Métrique circuit breaker absente: {recorder.events}")

print("Test d'acceptation pannes gateway LLM M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_llm_gateway_failures_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation pannes gateway LLM M-002: OK"
