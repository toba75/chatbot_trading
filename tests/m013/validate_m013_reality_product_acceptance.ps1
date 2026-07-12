param(
    [Parameter(Mandatory = $false)]
    [string] $ConfigPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$effectiveConfigPath = $ConfigPath
if ([string]::IsNullOrWhiteSpace($effectiveConfigPath)) {
    $effectiveConfigPath = Join-Path $repoRoot "config/application.yaml"
}
if (-not (Test-Path -LiteralPath $effectiveConfigPath -PathType Leaf)) {
    throw "Configuration locale requise pour le test produit M13-reality: $effectiveConfigPath"
}
$resolvedConfigPath = (Resolve-Path -LiteralPath $effectiveConfigPath).Path
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uvCommand) {
    throw "UV_RUNTIME_REQUIRED"
}
$uvExecutable = $uvCommand.Source
$postgresContainer = "ost-m013-reality-postgres-" + [System.Guid]::NewGuid().ToString("N")
$runtimeConfigPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_config_" + [System.Guid]::NewGuid().ToString("N") + ".yaml")
$tcpListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$tcpListener.Start()
$postgresPort = ([System.Net.IPEndPoint]$tcpListener.LocalEndpoint).Port
$tcpListener.Stop()
$postgresPasswordPath = Join-Path $repoRoot "deploy/local-compose/secrets/postgres_password"
if (-not (Test-Path -LiteralPath $postgresPasswordPath -PathType Leaf)) {
    throw "POSTGRES_SECRET_REQUIRED"
}
$postgresPassword = (Get-Content -Raw -Encoding UTF8 -LiteralPath $postgresPasswordPath).TrimEnd("`r", "`n")
$runtimeSecretRelativePath = "config/secrets/local/m013_reality_postgres_password"
$runtimeSecretPath = Join-Path $repoRoot $runtimeSecretRelativePath
[System.IO.File]::WriteAllText($runtimeSecretPath, $postgresPassword, $utf8NoBom)
$runtimeConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedConfigPath
$runtimeConfig = $runtimeConfig.Replace(
    "postgresql+psycopg://app@postgres/app",
    "postgresql+psycopg://app@127.0.0.1:$postgresPort/app"
)
$runtimeConfig = $runtimeConfig.Replace(
    "config/secrets/local/postgres_password",
    $runtimeSecretRelativePath
)
[System.IO.File]::WriteAllText($runtimeConfigPath, $runtimeConfig, $utf8NoBom)
$pythonCode = @'
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request


repo_root = sys.argv[1]
config_path = sys.argv[2]

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.configuration import load_application_configuration  # noqa: E402
from app.evaluation.domain.llm_real_path_benchmark import (  # noqa: E402
    REQUIRED_LLM_TASKS,
    REQUIRED_LLM_TECHNICAL_METRICS,
)


configuration = load_application_configuration(config_path=config_path, environment_snapshot={})
served_model = configuration.models.llm.served_model_name
model_revision = configuration.models.llm.model_revision
runtime_version = configuration.models.llm.runtime_version
if configuration.services.llm_gateway.auth_mode != "none":
    raise AssertionError("auth_mode doit valoir none pour le conteneur Spark actuel.")
if configuration.services.llm_gateway.tls_mode != "disabled":
    raise AssertionError("tls_mode doit valoir disabled pour le conteneur Spark actuel.")


orchestrator_url = "http://127.0.0.1:8080"
gateway_url = "http://127.0.0.1:8090"
real_path_segments = ("docker-local", "orchestrator-api", "llm-gateway", "vllm-spark")
forbidden_markers = ("fixture", "synthetic", "fake_provider", "stub_provider", "mock_provider")


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_text(value: object, message: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise AssertionError(message)
    if value != value.strip():
        raise AssertionError(f"{message} Valeur non normalisée: {value!r}")
    return value


def assert_sha256(value: object, message: str) -> None:
    parsed = assert_text(value, message)
    if re.fullmatch(r"[0-9a-f]{64}", parsed) is None:
        raise AssertionError(f"{message} Hash invalide: {parsed!r}")


def wait_health(base_url: str, service_name: str) -> None:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload.get("status") == "healthy":
                        return
        except Exception as exc:  # noqa: BLE001 - le message final conserve l'erreur exacte.
            last_error = exc
        time.sleep(0.5)
    raise AssertionError(f"Service {service_name} local indisponible: {last_error!r}")


def post_json(url: str, payload: dict[str, object], timeout_seconds: int) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
            body = json.loads(raw_body) if raw_body.strip() else {}
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw_error)
        except json.JSONDecodeError:
            body = raw_error
        return exc.code, body


def assert_no_fake_marker(payload: object, message: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for marker in forbidden_markers:
        if marker in serialized:
            raise AssertionError(f"{message} Marqueur interdit: {marker}")


def assert_provenance(payload: dict[str, object], message: str) -> None:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise AssertionError(f"{message} Provenance absente: {payload!r}")
    assert_equal(provenance.get("model_id"), served_model, f"{message} Modèle absent de la provenance.")
    assert_equal(
        provenance.get("model_revision"),
        model_revision,
        f"{message} Révision modèle absente de la provenance.",
    )
    assert_equal(
        provenance.get("runtime_version"),
        runtime_version,
        f"{message} Runtime absent de la provenance.",
    )
    assert_sha256(provenance.get("input_hash"), f"{message} Hash d'entrée absent.")
    assert_sha256(provenance.get("output_hash"), f"{message} Hash de sortie absent.")


wait_health(gateway_url, "llm-gateway")
wait_health(orchestrator_url, "orchestrator-api")

# Given un utilisateur appelle le contrat public du chat produit local.
chat_request = {
    "model": served_model,
    "conversation_id": "CONV-M013-REALITY-0001",
    "trace_id": "TRACE-M013-REALITY-CHAT-0001",
    "request_id": "REQ-M013-REALITY-CHAT-0001",
    "idempotency_key": "IDEMP-M013-REALITY-CHAT-0001",
    "messages": [
        {
            "role": "user",
            "content": "Réponds en français en une phrase au contrôle M13-reality.",
        }
    ],
    "sampling_parameters": {"max_tokens": 96, "temperature": 0},
}

# When la réponse est produite localement.
chat_status, chat_response = post_json(
    f"{orchestrator_url}/v1/chat/completions",
    chat_request,
    timeout_seconds=240,
)

# Then le chat produit doit passer par llm-gateway et Spark, sans provider factice.
if chat_status != 200 or not isinstance(chat_response, dict):
    raise AssertionError(f"Chat produit réel M13-reality attendu HTTP 200, obtenu {chat_status}: {chat_response!r}")
assert_equal(chat_response.get("object"), "chat.completion", "Objet chat OpenAI-compatible invalide.")
assert_equal(chat_response.get("model"), served_model, "Modèle chat invalide.")
choices = chat_response.get("choices")
if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
    raise AssertionError(f"Choix chat invalide: {chat_response!r}")
message = choices[0].get("message")
if not isinstance(message, dict):
    raise AssertionError(f"Message assistant absent: {chat_response!r}")
assert_equal(message.get("role"), "assistant", "Rôle assistant invalide.")
assert_text(message.get("content"), "Contenu assistant réel absent.")
product = chat_response.get("ost_product")
if not isinstance(product, dict):
    raise AssertionError(f"Métadonnées produit absentes: {chat_response!r}")
assert_equal(product.get("execution_mode"), "live_spark", "Le chat doit déclarer le mode réel Spark.")
assert_equal(tuple(product.get("path_segments", ())), real_path_segments, "Chemin produit réel invalide.")
assert_equal(product.get("gateway_endpoint"), f"{gateway_url}/v1/infer", "Endpoint gateway réel invalide.")
assert_text(product.get("raw_response_id"), "Identifiant brut Spark absent du chat.")
assert_provenance(product, "Chat produit réel.")
assert_no_fake_marker(chat_response, "Le chat produit ne doit pas exposer de provider factice.")

# Given le même runtime doit recalculer le benchmark LLM depuis le chemin réel.
benchmark_request = {
    "model": served_model,
    "run_id": "LLMRUN-M013-REALITY-LIVE-0001",
    "trace_id": "TRACE-M013-REALITY-BENCHMARK-0001",
    "request_id": "REQ-M013-REALITY-BENCHMARK-0001",
    "idempotency_key": "IDEMP-M013-REALITY-BENCHMARK-0001",
    "sampling_parameters": {"max_tokens": 96, "temperature": 0},
}

# When le benchmark est lancé depuis l'orchestrator.
benchmark_status, benchmark_response = post_json(
    f"{orchestrator_url}/v1/evaluation/llm-real-path-benchmark",
    benchmark_request,
    timeout_seconds=900,
)

# Then toutes les tâches obligatoires M-012 sont réellement rejouées et hashées.
if benchmark_status != 200 or not isinstance(benchmark_response, dict):
    raise AssertionError(
        f"Benchmark LLM réel M13-reality attendu HTTP 200, obtenu {benchmark_status}: {benchmark_response!r}"
    )
assert_equal(benchmark_response.get("object"), "llm_real_path_benchmark.run", "Objet benchmark invalide.")
assert_equal(benchmark_response.get("execution_mode"), "live_spark", "Le benchmark doit déclarer le mode réel Spark.")
assert_equal(benchmark_response.get("model"), served_model, "Modèle benchmark invalide.")
assert_equal(tuple(benchmark_response.get("path_segments", ())), real_path_segments, "Chemin benchmark réel invalide.")
assert_equal(tuple(benchmark_response.get("task_names", ())), REQUIRED_LLM_TASKS, "Tâches LLM obligatoires invalides.")
assert_equal(
    set(benchmark_response.get("technical_metric_names", ())),
    set(REQUIRED_LLM_TECHNICAL_METRICS),
    "Métriques techniques LLM obligatoires invalides.",
)
task_results = benchmark_response.get("task_results")
if not isinstance(task_results, list) or len(task_results) != len(REQUIRED_LLM_TASKS):
    raise AssertionError(f"Résultats de tâches LLM incomplets: {benchmark_response!r}")
seen_tasks: set[str] = set()
for task_result in task_results:
    if not isinstance(task_result, dict):
        raise AssertionError(f"Résultat de tâche non objet: {task_result!r}")
    task_name = assert_text(task_result.get("task_name"), "Nom de tâche LLM absent.")
    seen_tasks.add(task_name)
    if task_result.get("passed") is not True:
        raise AssertionError(f"Tâche LLM réelle non réussie: {task_result!r}")
    assert_text(task_result.get("raw_response_id"), f"Identifiant brut Spark absent pour {task_name}.")
    assert_sha256(task_result.get("response_json_sha256"), f"Hash JSON absent pour {task_name}.")
    assert_provenance(task_result, f"Tâche LLM {task_name}.")
assert_equal(tuple(sorted(seen_tasks)), tuple(sorted(REQUIRED_LLM_TASKS)), "Tâches LLM rejouées invalides.")
assert_no_fake_marker(benchmark_response, "Le benchmark ne doit pas exposer de fixture synthétique.")

print("Test d'acceptation M13-reality chat produit et benchmark LLM réels: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_product_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
$gatewayStdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_gateway_" + [System.Guid]::NewGuid().ToString("N") + ".out.log")
$gatewayStderrPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_gateway_" + [System.Guid]::NewGuid().ToString("N") + ".err.log")
$orchestratorStdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_orchestrator_" + [System.Guid]::NewGuid().ToString("N") + ".out.log")
$orchestratorStderrPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_orchestrator_" + [System.Guid]::NewGuid().ToString("N") + ".err.log")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $postgresImage = "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
    $postgresId = & docker run --detach --name $postgresContainer `
        --env POSTGRES_DB=app --env POSTGRES_USER=app --env "POSTGRES_PASSWORD=$postgresPassword" `
        --publish "127.0.0.1:${postgresPort}:5432" $postgresImage 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($postgresId)) {
        throw "POSTGRES_DOCKER_START_FAILED: $postgresId"
    }
    $postgresReady = $false
    foreach ($attempt in 1..120) {
        & docker exec $postgresContainer pg_isready -U app -d app *> $null
        if ($LASTEXITCODE -eq 0) {
            $postgresReady = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $postgresReady) {
        throw "POSTGRES_DOCKER_NOT_READY"
    }

    $gatewayProcess = Start-Process `
        -FilePath $pythonExecutable `
        -ArgumentList @("-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090", "--config", $runtimeConfigPath) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $gatewayStdoutPath `
        -RedirectStandardError $gatewayStderrPath `
        -WindowStyle Hidden `
        -PassThru

    $orchestratorProcess = Start-Process `
        -FilePath $uvExecutable `
        -ArgumentList @("run", "--no-sync", "api", "--config", $runtimeConfigPath) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $orchestratorStdoutPath `
        -RedirectStandardError $orchestratorStderrPath `
        -WindowStyle Hidden `
        -PassThru

    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath `
        $repoRoot `
        $runtimeConfigPath 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    if ($null -ne $gatewayProcess -and -not $gatewayProcess.HasExited) {
        Stop-Process -Id $gatewayProcess.Id -Force
    }
    if ($null -ne $orchestratorProcess -and -not $orchestratorProcess.HasExited) {
        Stop-Process -Id $orchestratorProcess.Id -Force
    }
    & docker rm --force $postgresContainer *> $null
    Remove-Item -LiteralPath $runtimeConfigPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $runtimeSecretPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pythonScriptPath -Force -ErrorAction SilentlyContinue
}

if ($exitCode -ne 0) {
    $runtimeOutput = @()
    foreach ($path in @($gatewayStdoutPath, $gatewayStderrPath, $orchestratorStdoutPath, $orchestratorStderrPath)) {
        if (Test-Path -LiteralPath $path) {
            $runtimeOutput += Get-Content -LiteralPath $path
        }
    }
    foreach ($path in @($gatewayStdoutPath, $gatewayStderrPath, $orchestratorStdoutPath, $orchestratorStderrPath)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    throw (($output + $runtimeOutput) -join "`n")
}

foreach ($path in @($gatewayStdoutPath, $gatewayStderrPath, $orchestratorStdoutPath, $orchestratorStderrPath)) {
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
}
Write-Host "Test d'acceptation M13-reality chat produit et benchmark LLM réels: OK"
