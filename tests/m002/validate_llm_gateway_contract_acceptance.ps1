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
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
)
from app.platform.observability import InMemoryObservabilityCollector


class ManualClock:
    def monotonic_seconds(self):
        return 0.0


class ControlledOpenAIDouble:
    def __init__(self) -> None:
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
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
                "tls_ca_bundle_path": tls_ca_bundle_path,
            }
        )

        if str(base_url) != "http://spark-inference.test:8000/v1":
            raise AssertionError(f"URL Spark inattendue: {base_url}")
        if tls_ca_bundle_path is not None:
            raise AssertionError(f"Bundle TLS inattendu: {tls_ca_bundle_path}")
        if timeout_seconds != 7:
            raise AssertionError(f"Timeout inattendu: {timeout_seconds}")
        if "Authorization" in headers:
            raise AssertionError(f"Authentification Spark interdite en mode none: {headers}")
        if headers.get("X-OST-Client") != "llm-gateway":
            raise AssertionError(f"Appel Spark hors gateway: {headers}")
        if headers.get("X-Trace-Id") != "trace-t005":
            raise AssertionError(f"trace_id non propagé: {headers}")
        if headers.get("X-Request-Id") != "request-t005":
            raise AssertionError(f"request_id non propagé: {headers}")
        if headers.get("Idempotency-Key") != "idem-t005":
            raise AssertionError(f"idempotency_key non propagée: {headers}")

        if body.get("model") != "gemma-research":
            raise AssertionError(f"Modèle servi non injecté: {body}")
        if body.get("messages") != [{"role": "user", "content": "Extraire un fait vérifiable."}]:
            raise AssertionError(f"Messages OpenAI inattendus: {body}")

        response_format = body.get("response_format")
        expected_schema = {
            "type": "object",
            "required": ["extracted_fact"],
            "properties": {"extracted_fact": {"type": "string"}},
            "additionalProperties": False,
        }
        if response_format != {
            "type": "json_schema",
            "json_schema": {
                "name": "fact_extraction",
                "schema": expected_schema,
                "strict": True,
            },
        }:
            raise AssertionError(f"Schéma de sortie OpenAI inattendu: {response_format}")

        return OpenAICompatibleResponse(
            payload={
                "id": "chatcmpl-t005",
                "model": "gemma-research",
                "model_revision": "gemma-4-revision-t005",
                "runtime_version": "vllm-openai-t005",
                "choices": [
                    {
                        "message": {
                            "content": '{"extracted_fact":"Kelly optimise une fraction de capital."}'
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 17,
                    "completion_tokens": 11,
                    "total_tokens": 28,
                },
            },
            headers={"x-request-id": "spark-request-t005"},
        )


configuration = GatewayConfiguration(
    base_url="http://spark-inference.test:8000/v1",
    served_model="gemma-research",
    auth_mode="none",
    api_key=None,
    tls_mode="disabled",
    tls_ca_bundle_path=None,
    timeout_seconds=7,
)
transport = ControlledOpenAIDouble()
gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=configuration,
    transport=transport,
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
        clock=ManualClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=InMemoryObservabilityCollector(),
    ),
)

request = InferenceRequest(
    messages=(InferenceMessage(role="user", content="Extraire un fait vérifiable."),),
    output_schema={
        "type": "object",
        "required": ["extracted_fact"],
        "properties": {"extracted_fact": {"type": "string"}},
        "additionalProperties": False,
    },
    schema_name="fact_extraction",
    schema_version="fact_extraction.v1",
    trace_id="trace-t005",
    request_id="request-t005",
    idempotency_key="idem-t005",
    prompt_id="prompt-fact-extraction",
    prompt_version="1",
    sampling_parameters={"temperature": 0, "top_p": 1},
)

result = gateway.infer(request)

if len(transport.calls) != 1:
    raise AssertionError(f"Nombre d'appels Spark inattendu: {len(transport.calls)}")

if result.structured_output != {"extracted_fact": "Kelly optimise une fraction de capital."}:
    raise AssertionError(f"Sortie structurée inattendue: {result.structured_output}")
if result.provenance.model_id != "gemma-research":
    raise AssertionError(f"Provenance modèle absente: {result.provenance}")
if result.provenance.model_revision != "gemma-4-revision-t005":
    raise AssertionError(f"Révision modèle absente: {result.provenance}")
if result.provenance.runtime_version != "vllm-openai-t005":
    raise AssertionError(f"Runtime vLLM absent: {result.provenance}")
if result.provenance.schema_version != "fact_extraction.v1":
    raise AssertionError(f"Version de schéma absente: {result.provenance}")
if result.provenance.prompt_id != "prompt-fact-extraction":
    raise AssertionError(f"Prompt id absent: {result.provenance}")
if result.provenance.sampling_parameters != {"temperature": 0, "top_p": 1}:
    raise AssertionError(f"Sampling non tracé: {result.provenance}")
if hasattr(result, "domain_decision"):
    raise AssertionError("Le gateway LLM ne doit pas exposer de décision métier.")

print("Test d'acceptation contrat gateway LLM M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_llm_gateway_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation contrat gateway LLM M-002: OK"
