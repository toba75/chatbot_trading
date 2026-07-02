$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from app.evidence_governance.domain.claim_relation import (
    ClaimRelation,
    ClaimRelationType,
    ClaimVersionRef,
    ScopeCompatibility,
    ScopeCompatibilityStatus,
)
from app.research_answering.domain.contradiction_assessment import (
    ContradictionClassification,
    DeepContradictionClassificationPolicy,
    DeepRelationClassificationContext,
)


SCOPE_DIMENSIONS = ("universe", "horizon", "metric", "frequency")


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def assert_no_frequency_consensus(value, path="payload"):
    forbidden_markers = {"raw_frequency_count", "raw_mention_count", "frequency_consensus"}
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key.lower() in forbidden_markers, f"Consensus par fréquence publié dans {path}.{key}.")
            assert_no_frequency_consensus(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_frequency_consensus(child, f"{path}[{index}]")


def claim_ref(suffix):
    return ClaimVersionRef(claim_id=f"CLM-M009-T006-{suffix}", claim_version=1)


def comparable_scope():
    return ScopeCompatibility(
        status=ScopeCompatibilityStatus.COMPARABLE,
        compared_dimensions=SCOPE_DIMENSIONS,
        reason_code=None,
    )


def non_comparable_scope(reason_code):
    return ScopeCompatibility(
        status=ScopeCompatibilityStatus.NON_COMPARABLE,
        compared_dimensions=SCOPE_DIMENSIONS,
        reason_code=reason_code,
    )


def relation_for(*, relation_id, relation_type, compatibility, basis="EXPLICIT_SCOPE_COMPARISON"):
    if relation_type == ClaimRelationType.SUPPORTS:
        basis = "EXPLICIT_SUPPORT_EVIDENCE"
    if relation_type == ClaimRelationType.QUALIFIES:
        basis = "EXPLICIT_SCOPE_QUALIFICATION"
    return ClaimRelation(
        relation_id=relation_id,
        source_claim_ref=claim_ref("SOURCE"),
        target_claim_ref=claim_ref("TARGET"),
        relation_type=relation_type,
        scope_compatibility=compatibility,
        relation_basis=basis,
        policy_version="claim-relation-policy-m009-t006-v1",
        recorded_at="2026-07-02T12:00:00Z",
        cycle_justification=None,
    )


def context_for(
    *,
    relation_id,
    public_reason="Raison publique documentée pour la synthèse approfondie.",
    reason_codes=("EXPLICIT_SCOPE_COMPARISON",),
    dependency_group_ids=("DEP-M009-T006-INDEPENDENT",),
):
    return DeepRelationClassificationContext(
        relation_id=relation_id,
        conditions=("univers et horizon explicitement comparés",),
        limits=("la conclusion ne vaut que pour la portée comparée",),
        public_reason=public_reason,
        reason_codes=reason_codes,
        independent_dependency_group_ids=dependency_group_ids,
    )


policy = DeepContradictionClassificationPolicy(policy_version="conditional-contradiction-m009-v1")


# SUPPORTS sur une portée compatible devient une compatibilité positive, sans consensus par fréquence.
support_relation = relation_for(
    relation_id="REL-M009-T006-SUPPORTS",
    relation_type=ClaimRelationType.SUPPORTS,
    compatibility=comparable_scope(),
)
support_assessment = policy.classify(
    support_relation,
    classification_context=context_for(
        relation_id=support_relation.relation_id,
        reason_codes=("EXPLICIT_POSITIVE_RELATION",),
    ),
)
assert_equal(
    support_assessment.classification,
    ContradictionClassification.POSITIVE_COMPATIBILITY,
    "Une relation SUPPORTS compatible doit rester une compatibilité positive.",
)
assert_equal(support_assessment.relation_type, "SUPPORTS", "Le type de relation public doit être conservé.")
assert_equal(support_assessment.compared_dimensions, SCOPE_DIMENSIONS, "Les dimensions comparées doivent être conservées.")
assert_false(support_assessment.blocks_publication, "Une compatibilité positive ne doit pas bloquer la publication.")
assert_no_frequency_consensus(support_assessment.to_payload())

# QUALIFIES compatible reste une compatibilité positive qualifiée.
qualifies_relation = relation_for(
    relation_id="REL-M009-T006-QUALIFIES",
    relation_type=ClaimRelationType.QUALIFIES,
    compatibility=comparable_scope(),
)
qualifies_assessment = policy.classify(
    qualifies_relation,
    classification_context=context_for(
        relation_id=qualifies_relation.relation_id,
        reason_codes=("EXPLICIT_POSITIVE_QUALIFICATION",),
    ),
)
assert_equal(
    qualifies_assessment.classification,
    ContradictionClassification.POSITIVE_COMPATIBILITY,
    "Une relation QUALIFIES compatible doit produire une compatibilité positive.",
)
assert_equal(qualifies_assessment.relation_type, "QUALIFIES", "La qualification positive doit rester visible.")

# Une convergence sans groupe indépendant est acceptée seulement si la limite publique est explicite.
unconfirmed_convergence = policy.classify(
    support_relation,
    classification_context=DeepRelationClassificationContext(
        relation_id=support_relation.relation_id,
        conditions=("les deux claims partagent une preuve primaire",),
        limits=("CONVERGENCE_WITHOUT_INDEPENDENT_GROUP",),
        public_reason="Les claims convergent, mais aucun groupe indépendant ne confirme cette convergence.",
        reason_codes=("EXPLICIT_POSITIVE_RELATION", "CONVERGENCE_WITHOUT_INDEPENDENT_GROUP"),
        independent_dependency_group_ids=(),
    ),
)
assert_equal(
    unconfirmed_convergence.classification,
    ContradictionClassification.POSITIVE_COMPATIBILITY,
    "Une convergence dépendante ne doit pas devenir un consensus implicite.",
)
assert_true(
    "CONVERGENCE_WITHOUT_INDEPENDENT_GROUP" in unconfirmed_convergence.limits,
    "La limite de dépendance documentaire doit rester publique.",
)

# Une contradiction comparable non qualifiée reste bloquante et nommée GENUINE_CONTRADICTION.
genuine_relation = relation_for(
    relation_id="REL-M009-T006-GENUINE",
    relation_type=ClaimRelationType.CONTRADICTS,
    compatibility=comparable_scope(),
)
genuine_assessment = policy.classify(
    genuine_relation,
    classification_context=context_for(
        relation_id=genuine_relation.relation_id,
        reason_codes=("GENUINE_CONTRADICTION",),
    ),
)
assert_equal(
    genuine_assessment.classification,
    ContradictionClassification.GENUINE_CONTRADICTION,
    "Une contradiction comparable non qualifiée doit rester un conflit réel.",
)
assert_true(genuine_assessment.blocks_publication, "Un conflit réel non qualifié doit bloquer la publication.")


def assert_apparent(reason_code, expected_classification):
    relation_suffix = expected_classification.value.replace("_", "-")
    relation = relation_for(
        relation_id=f"REL-M009-T006-{relation_suffix}",
        relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
        compatibility=non_comparable_scope(reason_code),
    )
    assessment = policy.classify(
        relation,
        classification_context=context_for(
            relation_id=relation.relation_id,
            reason_codes=(expected_classification.value,),
        ),
    )
    assert_equal(
        assessment.classification,
        expected_classification,
        f"La raison {reason_code} doit produire {expected_classification.value}.",
    )
    assert_true(assessment.requires_public_explanation, "Une contradiction conditionnelle doit être expliquée.")
    assert_false(assessment.blocks_publication, "Une contradiction conditionnelle qualifiée ne doit pas bloquer toute publication.")


assert_apparent("SCOPE_APPARENT_CONTRADICTION", ContradictionClassification.APPARENT_CONTRADICTION)
assert_apparent("SCOPE_CONTEXT_DEPENDENT", ContradictionClassification.CONTEXT_DEPENDENT)
assert_apparent("SCOPE_HORIZON_MISMATCH", ContradictionClassification.DIFFERENT_HORIZON)
assert_apparent("SCOPE_UNIVERSE_MISMATCH", ContradictionClassification.DIFFERENT_UNIVERSE)
assert_apparent("SCOPE_METRIC_MISMATCH", ContradictionClassification.DIFFERENT_METRIC)
assert_apparent("SCOPE_COST_ASSUMPTION_MISMATCH", ContradictionClassification.DIFFERENT_COST_ASSUMPTION)
assert_apparent("SCOPE_MARKET_REGIME_MISMATCH", ContradictionClassification.DIFFERENT_REGIME)

# Les garde-fous refusent une relation sans portée, la similarité textuelle seule et une raison publique absente.
assert_raises(
    "scope_compatibility absente",
    lambda: policy.classify(
        SimpleNamespace(
            relation_id="REL-M009-T006-NO-SCOPE",
            relation_type="CONTRADICTS",
            source_claim_ref=claim_ref("SOURCE"),
            target_claim_ref=claim_ref("TARGET"),
            relation_basis="EXPLICIT_SCOPE_COMPARISON",
        ),
        classification_context=context_for(relation_id="REL-M009-T006-NO-SCOPE"),
    ),
)
assert_raises(
    "classification par similarite textuelle seule interdite",
    lambda: policy.classify(
        SimpleNamespace(
            relation_id="REL-M009-T006-TEXTUAL",
            relation_type="CONTRADICTS",
            source_claim_ref=claim_ref("SOURCE"),
            target_claim_ref=claim_ref("TARGET"),
            scope_compatibility=comparable_scope(),
            relation_basis="TEXTUAL_SIMILARITY_ONLY",
        ),
        classification_context=context_for(relation_id="REL-M009-T006-TEXTUAL"),
    ),
)
assert_raises(
    "public_reason vide",
    lambda: policy.classify(
        support_relation,
        classification_context=context_for(
            relation_id=support_relation.relation_id,
            public_reason="",
        ),
    ),
)

print("Tests unitaires T-006 classification de contradictions conditionnelles M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_contradiction_classification_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 classification de contradictions conditionnelles M-009: OK"
