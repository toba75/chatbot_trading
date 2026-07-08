$ErrorActionPreference = "Stop"
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.platform.local_compose import parse_local_compose_document
from app.platform.topology import load_platform_topology
from app.platform.security.network_boundary import (
    build_network_flow_matrix,
    parse_spark_firewall_policy,
    validate_network_boundary,
)


repo_root = Path(sys.argv[1])
valid_compose_document = (repo_root / "deploy/local-compose/compose.yaml").read_text(
    encoding="utf-8-sig"
)
topology = load_platform_topology(repo_root / "app/platform/topology_registry.json")

VALID_FIREWALL_PAYLOAD = {
    "schema_version": "1.0",
    "architecture_decisions": ["ADR-007", "ADR-008", "ADR-009", "ADR-014"],
    "spark_endpoint": {
        "host": "spark-inference",
        "service": "gemma-vllm",
        "port": 8000,
        "protocol": "tcp",
        "auth_mode": "none",
        "tls_mode": "disabled",
        "tls_required": False,
        "certificate_authority_required": False,
    },
    "allowed_ingress": [
        {
            "source_host": "docker-local",
            "source_service": "llm-gateway",
            "destination_host": "spark-inference",
            "destination_service": "gemma-vllm",
            "destination_port": 8000,
            "purpose": "llm-gateway-to-vllm",
        }
    ],
    "denied_initiators": [
        "browser",
        "internet",
        "worker-documents",
        "worker-research",
        "worker-backtest",
        "postgres",
        "qdrant",
        "granite-docling",
        "ui",
        "orchestrator-api",
    ],
    "callbacks_from_spark_allowed": False,
    "browser_direct_access_allowed": False,
    "internet_ingress_allowed": False,
    "remote_user_access": {
        "enabled": False,
        "entrypoint_service": "edge-gateway",
        "allowed_bindings": [],
    },
}


def compose_from(document: str):
    return parse_local_compose_document(document, source="fixture-compose.yaml")


def firewall_from(payload):
    return parse_spark_firewall_policy(copy.deepcopy(payload))


def assert_boundary_error(expected_fragment: str, *, compose_document=None, firewall_payload=None):
    try:
        validate_network_boundary(
            compose=compose_from(compose_document or valid_compose_document),
            topology=topology,
            spark_firewall=firewall_from(firewall_payload or VALID_FIREWALL_PAYLOAD),
        )
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def add_published_port(document: str, service_id: str) -> str:
    service_header = f"\n  {service_id}:\n"
    if service_header not in document:
        raise AssertionError(f"Service fixture absent: {service_id}")
    return document.replace(
        service_header,
        f'\n  {service_id}:\n    ports:\n      - "0.0.0.0:9191:9191"\n',
        1,
    )


def add_profile_published_port(document: str, service_id: str) -> str:
    service_header = f"\n  {service_id}:\n"
    if service_header not in document:
        raise AssertionError(f"Service fixture absent: {service_id}")
    return document.replace(
        service_header,
        f'\n  {service_id}:\n    profiles:\n      - debug\n    ports:\n      - "127.0.0.1:6333:6333"\n',
        1,
    )


def add_spark_egress(document: str, service_id: str) -> str:
    service_header = f"\n  {service_id}:\n"
    service_index = document.find(service_header)
    if service_index < 0:
        raise AssertionError(f"Service fixture absent: {service_id}")

    network_block = "    networks:\n      - core\n"
    network_index = document.find(network_block, service_index)
    if network_index < 0:
        raise AssertionError(f"Bloc networks fixture absent: {service_id}")

    return (
        document[:network_index]
        + "    networks:\n      - core\n      - spark-egress\n"
        + document[network_index + len(network_block) :]
    )


def add_gateway_environment_line(document: str, line: str) -> str:
    gateway_header = "\n  llm-gateway:\n"
    gateway_index = document.find(gateway_header)
    if gateway_index < 0:
        raise AssertionError("Service fixture absent: llm-gateway")

    marker = "      GEMMA_BASE_URL:"
    marker_index = document.find(marker, gateway_index)
    if marker_index < 0:
        raise AssertionError("Variable GEMMA_BASE_URL absente du fixture")

    return document[:marker_index] + f"      {line}\n" + document[marker_index:]


def replace_gateway_base_url(document: str, value: str) -> str:
    current = '      GEMMA_BASE_URL: "${GEMMA_BASE_URL?GEMMA_BASE_URL requis}"'
    replacement = f'      GEMMA_BASE_URL: "{value}"'
    if current not in document:
        raise AssertionError("Variable GEMMA_BASE_URL absente du fixture")
    return document.replace(current, replacement)


def add_ui_environment_line(document: str, line: str) -> str:
    ui_header = "\n  ui:\n"
    ui_index = document.find(ui_header)
    if ui_index < 0:
        raise AssertionError("Service fixture absent: ui")

    marker = "      UI_API_URL:"
    marker_index = document.find(marker, ui_index)
    if marker_index < 0:
        raise AssertionError("Variable UI_API_URL absente du fixture")

    return document[:marker_index] + f"      {line}\n" + document[marker_index:]


validate_network_boundary(
    compose=compose_from(valid_compose_document),
    topology=topology,
    spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
)

flows = build_network_flow_matrix(
    compose=compose_from(valid_compose_document),
    spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
)
allowed_flows = [flow for flow in flows if flow.allowed]
if len(allowed_flows) != 1:
    raise AssertionError(f"Une seule autorisation Spark attendue: {allowed_flows}")
allowed_flow = allowed_flows[0]
if (
    allowed_flow.source_service != "llm-gateway"
    or allowed_flow.destination_host != "spark-inference"
    or allowed_flow.destination_port != 8000
):
    raise AssertionError(f"Flux Spark autorisé invalide: {allowed_flow}")
if not any(flow.source_service == "browser" and not flow.allowed for flow in flows):
    raise AssertionError(f"Flux navigateur refusé absent: {flows}")

assert_boundary_error(
    "Port public interdit pour stockage local: postgres",
    compose_document=add_published_port(valid_compose_document, "postgres"),
)

assert_boundary_error(
    "Profil Compose avec port public interdit pour service interne: qdrant",
    compose_document=add_profile_published_port(valid_compose_document, "qdrant"),
)

assert_boundary_error(
    "Egress Spark interdit hors llm-gateway: worker-research",
    compose_document=add_spark_egress(valid_compose_document, "worker-research"),
)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["allowed_ingress"][0]["source_service"] = "worker-research"
assert_boundary_error("Source Spark non autoris", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["spark_endpoint"]["auth_mode"] = "api_key_file"
assert_boundary_error("Mode d'authentification Spark invalide", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["spark_endpoint"]["tls_mode"] = "ca_bundle"
assert_boundary_error("Mode TLS Spark incohérent", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["callbacks_from_spark_allowed"] = True
assert_boundary_error("Callback Spark interdit", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["browser_direct_access_allowed"] = True
assert_boundary_error("navigateur direct au Spark interdit", firewall_payload=firewall_payload)

assert_boundary_error(
    "GEMMA_TLS_VERIFY",
    compose_document=add_gateway_environment_line(valid_compose_document, 'GEMMA_TLS_VERIFY: "false"'),
)

assert_boundary_error(
    "Endpoint Spark invalide pour llm-gateway",
    compose_document=replace_gateway_base_url(valid_compose_document, "https://api.openai.com/v1"),
)

assert_boundary_error(
    "Secret vLLM interdit",
    compose_document=add_ui_environment_line(valid_compose_document, 'GEMMA_API_KEY_FILE: "/run/secrets/gemma_api_key"'),
)

remote_compose_document = valid_compose_document.replace(
    "127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443",
    "192.168.10.20:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443",
)
assert_boundary_error(
    "edge-gateway: 192.168.10.20",
    compose_document=remote_compose_document,
)

remote_firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
remote_firewall_payload["remote_user_access"] = {
    "enabled": True,
    "entrypoint_service": "edge-gateway",
    "allowed_bindings": ["192.168.10.20"],
}
validate_network_boundary(
    compose=compose_from(remote_compose_document),
    topology=topology,
    spark_firewall=firewall_from(remote_firewall_payload),
)

public_remote_firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
public_remote_firewall_payload["remote_user_access"] = {
    "enabled": True,
    "entrypoint_service": "edge-gateway",
    "allowed_bindings": ["0.0.0.0"],
}
assert_boundary_error(
    "distant public interdit: 0.0.0.0",
    firewall_payload=public_remote_firewall_payload,
)

print("Tests unitaires fronti\u00e8re r\u00e9seau M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_network_boundary_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires fronti$($eGrave)re r$($eAcute)seau M-002: OK"
