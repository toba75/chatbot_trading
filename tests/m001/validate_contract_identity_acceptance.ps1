$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/identity_primitives_v1.json"
$missingSchemaFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/identity_primitives_missing_schema_version.json"
$technicalIdentityFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/identity_primitives_technical_primary_identity.json"

foreach ($fixturePath in @($validFixturePath, $missingSchemaFixturePath, $technicalIdentityFixturePath)) {
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Fixture de contrat absente: $fixturePath"
    }
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.identity import (
    ALLOWED_DOMAIN_IDENTIFIER_PREFIXES,
    serialize_contract_payload,
    validate_contract_payload,
)


EXPECTED_PREFIXES = {
    "DOC",
    "CSRC",
    "CVER",
    "PROJ",
    "CLM",
    "VER",
    "DEP",
    "RSC",
    "EVS",
    "ANS",
    "CONV",
    "TURN",
    "STRAT",
    "SVER",
    "EXP",
    "DATA",
}


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


valid_payload = load_payload(sys.argv[2])
missing_schema_payload = load_payload(sys.argv[3])
technical_identity_payload = load_payload(sys.argv[4])

# Given un contexte publie un contrat pour un autre contexte.
# When le contrat est serialise et valide.
# Then chaque identite metier est opaque, prefixee, versionnee et independante des chemins ou identifiants techniques.
validated = validate_contract_payload(valid_payload, supported_schema_versions={"1.0"})
serialized = serialize_contract_payload(validated, supported_schema_versions={"1.0"})
roundtrip_payload = json.loads(serialized)
roundtrip_validated = validate_contract_payload(roundtrip_payload, supported_schema_versions={"1.0"})

actual_prefixes = {
    identifier.split("-", 1)[0]
    for identifier in roundtrip_validated["identities"].values()
}

if actual_prefixes != EXPECTED_PREFIXES:
    raise AssertionError(f"Prefixes couverts invalides: {sorted(actual_prefixes)}")

if ALLOWED_DOMAIN_IDENTIFIER_PREFIXES != EXPECTED_PREFIXES:
    raise AssertionError("La politique de prefixes publies ne couvre pas T-004.")

if roundtrip_validated["schema_version"] != "1.0":
    raise AssertionError("schema_version doit etre conservee au round-trip.")

assert_raises(
    "schema_version absent",
    lambda: validate_contract_payload(missing_schema_payload, supported_schema_versions={"1.0"}),
)
assert_raises(
    "Identifiant technique interdit",
    lambda: validate_contract_payload(technical_identity_payload, supported_schema_versions={"1.0"}),
)

print("Contrat d'identite M-001 accepte et garde-fous refuses.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_contract_identity_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python -B $pythonScriptPath $repoRoot $validFixturePath $missingSchemaFixturePath $technicalIdentityFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation des identifiants de contrats M-001: OK"
