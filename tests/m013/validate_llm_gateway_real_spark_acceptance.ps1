$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$requiredVariables = @(
    "GEMMA_BASE_URL",
    "GEMMA_MODEL",
    "GEMMA_AUTH_MODE",
    "GEMMA_TLS_MODE",
    "GEMMA_MODEL_REVISION",
    "GEMMA_RUNTIME_VERSION"
)

foreach ($name in $requiredVariables) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Variable requise absente pour le test réel M13-reality: $name"
    }
    if ($value -ne $value.Trim()) {
        throw "Variable non normalisée pour le test réel M13-reality: $name"
    }
}

if ($env:GEMMA_AUTH_MODE -ne "none") {
    throw "GEMMA_AUTH_MODE doit valoir none pour le conteneur Spark actuel."
}
if ($env:GEMMA_TLS_MODE -ne "disabled") {
    throw "GEMMA_TLS_MODE doit valoir disabled pour le conteneur Spark actuel."
}

$pythonCode = @'
from __future__ import annotations

import json
import sys
import urllib.request

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
    SystemGatewayClock,
    UrllibOpenAICompatibleTransport,
)
from app.platform.observability import InMemoryObservabilityCollector


base_url = sys.argv[2]
served_model = sys.argv[3]
auth_mode = sys.argv[4]
tls_mode = sys.argv[5]
model_revision = sys.argv[6]
runtime_version = sys.argv[7]

models_url = f"{base_url.rstrip('/')}/models"
with urllib.request.urlopen(models_url, timeout=30) as response:
    models_payload = json.loads(response.read().decode("utf-8"))

model_items = models_payload.get("data")
if not isinstance(model_items, list):
    raise AssertionError(f"Catalogue modèles Spark invalide: {models_payload!r}")
served_model_ids = tuple(
    item["id"]
    for item in model_items
    if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip() == item["id"]
)
if served_model not in served_model_ids:
    raise AssertionError(
        f"Modèle GEMMA_MODEL absent du Spark réel: {served_model!r}; modèles exposés: {served_model_ids!r}"
    )

configuration = GatewayConfiguration(
    base_url=base_url,
    served_model=served_model,
    auth_mode=auth_mode,
    api_key=None,
    tls_mode=tls_mode,
    tls_ca_bundle_path=None,
    timeout_seconds=120,
    model_revision=model_revision,
    runtime_version=runtime_version,
)
collector = InMemoryObservabilityCollector()
gateway = OpenAICompatibleLocalLanguageModelGateway(
    configuration=configuration,
    transport=UrllibOpenAICompatibleTransport(),
    retry_policy=GatewayRetryPolicy(max_retries_before_first_token=1),
    circuit_breaker=GatewayCircuitBreaker(
        policy=GatewayCircuitBreakerPolicy(failure_threshold=2, open_seconds=30),
        clock=SystemGatewayClock(),
    ),
    failure_metric_recorder=GatewayFailureMetricRecorder(
        observability_collector=collector,
    ),
)

request = InferenceRequest(
    messages=(
        InferenceMessage(
            role="user",
            content='Réponds uniquement avec ce JSON: {"answer":"OK"}.',
        ),
    ),
    output_schema={
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    },
    schema_name="m13_reality_gateway_smoke",
    schema_version="1.0",
    trace_id="TRACE-M013-REALITY-GATEWAY-0001",
    request_id="REQ-M013-REALITY-GATEWAY-0001",
    idempotency_key="IDEMP-M013-REALITY-GATEWAY-0001",
    prompt_id="PROMPT-M013-REALITY-GATEWAY-SMOKE",
    prompt_version="1.0",
    sampling_parameters={"max_tokens": 64, "temperature": 0},
)

result = gateway.infer(request)

if result.structured_output != {"answer": "OK"}:
    raise AssertionError(f"Sortie structurée réelle inattendue: {result.structured_output!r}")
if result.provenance.model_id != served_model:
    raise AssertionError(f"Modèle servi absent de la provenance: {result.provenance!r}")
if result.provenance.model_revision != model_revision:
    raise AssertionError(f"Révision modèle déclarée absente: {result.provenance!r}")
if result.provenance.runtime_version != runtime_version:
    raise AssertionError(f"Runtime déclaré absent: {result.provenance!r}")

logs = collector.logs()
if len(logs) != 1:
    raise AssertionError(f"Observation gateway attendue: {len(logs)}")
log = logs[0].to_mapping()
if log.get("status") != "SUCCEEDED":
    raise AssertionError(f"Observation gateway non réussie: {log}")
if log.get("model_revision") != model_revision:
    raise AssertionError(f"Révision modèle absente de l'observabilité: {log}")
if log.get("runtime_version") != runtime_version:
    raise AssertionError(f"Runtime absent de l'observabilité: {log}")
if "Authorization" in repr(log):
    raise AssertionError(f"Header d'autorisation exposé en mode none: {log}")

print("Test d'acceptation M13-reality gateway LLM réel: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_real_spark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath `
        $repoRoot `
        $env:GEMMA_BASE_URL `
        $env:GEMMA_MODEL `
        $env:GEMMA_AUTH_MODE `
        $env:GEMMA_TLS_MODE `
        $env:GEMMA_MODEL_REVISION `
        $env:GEMMA_RUNTIME_VERSION 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation M13-reality gateway LLM réel: OK"
