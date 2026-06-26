$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.platform.topology import load_platform_topology, parse_platform_topology_registry


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def service_payload(payload, service_id):
    matches = [service for service in payload["services"] if service["id"] == service_id]
    if len(matches) != 1:
        raise AssertionError(f"Service fixture absent ou duplique: {service_id}")
    return matches[0]


repo_root = Path(sys.argv[1])
registry_path = repo_root / "app" / "platform" / "topology_registry.json"
payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
topology = load_platform_topology(registry_path)

expected_hosts = {
    "gemma-vllm": "spark-inference",
    "spark-model-cache": "spark-inference",
    "postgres": "docker-local",
    "qdrant": "docker-local",
    "corpus-store": "docker-local",
    "experiment-registry": "docker-local",
    "worker-documents": "docker-local",
    "worker-backtest": "docker-local",
    "backtest-engine": "docker-local",
    "llm-gateway": "docker-local",
}

for service_id, expected_host in expected_hosts.items():
    actual_host = topology.service(service_id).host
    if actual_host != expected_host:
        raise AssertionError(f"Placement invalide pour {service_id}: {actual_host}")

if topology.host("docker-local").exclusive_responsibility != "business_data_and_local_processing":
    raise AssertionError("Responsabilit\u00e9 exclusive docker-local incorrecte.")

if topology.host("spark-inference").exclusive_responsibility != "gemma_inference_only":
    raise AssertionError("Responsabilit\u00e9 exclusive spark-inference incorrecte.")

spark_cache = topology.service("spark-model-cache")
if spark_cache.durability != "regenerable_cache":
    raise AssertionError("Le cache Spark doit \u00eatre r\u00e9g\u00e9n\u00e9rable.")
if spark_cache.business_storage:
    raise AssertionError("Le cache Spark ne doit pas \u00eatre un stockage m\u00e9tier.")

duplicate_responsibility = copy.deepcopy(payload)
duplicate_responsibility["hosts"][1]["exclusive_responsibility"] = duplicate_responsibility["hosts"][0]["exclusive_responsibility"]
assert_raises(
    "Responsabilit\u00e9 exclusive dupliqu\u00e9e",
    lambda: parse_platform_topology_registry(duplicate_responsibility),
)

unknown_host = copy.deepcopy(payload)
service_payload(unknown_host, "llm-gateway")["host"] = "cloud-gpu"
assert_raises(
    "H\u00f4te inconnu pour service llm-gateway: cloud-gpu",
    lambda: parse_platform_topology_registry(unknown_host),
)

missing_host = copy.deepcopy(payload)
del service_payload(missing_host, "llm-gateway")["host"]
assert_raises(
    "H\u00f4te explicite absent pour service: llm-gateway",
    lambda: parse_platform_topology_registry(missing_host),
)

postgres_on_spark = copy.deepcopy(payload)
service_payload(postgres_on_spark, "postgres")["host"] = "spark-inference"
assert_raises(
    "Stockage m\u00e9tier interdit sur spark-inference: postgres",
    lambda: parse_platform_topology_registry(postgres_on_spark),
)

worker_on_spark = copy.deepcopy(payload)
service_payload(worker_on_spark, "worker-documents")["host"] = "spark-inference"
assert_raises(
    "Traitement local interdit sur spark-inference: worker-documents",
    lambda: parse_platform_topology_registry(worker_on_spark),
)

cache_not_regenerable = copy.deepcopy(payload)
service_payload(cache_not_regenerable, "spark-model-cache")["durability"] = "durable_business"
assert_raises(
    "Cache Spark non r\u00e9g\u00e9n\u00e9rable: spark-model-cache",
    lambda: parse_platform_topology_registry(cache_not_regenerable),
)

print("Tests unitaires de topologie M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_platform_topology_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires de topologie M-002: OK"
