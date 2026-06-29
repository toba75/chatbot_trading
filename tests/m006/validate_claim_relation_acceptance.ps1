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
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    Limitation,
)
from app.evidence_governance.domain.claim_relation import (
    ClaimRelationType,
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
    except ValueError as exc:
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


def claim_for(*, claim_id, claim_version, proposition, scope):
    return Claim(
        claim_id=claim_id,
        claim_version=claim_version,
        status=ClaimStatus.VERIFIED,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(proposition),
        scope=scope,
        conditions=(ClaimCondition("portée explicitement comparée"),),
        limitations=(Limitation("relation limitée aux versions citées"),),
        evidence_associations=(),
    )


def command_for(
    *,
    relation_id,
    source,
    target,
    requested_relation_type,
    relation_basis="EXPLICIT_SCOPE_COMPARISON",
    occurred_at="2026-06-29T18:30:00Z",
    cycle_justification=None,
):
    return RelateClaims(
        relation_id=relation_id,
        source_claim_id=source.claim_id,
        source_claim_version=source.claim_version,
        target_claim_id=target.claim_id,
        target_claim_version=target.claim_version,
        requested_relation_type=requested_relation_type,
        relation_basis=relation_basis,
        policy_version="claim-relation-policy-m006-t007-v1",
        occurred_at=occurred_at,
        cycle_justification=cycle_justification,
    )


same_scope = scope_for(
    universe="portefeuilles convexes antifragiles",
    horizon="crises de volatilité 2008-2024",
)
short_horizon_scope = scope_for(
    universe="portefeuilles convexes antifragiles",
    horizon="mois de crise",
)
long_horizon_scope = scope_for(
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

claim_positive = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-POSITIVE",
    claim_version=2,
    proposition="La couverture de queue améliore le rendement en crise.",
    scope=same_scope,
)
claim_negative = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-NEGATIVE",
    claim_version=3,
    proposition="La couverture de queue détériore le rendement en crise.",
    scope=same_scope,
)
claim_short = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-SHORT",
    claim_version=1,
    proposition="La couverture de queue améliore le rendement sur un mois de crise.",
    scope=short_horizon_scope,
)
claim_long = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-LONG",
    claim_version=1,
    proposition="La couverture de queue détériore le rendement sur un cycle complet.",
    scope=long_horizon_scope,
)
claim_general = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-GENERAL",
    claim_version=4,
    proposition="Les portefeuilles convexes protègent le rendement.",
    scope=general_scope,
)
claim_specific = claim_for(
    claim_id="CLM-M006-T007-ACCEPTANCE-SPECIFIC",
    claim_version=5,
    proposition="Les portefeuilles convexes antifragiles protègent le rendement.",
    scope=specific_scope,
)

claim_repository = InMemoryClaimRepository(
    claims=(
        claim_positive,
        claim_negative,
        claim_short,
        claim_long,
        claim_general,
        claim_specific,
    )
)
relation_repository = InMemoryClaimRelationRepository.empty()
handler = RelateClaimsHandler(
    claim_repository=claim_repository,
    claim_relation_repository=relation_repository,
)

# Given deux claims opposés avec même portée.
# When EG évalue une contradiction explicite entre versions.
comparable_result = handler.relate(
    command_for(
        relation_id="REL-M006-T007-ACCEPTANCE-COMPARABLE",
        source=claim_positive,
        target=claim_negative,
        requested_relation_type=ClaimRelationType.CONTRADICTS,
    )
)

# Then la contradiction générale est enregistrée avec les versions de claims.
assert_equal(comparable_result.status, "CLAIM_RELATION_RECORDED", "La relation doit être enregistrée explicitement.")
assert_equal(
    comparable_result.relation.relation_type,
    ClaimRelationType.CONTRADICTS,
    "Une contradiction comparable doit rester CONTRADICTS.",
)
assert_equal(
    comparable_result.relation.scope_compatibility.status,
    ScopeCompatibilityStatus.COMPARABLE,
    "La contradiction générale exige une portée comparable.",
)
assert_equal(
    comparable_result.events[0].event_type,
    "ClaimRelationRecorded",
    "La relation doit publier l'événement ClaimRelationRecorded.",
)
payload = comparable_result.events[0].to_payload()["payload"]
assert_equal(payload["source_claim_ref"]["claim_version"], 2, "La version source doit être publiée.")
assert_equal(payload["target_claim_ref"]["claim_version"], 3, "La version cible doit être publiée.")

# Given deux claims opposés avec horizons différents.
# When EG évalue une contradiction demandée.
apparent_result = handler.relate(
    command_for(
        relation_id="REL-M006-T007-ACCEPTANCE-APPARENT",
        source=claim_short,
        target=claim_long,
        requested_relation_type=ClaimRelationType.CONTRADICTS,
        occurred_at="2026-06-29T18:31:00Z",
    )
)

# Then aucune relation CONTRADICTS générale n'est créée et la raison de non-comparabilité est enregistrée.
assert_equal(
    apparent_result.relation.relation_type,
    ClaimRelationType.APPARENTLY_CONTRADICTS,
    "Deux horizons différents doivent produire une contradiction apparente.",
)
assert_equal(
    apparent_result.relation.scope_compatibility.status,
    ScopeCompatibilityStatus.NON_COMPARABLE,
    "La non-comparabilité de portée doit être explicite.",
)
assert_equal(
    apparent_result.relation.scope_compatibility.reason_code,
    "SCOPE_HORIZON_MISMATCH",
    "La raison de non-comparabilité doit nommer l'horizon.",
)
between_short_long = relation_repository.relations_between(
    source_claim_id=claim_short.claim_id,
    target_claim_id=claim_long.claim_id,
)
assert_true(
    all(relation.relation_type != ClaimRelationType.CONTRADICTS for relation in between_short_long),
    "La relation CONTRADICTS ne doit pas être enregistrée hors portée comparable.",
)

# Given un claim général et un claim plus spécifique.
# When EG enregistre une généralisation entre versions.
generalization_result = handler.relate(
    command_for(
        relation_id="REL-M006-T007-ACCEPTANCE-GENERAL",
        source=claim_general,
        target=claim_specific,
        requested_relation_type=ClaimRelationType.MORE_GENERAL_THAN,
        occurred_at="2026-06-29T18:32:00Z",
    )
)

# Then la généralisation conserve la comparaison de portée et les versions.
assert_equal(
    generalization_result.relation.relation_type,
    ClaimRelationType.MORE_GENERAL_THAN,
    "La relation de généralisation doit rester explicite.",
)
assert_equal(
    generalization_result.relation.scope_compatibility.status,
    ScopeCompatibilityStatus.SOURCE_BROADER,
    "La portée source doit être reconnue comme plus générale.",
)
assert_equal(
    generalization_result.relation.source_claim_ref.claim_version,
    4,
    "La version de claim source doit être obligatoire.",
)
assert_equal(
    generalization_result.relation.target_claim_ref.claim_version,
    5,
    "La version de claim cible doit être obligatoire.",
)

# Une relation vers un claim inexistant doit être refusée sans relation silencieuse.
missing_target_command = RelateClaims(
    relation_id="REL-M006-T007-ACCEPTANCE-MISSING",
    source_claim_id=claim_positive.claim_id,
    source_claim_version=claim_positive.claim_version,
    target_claim_id="CLM-M006-T007-ACCEPTANCE-MISSING",
    target_claim_version=1,
    requested_relation_type=ClaimRelationType.DERIVED_FROM,
    relation_basis="EXPLICIT_SOURCE_DEPENDENCY",
    policy_version="claim-relation-policy-m006-t007-v1",
    occurred_at="2026-06-29T18:33:00Z",
)
assert_raises(
    "claim inconnu: CLM-M006-T007-ACCEPTANCE-MISSING",
    lambda: handler.relate(missing_target_command),
)

print("Test d'acceptation T-007 relations claims après comparaison de portée M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_relation_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 relations claims après comparaison de portée M-006: OK"
