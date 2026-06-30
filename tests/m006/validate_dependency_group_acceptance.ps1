$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.adapters.in_memory_dependency_group_repository import InMemoryDependencyGroupRepository
from app.evidence_governance.application.dependency_groups import (
    AssignClaimDependencyGroup,
    AssignClaimDependencyGroupHandler,
    CountIndependentSupport,
)
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, EvidenceAssociation
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    Limitation,
)
from app.evidence_governance.domain.dependency_group import DependencyGroup


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref(*, suffix):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M006-T006-ACCEPTANCE-{suffix}",
            "document_id": f"DOC-M006-T006-ACCEPTANCE-{suffix}",
            "canonical_version_id": f"CVER-M006-T006-ACCEPTANCE-{suffix}-0001",
            "source_sha256": "9" * 64,
            "canonical_artifact_sha256": "a" * 64,
            "page_count": 8,
            "accepted_at": "2026-06-29T16:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t006-v1",
        }
    )


def source_locator_policy(ref, *, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )


def evidence_ref_for(*, suffix, evidence_id):
    source_text = (
        "les couvertures de queue réduisent le drawdown pendant les crises de volatilité"
    )
    ref = canonical_ref(suffix=suffix)
    item_id = f"DOC-M006-T006-ACCEPTANCE-{suffix}-P004-I001"
    content_hash = content_hash_for(source_text)
    policy = source_locator_policy(ref, item_id=item_id, content_hash=content_hash)
    source_locator = SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": 4,
            "item_id": item_id,
            "bbox": (0.10, 0.20, 0.84, 0.46),
            "content_hash": content_hash,
        },
        validation_policy=policy,
    )
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "source_locator": source_locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": content_hash,
        },
        source_locator_validation_policy=policy,
    )


def claim_for(*, claim_id, evidence_refs, status=ClaimStatus.EVIDENCE_ATTACHED):
    scope = ClaimScope(
        universe="portefeuille avec couvertures de queue",
        horizon="crises de volatilité",
        metric="drawdown",
        frequency="quotidienne",
    )
    verified_fields = {}
    if status == ClaimStatus.VERIFIED:
        verification_id = f"VER-{claim_id.removeprefix('CLM-')}"
        verified_fields = {
            "verified_claim_ref": VerifiedClaimRef(
                schema_version="1.0",
                claim_id=claim_id,
                claim_version=1,
                canonical_text="Les couvertures de queue réduisent le drawdown pendant les crises de volatilité.",
                scope=scope.to_payload(),
                status="VERIFIED",
                verification_id=verification_id,
                evidence_refs=tuple(evidence_refs),
                dependency_group_ids=("DEP-M006-T006-ACCEPTANCE-PRIMARY-STUDY",),
            ),
            "accepted_verification_id": verification_id,
        }
    return Claim(
        claim_id=claim_id,
        claim_version=1,
        status=status,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue réduisent le drawdown pendant les crises de volatilité."
        ),
        scope=scope,
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_associations=tuple(
            EvidenceAssociation.from_evidence_ref(evidence_ref)
            for evidence_ref in evidence_refs
        ),
        **verified_fields,
    )


def dependency_group(*, suffix, origin_label):
    return DependencyGroup.create(
        dependency_group_id=f"DEP-M006-T006-ACCEPTANCE-{suffix}",
        origin_label=origin_label,
        created_at="2026-06-29T16:05:00Z",
    )


def assign(handler, claim, evidence_ref, group, *, kind):
    return handler.assign(
        AssignClaimDependencyGroup(
            claim_id=claim.claim_id,
            claim_version=claim.claim_version,
            evidence_id=evidence_ref.evidence_id,
            dependency_group_id=group.dependency_group_id,
            dependency_kind=kind,
            occurred_at="2026-06-29T16:10:00Z",
        )
    )


# Given trois documents rattachés au même DependencyGroup.
primary_ref = evidence_ref_for(suffix="PRIMARY", evidence_id="EVS-M006-T006-ACCEPTANCE-PRIMARY")
secondary_ref = evidence_ref_for(suffix="SECONDARY", evidence_id="EVS-M006-T006-ACCEPTANCE-SECONDARY")
review_ref = evidence_ref_for(suffix="REVIEW", evidence_id="EVS-M006-T006-ACCEPTANCE-REVIEW")
claim = claim_for(
    claim_id="CLM-M006-T006-ACCEPTANCE-SAME",
    evidence_refs=(primary_ref, secondary_ref, review_ref),
)
shared_group = dependency_group(
    suffix="PRIMARY-STUDY",
    origin_label="Étude primaire TailRisk 2024 citée par deux reprises secondaires",
)
claim_repository = InMemoryClaimRepository(claims=(claim,))
dependency_group_repository = InMemoryDependencyGroupRepository(dependency_groups=(shared_group,))
handler = AssignClaimDependencyGroupHandler(
    claim_repository=claim_repository,
    dependency_group_repository=dependency_group_repository,
)
assign(handler, claim, primary_ref, shared_group, kind="PRIMARY_STUDY")
assign(handler, claim, secondary_ref, shared_group, kind="SECONDARY_REPRISE")
assign(handler, claim, review_ref, shared_group, kind="SECONDARY_REPRISE")

# When le nombre de confirmations indépendantes est calculé.
counter = CountIndependentSupport(
    claim_repository=claim_repository,
    dependency_group_repository=dependency_group_repository,
)
same_group_count = counter.count(
    claim_id=claim.claim_id,
    accepted_evidence_ids=(
        primary_ref.evidence_id,
        secondary_ref.evidence_id,
        review_ref.evidence_id,
    ),
)

# Then une seule confirmation indépendante est comptabilisée.
assert_equal(
    same_group_count.status,
    "CLAIM_INDEPENDENT_SUPPORT_COUNTED",
    "Le service doit publier un statut explicite.",
)
assert_equal(
    same_group_count.independent_confirmation_count,
    1,
    "Trois mentions du même DependencyGroup doivent compter une seule confirmation.",
)
assert_equal(
    same_group_count.dependency_group_ids,
    (shared_group.dependency_group_id,),
    "Le résultat doit exposer le groupe réellement compté.",
)

# Given deux groupes explicites distincts pour un autre claim.
first_ref = evidence_ref_for(suffix="FIRST", evidence_id="EVS-M006-T006-ACCEPTANCE-FIRST")
second_ref = evidence_ref_for(suffix="SECOND", evidence_id="EVS-M006-T006-ACCEPTANCE-SECOND")
distinct_claim = claim_for(
    claim_id="CLM-M006-T006-ACCEPTANCE-DISTINCT",
    evidence_refs=(first_ref, second_ref),
)
first_group = dependency_group(suffix="FIRST-STUDY", origin_label="Étude primaire optionnelle 2022")
second_group = dependency_group(suffix="SECOND-STUDY", origin_label="Étude primaire indépendante 2023")
distinct_claim_repository = InMemoryClaimRepository(claims=(distinct_claim,))
distinct_dependency_repository = InMemoryDependencyGroupRepository(
    dependency_groups=(first_group, second_group)
)
distinct_handler = AssignClaimDependencyGroupHandler(
    claim_repository=distinct_claim_repository,
    dependency_group_repository=distinct_dependency_repository,
)
assign(distinct_handler, distinct_claim, first_ref, first_group, kind="PRIMARY_STUDY")
assign(distinct_handler, distinct_claim, second_ref, second_group, kind="PRIMARY_STUDY")

# When le support indépendant est calculé.
distinct_count = CountIndependentSupport(
    claim_repository=distinct_claim_repository,
    dependency_group_repository=distinct_dependency_repository,
).count(
    claim_id=distinct_claim.claim_id,
    accepted_evidence_ids=(first_ref.evidence_id, second_ref.evidence_id),
)

# Then les deux origines explicites sont comptées.
assert_equal(
    distinct_count.independent_confirmation_count,
    2,
    "Deux DependencyGroup distincts doivent compter deux confirmations indépendantes.",
)

# Given un document sans groupe documenté.
ungrouped_ref = evidence_ref_for(suffix="UNGROUPED", evidence_id="EVS-M006-T006-ACCEPTANCE-UNGROUPED")
grouped_ref = evidence_ref_for(suffix="GROUPED", evidence_id="EVS-M006-T006-ACCEPTANCE-GROUPED")
partial_claim = claim_for(
    claim_id="CLM-M006-T006-ACCEPTANCE-MISSING",
    evidence_refs=(ungrouped_ref, grouped_ref),
)
partial_group = dependency_group(suffix="PARTIAL", origin_label="Étude primaire partiellement affectée")
partial_claim_repository = InMemoryClaimRepository(claims=(partial_claim,))
partial_dependency_repository = InMemoryDependencyGroupRepository(dependency_groups=(partial_group,))
partial_handler = AssignClaimDependencyGroupHandler(
    claim_repository=partial_claim_repository,
    dependency_group_repository=partial_dependency_repository,
)
assign(partial_handler, partial_claim, grouped_ref, partial_group, kind="PRIMARY_STUDY")

# When le compteur reçoit une preuve acceptée sans DependencyGroup.
# Then le document est refusé sans groupe par défaut ni regroupement silencieux.
assert_raises(
    f"dependency_group absent pour evidence_id: {ungrouped_ref.evidence_id}",
    lambda: CountIndependentSupport(
        claim_repository=partial_claim_repository,
        dependency_group_repository=partial_dependency_repository,
    ).count(
        claim_id=partial_claim.claim_id,
        accepted_evidence_ids=(ungrouped_ref.evidence_id, grouped_ref.evidence_id),
    ),
)

# Given un groupe déjà utilisé par un claim vérifié.
verified_claim = claim_for(
    claim_id=claim.claim_id,
    evidence_refs=(primary_ref, secondary_ref, review_ref),
    status=ClaimStatus.VERIFIED,
)
claim_repository.save(verified_claim)
new_ref = evidence_ref_for(suffix="NEW", evidence_id="EVS-M006-T006-ACCEPTANCE-NEW")
new_claim = claim_for(
    claim_id="CLM-M006-T006-ACCEPTANCE-NEW",
    evidence_refs=(new_ref,),
)
claim_repository.save(new_claim)

# When une nouvelle affectation tente de modifier ce groupe.
# Then la modification est refusée explicitement.
assert_raises(
    f"dependency_group utilise par claim verifie: {shared_group.dependency_group_id}",
    lambda: assign(handler, new_claim, new_ref, shared_group, kind="SECONDARY_REPRISE"),
)

# Les garde-fous refusent aussi les doubles affectations explicites et les groupes absents.
assert_raises(
    "claim verifie non modifiable",
    lambda: assign(handler, verified_claim, primary_ref, shared_group, kind="PRIMARY_STUDY"),
)
assert_raises(
    "dependency_group inconnu: DEP-M006-T006-ACCEPTANCE-UNKNOWN",
    lambda: handler.assign(
        AssignClaimDependencyGroup(
            claim_id=new_claim.claim_id,
            claim_version=new_claim.claim_version,
            evidence_id=new_ref.evidence_id,
            dependency_group_id="DEP-M006-T006-ACCEPTANCE-UNKNOWN",
            dependency_kind="PRIMARY_STUDY",
            occurred_at="2026-06-29T16:20:00Z",
        )
    ),
)

assert_true(
    "document_title" not in AssignClaimDependencyGroup.__dataclass_fields__,
    "La commande ne doit exposer aucun champ de regroupement par titre proche.",
)

print("Test d'acceptation T-006 confirmations indépendantes M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_dependency_group_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 confirmations indépendantes M-006: OK"
