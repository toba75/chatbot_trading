param(
    [Parameter(Mandatory = $false)]
    [string] $ConfigPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$effectiveConfigPath = $ConfigPath
if ([string]::IsNullOrWhiteSpace($effectiveConfigPath)) {
    $effectiveConfigPath = Join-Path $repoRoot "config/application.yaml"
}
if (-not (Test-Path -LiteralPath $effectiveConfigPath -PathType Leaf)) {
    throw "Configuration locale requise pour le test réel M13-reality: $effectiveConfigPath"
}
$resolvedConfigPath = (Resolve-Path -LiteralPath $effectiveConfigPath).Path
$pythonCode = @'
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


repo_root = sys.argv[1]
config_path = sys.argv[2]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.configuration import load_application_configuration  # noqa: E402


configuration = load_application_configuration(config_path=config_path, environment_snapshot={})
base_url = configuration.services.llm_gateway.spark_endpoint_url.rstrip("/")
served_model = configuration.models.llm.served_model_name
model_revision = configuration.models.llm.model_revision
runtime_version = configuration.models.llm.runtime_version
if configuration.services.llm_gateway.auth_mode != "none":
    raise AssertionError("auth_mode doit valoir none pour le conteneur Spark actuel.")
if configuration.services.llm_gateway.tls_mode != "disabled":
    raise AssertionError("tls_mode doit valoir disabled pour le conteneur Spark actuel.")
gateway_url = "http://127.0.0.1:8090"


def get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"Payload Spark non objet pour {path}: {payload!r}")
    return payload


def wait_for_gateway() -> None:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{gateway_url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - le message final conserve l'erreur exacte.
            last_error = exc
        time.sleep(0.5)
    raise AssertionError(f"Service llm-gateway local indisponible: {last_error!r}")


models_payload = get_json("/models")
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

metadata_payload = get_json("/metadata")
selected_profile_id = metadata_payload.get("selectedModelProfileId")
if not isinstance(selected_profile_id, str) or selected_profile_id.strip() == "":
    raise AssertionError(f"Profil modèle Spark absent de /metadata: {metadata_payload!r}")
expected_model_revision = f"{served_model}@{selected_profile_id}"
if model_revision != expected_model_revision:
    raise AssertionError(
        f"GEMMA_MODEL_REVISION incohérent: attendu {expected_model_revision!r}, obtenu {model_revision!r}"
    )

version_payload = get_json("/version")
release = version_payload.get("release")
api_version = version_payload.get("api")
if not isinstance(release, str) or not isinstance(api_version, str):
    raise AssertionError(f"Version runtime Spark invalide: {version_payload!r}")
expected_runtime_version = f"nim-{release}-api-{api_version}"
if runtime_version != expected_runtime_version:
    raise AssertionError(
        f"GEMMA_RUNTIME_VERSION incohérent: attendu {expected_runtime_version!r}, obtenu {runtime_version!r}"
    )

request_body = {
    "messages": [
        {
            "role": "user",
            "content": 'Réponds uniquement avec ce JSON: {"answer":"OK"}.',
        }
    ],
    "output_schema": {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    },
    "schema_name": "m13_reality_gateway_smoke",
    "schema_version": "1.0",
    "trace_id": "TRACE-M013-REALITY-GATEWAY-0001",
    "request_id": "REQ-M013-REALITY-GATEWAY-0001",
    "idempotency_key": "IDEMP-M013-REALITY-GATEWAY-0001",
    "prompt_id": "PROMPT-M013-REALITY-GATEWAY-SMOKE",
    "prompt_version": "1.0",
    "sampling_parameters": {"max_tokens": 64, "temperature": 0},
}

wait_for_gateway()
request = urllib.request.Request(
    f"{gateway_url}/v1/infer",
    data=json.dumps(request_body).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=180) as response:
        status_code = response.status
        response_body = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    error_body = exc.read().decode("utf-8", errors="replace")
    raise AssertionError(f"Réponse llm-gateway réelle inattendue: {exc.code}, {error_body}") from exc

if status_code != 200 or not isinstance(response_body, dict):
    raise AssertionError(f"Réponse llm-gateway réelle inattendue: {status_code}, {response_body!r}")

if response_body.get("structured_output") != {"answer": "OK"}:
    raise AssertionError(f"Sortie structurée réelle inattendue: {response_body!r}")

provenance = response_body.get("provenance")
if not isinstance(provenance, dict):
    raise AssertionError(f"Provenance gateway absente: {response_body!r}")
if provenance.get("model_id") != served_model:
    raise AssertionError(f"Modèle servi absent de la provenance: {provenance!r}")
if provenance.get("model_revision") != model_revision:
    raise AssertionError(f"Révision modèle déclarée absente: {provenance!r}")
if provenance.get("runtime_version") != runtime_version:
    raise AssertionError(f"Runtime déclaré absent: {provenance!r}")
if provenance.get("prompt_id") != "PROMPT-M013-REALITY-GATEWAY-SMOKE":
    raise AssertionError(f"Prompt id absent de la provenance: {provenance!r}")
if not isinstance(response_body.get("raw_response_id"), str) or response_body["raw_response_id"].strip() == "":
    raise AssertionError(f"Identifiant brut Spark absent: {response_body!r}")

print("Test d'acceptation M13-reality gateway LLM réel: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_real_spark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
$runtimeStdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_runtime_" + [System.Guid]::NewGuid().ToString("N") + ".out.log")
$runtimeStderrPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_llm_gateway_runtime_" + [System.Guid]::NewGuid().ToString("N") + ".err.log")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $runtimeProcess = Start-Process `
        -FilePath $pythonExecutable `
        -ArgumentList @("-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090", "--config", $resolvedConfigPath) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $runtimeStdoutPath `
        -RedirectStandardError $runtimeStderrPath `
        -WindowStyle Hidden `
        -PassThru

    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath `
        $repoRoot `
        $resolvedConfigPath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    if ($null -ne $runtimeProcess -and -not $runtimeProcess.HasExited) {
        Stop-Process -Id $runtimeProcess.Id -Force
    }
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    $runtimeOutput = @()
    if (Test-Path -LiteralPath $runtimeStdoutPath) {
        $runtimeOutput += Get-Content -LiteralPath $runtimeStdoutPath
    }
    if (Test-Path -LiteralPath $runtimeStderrPath) {
        $runtimeOutput += Get-Content -LiteralPath $runtimeStderrPath
    }
    Remove-Item -LiteralPath $runtimeStdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $runtimeStderrPath -Force -ErrorAction SilentlyContinue
    throw (($output + $runtimeOutput) -join "`n")
}

Remove-Item -LiteralPath $runtimeStdoutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $runtimeStderrPath -Force -ErrorAction SilentlyContinue
Write-Host "Test d'acceptation M13-reality gateway LLM réel: OK"
