$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import copy
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.local_compose import parse_local_compose_document, validate_local_compose


BASE_GATEWAY_ENVIRONMENT = {
    "GEMMA_BASE_URL": "${GEMMA_BASE_URL?GEMMA_BASE_URL requis}",
    "GEMMA_MODEL": "${GEMMA_MODEL?GEMMA_MODEL requis}",
    "GEMMA_MODEL_REVISION": "${GEMMA_MODEL_REVISION?GEMMA_MODEL_REVISION requis}",
    "GEMMA_RUNTIME_VERSION": "${GEMMA_RUNTIME_VERSION?GEMMA_RUNTIME_VERSION requis}",
    "GEMMA_AUTH_MODE": "none",
    "GEMMA_TLS_MODE": "disabled",
    "GEMMA_TIMEOUT_SECONDS": "${GEMMA_TIMEOUT_SECONDS?GEMMA_TIMEOUT_SECONDS requis}",
    "GEMMA_RETRY_BEFORE_FIRST_TOKEN": "${GEMMA_RETRY_BEFORE_FIRST_TOKEN?GEMMA_RETRY_BEFORE_FIRST_TOKEN requis}",
    "GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD": (
        "${GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD?GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD requis}"
    ),
    "GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS": (
        "${GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS?GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS requis}"
    ),
}


def gateway_environment(**overrides):
    environment = dict(BASE_GATEWAY_ENVIRONMENT)
    for key, value in overrides.items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value
    return environment


BASE_SERVICES = {
    "edge-gateway": {
        "image": "caddy@sha256:" + "a" * 64,
        "ports": ["127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:443"],
        "networks": ["edge", "core"],
        "tmpfs": ["/tmp"],
    },
    "ui": {
        "image": "ostrading/ui:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "ui", "8081"],
        "expose": ["8081"],
        "networks": ["core"],
        "environment": {"UI_API_URL": "${UI_API_URL?UI_API_URL requis}"},
    },
    "orchestrator-api": {
        "image": "ostrading/orchestrator-api:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "orchestrator-api", "8080"],
        "expose": ["8080"],
        "networks": ["core"],
        "environment": {
            "DATABASE_URL": "${DATABASE_URL?DATABASE_URL requis}",
            "QDRANT_URL": "${QDRANT_URL?QDRANT_URL requis}",
            "LLM_GATEWAY_URL": "${LLM_GATEWAY_URL?LLM_GATEWAY_URL requis}",
        },
    },
    "llm-gateway": {
        "image": "ostrading/llm-gateway:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "llm-gateway", "8090"],
        "expose": ["8090"],
        "networks": ["core", "spark-egress"],
        "environment": gateway_environment(),
    },
    "postgres": {
        "image": "postgres@sha256:" + "b" * 64,
        "expose": ["5432"],
        "networks": ["core"],
        "environment": {
            "POSTGRES_DB": "${POSTGRES_DB?POSTGRES_DB requis}",
            "POSTGRES_USER": "${POSTGRES_USER?POSTGRES_USER requis}",
            "POSTGRES_PASSWORD_FILE": "/run/secrets/postgres_password",
        },
        "secrets": ["postgres_password"],
    },
    "qdrant": {
        "image": "qdrant/qdrant@sha256:" + "c" * 64,
        "expose": ["6333"],
        "networks": ["core"],
    },
    "granite-docling": {
        "image": "ostrading/granite-docling:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "granite-docling", "8001"],
        "expose": ["8001"],
        "networks": ["core"],
    },
    "embedding-service": {
        "image": "ostrading/embedding-service:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "embedding-service", "8101"],
        "expose": ["8101"],
        "networks": ["core"],
    },
    "reranker-service": {
        "image": "ostrading/reranker-service:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "reranker-service", "8102"],
        "expose": ["8102"],
        "networks": ["core"],
    },
    "worker-documents": {
        "image": "ostrading/worker-documents:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "run-worker", "worker-documents"],
        "networks": ["core"],
    },
    "worker-research": {
        "image": "ostrading/worker-research:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "run-worker", "worker-research"],
        "networks": ["core"],
    },
    "worker-backtest": {
        "image": "ostrading/worker-backtest:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "run-worker", "worker-backtest"],
        "networks": ["core"],
    },
    "backtest-engine": {
        "image": "ostrading/backtest-engine:0.0.0-m002",
        "command": ["python", "-m", "app.platform.local_runtime", "serve-http", "backtest-engine", "8200"],
        "expose": ["8200"],
        "networks": ["core"],
    },
}


def service_lines(service_id, definition):
    lines = [f"  {service_id}:", f"    image: {definition['image']}"]
    command = definition.get("command", [])
    if command:
        lines.append("    command:")
        for value in command:
            lines.append(f'      - "{value}"')
    for section in ("ports", "expose", "networks", "secrets"):
        values = definition.get(section, [])
        if values:
            lines.append(f"    {section}:")
            for value in values:
                lines.append(f'      - "{value}"')

    tmpfs = definition.get("tmpfs", [])
    if tmpfs:
        lines.append("    tmpfs:")
        for value in tmpfs:
            lines.append(f'      - "{value}"')

    environment = definition.get("environment", {})
    if environment:
        lines.append("    environment:")
        for name, value in environment.items():
            lines.append(f'      {name}: "{value}"')

    if definition.get("healthcheck", True):
        lines.extend(
            [
                "    healthcheck:",
                "      test:",
                "        - CMD-SHELL",
                f'        - "test -f /tmp/{service_id}.health"',
                "      interval: 30s",
                "      timeout: 5s",
                "      retries: 3",
                "      start_period: 10s",
            ]
        )

    return lines


def valid_compose(service_overrides=None, top_level_secrets=None):
    services = copy.deepcopy(BASE_SERVICES)
    for service_id, overrides in (service_overrides or {}).items():
        services[service_id].update(overrides)
        for key, value in overrides.items():
            if value is None:
                services[service_id].pop(key, None)

    secret_names = top_level_secrets or ["postgres_password"]
    lines = ["name: trading-research-assistant", "services:"]
    for service_id, definition in services.items():
        lines.extend(service_lines(service_id, definition))
    lines.extend(
        [
            "networks:",
            "  edge: {}",
            "  core:",
            "    internal: true",
            "  spark-egress: {}",
            "secrets:",
        ]
    )
    for secret_name in secret_names:
        suffix = ".pem" if secret_name == "spark_ca" else ""
        lines.extend([f"  {secret_name}:", f"    file: ./secrets/{secret_name}{suffix}"])

    return "\n".join(lines) + "\n"


def assert_raises(expected_fragment, document):
    try:
        validate_local_compose(parse_local_compose_document(document, source="fixture-compose.yaml"))
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


compose = parse_local_compose_document(valid_compose(), source="fixture-compose.yaml")
validate_local_compose(compose)

postgres = compose.service("postgres")
if postgres.ports != ():
    raise AssertionError("Le parseur ne doit pas confondre ports et expose pour PostgreSQL.")
if postgres.expose != ("5432",):
    raise AssertionError(f"Expose PostgreSQL incorrect: {postgres.expose}")

edge_gateway = compose.service("edge-gateway")
if edge_gateway.ports != ("127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:443",):
    raise AssertionError(f"Ports edge-gateway incorrects: {edge_gateway.ports}")
if edge_gateway.tmpfs != ("/tmp",):
    raise AssertionError(f"tmpfs edge-gateway incorrect: {edge_gateway.tmpfs}")

assert_raises(
    "tmpfs /tmp requis pour edge-gateway",
    valid_compose({"edge-gateway": {"tmpfs": []}}),
)

assert_raises(
    "interdit pour service interne: postgres",
    valid_compose({"postgres": {"ports": ["127.0.0.1:5432:5432"]}}),
)

assert_raises(
    "pour service qdrant",
    valid_compose({"qdrant": {"image": "qdrant/qdrant:latest"}}),
)

assert_raises(
    "Image tierce sans digest",
    valid_compose({"postgres": {"image": "postgres:17.2-alpine"}}),
)

assert_raises(
    "Endpoint Spark invalide",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_BASE_URL="https://api.openai.com/v1")}}),
)

assert_raises(
    "module_absent",
    valid_compose({"llm-gateway": {"command": ["python", "-m", "app.platform.module_absent"]}}),
)

assert_raises(
    "Healthcheck absent pour service: embedding-service",
    valid_compose({"embedding-service": {"healthcheck": False}}),
)

assert_raises(
    "Variable gateway Spark absente: GEMMA_AUTH_MODE",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_AUTH_MODE=None)}}),
)

assert_raises(
    "Variable gateway Spark absente: GEMMA_MODEL_REVISION",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_MODEL_REVISION=None)}}),
)

assert_raises(
    "Variable gateway Spark absente: GEMMA_RUNTIME_VERSION",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_RUNTIME_VERSION=None)}}),
)

assert_raises(
    "Entier positif requis pour service llm-gateway: GEMMA_TIMEOUT_SECONDS",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_TIMEOUT_SECONDS="0")}}),
)

assert_raises(
    "Entier positif ou nul requis pour service llm-gateway: GEMMA_RETRY_BEFORE_FIRST_TOKEN",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_RETRY_BEFORE_FIRST_TOKEN="-1")}}),
)

assert_raises(
    "spark-egress interdit pour service: worker-research",
    valid_compose({"worker-research": {"networks": ["core", "spark-egress"]}}),
)

assert_raises(
    "GEMMA_API_KEY_FILE interdit quand GEMMA_AUTH_MODE=none",
    valid_compose(
        {"llm-gateway": {"environment": gateway_environment(GEMMA_API_KEY_FILE="/run/secrets/gemma_api_key")}}
    ),
)

assert_raises(
    "Secret Spark interdit pour llm-gateway: gemma_api_key",
    valid_compose(
        {"llm-gateway": {"secrets": ["gemma_api_key"]}},
        top_level_secrets=["postgres_password", "gemma_api_key"],
    ),
)

assert_raises(
    "Mode TLS Spark invalide",
    valid_compose({"llm-gateway": {"environment": gateway_environment(GEMMA_TLS_MODE="implicit")}}),
)

print("Tests unitaires Compose local M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_local_compose_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires Compose local M-002: OK"
