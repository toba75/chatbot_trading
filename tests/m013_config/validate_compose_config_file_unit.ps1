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


APPLICATION_CONFIG_VOLUME = "./application.compose.yaml:/workspace/config/application.yaml:ro"
APPLICATION_SCHEMA_VOLUME = "../../config/application.schema.json:/workspace/config/application.schema.json:ro"
LLM_GATEWAY_LOCAL_SECRETS_VOLUME = "../../config/secrets/local:/workspace/config/secrets/local:ro"
APPLICATION_CONFIG_ARGUMENTS = ["--config", "/workspace/config/application.yaml"]

APPLICATION_SERVICE_IDS = (
    "ui",
    "orchestrator-api",
    "llm-gateway",
    "granite-docling",
    "embedding-service",
    "reranker-service",
    "worker-documents",
    "worker-research",
    "worker-backtest",
    "backtest-engine",
)


def runtime_command(*values: str) -> list[str]:
    return ["python", "-m", "app.platform.local_runtime", *values, *APPLICATION_CONFIG_ARGUMENTS]


def document_worker_command() -> list[str]:
    return ["--worker-id", "worker-documents", "--lease-seconds", "120", "--poll-seconds", "0.5", *APPLICATION_CONFIG_ARGUMENTS]


BASE_SERVICES = {
    "edge-gateway": {
        "image": "caddy@sha256:" + "a" * 64,
        "ports": ["127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"],
        "networks": ["edge", "core"],
        "tmpfs": ["/tmp"],
        "environment": {"CADDY_ADMIN": "${CADDY_ADMIN?CADDY_ADMIN requis}"},
        "read_only": True,
    },
    "ui": {
        "image": "ostrading/ui:0.0.0-m002",
        "command": runtime_command("serve-http", "ui", "8081"),
        "expose": ["8081"],
        "networks": ["core"],
        "volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
    "orchestrator-api": {
        "image": "ostrading/orchestrator-api:0.0.0-m002",
        "command": [*APPLICATION_CONFIG_ARGUMENTS],
        "expose": ["8080"],
        "networks": ["core"],
        "volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "tmpfs": ["/tmp:size=128m,mode=1777"],
        "read_only": True,
    },
    "llm-gateway": {
        "image": "ostrading/llm-gateway:0.0.0-m002",
        "command": runtime_command("serve-http", "llm-gateway", "8090"),
        "expose": ["8090"],
        "networks": ["core", "spark-egress"],
        "volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME, LLM_GATEWAY_LOCAL_SECRETS_VOLUME],
        "read_only": True,
    },
    "postgres": {
        "image": "postgres@sha256:" + "b" * 64,
        "expose": ["5432"],
        "networks": ["core"],
        "volumes": ["postgres-data:/var/lib/postgresql/data"],
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
        "volumes": ["qdrant-data:/qdrant/storage"],
    },
    "granite-docling": {
        "image": "ostrading/granite-docling:0.0.0-m002",
        "command": runtime_command("serve-http", "granite-docling", "8001"),
        "expose": ["8001"],
        "networks": ["core"],
        "volumes": ["model-cache:/models", APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
    "embedding-service": {
        "image": "ostrading/embedding-service:0.0.0-m002",
        "command": runtime_command("serve-http", "embedding-service", "8101"),
        "expose": ["8101"],
        "networks": ["core"],
        "volumes": ["model-cache:/models", APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
    "reranker-service": {
        "image": "ostrading/reranker-service:0.0.0-m002",
        "command": runtime_command("serve-http", "reranker-service", "8102"),
        "expose": ["8102"],
        "networks": ["core"],
        "volumes": ["model-cache:/models", APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
    "worker-documents": {
        "image": "ostrading/worker-documents:0.0.0-m002",
        "command": document_worker_command(),
        "networks": ["core"],
        "volumes": [
            "corpus-data:/workspace/corpus",
            "document-artifacts:/workspace/data",
            APPLICATION_CONFIG_VOLUME,
            APPLICATION_SCHEMA_VOLUME,
        ],
    },
    "worker-research": {
        "image": "ostrading/worker-research:0.0.0-m002",
        "command": runtime_command("run-worker", "worker-research"),
        "networks": ["core"],
        "volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
    "worker-backtest": {
        "image": "ostrading/worker-backtest:0.0.0-m002",
        "command": runtime_command("run-worker", "worker-backtest"),
        "networks": ["core"],
        "volumes": ["experiment-data:/workspace/data/experiments", APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
    },
    "backtest-engine": {
        "image": "ostrading/backtest-engine:0.0.0-m002",
        "command": runtime_command("serve-http", "backtest-engine", "8200"),
        "expose": ["8200"],
        "networks": ["core"],
        "volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME],
        "read_only": True,
    },
}


def service_lines(service_id: str, definition: dict) -> list[str]:
    lines = [f"  {service_id}:", f"    image: {definition['image']}"]
    command = definition.get("command", [])
    if command:
        lines.append("    command:")
        for value in command:
            lines.append(f'      - "{value}"')
    for section in ("ports", "expose", "networks", "volumes", "secrets", "env_file"):
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

    if definition.get("read_only"):
        lines.append("    read_only: true")

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


def valid_compose(service_overrides=None, top_level_secrets=None) -> str:
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
            "volumes:",
            "  caddy-data: {}",
            "  caddy-config: {}",
            "  postgres-data: {}",
            "  qdrant-data: {}",
            "  model-cache: {}",
            "  corpus-data: {}",
            "  document-artifacts: {}",
            "  experiment-data: {}",
            "secrets:",
        ]
    )
    for secret_name in secret_names:
        lines.extend([f"  {secret_name}:", f"    file: ./secrets/{secret_name}"])
    return "\n".join(lines) + "\n"


def assert_raises(expected_fragment: str, document: str) -> None:
    try:
        validate_local_compose(parse_local_compose_document(document, source="fixture-compose.yaml"))
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


compose = parse_local_compose_document(valid_compose(), source="fixture-compose.yaml")
validate_local_compose(compose)

for service_id in APPLICATION_SERVICE_IDS:
    service = compose.service(service_id)
    if "--config" not in service.command:
        raise AssertionError(f"--config absent pour service applicatif: {service_id}")
    if APPLICATION_CONFIG_VOLUME not in service.volumes:
        raise AssertionError(f"Montage configuration absent pour service applicatif: {service_id}")
    if APPLICATION_SCHEMA_VOLUME not in service.volumes:
        raise AssertionError(f"Montage schéma configuration absent pour service applicatif: {service_id}")
    if service_id == "llm-gateway" and LLM_GATEWAY_LOCAL_SECRETS_VOLUME not in service.volumes:
        raise AssertionError("Montage secrets Spark local absent pour llm-gateway")
    if service.environment:
        raise AssertionError(f"Environment applicatif non vide: {service_id}")

postgres = compose.service("postgres")
if set(postgres.environment) != {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD_FILE"}:
    raise AssertionError(f"Allowlist PostgreSQL invalide: {postgres.environment}")

orchestrator_api = compose.service("orchestrator-api")
if orchestrator_api.tmpfs != ("/tmp:size=128m,mode=1777",):
    raise AssertionError(f"tmpfs orchestrator-api incorrect: {orchestrator_api.tmpfs}")

assert_raises(
    "ORCHESTRATOR_TMPFS_BOUNDED_REQUIRED",
    valid_compose({"orchestrator-api": {"tmpfs": []}}),
)

assert_raises(
    "env_file interdit pour service worker-research",
    valid_compose({"worker-research": {"env_file": [".env"]}}),
)

assert_raises(
    "Montage config/application.yaml read-only absent pour service applicatif: llm-gateway",
    valid_compose({"llm-gateway": {"volumes": ["../../config/application.yaml:/workspace/config/application.yaml", APPLICATION_SCHEMA_VOLUME]}}),
)
assert_raises(
    "Montage config/application.schema.json read-only absent pour service applicatif: llm-gateway",
    valid_compose({"llm-gateway": {"volumes": [APPLICATION_CONFIG_VOLUME]}}),
)
assert_raises(
    "Montage config/secrets/local read-only absent pour service llm-gateway",
    valid_compose({"llm-gateway": {"volumes": [APPLICATION_CONFIG_VOLUME, APPLICATION_SCHEMA_VOLUME]}}),
)

assert_raises(
    "Argument --config absent pour service applicatif: orchestrator-api",
    valid_compose(
        {
            "orchestrator-api": {
                "command": [
                    "python",
                    "-m",
                    "app.platform.local_runtime",
                    "serve-http",
                    "orchestrator-api",
                    "8080",
                ]
            }
        }
    ),
)

assert_raises(
    "Variable applicative interdite pour service orchestrator-api: DATABASE_URL",
    valid_compose(
        {
            "orchestrator-api": {
                "environment": {"DATABASE_URL": "${DATABASE_URL?DATABASE_URL requis}"}
            }
        }
    ),
)

assert_raises(
    "Variable applicative interdite pour service llm-gateway: GEMMA_MODEL_REVISION",
    valid_compose(
        {
            "llm-gateway": {
                "environment": {"GEMMA_MODEL_REVISION": "${GEMMA_MODEL_REVISION?GEMMA_MODEL_REVISION requis}"}
            }
        }
    ),
)

assert_raises(
    "Variable applicative interdite pour service edge-gateway: UI_API_URL",
    valid_compose({"edge-gateway": {"environment": {"UI_API_URL": "${UI_API_URL?UI_API_URL requis}"}}}),
)

assert_raises(
    "Variable non allowlistée pour service qdrant: QDRANT__SERVICE__GRPC_PORT",
    valid_compose({"qdrant": {"environment": {"QDRANT__SERVICE__GRPC_PORT": "${QDRANT_GRPC_PORT?QDRANT_GRPC_PORT requis}"}}}),
)

print("Tests unitaires Compose M13-config: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_compose_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires Compose M13-config: OK"
