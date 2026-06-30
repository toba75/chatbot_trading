$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.adapters.in_memory_claim_relation_repository import InMemoryClaimRelationRepository
from app.evidence_governance.application.relate_claims import RelateClaims, RelateClaimsHandler
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, SupersededBy
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    Limitation,
)
from app.evidence_governance.domain.claim_relation import (
    ClaimRelation,
    ClaimRelationPolicy,
    ClaimRelationRecorded,
    ClaimRelationType,
    ClaimVersionRef,
    ScopeCompatibility,
    ScopeCompatibilityStatus,
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


def scope_for(*, universe, horizon, metric="rendement", frequency="mensuelle"):
    return ClaimScope(
        universe=universe,
        horizon=horizon,
        metric=metric,
        frequency=frequency,
    )


def claim_for(*, claim_id, claim_version, proposition, scope, status=ClaimStatus.EVIDENCE_ATTACHED, **extra):
    return Claim(
        claim_id=claim_id,
        claim_version=claim_version,
        status=status,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(proposition),
        scope=scope,
        conditions=(ClaimCondition("portée explicitement comparée"),),
        limitations=(Limitation("relation limitée aux versions citées"),),
        evidence_associations=(),
        **extra,
    )


def relation_for(*, relation_id, source, target, relation_type, compatibility, cycle_justification=None):
    return ClaimRelation(
        relation_id=relation_id,
        source_claim_ref=ClaimVersionRef(
            claim_id=source.claim_id,
            claim_version=source.claim_version,
        ),
        target_claim_ref=ClaimVersionRef(
            claim_id=target.claim_id,
            claim_version=target.claim_version,
        ),
        relation_type=relation_type,
        scope_compatibility=compatibility,
        relation_basis="EXPLICIT_SCOPE_COMPARISON",
        policy_version="claim-relation-policy-m006-t007-v1",
        recorded_at="2026-06-29T19:00:00Z",
        cycle_justification=cycle_justification,
    )


same_scope = scope_for(
    universe="portefeuilles convexes antifragiles",
    horizon="crises de volatilité 2008-2024",
)
short_scope = scope_for(
    universe="portefeuilles convexes antifragiles",
    horizon="mois de crise",
)
long_scope = scope_for(
    universe="portefeuilles convexes antifragiles",
    horizon="cycle complet 2008-2024",
)
general_scope = scope_for(
    universe="tous les portefeuilles convexes",
    horizon="cycle complet 2008-2024",
)
specific_scope = scope_for(
    universe="portefeuilles convexes antifragiles avec couverture de queue",
    horizon="cycle complet 2008-2024",
)

claim_a = claim_for(
    claim_id="CLM-M006-T007-UNIT-A",
    claim_version=1,
    proposition="La couverture de queue améliore le rendement.",
    scope=same_scope,
)
claim_b = claim_for(
    claim_id="CLM-M006-T007-UNIT-B",
    claim_version=2,
    proposition="La couverture de queue détériore le rendement.",
    scope=same_scope,
)
claim_c = claim_for(
    claim_id="CLM-M006-T007-UNIT-C",
    claim_version=1,
    proposition="La couverture de queue améliore le rendement mensuel.",
    scope=short_scope,
)
claim_d = claim_for(
    claim_id="CLM-M006-T007-UNIT-D",
    claim_version=1,
    proposition="La couverture de queue détériore le rendement long.",
    scope=long_scope,
)
claim_general = claim_for(
    claim_id="CLM-M006-T007-UNIT-GENERAL",
    claim_version=1,
    proposition="Les portefeuilles convexes protègent le rendement.",
    scope=general_scope,
)
claim_specific = claim_for(
    claim_id="CLM-M006-T007-UNIT-SPECIFIC",
    claim_version=1,
    proposition="Les portefeuilles convexes antifragiles protègent le rendement.",
    scope=specific_scope,
)

# Les références de claim exigent une version explicite.
claim_ref = ClaimVersionRef(claim_id=claim_a.claim_id, claim_version=claim_a.claim_version)
assert_equal(claim_ref.to_payload()["claim_version"], 1, "La version doit être publiée.")
assert_raises(
    "claim_version invalide",
    lambda: ClaimVersionRef(claim_id=claim_a.claim_id, claim_version=0),
)

# La compatibilité de portée contrôle les quatre dimensions et la raison de non-comparabilité.
compatible = ScopeCompatibility.compare(source_scope=same_scope, target_scope=same_scope)
assert_equal(compatible.status, ScopeCompatibilityStatus.COMPARABLE, "Les portées identiques doivent être comparables.")
assert_equal(
    compatible.compared_dimensions,
    ("universe", "horizon", "metric", "frequency"),
    "Toutes les dimensions de portée doivent être comparées.",
)
non_comparable = ScopeCompatibility.compare(source_scope=short_scope, target_scope=long_scope)
assert_equal(
    non_comparable.status,
    ScopeCompatibilityStatus.NON_COMPARABLE,
    "Deux horizons différents doivent être non comparables.",
)
assert_equal(
    non_comparable.reason_code,
    "SCOPE_HORIZON_MISMATCH",
    "La raison de non-comparabilité doit être obligatoire.",
)
assert_raises(
    "scope_dimensions incompletes",
    lambda: ScopeCompatibility(
        status=ScopeCompatibilityStatus.COMPARABLE,
        compared_dimensions=("universe", "horizon"),
        reason_code=None,
    ),
)
assert_raises(
    "scope_incompatibility_reason absente",
    lambda: ScopeCompatibility(
        status=ScopeCompatibilityStatus.NON_COMPARABLE,
        compared_dimensions=("universe", "horizon", "metric", "frequency"),
        reason_code=None,
    ),
)

# La politique transforme seulement une contradiction hors portée en contradiction apparente.
policy = ClaimRelationPolicy()
contradiction = policy.evaluate(
    source_claim=claim_a,
    target_claim=claim_b,
    requested_relation_type=ClaimRelationType.CONTRADICTS,
    relation_basis="EXPLICIT_SCOPE_COMPARISON",
)
assert_equal(
    contradiction.relation_type,
    ClaimRelationType.CONTRADICTS,
    "Une contradiction comparable doit rester générale.",
)
apparent = policy.evaluate(
    source_claim=claim_c,
    target_claim=claim_d,
    requested_relation_type=ClaimRelationType.CONTRADICTS,
    relation_basis="EXPLICIT_SCOPE_COMPARISON",
)
assert_equal(
    apparent.relation_type,
    ClaimRelationType.APPARENTLY_CONTRADICTS,
    "Une contradiction hors portée comparable devient apparente.",
)
generalization = policy.evaluate(
    source_claim=claim_general,
    target_claim=claim_specific,
    requested_relation_type=ClaimRelationType.MORE_GENERAL_THAN,
    relation_basis="EXPLICIT_SCOPE_COMPARISON",
)
assert_equal(
    generalization.scope_compatibility.status,
    ScopeCompatibilityStatus.SOURCE_BROADER,
    "La généralisation doit prouver une portée source plus large.",
)
assert_raises(
    "relation par similarite textuelle seule interdite",
    lambda: policy.evaluate(
        source_claim=claim_a,
        target_claim=claim_b,
        requested_relation_type=ClaimRelationType.CONTRADICTS,
        relation_basis="TEXTUAL_SIMILARITY_ONLY",
    ),
)
assert_raises(
    "relation_type absent",
    lambda: policy.evaluate(
        source_claim=claim_a,
        target_claim=claim_b,
        requested_relation_type=None,
        relation_basis="EXPLICIT_SCOPE_COMPARISON",
    ),
)

# ClaimRelation refuse les types implicites et publie un événement versionné.
relation = relation_for(
    relation_id="REL-M006-T007-UNIT-VALID",
    source=claim_a,
    target=claim_b,
    relation_type=ClaimRelationType.CONTRADICTS,
    compatibility=compatible,
)
event = ClaimRelationRecorded.from_relation(relation)
assert_equal(event.event_type, "ClaimRelationRecorded", "L'événement de relation doit être nommé.")
assert_equal(
    event.to_payload()["payload"]["source_claim_ref"]["claim_version"],
    1,
    "L'événement doit publier la version source.",
)
assert_raises(
    "relation_type absent",
    lambda: relation_for(
        relation_id="REL-M006-T007-UNIT-NOTYPE",
        source=claim_a,
        target=claim_b,
        relation_type=None,
        compatibility=compatible,
    ),
)
assert_raises(
    "contradiction_scope non comparable",
    lambda: relation_for(
        relation_id="REL-M006-T007-UNIT-BAD-CONTRADICTION",
        source=claim_c,
        target=claim_d,
        relation_type=ClaimRelationType.CONTRADICTS,
        compatibility=non_comparable,
    ),
)

# Le repository refuse les doublons et le handler interdit les cycles sans justification explicite.
claim_repository = InMemoryClaimRepository(claims=(claim_a, claim_b))
relation_repository = InMemoryClaimRelationRepository.empty()
handler = RelateClaimsHandler(
    claim_repository=claim_repository,
    claim_relation_repository=relation_repository,
)
old_version = claim_for(
    claim_id="CLM-M006-T007-UNIT-VERSIONED",
    claim_version=1,
    proposition="La couverture de queue améliore le rendement sur l'ancienne fenêtre.",
    scope=same_scope,
    status=ClaimStatus.SUPERSEDED,
    superseded_by=SupersededBy(claim_id="CLM-M006-T007-UNIT-VERSIONED", claim_version=2),
    supersession_reason="Nouvelle fenêtre de mesure.",
    superseded_at="2026-06-29T19:05:00Z",
)
latest_version = claim_for(
    claim_id=old_version.claim_id,
    claim_version=2,
    proposition="La couverture de queue améliore le rendement sur la nouvelle fenêtre.",
    scope=same_scope,
)
version_target = claim_for(
    claim_id="CLM-M006-T007-UNIT-VERSION-TARGET",
    claim_version=1,
    proposition="La couverture de queue améliore le rendement sur le témoin.",
    scope=same_scope,
)
versioned_handler = RelateClaimsHandler(
    claim_repository=InMemoryClaimRepository(claims=(old_version, latest_version, version_target)),
    claim_relation_repository=InMemoryClaimRelationRepository.empty(),
)
versioned_result = versioned_handler.relate(
    RelateClaims(
        relation_id="REL-M006-T007-UNIT-EXPLICIT-VERSION",
        source_claim_id=old_version.claim_id,
        source_claim_version=old_version.claim_version,
        target_claim_id=version_target.claim_id,
        target_claim_version=version_target.claim_version,
        requested_relation_type=ClaimRelationType.DERIVED_FROM,
        relation_basis="EXPLICIT_SOURCE_DEPENDENCY",
        policy_version="claim-relation-policy-m006-t007-v1",
        occurred_at="2026-06-29T19:06:00Z",
    )
)
assert_equal(
    versioned_result.relation.source_claim_ref.claim_version,
    1,
    "Le handler doit charger la version source demandée, pas la dernière version.",
)
first = handler.relate(
    RelateClaims(
        relation_id="REL-M006-T007-UNIT-A-B",
        source_claim_id=claim_a.claim_id,
        source_claim_version=claim_a.claim_version,
        target_claim_id=claim_b.claim_id,
        target_claim_version=claim_b.claim_version,
        requested_relation_type=ClaimRelationType.DERIVED_FROM,
        relation_basis="EXPLICIT_SOURCE_DEPENDENCY",
        policy_version="claim-relation-policy-m006-t007-v1",
        occurred_at="2026-06-29T19:10:00Z",
    )
)
assert_equal(first.status, "CLAIM_RELATION_RECORDED", "La première relation doit être enregistrée.")
assert_raises(
    "claim_relation duplique",
    lambda: relation_repository.save(first.relation),
)
assert_raises(
    "cycle relation claim interdit",
    lambda: handler.relate(
        RelateClaims(
            relation_id="REL-M006-T007-UNIT-B-A-BLOCKED",
            source_claim_id=claim_b.claim_id,
            source_claim_version=claim_b.claim_version,
            target_claim_id=claim_a.claim_id,
            target_claim_version=claim_a.claim_version,
            requested_relation_type=ClaimRelationType.DERIVED_FROM,
            relation_basis="EXPLICIT_SOURCE_DEPENDENCY",
            policy_version="claim-relation-policy-m006-t007-v1",
            occurred_at="2026-06-29T19:11:00Z",
        )
    ),
)
cycle_result = handler.relate(
    RelateClaims(
        relation_id="REL-M006-T007-UNIT-B-A-JUSTIFIED",
        source_claim_id=claim_b.claim_id,
        source_claim_version=claim_b.claim_version,
        target_claim_id=claim_a.claim_id,
        target_claim_version=claim_a.claim_version,
        requested_relation_type=ClaimRelationType.DERIVED_FROM,
        relation_basis="EXPLICIT_SOURCE_DEPENDENCY",
        policy_version="claim-relation-policy-m006-t007-v1",
        occurred_at="2026-06-29T19:12:00Z",
        cycle_justification="Cycle accepté pour représenter une dépendance bidirectionnelle auditée.",
    )
)
assert_true(
    cycle_result.relation.cycle_justification is not None,
    "Une justification explicite doit permettre le cycle auditable.",
)

print("Tests unitaires T-007 relations claims après comparaison de portée M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_relation_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 relations claims après comparaison de portée M-006: OK"
