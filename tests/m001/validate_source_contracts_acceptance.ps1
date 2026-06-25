$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$canonicalSourceFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/sp_canonical_source_ref_v1.json"
$spLocatorFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/sp_source_locator_v1.json"
$kaLocatorFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/ka_source_locator_v1.json"
$egLocatorFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/eg_source_locator_v1.json"

foreach ($fixturePath in @($canonicalSourceFixturePath, $spLocatorFixturePath, $kaLocatorFixturePath, $egLocatorFixturePath)) {
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Fixture de contrat source absente: $fixturePath"
    }
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import (
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


canonical_payload = load_payload(sys.argv[2])
sp_locator_payload = load_payload(sys.argv[3])
ka_locator_payload = load_payload(sys.argv[4])
eg_locator_payload = load_payload(sys.argv[5])

# Given SP publie une version canonique acceptée.
canonical_ref = CanonicalSourceRef.from_payload(canonical_payload)
validation_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={
        "CVER-000004": "ACCEPTED",
        "CVER-000005": "QUARANTINED",
        "CVER-000006": "RETIRED",
    },
    resolvable_item_ids_by_version_id={
        "CVER-000004": {"DOC-000001-P037-I004": "c" * 64},
    },
)

# When KA ou EG reçoit un SourceLocator.
sp_locator = SourceLocator.from_payload(sp_locator_payload, validation_policy=validation_policy)
ka_locator = SourceLocator.from_payload(ka_locator_payload, validation_policy=validation_policy)
eg_locator = SourceLocator.from_payload(eg_locator_payload, validation_policy=validation_policy)

# Then le consommateur vérifie la version, la page, l'item et le hash sans accéder au modèle interne SP.
if ka_locator != sp_locator:
    raise AssertionError("La fixture consommateur KA doit rester compatible avec le producteur SP.")
if eg_locator != sp_locator:
    raise AssertionError("La fixture consommateur EG doit rester compatible avec le producteur SP.")

canonical_roundtrip = CanonicalSourceRef.from_json(canonical_ref.to_json())
locator_roundtrip = SourceLocator.from_json(sp_locator.to_json(), validation_policy=validation_policy)
if canonical_roundtrip != canonical_ref:
    raise AssertionError("Round-trip CanonicalSourceRef instable.")
if locator_roundtrip != sp_locator:
    raise AssertionError("Round-trip SourceLocator instable.")

serialized_locator = sp_locator.to_json()
if serialized_locator != locator_roundtrip.to_json():
    raise AssertionError("La sérialisation SourceLocator doit être déterministe.")

for forbidden_key in ("sp_table", "qdrant_id", "source_processing_model"):
    if forbidden_key in canonical_payload or forbidden_key in sp_locator_payload:
        raise AssertionError(f"Modèle interne exposé dans le contrat: {forbidden_key}")

missing_version_payload = dict(sp_locator_payload)
missing_version_payload["canonical_version_id"] = "CVER-999999"
assert_raises(
    "Version canonique absente",
    lambda: SourceLocator.from_payload(missing_version_payload, validation_policy=validation_policy),
)

quarantined_payload = dict(sp_locator_payload)
quarantined_payload["canonical_version_id"] = "CVER-000005"
assert_raises(
    "Version canonique indisponible: QUARANTINED",
    lambda: SourceLocator.from_payload(quarantined_payload, validation_policy=validation_policy),
)

retired_payload = dict(sp_locator_payload)
retired_payload["canonical_version_id"] = "CVER-000006"
assert_raises(
    "Version canonique indisponible: RETIRED",
    lambda: SourceLocator.from_payload(retired_payload, validation_policy=validation_policy),
)

print("Contrats CanonicalSourceRef et SourceLocator M-001 acceptés.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_source_contracts_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot $canonicalSourceFixturePath $spLocatorFixturePath $kaLocatorFixturePath $egLocatorFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation des contrats source M-001: OK"
