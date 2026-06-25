$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$canonicalSourceFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/sp_canonical_source_ref_v1.json"
$egEvidenceFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/eg_evidence_ref_v1.json"
$egToRaClaimFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/eg_to_ra_verified_claim_ref_v1.json"
$egToSdClaimFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/eg_to_sd_verified_claim_ref_v1.json"
$verifiedWithoutEvidenceFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/eg_verified_claim_ref_verified_without_evidence_refs.json"

foreach ($fixturePath in @($canonicalSourceFixturePath, $egEvidenceFixturePath, $egToRaClaimFixturePath, $egToSdClaimFixturePath, $verifiedWithoutEvidenceFixturePath)) {
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Fixture de contrat claim absente: $fixturePath"
    }
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocatorValidationPolicy


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


def assert_no_internal_eg_keys(payload):
    forbidden_keys = {
        "claim_record_id",
        "verification_case_id",
        "eg_graph_node_id",
        "claim_repository_id",
        "evidence_link_id",
        "nli_trace",
        "extractor_prompt_hash",
    }

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden_keys:
                raise AssertionError(f"Modele interne EG expose dans le contrat: {key}")
            assert_no_internal_eg_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_internal_eg_keys(item)


canonical_payload = load_payload(sys.argv[2])
eg_evidence_payload = load_payload(sys.argv[3])
eg_to_ra_claim_payload = load_payload(sys.argv[4])
eg_to_sd_claim_payload = load_payload(sys.argv[5])
verified_without_evidence_payload = load_payload(sys.argv[6])

canonical_ref = CanonicalSourceRef.from_payload(canonical_payload)
validation_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "ACCEPTED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: frozenset({"DOC-000001-P037-I004"}),
    },
)

# Given EG a verifie une affirmation avec une preuve directe et une portee explicite.
eg_evidence = EvidenceRef.from_payload(
    eg_evidence_payload,
    source_locator_validation_policy=validation_policy,
)
ra_claim = VerifiedClaimRef.from_payload(
    eg_to_ra_claim_payload,
    source_locator_validation_policy=validation_policy,
)
sd_claim = VerifiedClaimRef.from_payload(
    eg_to_sd_claim_payload,
    source_locator_validation_policy=validation_policy,
)

# When RA ou SD consomme VerifiedClaimRef.
# Then le claim versionne, ses preuves, sa portee et ses dependances sont conserves sans modele interne EG.
if ra_claim != sd_claim:
    raise AssertionError("Les fixtures RA et SD doivent exposer le meme langage publie EG.")

if ra_claim.evidence_refs != (eg_evidence,):
    raise AssertionError("La preuve EG publiee doit etre incluse sans mutation dans VerifiedClaimRef.")

if ra_claim.dependency_group_ids != ("DEP-000123", "DEP-000124"):
    raise AssertionError("Les groupes de dependance doivent etre conserves pour RA et SD.")

if ra_claim.scope["universe"] != ["futures"] or ra_claim.scope["frequency"] != "daily":
    raise AssertionError("La portee de l'affirmation doit etre conservee.")

claim_roundtrip = VerifiedClaimRef.from_json(
    ra_claim.to_json(),
    source_locator_validation_policy=validation_policy,
)
if claim_roundtrip != ra_claim:
    raise AssertionError("Round-trip VerifiedClaimRef instable.")

if claim_roundtrip.to_json() != ra_claim.to_json():
    raise AssertionError("La serialisation VerifiedClaimRef doit etre deterministe.")

for payload in (eg_evidence_payload, eg_to_ra_claim_payload, eg_to_sd_claim_payload):
    assert_no_internal_eg_keys(payload)

assert_raises(
    "evidence_refs requis pour VERIFIED",
    lambda: VerifiedClaimRef.from_payload(
        verified_without_evidence_payload,
        source_locator_validation_policy=validation_policy,
    ),
)

print("Contrats EvidenceRef et VerifiedClaimRef M-001 acceptes.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_evidence_claim_contracts_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python -B $pythonScriptPath $repoRoot $canonicalSourceFixturePath $egEvidenceFixturePath $egToRaClaimFixturePath $egToSdClaimFixturePath $verifiedWithoutEvidenceFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation des contrats preuves et claims M-001: OK"
