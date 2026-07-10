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
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
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
valid_application_configuration_text = (repo_root / "config/application.example.yaml").read_text(
    encoding="utf-8-sig"
).replace("\r\n", "\n")
topology = load_platform_topology(repo_root / "app/platform/topology_registry.json")
temporary_config_root = tempfile.TemporaryDirectory(prefix="ost_m002_network_boundary_config_")

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


def application_configuration_from(text: str):
    path = Path(temporary_config_root.name) / f"application_{abs(hash(text))}.yaml"
    path.write_text(text, encoding="utf-8")
    return load_application_configuration(config_path=path, environment_snapshot={})


def assert_boundary_error(expected_fragment: str, *, compose_document=None, firewall_payload=None):
    try:
        validate_network_boundary(
            compose=compose_from(compose_document or valid_compose_document),
            topology=topology,
            spark_firewall=firewall_from(firewall_payload or VALID_FIREWALL_PAYLOAD),
            application_configuration=application_configuration_from(valid_application_configuration_text),
        )
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def _lines(document: str) -> list[str]:
    return document.splitlines()


def _service_header_index(lines: list[str], service_id: str) -> int:
    expected = f"  {service_id}:"
    for index, line in enumerate(lines):
        if line == expected:
            return index
    raise AssertionError(f"Service fixture absent: {service_id}")


def _service_end_index(lines: list[str], service_start: int) -> int:
    for index in range(service_start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    "):
            return index
    return len(lines)


def _join(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def add_published_port(document: str, service_id: str) -> str:
    lines = _lines(document)
    service_start = _service_header_index(lines, service_id)
    lines[service_start + 1:service_start + 1] = [
        "    ports:",
        '      - "0.0.0.0:9191:9191"',
    ]
    return _join(lines)


def add_profile_published_port(document: str, service_id: str) -> str:
    lines = _lines(document)
    service_start = _service_header_index(lines, service_id)
    lines[service_start + 1:service_start + 1] = [
        "    profiles:",
        "      - debug",
        "    ports:",
        '      - "127.0.0.1:6333:6333"',
    ]
    return _join(lines)


def add_spark_egress(document: str, service_id: str) -> str:
    lines = _lines(document)
    service_start = _service_header_index(lines, service_id)
    service_end = _service_end_index(lines, service_start)
    for index in range(service_start, service_end):
        if lines[index] == "      - core":
            lines.insert(index + 1, "      - spark-egress")
            return _join(lines)
    raise AssertionError(f"Réseau core absent du fixture: {service_id}")


def add_service_environment_line(document: str, service_id: str, line: str) -> str:
    lines = _lines(document)
    service_start = _service_header_index(lines, service_id)
    service_end = _service_end_index(lines, service_start)
    for index in range(service_start, service_end):
        if lines[index] == "    networks:":
            lines[index:index] = ["    environment:", f"      {line}"]
            return _join(lines)
    raise AssertionError(f"Bloc networks absent du fixture: {service_id}")


validate_network_boundary(
    compose=compose_from(valid_compose_document),
    topology=topology,
    spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
    application_configuration=application_configuration_from(valid_application_configuration_text),
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

assert_boundary_error(
    "Variable applicative interdite pour service llm-gateway: GEMMA_TLS_VERIFY",
    compose_document=add_service_environment_line(valid_compose_document, "llm-gateway", 'GEMMA_TLS_VERIFY: "false"'),
)

assert_boundary_error(
    "Variable applicative interdite pour service ui: GEMMA_API_KEY_FILE",
    compose_document=add_service_environment_line(valid_compose_document, "ui", 'GEMMA_API_KEY_FILE: "/run/secrets/gemma_api_key"'),
)

spark_port_mismatch_configuration = application_configuration_from(
    valid_application_configuration_text.replace(
        "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
        "    spark_endpoint_url: http://192.168.1.120:22/v1\n",
        1,
    )
)
try:
    validate_network_boundary(
        compose=compose_from(valid_compose_document),
        topology=topology,
        spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
        application_configuration=spark_port_mismatch_configuration,
    )
except ValueError as exc:
    if "Port Spark applicatif incohérent" not in str(exc):
        raise AssertionError(f"Erreur port Spark inattendue: {exc}")
else:
    raise AssertionError("Configuration applicative avec port Spark incohérent acceptée.")

spark_auth_mismatch_configuration = application_configuration_from(
    valid_application_configuration_text.replace("    require_api_key: false\n", "    require_api_key: true\n", 1)
    .replace("    auth_mode: none\n", "    auth_mode: api_key_file\n", 1)
)
try:
    validate_network_boundary(
        compose=compose_from(valid_compose_document),
        topology=topology,
        spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
        application_configuration=spark_auth_mismatch_configuration,
    )
except ValueError as exc:
    if "Mode auth Spark applicatif incohérent" not in str(exc):
        raise AssertionError(f"Erreur auth Spark inattendue: {exc}")
else:
    raise AssertionError("Configuration applicative avec auth Spark incohérente acceptée.")

spark_tls_mismatch_configuration = application_configuration_from(
    valid_application_configuration_text.replace("    require_tls: false\n", "    require_tls: true\n", 1)
    .replace(
        "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
        "    spark_endpoint_url: https://192.168.1.120:8000/v1\n",
        1,
    )
    .replace("    tls_mode: disabled\n", "    tls_mode: ca_bundle\n", 1)
)
try:
    validate_network_boundary(
        compose=compose_from(valid_compose_document),
        topology=topology,
        spark_firewall=firewall_from(VALID_FIREWALL_PAYLOAD),
        application_configuration=spark_tls_mismatch_configuration,
    )
except ValueError as exc:
    if "Mode TLS Spark applicatif incohérent" not in str(exc):
        raise AssertionError(f"Erreur TLS Spark inattendue: {exc}")
else:
    raise AssertionError("Configuration applicative avec TLS Spark incohérent acceptée.")

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["allowed_ingress"][0]["source_service"] = "worker-research"
assert_boundary_error("Source Spark non autoris", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["spark_endpoint"]["auth_mode"] = "api_key_file"
assert_boundary_error("Mode d'authentification Spark invalide", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["spark_endpoint"]["tls_mode"] = "ca_bundle"
assert_boundary_error("Mode TLS Spark", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["callbacks_from_spark_allowed"] = True
assert_boundary_error("Callback Spark interdit", firewall_payload=firewall_payload)

firewall_payload = copy.deepcopy(VALID_FIREWALL_PAYLOAD)
firewall_payload["browser_direct_access_allowed"] = True
assert_boundary_error("navigateur direct au Spark interdit", firewall_payload=firewall_payload)

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
    "allowed_bindings": ["0.0.0.0"],
}
assert_boundary_error(
    "distant public interdit: 0.0.0.0",
    firewall_payload=remote_firewall_payload,
)

print("Tests unitaires frontière réseau M-002: OK")
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
