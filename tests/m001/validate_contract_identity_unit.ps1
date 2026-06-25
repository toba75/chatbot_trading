$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")

$pythonCode = @'
from app.contracts.identity import (
    ALLOWED_DOMAIN_IDENTIFIER_PREFIXES,
    ContractSchemaVersion,
    DomainIdentifier,
    validate_contract_payload,
)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


for prefix in sorted(ALLOWED_DOMAIN_IDENTIFIER_PREFIXES):
    value = f"{prefix}-000001"
    parsed = DomainIdentifier.parse(value)
    if parsed.prefix != prefix:
        raise AssertionError(f"Prefixe incorrect pour {value}: {parsed.prefix}")
    if str(parsed) != value:
        raise AssertionError(f"Round-trip incorrect pour {value}: {parsed}")

assert_raises("Prefixe inconnu", lambda: DomainIdentifier.parse("BAD-000001"))
assert_raises("Identifiant vide", lambda: DomainIdentifier.parse(""))
assert_raises("Identifiant vide", lambda: DomainIdentifier.parse("   "))
assert_raises("Chemin de fichier interdit", lambda: DomainIdentifier.parse("C:\\sources\\doc.pdf"))
assert_raises("Chemin de fichier interdit", lambda: DomainIdentifier.parse("sources/doc.pdf"))
assert_raises("Identifiant technique interdit", lambda: DomainIdentifier.parse("qdrant:knowledge_access:42"))

version = ContractSchemaVersion.parse("1.0", supported_schema_versions={"1.0"})
if str(version) != "1.0":
    raise AssertionError("Round-trip de schema_version incorrect.")

assert_raises("schema_version absent", lambda: ContractSchemaVersion.require_in_payload({}, supported_schema_versions={"1.0"}))
assert_raises("schema_version vide", lambda: ContractSchemaVersion.parse("", supported_schema_versions={"1.0"}))
assert_raises("schema_version non supportee", lambda: ContractSchemaVersion.parse("2.0", supported_schema_versions={"1.0"}))

payload = {
    "schema_version": "1.0",
    "contract_name": "IdentityPrimitiveUnitFixture",
    "primary_identity": "DOC-000001",
    "identities": {"document_id": "DOC-000001"},
}
validated = validate_contract_payload(payload, supported_schema_versions={"1.0"})
if validated["primary_identity"] != "DOC-000001":
    raise AssertionError("Identite principale perdue pendant la validation.")

payload_without_primary_identity = dict(payload)
del payload_without_primary_identity["primary_identity"]
assert_raises(
    "primary_identity absent",
    lambda: validate_contract_payload(payload_without_primary_identity, supported_schema_versions={"1.0"}),
)

payload_with_technical_primary_identity = dict(payload)
payload_with_technical_primary_identity["primary_identity"] = "prompt_hash:abc123"
assert_raises(
    "Identifiant technique interdit",
    lambda: validate_contract_payload(payload_with_technical_primary_identity, supported_schema_versions={"1.0"}),
)

payload_with_unknown_identity = dict(payload)
payload_with_unknown_identity["identities"] = {"document_id": "UNK-000001"}
assert_raises(
    "Prefixe inconnu",
    lambda: validate_contract_payload(payload_with_unknown_identity, supported_schema_versions={"1.0"}),
)

print("Primitives unitaires d'identite de contrat M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_contract_identity_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python $pythonScriptPath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires des identifiants de contrats M-001: OK"
