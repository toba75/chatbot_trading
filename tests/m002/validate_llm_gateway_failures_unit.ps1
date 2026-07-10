$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import sys
import urllib.error

sys.path.insert(0, sys.argv[1])

import app.platform.llm_gateway as gateway_module
from app.platform.llm_gateway import (
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayConfiguration,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceMessage,
    InferenceRequest,
    LLMGatewayContractError,
    LLMGatewayInferenceError,
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
    SparkAuthenticationError,
    SparkFirstTokenTimeoutError,
    SparkHTTPStatusError,
    SparkStreamingInterruptedError,
    SparkTLSCertificateInvalidError,
    SparkUnavailableError,
    UrllibOpenAICompatibleTransport,
    classify_gateway_failure,
)
from app.platform.observability import InMemoryObservabilityCollector


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic_seconds(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ScriptedTransport:
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
        self.calls.append({"headers": dict(headers), "body": dict(body)})
        if len(self.outcomes) == 0:
            raise AssertionError("Appel Spark non prévu.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def valid_configuration() -> GatewayConfiguration:
    return GatewayConfiguration(
        base_url="https://spark-inference.test:8443/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit-t006",
        runtime_version="vllm-openai-declared-unit-t006",
        configuration_hash="c" * 64,
        auth_mode="api_key_file",
        api_key="secret-unit-t006",
        tls_mode="ca_bundle",
        tls_ca_bundle_path="C:/spark/ca.pem",
        timeout_seconds=9,
    )


def valid_request() -> InferenceRequest:
    return InferenceRequest(
        messages=(InferenceMessage(role="user", content="Répondre en JSON."),),
        output_schema={
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string"}},
            "additionalProperties": False,
        },
        schema_name="answer_schema",
        schema_version="answer_schema.v1",
        trace_id="trace-unit-t006",
        request_id="request-unit-t006",
        idempotency_key="idem-unit-t006",
        prompt_id="prompt-unit",
        prompt_version="1",
        sampling_parameters={"temperature": 0, "top_p": 1},
    )


def success_response() -> OpenAICompatibleResponse:
    return OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-unit-t006",
            "model": "gemma-research",
            "model_revision": "gemma-4-revision-unit-t006",
            "runtime_version": "vllm-openai-unit-t006",
            "choices": [{"message": {"content": '{"answer":"ok"}'}}],
        },
        headers={"x-request-id": "spark-unit-t006"},
    )


def gateway_for(outcomes, *, max_retries_before_first_token, failure_threshold=3):
    transport = ScriptedTransport(outcomes)
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
        configuration=valid_configuration(),
        transport=transport,
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=max_retries_before_first_token),
        circuit_breaker=breaker,
        failure_metric_recorder=recorder,
    )
    return gateway, transport, recorder, breaker


def assert_contract_error(expected_code, callback) -> None:
    try:
        callback()
    except LLMGatewayContractError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Erreur contrat inattendue: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Erreur contrat attendue absente: {expected_code}")


def assert_inference_error(expected_code, callback) -> LLMGatewayInferenceError:
    try:
        callback()
    except LLMGatewayInferenceError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Erreur inférence inattendue: {exc.code}, attendu: {expected_code}")
        return exc
    else:
        raise AssertionError(f"Erreur inférence attendue absente: {expected_code}")


classification = classify_gateway_failure(SparkUnavailableError("spark indisponible"))
if classification.code != "LLM_UNAVAILABLE" or not classification.retryable or not classification.before_first_token:
    raise AssertionError(f"Classification indisponibilité invalide: {classification}")

classification = classify_gateway_failure(SparkFirstTokenTimeoutError("timeout avant premier token"))
if classification.code != "LLM_FIRST_TOKEN_TIMEOUT" or not classification.retryable or not classification.before_first_token:
    raise AssertionError(f"Classification timeout invalide: {classification}")

classification = classify_gateway_failure(SparkTLSCertificateInvalidError("certificat invalide"))
if classification.code != "LLM_TLS_CERTIFICATE_INVALID" or classification.retryable or not classification.before_first_token:
    raise AssertionError(f"Classification TLS invalide: {classification}")

classification = classify_gateway_failure(SparkAuthenticationError("authentification Spark refusée"))
if classification.code != "LLM_AUTHENTICATION_FAILED" or classification.retryable or not classification.before_first_token:
    raise AssertionError(f"Classification authentification invalide: {classification}")

classification = classify_gateway_failure(SparkHTTPStatusError("erreur HTTP Spark", status_code=503))
if classification.code != "LLM_SPARK_HTTP_ERROR" or not classification.retryable or not classification.before_first_token:
    raise AssertionError(f"Classification HTTP Spark invalide: {classification}")

classification = classify_gateway_failure(
    SparkStreamingInterruptedError("flux interrompu", partial_output="fragment secret")
)
if classification.code != "LLM_PARTIAL_OUTPUT" or classification.retryable or classification.before_first_token:
    raise AssertionError(f"Classification sortie partielle invalide: {classification}")
if classification.publishable:
    raise AssertionError("Une sortie partielle ne doit jamais être publiable.")


assert_contract_error(
    "LLM_IDEMPOTENCY_KEY_REQUIRED",
    lambda: InferenceRequest(
        messages=(InferenceMessage(role="user", content="Répondre en JSON."),),
        output_schema={"type": "object"},
        schema_name="answer_schema",
        schema_version="answer_schema.v1",
        trace_id="trace-unit-t006",
        request_id="request-unit-t006",
        idempotency_key="",
        prompt_id="prompt-unit",
        prompt_version="1",
        sampling_parameters={"temperature": 0},
    ),
)


gateway, transport, recorder, breaker = gateway_for(
    [SparkUnavailableError("spark indisponible"), success_response()],
    max_retries_before_first_token=1,
)
result = gateway.infer(valid_request())
if result.structured_output != {"answer": "ok"}:
    raise AssertionError(f"Résultat après retry invalide: {result.structured_output}")
if len(transport.calls) != 2:
    raise AssertionError(f"Retry transitoire non borné: {len(transport.calls)}")
idempotency_keys = {call["headers"].get("Idempotency-Key") for call in transport.calls}
if idempotency_keys != {"idem-unit-t006"}:
    raise AssertionError(f"Idempotence perdue: {idempotency_keys}")
if recorder.events[0].status != "RETRY_PENDING":
    raise AssertionError(f"Métrique RETRY_PENDING absente: {recorder.events}")


gateway, transport, recorder, breaker = gateway_for(
    [
        SparkFirstTokenTimeoutError("timeout avant premier token"),
        SparkFirstTokenTimeoutError("timeout avant premier token"),
        success_response(),
    ],
    max_retries_before_first_token=1,
)
failure = assert_inference_error("LLM_FIRST_TOKEN_TIMEOUT", lambda: gateway.infer(valid_request()))
if failure.retry_pending:
    raise AssertionError("La panne finale ne doit pas rester en RETRY_PENDING.")
if len(transport.calls) != 2:
    raise AssertionError(f"Nombre d'essais timeout invalide: {len(transport.calls)}")


gateway, transport, recorder, breaker = gateway_for(
    [SparkStreamingInterruptedError("flux interrompu", partial_output="réponse partielle secrète")],
    max_retries_before_first_token=3,
)
failure = assert_inference_error("LLM_PARTIAL_OUTPUT", lambda: gateway.infer(valid_request()))
if failure.publishable:
    raise AssertionError("La sortie partielle ne doit pas être publiable.")
if failure.retryable:
    raise AssertionError("Une sortie partielle ne doit pas être retentée.")
if len(transport.calls) != 1:
    raise AssertionError(f"Retry après premier token interdit: {len(transport.calls)}")
if "réponse partielle" in str(failure):
    raise AssertionError("La sortie partielle ne doit pas apparaître dans le message.")

partial_finish_transport = ScriptedTransport([
    OpenAICompatibleResponse(
        payload={
            "id": "chatcmpl-unit-t006",
            "model": "gemma-research",
            "model_revision": "gemma-4-revision-unit-t006",
            "runtime_version": "vllm-openai-unit-t006",
            "choices": [{"finish_reason": "length", "message": {"content": '{"answer":"ok"}'}}],
        },
        headers={"x-request-id": "spark-unit-t006"},
    )
])
partial_finish_gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=valid_configuration(),
    transport=partial_finish_transport,
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=InMemoryObservabilityCollector(),
    ),
)
failure = assert_inference_error("LLM_PARTIAL_OUTPUT", lambda: partial_finish_gateway.infer(valid_request()))
if failure.publishable:
    raise AssertionError("Un finish_reason length ne doit pas être publiable.")


gateway, transport, recorder, breaker = gateway_for(
    [SparkUnavailableError("spark indisponible avec secret-unit-t006")],
    max_retries_before_first_token=0,
)
failure = assert_inference_error("LLM_UNAVAILABLE", lambda: gateway.infer(valid_request()))
if "secret-unit-t006" in str(failure) or "secret-unit-t006" in failure.message:
    raise AssertionError(f"Secret exposé dans l'erreur: {failure}")
if "secret-unit-t006" in recorder.events[-1].message:
    raise AssertionError(f"Secret exposé dans la métrique: {recorder.events[-1]}")
if recorder.events[-1].trace_id != "trace-unit-t006":
    raise AssertionError(f"trace_id absent de la métrique: {recorder.events[-1]}")


gateway, transport, recorder, breaker = gateway_for(
    [SparkTLSCertificateInvalidError("certificat invalide"), success_response()],
    max_retries_before_first_token=3,
)
failure = assert_inference_error("LLM_TLS_CERTIFICATE_INVALID", lambda: gateway.infer(valid_request()))
if failure.retryable:
    raise AssertionError("TLS invalide ne doit pas être retryable.")
if len(transport.calls) != 1:
    raise AssertionError(f"Retry TLS interdit: {len(transport.calls)}")


class RaisingUrlopen:
    def __init__(self, error):
        self.error = error

    def __call__(self, *args, **kwargs):
        raise self.error


def assert_transport_error(expected_type, callback) -> None:
    try:
        callback()
    except expected_type:
        return
    except BaseException as exc:
        raise AssertionError(f"Erreur transport inattendue: {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"Erreur transport attendue absente: {expected_type.__name__}")


original_urlopen = gateway_module.urllib.request.urlopen
original_context = gateway_module.ssl.create_default_context
try:
    gateway_module.ssl.create_default_context = lambda cafile: object()
    gateway_module.urllib.request.urlopen = RaisingUrlopen(
        urllib.error.HTTPError(
            url="https://spark-inference.test:8443/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
    )
    assert_transport_error(
        SparkAuthenticationError,
        lambda: UrllibOpenAICompatibleTransport().post_chat_completion(
            base_url="https://spark-inference.test:8443/v1",
            headers={},
            body={"model": "gemma-research"},
            timeout_seconds=1,
            tls_ca_bundle_path="C:/spark/ca.pem",
        ),
    )
finally:
    gateway_module.urllib.request.urlopen = original_urlopen
    gateway_module.ssl.create_default_context = original_context

assert_transport_error(
    SparkTLSCertificateInvalidError,
    lambda: UrllibOpenAICompatibleTransport().post_chat_completion(
        base_url="https://spark-inference.test:8443/v1",
        headers={},
        body={"model": "gemma-research"},
        timeout_seconds=1,
        tls_ca_bundle_path="C:/spark/ca-file-does-not-exist.pem",
    ),
)


gateway, transport, recorder, breaker = gateway_for(
    [RuntimeError("erreur inattendue non masquée")],
    max_retries_before_first_token=1,
)
try:
    gateway.infer(valid_request())
except RuntimeError as exc:
    if isinstance(exc, LLMGatewayInferenceError):
        raise AssertionError(f"Erreur inattendue masquée: {exc}")
    if str(exc) != "erreur inattendue non masquée":
        raise AssertionError(f"Cause inattendue altérée: {exc}")
else:
    raise AssertionError("Erreur inattendue non propagée.")


gateway, transport, recorder, breaker = gateway_for(
    [SparkUnavailableError("spark indisponible"), SparkUnavailableError("spark indisponible")],
    max_retries_before_first_token=0,
    failure_threshold=2,
)
assert_inference_error("LLM_UNAVAILABLE", lambda: gateway.infer(valid_request()))
assert_inference_error("LLM_UNAVAILABLE", lambda: gateway.infer(valid_request()))
if not breaker.is_open():
    raise AssertionError("Le circuit breaker doit être ouvert après le seuil.")
failure = assert_inference_error("LLM_CIRCUIT_OPEN", lambda: gateway.infer(valid_request()))
if failure.retryable:
    raise AssertionError("Un circuit ouvert refuse sans retry immédiat.")
if len(transport.calls) != 2:
    raise AssertionError(f"Appel Spark interdit circuit ouvert: {len(transport.calls)}")

print("Tests unitaires pannes gateway LLM M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_llm_gateway_failures_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires pannes gateway LLM M-002: OK"
