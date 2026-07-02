$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.research_answering.application.collect_evidence import CandidateEvidence
from app.research_answering.application.resolve_claim_dependencies import (
    ResolveVerifiedClaimDependenciesCommand,
    ResolveVerifiedClaimDependenciesHandler,
)
from app.research_answering.domain.evidence_set import EvidenceSet


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_no_forbidden_storage_payload(value, path="payload"):
    forbidden_keys = {
        "qdrant_collection",
        "qdrant_point_id",
        "eg_registry_table",
        "sp_table",
        "prompt_override",
        "raw_frequency_count",
        "raw_mention_count",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key in forbidden_keys, f"Champ interdit dans {path}.{key}.")
            assert_no_forbidden_storage_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_storage_payload(child, f"{path}[{index}]")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t005-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T005-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=8,
        accepted_at="2026-07-02T11:00:00Z",
        quality_policy_version="canonical-quality-m004-v1",
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={canonical_source.canonical_version_id: canonical_source},
        version_statuses_by_version_id={
            canonical_source.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            canonical_source.canonical_version_id: {resolved_item_id: content_hash},
        },
    )


def source_locator(*, suffix, document_id, canonical_version_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id,
            "document_id": document_id,
            "page_pdf": 2,
            "item_id": f"item-m009-t005-{suffix.lower()}",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": content_hash,
        },
        validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=document_id,
            canonical_version_id=canonical_version_id,
            content_hash=content_hash,
        ),
    )


def evidence_ref(*, suffix, content_seed, span_seed):
    document_id = f"DOC-M009-T005-{suffix}"
    canonical_version_id = f"CVER-M009-T005-{suffix}"
    locator = source_locator(
        suffix=suffix,
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        content_hash=hash_for(content_seed),
    )
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T005-{suffix}",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": hash_for(span_seed),
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=locator.document_id,
            canonical_version_id=locator.canonical_version_id,
            content_hash=locator.content_hash,
            item_id=locator.item_id,
        ),
    )


def candidate(*, evidence, suffix):
    return CandidateEvidence(
        evidence_ref=evidence,
        source_text=f"Document M-009 T-005 {suffix} citant la même étude primaire.",
        search_trace_id=f"STRC-M009T005{suffix:0>24}",
        document_id=evidence.source_locator.document_id,
        covered_obligations=("dependances",),
    )


def verified_claim_ref(*, evidence_refs):
    return VerifiedClaimRef(
        schema_version="1.0",
        claim_id="CLM-M009-T005-SHARED",
        claim_version=3,
        canonical_text="Trois documents reprennent la même étude primaire sur la réduction du drawdown.",
        scope={
            "milestone": "M-009",
            "task": "T-005",
            "universe": "portefeuille convexe documenté",
        },
        status="VERIFIED",
        verification_id="VER-M009-T005-SHARED-CASE",
        evidence_refs=tuple(evidence_refs),
        dependency_group_ids=("DEP-M009-T005-PRIMARY-STUDY",),
    )


class PublicClaim:
    def __init__(self, verified_claim_ref):
        self.status = "VERIFIED"
        self.verified_claim_ref = verified_claim_ref
        self.accepted_verification_id = verified_claim_ref.verification_id


class PublicClaimEvidenceResult:
    def __init__(self, verified_claim_ref):
        self.claim = PublicClaim(verified_claim_ref)
        self.evidence_refs = tuple(verified_claim_ref.evidence_refs)
        self.dependency_group_ids = tuple(verified_claim_ref.dependency_group_ids)
        self.verification_case_ids = (verified_claim_ref.verification_id,)


class FakePublicVerifiedClaimCatalog:
    def __init__(self, verified_claim_ref):
        self.verified_claim_ref = verified_claim_ref
        self.requests = []
        self.internal_reads = 0
        self.mutations = 0

    def read_evidence(self, claim_id):
        self.requests.append(claim_id)
        return PublicClaimEvidenceResult(self.verified_claim_ref)

    def read_internal_registry(self, claim_id):
        self.internal_reads += 1
        raise AssertionError("RA ne doit pas lire le registre EG interne.")

    def save(self, claim):
        self.mutations += 1
        raise AssertionError("RA ne doit pas muter EG.")


# Given trois documents reprennent la même étude primaire pour soutenir un claim.
primary = evidence_ref(suffix="PRIMARY", content_seed=1, span_seed=4)
secondary = evidence_ref(suffix="SECONDARY", content_seed=2, span_seed=5)
review = evidence_ref(suffix="REVIEW", content_seed=3, span_seed=6)
claim_ref = verified_claim_ref(evidence_refs=(primary, secondary, review))
evidence_set = EvidenceSet.assemble(
    research_case_id="RSC-M009-T005-DEPENDENCIES",
    coverage_obligations=("dependances",),
    candidates=(
        candidate(evidence=primary, suffix="PRIMARY"),
        candidate(evidence=secondary, suffix="SECONDARY"),
        candidate(evidence=review, suffix="REVIEW"),
    ),
    verified_claim_refs=(claim_ref,),
    coverage_policy_version="deep-evidence-coverage-m009-v1",
    diversification_policy_version="deep-evidence-diversification-m009-v1",
)
catalog = FakePublicVerifiedClaimCatalog(claim_ref)
handler = ResolveVerifiedClaimDependenciesHandler(verified_claim_catalog=catalog)

# When RA résout les claims vérifiés et leurs dépendances.
result = handler.resolve(
    ResolveVerifiedClaimDependenciesCommand(
        evidence_set=evidence_set,
        occurred_at="2026-07-02T11:10:00Z",
    )
)

# Then une seule confirmation indépendante est comptée et la synthèse conserve la dépendance documentaire.
assert_equal(
    result.status,
    "VERIFIED_CLAIM_DEPENDENCIES_RESOLVED",
    "Le statut de résolution des dépendances doit être explicite.",
)
assert_equal(
    result.dependency_set.evidence_set_id,
    evidence_set.evidence_set_id,
    "La structure RA doit rester rattachée à l'EvidenceSet approfondi.",
)
assert_equal(len(result.dependency_set.claim_dependencies), 1, "Le claim partagé doit produire une résolution.")
dependency = result.dependency_set.claim_dependencies[0]
assert_equal(dependency.claim_id, claim_ref.claim_id, "Le claim vérifié doit être conservé.")
assert_equal(dependency.claim_version, 3, "La version EG du claim doit être conservée.")
assert_equal(
    dependency.verification_case_id,
    "VER-M009-T005-SHARED-CASE",
    "Le verification_case_id publié par EG doit être conservé.",
)
assert_equal(
    dependency.accepted_evidence_ids,
    (primary.evidence_id, secondary.evidence_id, review.evidence_id),
    "Les preuves du deep EvidenceSet doivent rester rattachées au claim.",
)
assert_equal(
    dependency.dependency_group_ids,
    ("DEP-M009-T005-PRIMARY-STUDY",),
    "Le DependencyGroup public doit être conservé.",
)
assert_equal(
    dependency.independent_confirmation_count,
    1,
    "Trois reprises du même DependencyGroup doivent compter une seule confirmation indépendante.",
)
assert_equal(
    tuple(event.event_type for event in result.events),
    ("ClaimDependencyGroupResolved",),
    "La résolution doit publier un événement métier dédié.",
)
payload = result.dependency_set.to_payload()
assert_no_forbidden_storage_payload(payload)
assert_false("frequency" in repr(payload).lower(), "La résolution ne doit pas publier de fréquence brute.")
assert_equal(catalog.requests, [claim_ref.claim_id], "RA doit lire EG via le contrat public read_evidence.")
assert_equal(catalog.internal_reads, 0, "RA ne doit pas lire le registre EG interne.")
assert_equal(catalog.mutations, 0, "RA ne doit pas muter EG.")

print("Test d'acceptation T-005 dépendances de claims vérifiés M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_verified_claim_dependency_resolution_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 dépendances de claims vérifiés M-009: OK"
