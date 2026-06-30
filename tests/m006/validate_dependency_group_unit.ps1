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
from app.evidence_governance.domain.dependency_group import (
    DependencyGroup,
    SourceIndependencePolicy,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
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
            "canonical_source_id": f"CSRC-M006-T006-UNIT-{suffix}",
            "document_id": f"DOC-M006-T006-UNIT-{suffix}",
            "canonical_version_id": f"CVER-M006-T006-UNIT-{suffix}-0001",
            "source_sha256": "b" * 64,
            "canonical_artifact_sha256": "c" * 64,
            "page_count": 4,
            "accepted_at": "2026-06-29T17:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t006-unit-v1",
        }
    )


def evidence_ref_for(*, suffix, evidence_id):
    source_text = "les couvertures de queue réduisent le drawdown"
    ref = canonical_ref(suffix=suffix)
    item_id = f"DOC-M006-T006-UNIT-{suffix}-P001-I001"
    content_hash = content_hash_for(source_text)
    policy = SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )
    locator = SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": 1,
            "item_id": item_id,
            "bbox": (0.11, 0.21, 0.71, 0.41),
            "content_hash": content_hash,
        },
        validation_policy=policy,
    )
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "source_locator": locator.to_payload(),
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
                canonical_text="Les couvertures de queue réduisent le drawdown.",
                scope=scope.to_payload(),
                status="VERIFIED",
                verification_id=verification_id,
                evidence_refs=tuple(evidence_refs),
                dependency_group_ids=("DEP-M006-T006-UNIT-LOCKED",),
            ),
            "accepted_verification_id": verification_id,
        }
    return Claim(
        claim_id=claim_id,
        claim_version=1,
        status=status,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue réduisent le drawdown."
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


def group_for(*, suffix):
    return DependencyGroup.create(
        dependency_group_id=f"DEP-M006-T006-UNIT-{suffix}",
        origin_label=f"Origine empirique explicite {suffix}",
        created_at="2026-06-29T17:05:00Z",
    )


primary_ref = evidence_ref_for(suffix="PRIMARY", evidence_id="EVS-M006-T006-UNIT-PRIMARY")
secondary_ref = evidence_ref_for(suffix="SECONDARY", evidence_id="EVS-M006-T006-UNIT-SECONDARY")
third_ref = evidence_ref_for(suffix="THIRD", evidence_id="EVS-M006-T006-UNIT-THIRD")
claim = claim_for(
    claim_id="CLM-M006-T006-UNIT-CLAIM",
    evidence_refs=(primary_ref, secondary_ref, third_ref),
)

# DependencyGroup exige une origine explicite et ne crée aucun groupe par défaut.
group = group_for(suffix="PRIMARY")
assert_equal(group.dependency_group_id, "DEP-M006-T006-UNIT-PRIMARY", "Le groupe doit conserver son identité.")
assert_equal(group.origin_label, "Origine empirique explicite PRIMARY", "L'origine documentée doit être conservée.")
assert_equal(group.assignments, (), "Un groupe nouveau ne doit pas contenir d'affectation implicite.")
assert_raises(
    "origin_label vide",
    lambda: DependencyGroup.create(
        dependency_group_id="DEP-M006-T006-UNIT-EMPTY",
        origin_label="",
        created_at="2026-06-29T17:05:00Z",
    ),
)

# L'affectation est explicite et publie un événement traçable.
updated_group, event = group.assign_claim_evidence(
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    evidence_id=primary_ref.evidence_id,
    dependency_kind="PRIMARY_STUDY",
    occurred_at="2026-06-29T17:10:00Z",
)
assert_equal(event.event_type, "ClaimDependencyAssigned", "L'affectation doit publier un événement nommé.")
assert_equal(updated_group.assignments[0].dependency_kind, "PRIMARY_STUDY", "Le type de dépendance doit être explicite.")
assert_raises(
    "dependency_assignment duplique",
    lambda: updated_group.assign_claim_evidence(
        claim_id=claim.claim_id,
        claim_version=claim.claim_version,
        evidence_id=primary_ref.evidence_id,
        dependency_kind="PRIMARY_STUDY",
        occurred_at="2026-06-29T17:11:00Z",
    ),
)
assert_raises(
    "dependency_kind non autorise",
    lambda: group.assign_claim_evidence(
        claim_id=claim.claim_id,
        claim_version=claim.claim_version,
        evidence_id=secondary_ref.evidence_id,
        dependency_kind="TITLE_MATCH",
        occurred_at="2026-06-29T17:12:00Z",
    ),
)

# SourceIndependencePolicy compte les groupes uniques et refuse un document sans groupe.
secondary_group, _ = updated_group.assign_claim_evidence(
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    evidence_id=secondary_ref.evidence_id,
    dependency_kind="SECONDARY_REPRISE",
    occurred_at="2026-06-29T17:13:00Z",
)
distinct_group, _ = group_for(suffix="DISTINCT").assign_claim_evidence(
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    evidence_id=third_ref.evidence_id,
    dependency_kind="PRIMARY_STUDY",
    occurred_at="2026-06-29T17:14:00Z",
)
policy_result = SourceIndependencePolicy().count_independent_support(
    claim_id=claim.claim_id,
    accepted_evidence_ids=(
        primary_ref.evidence_id,
        secondary_ref.evidence_id,
        third_ref.evidence_id,
    ),
    dependency_groups=(secondary_group, distinct_group),
)
assert_equal(policy_result.independent_confirmation_count, 2, "Deux groupes uniques doivent être comptés.")
assert_equal(
    policy_result.dependency_group_ids,
    ("DEP-M006-T006-UNIT-PRIMARY", "DEP-M006-T006-UNIT-DISTINCT"),
    "L'ordre d'apparition des groupes doit être stable.",
)
assert_raises(
    f"dependency_group absent pour evidence_id: {third_ref.evidence_id}",
    lambda: SourceIndependencePolicy().count_independent_support(
        claim_id=claim.claim_id,
        accepted_evidence_ids=(
            primary_ref.evidence_id,
            third_ref.evidence_id,
        ),
        dependency_groups=(secondary_group,),
    ),
)

# Le repository mémoire refuse les doublons et ne fabrique pas un groupe absent.
repository = InMemoryDependencyGroupRepository(dependency_groups=(secondary_group, distinct_group))
assert_equal(repository.group_count(), 2, "Deux groupes explicites doivent être stockés.")
assert_raises(
    "dependency_group duplique",
    lambda: InMemoryDependencyGroupRepository(dependency_groups=(secondary_group, secondary_group)),
)
assert_raises(
    "dependency_group inconnu: DEP-M006-T006-UNIT-UNKNOWN",
    lambda: repository.group_for_id("DEP-M006-T006-UNIT-UNKNOWN"),
)

# Le handler refuse les claims, preuves et mutations ambiguës.
claim_repository = InMemoryClaimRepository(claims=(claim,))
handler = AssignClaimDependencyGroupHandler(
    claim_repository=claim_repository,
    dependency_group_repository=InMemoryDependencyGroupRepository(dependency_groups=(group_for(suffix="HANDLER"),)),
)
handler_result = handler.assign(
    AssignClaimDependencyGroup(
        claim_id=claim.claim_id,
        claim_version=claim.claim_version,
        evidence_id=primary_ref.evidence_id,
        dependency_group_id="DEP-M006-T006-UNIT-HANDLER",
        dependency_kind="PRIMARY_STUDY",
        occurred_at="2026-06-29T17:20:00Z",
    )
)
assert_equal(handler_result.status, "CLAIM_DEPENDENCY_ASSIGNED", "Le handler doit publier un statut explicite.")
assert_equal(len(handler_result.events), 1, "Une affectation acceptée publie un événement.")
assert_raises(
    "dependency_assignment duplique",
    lambda: handler.assign(
        AssignClaimDependencyGroup(
            claim_id=claim.claim_id,
            claim_version=claim.claim_version,
            evidence_id=primary_ref.evidence_id,
            dependency_group_id="DEP-M006-T006-UNIT-HANDLER",
            dependency_kind="PRIMARY_STUDY",
            occurred_at="2026-06-29T17:21:00Z",
        )
    ),
)
assert_raises(
    "evidence_ref non attachee au claim",
    lambda: handler.assign(
        AssignClaimDependencyGroup(
            claim_id=claim.claim_id,
            claim_version=claim.claim_version,
            evidence_id="EVS-M006-T006-UNIT-UNKNOWN",
            dependency_group_id="DEP-M006-T006-UNIT-HANDLER",
            dependency_kind="PRIMARY_STUDY",
            occurred_at="2026-06-29T17:22:00Z",
        )
    ),
)

verified_ref = evidence_ref_for(suffix="VERIFIED", evidence_id="EVS-M006-T006-UNIT-VERIFIED")
verified_claim = claim_for(
    claim_id="CLM-M006-T006-UNIT-VERIFIED",
    evidence_refs=(verified_ref,),
    status=ClaimStatus.VERIFIED,
)
locked_group = group_for(suffix="LOCKED")
locked_group, _ = locked_group.assign_claim_evidence(
    claim_id=verified_claim.claim_id,
    claim_version=verified_claim.claim_version,
    evidence_id=verified_ref.evidence_id,
    dependency_kind="PRIMARY_STUDY",
    occurred_at="2026-06-29T17:23:00Z",
)
new_ref = evidence_ref_for(suffix="NEW", evidence_id="EVS-M006-T006-UNIT-NEW")
new_claim = claim_for(
    claim_id="CLM-M006-T006-UNIT-NEW",
    evidence_refs=(new_ref,),
)
locked_handler = AssignClaimDependencyGroupHandler(
    claim_repository=InMemoryClaimRepository(claims=(verified_claim, new_claim)),
    dependency_group_repository=InMemoryDependencyGroupRepository(dependency_groups=(locked_group,)),
)
assert_raises(
    "claim verifie non modifiable",
    lambda: locked_handler.assign(
        AssignClaimDependencyGroup(
            claim_id=verified_claim.claim_id,
            claim_version=verified_claim.claim_version,
            evidence_id=verified_ref.evidence_id,
            dependency_group_id=locked_group.dependency_group_id,
            dependency_kind="PRIMARY_STUDY",
            occurred_at="2026-06-29T17:24:00Z",
        )
    ),
)
assert_raises(
    f"dependency_group utilise par claim verifie: {locked_group.dependency_group_id}",
    lambda: locked_handler.assign(
        AssignClaimDependencyGroup(
            claim_id=new_claim.claim_id,
            claim_version=new_claim.claim_version,
            evidence_id=new_ref.evidence_id,
            dependency_group_id=locked_group.dependency_group_id,
            dependency_kind="SECONDARY_REPRISE",
            occurred_at="2026-06-29T17:25:00Z",
        )
    ),
)

count_result = CountIndependentSupport(
    claim_repository=claim_repository,
    dependency_group_repository=repository,
).count(
    claim_id=claim.claim_id,
    accepted_evidence_ids=(
        primary_ref.evidence_id,
        secondary_ref.evidence_id,
        third_ref.evidence_id,
    ),
)
assert_equal(count_result.independent_confirmation_count, 2, "La requête doit déléguer à SourceIndependencePolicy.")

print("Tests unitaires T-006 confirmations indépendantes M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_dependency_group_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 confirmations indépendantes M-006: OK"
