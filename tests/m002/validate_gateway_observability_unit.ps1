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

from app.platform.observability import (
    GatewayObservation,
    InMemoryObservabilityCollector,
    JobObservation,
    ObservabilityContractError,
    OutboxObservation,
    redact_secret_fields,
    sha256_text,
)


PROMPT_CANARY = "PROMPT_COMPLET_UNIT_T010_INTERDIT"
RESPONSE_CANARY = "REPONSE_COMPLETE_UNIT_T010_INTERDITE"
SECRET_CANARY = "secret-unit-t010-interdit"


def assert_contract_error(expected_code: str, callback) -> None:
    try:
        callback()
    except ObservabilityContractError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code observabilité inattendu: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Erreur observabilité attendue absente: {expected_code}")


prompt_hash = sha256_text(PROMPT_CANARY)
if len(prompt_hash) != 64 or PROMPT_CANARY in prompt_hash:
    raise AssertionError(f"Hash de prompt invalide: {prompt_hash}")

redacted = redact_secret_fields(
    {"Authorization": f"Bearer {SECRET_CANARY}", "api_key": SECRET_CANARY, "X-Trace-Id": "trace-unit-t010"},
    secret_field_names=("authorization", "api_key"),
)
if redacted["Authorization"] != "<secret-masked>" or redacted["api_key"] != "<secret-masked>":
    raise AssertionError(f"Secrets non masqués: {redacted}")
if redacted["X-Trace-Id"] != "trace-unit-t010":
    raise AssertionError(f"Champ non secret altéré: {redacted}")

collector = InMemoryObservabilityCollector()
collector.record_gateway_observation(
    GatewayObservation(
        trace_id="trace-unit-t010-success",
        request_id="request-unit-t010-success",
        idempotency_key="idem-unit-t010-success",
        phase="spark_inference",
        status="SUCCEEDED",
        latency_ms=42.5,
        served_model="gemma-research-t010",
        model_revision="gemma-4-revision-t010",
        runtime_version="vllm-openai-t010",
        prompt_hash=prompt_hash,
        request_payload_bytes=512,
        response_payload_bytes=128,
        ttft_ms=11.25,
        retry_count=1,
        circuit_open=False,
        output_interrupted=False,
        error_code=None,
    )
)

serialized = json.dumps(
    {
        "logs": [log.to_mapping() for log in collector.logs()],
        "metrics": [metric.to_mapping() for metric in collector.metrics()],
    },
    ensure_ascii=False,
    sort_keys=True,
)
for forbidden in (PROMPT_CANARY, RESPONSE_CANARY, SECRET_CANARY):
    if forbidden in serialized:
        raise AssertionError(f"Contenu interdit exposé dans l'observabilité: {forbidden}")

log = collector.logs()[0]
log_mapping = log.to_mapping()
for required_field in (
    "component",
    "trace_id",
    "phase",
    "status",
    "latency_ms",
    "served_model",
    "model_revision",
    "runtime_version",
    "prompt_hash",
):
    if required_field not in log_mapping:
        raise AssertionError(f"Champ obligatoire absent du log: {required_field}")
if log_mapping["component"] != "llm-gateway":
    raise AssertionError(f"Composant gateway invalide: {log_mapping}")
if log_mapping["model_revision"] != "gemma-4-revision-t010":
    raise AssertionError(f"Version modèle absente: {log_mapping}")
if log_mapping["runtime_version"] != "vllm-openai-t010":
    raise AssertionError(f"Version vLLM absente: {log_mapping}")

metric_names = {metric.name for metric in collector.metrics()}
for expected_metric in (
    "llm_gateway_request_total",
    "llm_gateway_request_latency_ms",
    "llm_gateway_ttft_ms",
    "llm_gateway_payload_bytes",
    "llm_gateway_retry_before_first_token_total",
):
    if expected_metric not in metric_names:
        raise AssertionError(f"Métrique gateway absente: {expected_metric}")

collector.record_gateway_observation(
    GatewayObservation(
        trace_id="trace-unit-t010-circuit",
        request_id="request-unit-t010-circuit",
        idempotency_key="idem-unit-t010-circuit",
        phase="spark_inference",
        status="LLM_CIRCUIT_OPEN",
        latency_ms=1.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version=None,
        prompt_hash=prompt_hash,
        request_payload_bytes=512,
        response_payload_bytes=None,
        ttft_ms=None,
        retry_count=0,
        circuit_open=True,
        output_interrupted=False,
        error_code="LLM_CIRCUIT_OPEN",
    )
)
collector.record_gateway_observation(
    GatewayObservation(
        trace_id="trace-unit-t010-partial",
        request_id="request-unit-t010-partial",
        idempotency_key="idem-unit-t010-partial",
        phase="spark_inference",
        status="LLM_PARTIAL_OUTPUT",
        latency_ms=15.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version=None,
        prompt_hash=prompt_hash,
        request_payload_bytes=512,
        response_payload_bytes=None,
        ttft_ms=8.0,
        retry_count=0,
        circuit_open=False,
        output_interrupted=True,
        error_code="LLM_PARTIAL_OUTPUT",
    )
)
metric_names = {metric.name for metric in collector.metrics()}
if "llm_gateway_circuit_breaker_open" not in metric_names:
    raise AssertionError("Métrique circuit breaker absente.")
if "llm_gateway_output_interrupted_total" not in metric_names:
    raise AssertionError("Métrique sortie interrompue absente.")

collector.record_job_observation(
    JobObservation(
        trace_id="trace-unit-t010-job",
        job_id="JOB-M002-000010",
        job_name="VERIFY_RESPONSE",
        phase="execute",
        status="succeeded",
        latency_ms=9.5,
        attempt=1,
    )
)
collector.record_outbox_observation(
    OutboxObservation(
        trace_id="trace-unit-t010-outbox",
        event_id="EVT-M002-T010",
        producer_context="research_answering",
        phase="deliver",
        status="delivered",
        latency_ms=3.0,
        duplicate=False,
    )
)
components = {entry.component for entry in collector.logs()}
if {"job-runtime", "outbox"} - components:
    raise AssertionError(f"Collecteurs jobs/outbox absents: {components}")

assert_contract_error(
    "OBS_TRACE_ID_REQUIRED",
    lambda: GatewayObservation(
        trace_id="",
        request_id="request-unit-t010",
        idempotency_key="idem-unit-t010",
        phase="spark_inference",
        status="SUCCEEDED",
        latency_ms=1.0,
        served_model="gemma-research-t010",
        model_revision="gemma-4-revision-t010",
        runtime_version="vllm-openai-t010",
        prompt_hash=prompt_hash,
        request_payload_bytes=1,
        response_payload_bytes=1,
        ttft_ms=1.0,
        retry_count=0,
        circuit_open=False,
        output_interrupted=False,
        error_code=None,
    ),
)
assert_contract_error(
    "OBS_MODEL_REVISION_REQUIRED",
    lambda: GatewayObservation(
        trace_id="trace-unit-t010",
        request_id="request-unit-t010",
        idempotency_key="idem-unit-t010",
        phase="spark_inference",
        status="SUCCEEDED",
        latency_ms=1.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version="vllm-openai-t010",
        prompt_hash=prompt_hash,
        request_payload_bytes=1,
        response_payload_bytes=1,
        ttft_ms=1.0,
        retry_count=0,
        circuit_open=False,
        output_interrupted=False,
        error_code=None,
    ),
)
assert_contract_error(
    "OBS_LATENCY_INVALID",
    lambda: GatewayObservation(
        trace_id="trace-unit-t010",
        request_id="request-unit-t010",
        idempotency_key="idem-unit-t010",
        phase="spark_inference",
        status="LLM_FIRST_TOKEN_TIMEOUT",
        latency_ms=-1.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version=None,
        prompt_hash=prompt_hash,
        request_payload_bytes=1,
        response_payload_bytes=None,
        ttft_ms=None,
        retry_count=0,
        circuit_open=False,
        output_interrupted=False,
        error_code="LLM_FIRST_TOKEN_TIMEOUT",
    ),
)
assert_contract_error(
    "OBS_PROMPT_HASH_INVALID",
    lambda: GatewayObservation(
        trace_id="trace-unit-t010",
        request_id="request-unit-t010",
        idempotency_key="idem-unit-t010",
        phase="spark_inference",
        status="LLM_FIRST_TOKEN_TIMEOUT",
        latency_ms=1.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version=None,
        prompt_hash=PROMPT_CANARY,
        request_payload_bytes=1,
        response_payload_bytes=None,
        ttft_ms=None,
        retry_count=0,
        circuit_open=False,
        output_interrupted=False,
        error_code="LLM_FIRST_TOKEN_TIMEOUT",
    ),
)
assert_contract_error(
    "OBS_RETRY_COUNT_INVALID",
    lambda: GatewayObservation(
        trace_id="trace-unit-t010",
        request_id="request-unit-t010",
        idempotency_key="idem-unit-t010",
        phase="spark_inference",
        status="LLM_FIRST_TOKEN_TIMEOUT",
        latency_ms=1.0,
        served_model="gemma-research-t010",
        model_revision=None,
        runtime_version=None,
        prompt_hash=prompt_hash,
        request_payload_bytes=1,
        response_payload_bytes=None,
        ttft_ms=None,
        retry_count=-1,
        circuit_open=False,
        output_interrupted=False,
        error_code="LLM_FIRST_TOKEN_TIMEOUT",
    ),
)

print("Tests unitaires observabilité gateway M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_gateway_observability_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires observabilit$($eAcute) gateway M-002: OK"
