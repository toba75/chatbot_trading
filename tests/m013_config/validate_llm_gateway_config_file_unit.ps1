$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, sys.argv[1])

import app.platform.local_runtime as local_runtime_module  # noqa: E402
from app.platform.configuration import (  # noqa: E402
    ApplicationConfigurationError,
    load_application_configuration,
)
from app.platform.llm_gateway import (  # noqa: E402
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    LLMGatewayContractError,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceMessage,
    InferenceRequest,
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
)
from app.platform.local_runtime import (  # noqa: E402
    _build_gateway_configuration_from_application_configuration,
    _configured_http_bind_host,
    _configured_http_port,
    _llm_gateway_readiness_response,
    _post_local_gateway_inference,
)
from app.platform.observability import InMemoryObservabilityCollector  # noqa: E402


class ManualClock:
    def monotonic_seconds(self) -> float:
        return 0.0


class CapturingTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post_chat_completion(
        self,
        *,
        base_url,
        headers,
        body,
        timeout_seconds,
        tls_ca_bundle_path,
    ) -> OpenAICompatibleResponse:
        self.calls.append(
            {
                "base_url": base_url,
                "headers": dict(headers),
                "body": dict(body),
                "timeout_seconds": timeout_seconds,
                "tls_ca_bundle_path": tls_ca_bundle_path,
            }
        )
        return OpenAICompatibleResponse(
            payload={
                "id": "chatcmpl-m013-config-unit",
                "model": "google/gemma-4-26B-A4B-it",
                "choices": [{"message": {"content": '{"answer":"OK"}'}, "finish_reason": "stop"}],
            },
            headers={},
        )


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


def assert_raises_gateway(expected_code: str, action) -> None:
    try:
        action()
    except LLMGatewayContractError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code gateway inattendu: {exc.code}. Attendu: {expected_code}.") from exc
        return
    raise AssertionError(f"Erreur gateway attendue absente: {expected_code}")


def valid_request() -> InferenceRequest:
    return InferenceRequest(
        messages=(InferenceMessage(role="user", content='Réponds uniquement {"answer":"OK"}.'),),
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        schema_name="m013_config_unit_answer",
        schema_version="1.0",
        trace_id="TRACE-M013-CONFIG-UNIT-0001",
        request_id="REQ-M013-CONFIG-UNIT-0001",
        idempotency_key="IDEMP-M013-CONFIG-UNIT-0001",
        prompt_id="PROMPT-M013-CONFIG-UNIT",
        prompt_version="1.0",
        sampling_parameters={"max_tokens": 16, "temperature": 0},
    )


repo_root = Path(sys.argv[1])
example_path = repo_root / "config" / "application.example.yaml"
example_text = example_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

configuration = load_application_configuration(config_path=example_path, environment_snapshot={})

assert_equal(
    _configured_http_port("orchestrator-api", configuration),
    configuration.services.api.port,
    "Le port orchestrator-api doit provenir du fichier applicatif.",
)
assert_equal(
    _configured_http_port("llm-gateway", configuration),
    configuration.services.llm_gateway.port,
    "Le port llm-gateway doit provenir du fichier applicatif.",
)
assert_equal(
    _configured_http_bind_host("llm-gateway", configuration),
    configuration.deployment.hosts.docker_local.container_listen_host,
    "Le bind llm-gateway doit utiliser l'écoute conteneur déclarée.",
)
assert_equal(
    _configured_http_bind_host("orchestrator-api", configuration),
    configuration.services.api.bind_host,
    "Le bind orchestrator-api doit utiliser l'écoute interne déclarée.",
)

# Given le fichier applicatif porte tout le contrat llm-gateway.
# When local_runtime construit GatewayConfiguration depuis l'objet validé.
# Then aucune variable GEMMA_* ne participe au mapping et les valeurs strictes sont conservées.
gateway_configuration = _build_gateway_configuration_from_application_configuration(configuration)

assert_equal(
    gateway_configuration.base_url,
    configuration.services.llm_gateway.spark_endpoint_url,
    "Endpoint Spark non mappé depuis le fichier.",
)
assert_equal(
    gateway_configuration.served_model,
    configuration.models.llm.served_model_name,
    "Modèle servi non mappé depuis le fichier.",
)
assert_equal(
    gateway_configuration.model_revision,
    configuration.models.llm.model_revision,
    "Révision modèle non mappée depuis le fichier.",
)
assert_equal(
    gateway_configuration.runtime_version,
    configuration.models.llm.runtime_version,
    "Version runtime non mappée depuis le fichier.",
)
assert_equal(gateway_configuration.auth_mode, "none", "Mode auth Spark attendu pour le Spark actuel.")
assert_equal(gateway_configuration.api_key, None, "Aucune clé API ne doit être injectée en mode none.")
assert_equal(gateway_configuration.tls_mode, "disabled", "Mode TLS attendu pour le Spark actuel.")
assert_equal(gateway_configuration.tls_ca_bundle_path, None, "Aucun bundle CA ne doit être injecté en mode disabled.")
assert_equal(
    gateway_configuration.timeout_seconds,
    configuration.services.llm_gateway.timeout_seconds,
    "Timeout gateway non mappé.",
)
assert_equal(
    gateway_configuration.configuration_hash,
    configuration.configuration_hash,
    "Hash de configuration absent du contrat gateway.",
)

with tempfile.TemporaryDirectory(prefix="ost_m013_llm_gateway_installation_") as temporary_directory_name:
    temporary_directory = Path(temporary_directory_name)
    declared_dns_path = temporary_directory / "dns_declare.yaml"
    declared_dns_path.write_text(
        example_text.replace(
            "    dns_name: spark-inference\n",
            "    dns_name: spark-inference.home.arpa\n",
            1,
        ).replace(
            "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
            "    spark_endpoint_url: http://spark-inference.home.arpa:8000/v1\n",
            1,
        ),
        encoding="utf-8",
    )
    declared_dns_configuration = load_application_configuration(config_path=declared_dns_path, environment_snapshot={})
    assert_equal(
        _build_gateway_configuration_from_application_configuration(declared_dns_configuration).base_url,
        "http://spark-inference.home.arpa:8000/v1",
        "Le DNS Spark declare dans application.yaml doit etre accepte sans changement de code.",
    )

    external_dns_path = temporary_directory / "dns_externe.yaml"
    external_dns_path.write_text(
        example_text.replace(
            "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
            "    spark_endpoint_url: http://spark-public.example.com:8000/v1\n",
            1,
        ),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=external_dns_path, environment_snapshot={}),
    )

    private_ip_non_declared_path = temporary_directory / "ip_privee_non_declaree.yaml"
    private_ip_non_declared_path.write_text(
        example_text.replace(
            "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
            "    spark_endpoint_url: http://192.168.1.121:8000/v1\n",
            1,
        ),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=private_ip_non_declared_path, environment_snapshot={}),
    )

    require_tls_conflict_path = temporary_directory / "require_tls_conflit.yaml"
    require_tls_conflict_path.write_text(
        example_text.replace("    require_tls: false\n", "    require_tls: true\n", 1),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=require_tls_conflict_path, environment_snapshot={}),
    )

    require_api_key_conflict_path = temporary_directory / "require_api_key_conflit.yaml"
    require_api_key_conflict_path.write_text(
        example_text.replace("    require_api_key: false\n", "    require_api_key: true\n", 1),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=require_api_key_conflict_path, environment_snapshot={}),
    )

    missing_api_key_path = temporary_directory / "secret_absent.yaml"
    missing_api_key_path.write_text(
        example_text.replace("    require_api_key: false\n", "    require_api_key: true\n", 1)
        .replace("    auth_mode: none\n", "    auth_mode: api_key_file\n", 1)
        .replace(
            "    llm_gateway_api_key_path: config/secrets/local/llm_gateway_api_key.txt\n",
            f"    llm_gateway_api_key_path: {temporary_directory.as_posix()}/secret_absent.txt\n",
            1,
        ),
        encoding="utf-8",
    )
    missing_api_key_configuration = load_application_configuration(config_path=missing_api_key_path, environment_snapshot={})
    assert_raises_gateway(
        "LLM_GATEWAY_API_KEY_FILE_UNREADABLE",
        lambda: _build_gateway_configuration_from_application_configuration(missing_api_key_configuration),
    )
    readiness_status, readiness_body = _llm_gateway_readiness_response(
        application_configuration=missing_api_key_configuration,
    )
    assert_equal(readiness_status, 503, "Le healthcheck gateway doit refuser un secret manquant.")
    assert_equal(
        readiness_body["error_code"],
        "LLM_GATEWAY_API_KEY_FILE_UNREADABLE",
        "Le healthcheck gateway doit exposer le code de configuration serveur.",
    )


class InvalidJsonResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b"not-json"


original_urlopen = local_runtime_module.urllib.request.urlopen
try:
    local_runtime_module.urllib.request.urlopen = lambda request, timeout: InvalidJsonResponse()
    invalid_status, invalid_payload, _elapsed = _post_local_gateway_inference(
        body={"messages": [], "output_schema": {}, "schema_name": "invalid", "schema_version": "1.0"},
        application_configuration=configuration,
    )
finally:
    local_runtime_module.urllib.request.urlopen = original_urlopen

assert_equal(invalid_status, 502, "Une réponse gateway 200 non JSON doit être traduite en 502.")
assert_equal(
    invalid_payload["error_code"],
    "LLM_GATEWAY_RESPONSE_INVALID",
    "Une réponse gateway 200 non JSON doit avoir un code stable.",
)

assert_raises_config(
    "CONFIG_ENV_INPUT_REJECTED",
    lambda: load_application_configuration(
        config_path=example_path,
        environment_snapshot={"GEMMA_BASE_URL": "http://pollution.example/v1"},
    ),
)

with tempfile.TemporaryDirectory(prefix="ost_m013_llm_gateway_config_unit_") as temporary_directory_name:
    temporary_directory = Path(temporary_directory_name)
    empty_model_path = temporary_directory / "modele_vide.yaml"
    empty_model_path.write_text(
        example_text.replace(
            "    served_model_name: google/gemma-4-26B-A4B-it\n",
            '    served_model_name: ""\n',
            1,
        ),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_KEY_EMPTY",
        lambda: load_application_configuration(config_path=empty_model_path, environment_snapshot={}),
    )

    missing_provenance_path = temporary_directory / "provenance_absente.yaml"
    missing_provenance_path.write_text(
        example_text.replace(
            "    model_revision: google/gemma-4-26B-A4B-it@declared-revision\n",
            "",
            1,
        ),
        encoding="utf-8",
    )
    assert_raises_config(
        "CONFIG_KEY_MISSING",
        lambda: load_application_configuration(config_path=missing_provenance_path, environment_snapshot={}),
    )

retry_policy = GatewayRetryPolicy(
    max_retries_before_first_token=configuration.services.llm_gateway.retry_before_first_token,
)
assert_equal(
    retry_policy.max_retries_before_first_token,
    configuration.services.llm_gateway.retry_before_first_token,
    "Retry avant premier token non mappé.",
)
circuit_policy = GatewayCircuitBreakerPolicy(
    failure_threshold=configuration.services.llm_gateway.circuit_breaker_failure_threshold,
    open_seconds=configuration.services.llm_gateway.circuit_breaker_reset_seconds,
)
assert_equal(
    circuit_policy.failure_threshold,
    configuration.services.llm_gateway.circuit_breaker_failure_threshold,
    "Seuil circuit breaker non mappé.",
)
assert_equal(
    circuit_policy.open_seconds,
    configuration.services.llm_gateway.circuit_breaker_reset_seconds,
    "Durée circuit breaker non mappée.",
)

collector = InMemoryObservabilityCollector()
transport = CapturingTransport()
gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=gateway_configuration,
    transport=transport,
    retry_policy=retry_policy,
    circuit_breaker=GatewayCircuitBreaker(policy=circuit_policy, clock=ManualClock()),
    failure_metric_recorder=GatewayFailureMetricRecorder(observability_collector=collector),
)
result = gateway.infer(valid_request())
assert_equal(result.structured_output, {"answer": "OK"}, "Sortie structurée gateway invalide.")
assert_true(len(transport.calls) == 1, "Un seul appel Spark attendu.")
headers = transport.calls[0]["headers"]
assert_true(isinstance(headers, dict), "Headers transport non capturés.")
assert_true("Authorization" not in headers, "Authorization interdit en auth_mode none.")

log_mapping = collector.logs()[0].to_mapping()
assert_equal(
    log_mapping.get("configuration_hash"),
    configuration.configuration_hash,
    "Hash de configuration absent du log gateway.",
)
for metric in collector.metrics():
    assert_equal(
        metric.tags.get("configuration_hash"),
        configuration.configuration_hash,
        f"Hash de configuration absent de la métrique {metric.name}.",
    )

print("Tests unitaires T-004 gateway LLM configuré par fichier: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_config_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 gateway LLM configuré par fichier: OK"
