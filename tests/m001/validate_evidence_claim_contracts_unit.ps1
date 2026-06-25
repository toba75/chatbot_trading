$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocatorValidationPolicy


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


canonical_payload = {
    "schema_version": "1.0",
    "canonical_source_id": "CSRC-000001",
    "document_id": "DOC-000001",
    "canonical_version_id": "CVER-000004",
    "source_sha256": "a" * 64,
    "canonical_artifact_sha256": "b" * 64,
    "page_count": 3,
    "accepted_at": "2026-06-21T08:30:00Z",
    "quality_policy_version": "source-qa-v3",
}
source_locator_payload = {
    "schema_version": "1.0",
    "canonical_version_id": "CVER-000004",
    "document_id": "DOC-000001",
    "page_pdf": 2,
    "item_id": "DOC-000001-P002-I001",
    "bbox": [0.1, 0.2, 0.8, 0.4],
    "content_hash": "c" * 64,
}
evidence_payload = {
    "schema_version": "1.0",
    "evidence_id": "EVS-001204",
    "source_locator": source_locator_payload,
    "relation": "SUPPORTS_DIRECTLY",
    "quoted_span_hash": "d" * 64,
}
claim_payload = {
    "schema_version": "1.0",
    "claim_id": "CLM-004812",
    "claim_version": 3,
    "canonical_text": "Les strategies de suivi de tendance quotidiennes sur futures ont ete rentables sur la periode etudiee.",
    "scope": {
        "universe": ["futures"],
        "frequency": "daily",
        "sample_period": "1985-2018",
        "transaction_costs_included": True,
    },
    "status": "VERIFIED",
    "verification_id": "VER-002991",
    "evidence_refs": [evidence_payload],
    "dependency_group_ids": ["DEP-000123", "DEP-000124"],
}

canonical_ref = CanonicalSourceRef.from_payload(canonical_payload)
validation_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "ACCEPTED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: frozenset({"DOC-000001-P002-I001"}),
    },
)

evidence = EvidenceRef.from_payload(
    evidence_payload,
    source_locator_validation_policy=validation_policy,
)
if EvidenceRef.from_json(evidence.to_json(), source_locator_validation_policy=validation_policy) != evidence:
    raise AssertionError("Le round-trip unitaire EvidenceRef doit rester stable.")

claim = VerifiedClaimRef.from_payload(
    claim_payload,
    source_locator_validation_policy=validation_policy,
)
if VerifiedClaimRef.from_json(claim.to_json(), source_locator_validation_policy=validation_policy) != claim:
    raise AssertionError("Le round-trip unitaire VerifiedClaimRef doit rester stable.")

if claim.dependency_group_ids != ("DEP-000123", "DEP-000124"):
    raise AssertionError("dependency_group_ids perdus pendant la validation.")

claim_json = claim.to_json()
try:
    claim.scope["universe"] = ["mutated"]
except TypeError:
    pass
else:
    raise AssertionError("VerifiedClaimRef.scope doit etre immuable apres validation.")
if claim.to_json() != claim_json:
    raise AssertionError("Une mutation externe ne doit pas modifier VerifiedClaimRef.")

missing_status = dict(claim_payload)
del missing_status["status"]
assert_raises(
    "status absent",
    lambda: VerifiedClaimRef.from_payload(missing_status, source_locator_validation_policy=validation_policy),
)

implicit_status = dict(claim_payload)
implicit_status["status"] = ""
assert_raises(
    "status vide",
    lambda: VerifiedClaimRef.from_payload(implicit_status, source_locator_validation_policy=validation_policy),
)

unknown_status = dict(claim_payload)
unknown_status["status"] = "DRAFT"
assert_raises(
    "status non autorise: DRAFT",
    lambda: VerifiedClaimRef.from_payload(unknown_status, source_locator_validation_policy=validation_policy),
)

without_evidence_refs = dict(claim_payload)
without_evidence_refs["evidence_refs"] = []
assert_raises(
    "evidence_refs requis pour VERIFIED",
    lambda: VerifiedClaimRef.from_payload(without_evidence_refs, source_locator_validation_policy=validation_policy),
)

empty_evidence = dict(claim_payload)
empty_evidence["evidence_refs"] = [{}]
assert_raises(
    "evidence_refs invalide",
    lambda: VerifiedClaimRef.from_payload(empty_evidence, source_locator_validation_policy=validation_policy),
)

missing_claim_version = dict(claim_payload)
del missing_claim_version["claim_version"]
assert_raises(
    "claim_version absent",
    lambda: VerifiedClaimRef.from_payload(missing_claim_version, source_locator_validation_policy=validation_policy),
)

invalid_claim_version = dict(claim_payload)
invalid_claim_version["claim_version"] = 0
assert_raises(
    "claim_version invalide",
    lambda: VerifiedClaimRef.from_payload(invalid_claim_version, source_locator_validation_policy=validation_policy),
)

missing_scope = dict(claim_payload)
del missing_scope["scope"]
assert_raises(
    "scope absent",
    lambda: VerifiedClaimRef.from_payload(missing_scope, source_locator_validation_policy=validation_policy),
)

empty_scope = dict(claim_payload)
empty_scope["scope"] = {}
assert_raises(
    "scope vide",
    lambda: VerifiedClaimRef.from_payload(empty_scope, source_locator_validation_policy=validation_policy),
)

invalid_source_locator_evidence = dict(evidence_payload)
invalid_source_locator = dict(source_locator_payload)
invalid_source_locator["item_id"] = "DOC-000001-P002-I999"
invalid_source_locator_evidence["source_locator"] = invalid_source_locator
assert_raises(
    "source_locator invalide",
    lambda: EvidenceRef.from_payload(
        invalid_source_locator_evidence,
        source_locator_validation_policy=validation_policy,
    ),
)

missing_dependency_groups = dict(claim_payload)
del missing_dependency_groups["dependency_group_ids"]
assert_raises(
    "dependency_group_ids absent",
    lambda: VerifiedClaimRef.from_payload(missing_dependency_groups, source_locator_validation_policy=validation_policy),
)

empty_dependency_groups = dict(claim_payload)
empty_dependency_groups["dependency_group_ids"] = []
assert_raises(
    "dependency_group_ids vide",
    lambda: VerifiedClaimRef.from_payload(empty_dependency_groups, source_locator_validation_policy=validation_policy),
)

invalid_dependency_group = dict(claim_payload)
invalid_dependency_group["dependency_group_ids"] = ["CLM-000001"]
assert_raises(
    "dependency_group_ids invalide",
    lambda: VerifiedClaimRef.from_payload(invalid_dependency_group, source_locator_validation_policy=validation_policy),
)

invalid_relation = dict(evidence_payload)
invalid_relation["relation"] = "QUALIFIES"
assert_raises(
    "relation non autorisee: QUALIFIES",
    lambda: EvidenceRef.from_payload(invalid_relation, source_locator_validation_policy=validation_policy),
)

internal_evidence_key = dict(evidence_payload)
internal_evidence_key["claim_repository_id"] = "eg.internal.claims"
assert_raises(
    "champ interdit",
    lambda: EvidenceRef.from_payload(internal_evidence_key, source_locator_validation_policy=validation_policy),
)

internal_scope_key = dict(claim_payload)
internal_scope_key["scope"] = dict(internal_scope_key["scope"])
internal_scope_key["scope"]["claim_repository_id"] = "eg.internal.claims"
assert_raises(
    "cle interdite",
    lambda: VerifiedClaimRef.from_payload(internal_scope_key, source_locator_validation_policy=validation_policy),
)

non_finite_scope_value = dict(claim_payload)
non_finite_scope_value["scope"] = dict(non_finite_scope_value["scope"])
non_finite_scope_value["scope"]["score"] = float("nan")
assert_raises(
    "scope invalide",
    lambda: VerifiedClaimRef.from_payload(non_finite_scope_value, source_locator_validation_policy=validation_policy),
)

print("Invariants unitaires EvidenceRef et VerifiedClaimRef M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_evidence_claim_contracts_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires EvidenceRef et VerifiedClaimRef M-001: OK"
