$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

from dataclasses import MISSING, fields
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
    LLMGatewayContractError,
    LLMGatewayInferenceError,
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
    build_openai_chat_completion_request,
)
from app.platform import local_runtime
from app.platform.configuration import load_application_configuration
from app.platform.observability import InMemoryObservabilityCollector


OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
    "additionalProperties": False,
}


class ManualClock:
    def monotonic_seconds(self):
        return 0.0


def valid_configuration() -> GatewayConfiguration:
    return GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    )


def valid_request(*, output_schema=OUTPUT_SCHEMA) -> InferenceRequest:
    return InferenceRequest(
        messages=(InferenceMessage(role="user", content="Répondre en JSON."),),
        output_schema=output_schema,
        schema_name="answer_schema",
        schema_version="answer_schema.v1",
        trace_id="trace-unit",
        request_id="request-unit",
        idempotency_key="idem-unit",
        prompt_id="prompt-unit",
        prompt_version="1",
        sampling_parameters={"temperature": 0, "top_p": 1},
    )


def assert_raises_code(expected_code, callback):
    try:
        callback()
    except LLMGatewayContractError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code erreur inattendu: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_code}")


def assert_gateway_error_code(expected_code, callback):
    try:
        callback()
    except (LLMGatewayContractError, LLMGatewayInferenceError) as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code erreur inattendu: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_code}")


assert_raises_code(
    "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="ftp://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://attacker.example:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

GatewayConfiguration(
    base_url="http://192.168.1.120:8000/v1",
    served_model="gemma-research",
    model_revision="gemma-4-declared-revision-unit",
    runtime_version="vllm-openai-declared-unit",
    configuration_hash="c" * 64,
    auth_mode="none",
    api_key=None,
    tls_mode="disabled",
    tls_ca_bundle_path=None,
    timeout_seconds=9,
)

assert_raises_code(
    "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://127.0.0.1:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://10.1.2.3:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_AUTH_MODE_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_API_KEY_FORBIDDEN",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key="unit-secret-key",
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_TLS_CA_FORBIDDEN",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path="C:/spark/ca.pem",
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_MODEL_REVISION_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_MODEL_REVISION_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision=" gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_RUNTIME_VERSION_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

assert_raises_code(
    "LLM_GATEWAY_RUNTIME_VERSION_REQUIRED",
    lambda: GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-research",
        model_revision="gemma-4-declared-revision-unit",
        runtime_version="vllm-openai-declared-unit ",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=9,
    ),
)

field_by_name = {field.name: field for field in fields(GatewayConfiguration)}
for required_field_name in ("model_revision", "runtime_version", "configuration_hash"):
    field = field_by_name[required_field_name]
    if field.default is not MISSING or field.default_factory is not MISSING:
        raise AssertionError(f"Valeur par defaut interdite pour {required_field_name}.")

runtime_configuration = load_application_configuration(
    config_path=f"{sys.argv[1]}/config/application.example.yaml",
    environment_snapshot={},
)
local_runtime._LLM_GATEWAY_INSTANCE = None
local_runtime._LLM_GATEWAY_CONFIGURATION_HASH = None
first_runtime_gateway = local_runtime._get_local_language_model_gateway(
    application_configuration=runtime_configuration,
)
second_runtime_gateway = local_runtime._get_local_language_model_gateway(
    application_configuration=runtime_configuration,
)
if first_runtime_gateway is not second_runtime_gateway:
    raise AssertionError("Le runtime local doit conserver l'instance gateway LLM et son circuit breaker.")
local_runtime._LLM_GATEWAY_INSTANCE = None
local_runtime._LLM_GATEWAY_CONFIGURATION_HASH = None

assert_raises_code("LLM_OUTPUT_SCHEMA_REQUIRED", lambda: valid_request(output_schema={}))

configuration = valid_configuration()
request = valid_request()
payload = build_openai_chat_completion_request(configuration=configuration, request=request)
configuration_logs = configuration.masked_for_logs()
if configuration_logs["model_revision"] != "gemma-4-declared-revision-unit":
    raise AssertionError(f"Revision declaree absente des logs: {configuration_logs}")
if configuration_logs["runtime_version"] != "vllm-openai-declared-unit":
    raise AssertionError(f"Runtime declare absent des logs: {configuration_logs}")

if payload["model"] != "gemma-research":
    raise AssertionError(f"Modèle servi absent du payload: {payload}")
if payload["messages"] != [{"role": "user", "content": "Répondre en JSON."}]:
    raise AssertionError(f"Messages OpenAI invalides: {payload}")
if payload["response_format"] != {
    "type": "json_schema",
    "json_schema": {"name": "answer_schema", "schema": OUTPUT_SCHEMA, "strict": True},
}:
    raise AssertionError(f"Schéma OpenAI invalide: {payload}")
if payload["temperature"] != 0 or payload["top_p"] != 1:
    raise AssertionError(f"Paramètres de sampling absents du payload: {payload}")

mutable_sampling_parameters = {"temperature": 0, "top_p": 1}
immutable_request = InferenceRequest(
    messages=(InferenceMessage(role="user", content="Répondre en JSON."),),
    output_schema=OUTPUT_SCHEMA,
    schema_name="answer_schema",
    schema_version="answer_schema.v1",
    trace_id="trace-unit-immutable",
    request_id="request-unit-immutable",
    idempotency_key="idem-unit-immutable",
    prompt_id="prompt-unit",
    prompt_version="1",
    sampling_parameters=mutable_sampling_parameters,
)
mutable_sampling_parameters["model"] = "fallback-model"
immutable_payload = build_openai_chat_completion_request(
    configuration=configuration,
    request=immutable_request,
)
if immutable_payload["model"] != "gemma-research":
    raise AssertionError(f"Paramètres de sampling mutables: {immutable_payload}")

api_key_configuration = GatewayConfiguration(
    base_url="https://spark-inference.test:8443/v1",
    served_model="gemma-research",
    model_revision="gemma-4-declared-revision-unit",
    runtime_version="vllm-openai-declared-unit",
    configuration_hash="c" * 64,
    auth_mode="api_key_file",
    api_key="unit-secret-key",
    tls_mode="ca_bundle",
    tls_ca_bundle_path="C:/spark/ca.pem",
    timeout_seconds=9,
)
masked = api_key_configuration.masked_for_logs()
if masked["api_key"] != "<secret-masked>":
    raise AssertionError(f"Secret non masqué: {masked}")
if "unit-secret-key" in repr(api_key_configuration) or "unit-secret-key" in str(masked):
    raise AssertionError("La clé d'API ne doit jamais apparaître dans les représentations journalisables.")


class FixedTransport:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = {"x-request-id": "spark-unit"} if headers is None else headers
        self.call = None

    def post_chat_completion(
        self,
        *,
        base_url,
        headers,
        body,
        timeout_seconds,
        tls_ca_bundle_path,
    ):
        self.call = {
            "base_url": base_url,
            "headers": headers,
            "body": body,
            "timeout_seconds": timeout_seconds,
            "tls_ca_bundle_path": tls_ca_bundle_path,
        }
        return OpenAICompatibleResponse(payload=self.payload, headers=self.headers)


successful_transport = FixedTransport(
    {
        "id": "chatcmpl-unit",
        "model": "gemma-research",
        "model_revision": "gemma-4-revision-unit",
        "runtime_version": "vllm-openai-unit",
        "choices": [{"message": {"content": '{"answer":"ok"}'}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }
)
gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=configuration,
    transport=successful_transport,
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=InMemoryObservabilityCollector(),
    ),
)
result = gateway.infer(request)

if result.structured_output != {"answer": "ok"}:
    raise AssertionError(f"Sortie JSON non traduite: {result.structured_output}")
if result.provenance.model_id != "gemma-research":
    raise AssertionError(f"model_id absent: {result.provenance}")
if result.provenance.model_revision != "gemma-4-revision-unit":
    raise AssertionError(f"model_revision absent: {result.provenance}")
if result.provenance.runtime_version != "vllm-openai-unit":
    raise AssertionError(f"runtime_version absent: {result.provenance}")
if result.provenance.input_hash == "" or result.provenance.output_hash == "":
    raise AssertionError(f"Hashes de provenance absents: {result.provenance}")
if result.provenance.schema_version != "answer_schema.v1":
    raise AssertionError(f"schema_version absent: {result.provenance}")
if result.provenance.sampling_parameters != {"temperature": 0, "top_p": 1}:
    raise AssertionError(f"sampling_parameters absents: {result.provenance}")
if successful_transport.call["headers"].get("Authorization") is not None:
    raise AssertionError(f"Header Authorization interdit en auth none: {successful_transport.call['headers']}")
if successful_transport.call["tls_ca_bundle_path"] is not None:
    raise AssertionError(f"Bundle TLS interdit en mode disabled: {successful_transport.call}")

header_provenance_transport = FixedTransport(
    {
        "id": "chatcmpl-unit",
        "model": "gemma-research",
        "choices": [{"message": {"content": '{"answer":"ok"}'}}],
    },
    headers={
        "x-request-id": "spark-unit",
        "x-model-revision": "gemma-4-header-revision",
        "x-runtime-version": "vllm-openai-header",
    },
)
header_provenance_result = OpenAICompatibleLocalLanguageModelGateway(
    configuration=configuration,
    transport=header_provenance_transport,
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=InMemoryObservabilityCollector(),
    ),
).infer(request)
if header_provenance_result.provenance.model_revision != "gemma-4-header-revision":
    raise AssertionError(f"model_revision header ignorée: {header_provenance_result.provenance}")
if header_provenance_result.provenance.runtime_version != "vllm-openai-header":
    raise AssertionError(f"runtime_version header ignorée: {header_provenance_result.provenance}")

declared_provenance_transport = FixedTransport(
    {
        "id": "chatcmpl-unit",
        "model": "gemma-research",
        "choices": [{"message": {"content": '{"answer":"ok"}'}}],
    }
)
declared_collector = InMemoryObservabilityCollector()
declared_provenance_result = OpenAICompatibleLocalLanguageModelGateway(
    configuration=configuration,
    transport=declared_provenance_transport,
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=declared_collector,
    ),
).infer(request)
if declared_provenance_result.provenance.model_revision != "gemma-4-declared-revision-unit":
    raise AssertionError(f"model_revision declaree ignoree: {declared_provenance_result.provenance}")
if declared_provenance_result.provenance.runtime_version != "vllm-openai-declared-unit":
    raise AssertionError(f"runtime_version declare ignore: {declared_provenance_result.provenance}")
declared_log = declared_collector.logs()[0].to_mapping()
if declared_log["model_revision"] != "gemma-4-declared-revision-unit":
    raise AssertionError(f"model_revision finale absente de l'observabilite: {declared_log}")
if declared_log["runtime_version"] != "vllm-openai-declared-unit":
    raise AssertionError(f"runtime_version finale absente de l'observabilite: {declared_log}")

schema_violation_transport = FixedTransport(
    {
        "id": "chatcmpl-unit",
        "model": "gemma-research",
        "model_revision": "gemma-4-revision-unit",
        "runtime_version": "vllm-openai-unit",
        "choices": [{"message": {"content": '{"answer":"ok","unexpected":"exfil"}'}}],
    }
)
assert_gateway_error_code(
    "LLM_RESPONSE_SCHEMA_INVALID",
    lambda: OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration,
        transport=schema_violation_transport,
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
            clock=ManualClock(),
        ),
        failure_metric_recorder=GatewayFailureMetricRecorder(
            observability_collector=InMemoryObservabilityCollector(),
        ),
    ).infer(request),
)

invalid_revision_transport = FixedTransport(
    {
        "id": "chatcmpl-unit",
        "model": "gemma-research",
        "model_revision": " gemma-4-revision-unit",
        "runtime_version": "vllm-openai-unit",
        "choices": [{"message": {"content": '{"answer":"ok"}'}}],
    }
)
assert_gateway_error_code(
    "LLM_RESPONSE_PROVENANCE_MISSING",
    lambda: OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration,
        transport=invalid_revision_transport,
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
            clock=ManualClock(),
        ),
        failure_metric_recorder=GatewayFailureMetricRecorder(
            observability_collector=InMemoryObservabilityCollector(),
        ),
    ).infer(request),
)

print("Tests unitaires contrat gateway LLM M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_llm_gateway_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires contrat gateway LLM M-002: OK"
