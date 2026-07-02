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
from app.evidence_governance.domain.claim_relation import (
    ClaimRelation,
    ClaimRelationType,
    ClaimVersionRef,
    ScopeCompatibility,
    ScopeCompatibilityStatus,
)
from app.research_answering.adapters.in_memory_research_case_repository import (
    InMemoryResearchCaseRepository,
)
from app.research_answering.application.classify_contradictions import (
    RecordDeepContradictionAssessment,
    RecordDeepContradictionAssessmentHandler,
)
from app.research_answering.application.collect_evidence import CandidateEvidence
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.contradiction_assessment import (
    ContradictionClassification,
    DeepRelationClassificationContext,
)
from app.research_answering.domain.evidence_set import EvidenceSet
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import DeepResearchPlanningPolicy


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


def assert_no_frequency_consensus(value, path="payload"):
    forbidden_markers = {"raw_frequency_count", "raw_mention_count", "frequency_consensus"}
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key.lower() in forbidden_markers, f"Consensus par fréquence publié dans {path}.{key}.")
            assert_no_frequency_consensus(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_frequency_consensus(child, f"{path}[{index}]")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t006-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T006-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=6,
        accepted_at="2026-07-02T12:10:00Z",
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


def source_locator(*, suffix, content_seed):
    document_id = f"DOC-M009-T006-{suffix}"
    canonical_version_id = f"CVER-M009-T006-{suffix}"
    content_hash = hash_for(content_seed)
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id,
            "document_id": document_id,
            "page_pdf": 2,
            "item_id": f"item-m009-t006-{suffix.lower()}",
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
    locator = source_locator(suffix=suffix, content_seed=content_seed)
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T006-{suffix}",
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


def verified_claim_ref(*, suffix, evidence, canonical_text, scope, dependency_group_ids):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": f"CLM-M009-T006-{suffix}",
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": scope,
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T006-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": dependency_group_ids,
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=evidence.source_locator.document_id,
            canonical_version_id=evidence.source_locator.canonical_version_id,
            content_hash=evidence.source_locator.content_hash,
            item_id=evidence.source_locator.item_id,
        ),
    )


def candidate_for(evidence, *, suffix, text, obligations):
    return CandidateEvidence(
        evidence_ref=evidence,
        source_text=text,
        search_trace_id=f"STRC-M009T006{suffix:0>24}",
        document_id=evidence.source_locator.document_id,
        covered_obligations=obligations,
    )


def planned_deep_case_repository():
    payload = {
        "resolved_question": (
            "Comparer les limites des stratégies convexes sans effacer convergences "
            "ni contradictions conditionnelles."
        ),
        "research_mandate": {
            "allowed_universe": (
                "portefeuille convexe documenté",
                "Kelly fractionné",
                "volatility targeting",
            ),
            "horizon": "connaissances documentaires stables",
            "data_requirements": (
                "methodes",
                "preuves favorables",
                "preuves defavorables",
                "dépendances",
                "limites",
                "zones non documentees",
            ),
            "exclusions": (
                "données de marché actuelles",
                "paramètre de stratégie inventé",
            ),
            "language": "fr",
            "detail_level": "synthese approfondie multi-sources",
        },
        "requested_mode": "DEEP_RESEARCH",
        "requested_by_context": "CV",
        "idempotency_key": "CLASSIFY-DEEP-CONTRADICTIONS-M009-T006-0001",
        "occurred_at": "2026-07-02T12:15:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


class OpeningCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


def sealed_case_with_claims():
    support_a_evidence = evidence_ref(suffix="SUPPORT-A", content_seed=1, span_seed=4)
    support_b_evidence = evidence_ref(suffix="SUPPORT-B", content_seed=2, span_seed=5)
    short_evidence = evidence_ref(suffix="SHORT", content_seed=3, span_seed=6)
    long_evidence = evidence_ref(suffix="LONG", content_seed=4, span_seed=7)
    compatible_scope = {
        "universe": "portefeuille convexe documenté",
        "horizon": "cycle complet 2008-2024",
        "metric": "drawdown maximum",
        "frequency": "mensuelle",
    }
    support_a = verified_claim_ref(
        suffix="SUPPORT-A",
        evidence=support_a_evidence,
        canonical_text="La couverture de queue réduit le drawdown mensuel dans le portefeuille convexe documenté.",
        scope=compatible_scope,
        dependency_group_ids=("DEP-M009-T006-SUPPORT-A",),
    )
    support_b = verified_claim_ref(
        suffix="SUPPORT-B",
        evidence=support_b_evidence,
        canonical_text="La diversification convexe limite le drawdown mensuel sur le même univers documentaire.",
        scope=compatible_scope,
        dependency_group_ids=("DEP-M009-T006-SUPPORT-B",),
    )
    short_claim = verified_claim_ref(
        suffix="SHORT",
        evidence=short_evidence,
        canonical_text="Le levier Kelly améliore le rendement pendant un choc mensuel isolé.",
        scope={
            "universe": "portefeuille convexe documenté",
            "horizon": "mois de crise",
            "metric": "rendement net avant couts",
            "frequency": "mensuelle",
        },
        dependency_group_ids=("DEP-M009-T006-SHORT",),
    )
    long_claim = verified_claim_ref(
        suffix="LONG",
        evidence=long_evidence,
        canonical_text="Le levier Kelly dégrade le rendement net après coûts sur un cycle complet.",
        scope={
            "universe": "portefeuille convexe documenté",
            "horizon": "cycle complet 2008-2024",
            "metric": "rendement net apres couts",
            "frequency": "mensuelle",
        },
        dependency_group_ids=("DEP-M009-T006-LONG",),
    )
    repository, research_case_id = planned_deep_case_repository()
    research_case = repository.case_for_id(research_case_id)
    evidence_set = EvidenceSet.assemble(
        research_case_id=research_case_id,
        coverage_obligations=tuple(obligation.name for obligation in research_case.research_plan.coverage_obligations),
        candidates=(
            candidate_for(support_a_evidence, suffix="1", text="Preuve favorable sur la couverture de queue.", obligations=("methodes", "preuves_favorables")),
            candidate_for(support_b_evidence, suffix="2", text="Preuve favorable indépendante sur la diversification.", obligations=("preuves_favorables", "dependances")),
            candidate_for(short_evidence, suffix="3", text="Preuve défavorable limitée au choc mensuel.", obligations=("preuves_defavorables", "limites")),
            candidate_for(long_evidence, suffix="4", text="Preuve défavorable après coûts sur cycle complet.", obligations=("preuves_defavorables", "limites", "zones_non_documentees")),
        ),
        verified_claim_refs=(support_a, support_b, short_claim, long_claim),
        coverage_policy_version="deep-evidence-coverage-m009-v1",
        diversification_policy_version="deep-evidence-diversification-m009-v1",
    )
    assembled_case, _ = research_case.attach_evidence_set(
        evidence_set,
        occurred_at="2026-07-02T12:20:00Z",
    )
    sealed_case, _ = assembled_case.seal_evidence_set(
        evidence_set_id=evidence_set.evidence_set_id,
        citation_resolver=OpeningCitationResolver(),
        occurred_at="2026-07-02T12:21:00Z",
    )
    repository.update(sealed_case)
    return repository, sealed_case, support_a, support_b, short_claim, long_claim


def relation_for(*, relation_id, source_claim, target_claim, relation_type, compatibility, basis):
    return ClaimRelation(
        relation_id=relation_id,
        source_claim_ref=ClaimVersionRef(
            claim_id=source_claim.claim_id,
            claim_version=source_claim.claim_version,
        ),
        target_claim_ref=ClaimVersionRef(
            claim_id=target_claim.claim_id,
            claim_version=target_claim.claim_version,
        ),
        relation_type=relation_type,
        scope_compatibility=compatibility,
        relation_basis=basis,
        policy_version="claim-relation-policy-m009-t006-v1",
        recorded_at="2026-07-02T12:22:00Z",
        cycle_justification=None,
    )


# Given deux affirmations vérifiées se soutiennent sur une portée compatible
# et deux autres affirmations opposées portent sur des horizons et coûts distincts.
repository, research_case, support_a, support_b, short_claim, long_claim = sealed_case_with_claims()
support_relation = relation_for(
    relation_id="REL-M009-T006-ACCEPTANCE-SUPPORT",
    source_claim=support_a,
    target_claim=support_b,
    relation_type=ClaimRelationType.SUPPORTS,
    compatibility=ScopeCompatibility(
        status=ScopeCompatibilityStatus.COMPARABLE,
        compared_dimensions=SCOPE_DIMENSIONS,
        reason_code=None,
    ),
    basis="EXPLICIT_SUPPORT_EVIDENCE",
)
conditional_relation = relation_for(
    relation_id="REL-M009-T006-ACCEPTANCE-HORIZON-COST",
    source_claim=short_claim,
    target_claim=long_claim,
    relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
    compatibility=ScopeCompatibility(
        status=ScopeCompatibilityStatus.NON_COMPARABLE,
        compared_dimensions=SCOPE_DIMENSIONS,
        reason_code="SCOPE_HORIZON_MISMATCH",
    ),
    basis="EXPLICIT_SCOPE_COMPARISON",
)

# When l'analyse M-009 des contradictions approfondies est exécutée.
result = RecordDeepContradictionAssessmentHandler(
    research_case_repository=repository,
).record(
    RecordDeepContradictionAssessment(
        research_case_id=research_case.research_case_id,
        claim_relations=(support_relation, conditional_relation),
        relation_contexts=(
            DeepRelationClassificationContext(
                relation_id=support_relation.relation_id,
                conditions=("même univers", "même horizon", "même métrique"),
                limits=("ne vaut pas comme consensus par nombre de mentions",),
                public_reason="Deux claims vérifiés se soutiennent sur une portée compatible et indépendante.",
                reason_codes=("EXPLICIT_POSITIVE_RELATION",),
                independent_dependency_group_ids=(
                    "DEP-M009-T006-SUPPORT-A",
                    "DEP-M009-T006-SUPPORT-B",
                ),
            ),
            DeepRelationClassificationContext(
                relation_id=conditional_relation.relation_id,
                conditions=("mois de crise contre cycle complet", "rendement avant coûts contre rendement après coûts"),
                limits=("pas de contradiction générale hors horizons comparés", "coûts de transaction non homogènes"),
                public_reason=(
                    "L'opposition est limitée par un horizon différent et par une hypothèse de coût distincte."
                ),
                reason_codes=("DIFFERENT_HORIZON", "DIFFERENT_COST_ASSUMPTION"),
                independent_dependency_group_ids=(
                    "DEP-M009-T006-SHORT",
                    "DEP-M009-T006-LONG",
                ),
            ),
        ),
        classification_basis="EG_SCOPE_RELATION",
        occurred_at="2026-07-02T12:30:00Z",
    )
)

# Then la convergence et l'opposition conditionnelle sont conservées avec conditions, limites et raisons publiques.
assert_equal(
    result.status,
    "DEEP_CONTRADICTION_CLASSIFICATION_RECORDED",
    "Le statut d'analyse approfondie doit être observable.",
)
assert_equal(len(result.assessments), 2, "Les deux relations EG publiques doivent rester visibles.")
by_relation_id = {assessment.relation_id: assessment for assessment in result.assessments}
support_assessment = by_relation_id[support_relation.relation_id]
conditional_assessment = by_relation_id[conditional_relation.relation_id]

assert_equal(
    support_assessment.classification,
    ContradictionClassification.POSITIVE_COMPATIBILITY,
    "La convergence SUPPORTS compatible doit être conservée comme compatibilité positive.",
)
assert_equal(
    support_assessment.compared_dimensions,
    SCOPE_DIMENSIONS,
    "La compatibilité positive doit conserver les dimensions comparées.",
)
assert_true(
    "ne vaut pas comme consensus par nombre de mentions" in support_assessment.limits,
    "La limite anti-consensus doit rester publique.",
)
assert_false(support_assessment.blocks_publication, "Une compatibilité positive ne doit pas bloquer la publication.")

assert_equal(
    conditional_assessment.classification,
    ContradictionClassification.DIFFERENT_HORIZON,
    "L'opposition d'horizon ne doit pas devenir une contradiction générale.",
)
assert_equal(
    conditional_assessment.reason_codes,
    ("DIFFERENT_HORIZON", "DIFFERENT_COST_ASSUMPTION"),
    "Les raisons publiques doivent conserver l'horizon et l'hypothèse de coût.",
)
assert_true(
    "coûts de transaction non homogènes" in conditional_assessment.limits,
    "La limite de coût doit rester visible.",
)
assert_true(
    conditional_assessment.blocks_general_supported_status,
    "Une contradiction conditionnelle doit empêcher un SUPPORTED général abusif.",
)
assert_false(conditional_assessment.blocks_publication, "La contradiction conditionnelle qualifiée ne doit pas bloquer toute publication.")
assert_equal(
    result.research_case.status,
    ResearchCaseStatus.EVIDENCE_SET_SEALED,
    "L'analyse conditionnelle ne doit pas transformer la recherche en conflit terminal.",
)
assert_equal(
    tuple(event.event_type for event in result.events),
    ("ConditionalContradictionDetected", "ConditionalContradictionDetected"),
    "Chaque classification M-009 doit publier un événement public.",
)
for assessment in result.assessments:
    assert_true(assessment.public_reason, "Une raison publique est obligatoire.")
    assert_no_frequency_consensus(assessment.to_payload())

print("Test d'acceptation T-006 classification de contradictions conditionnelles M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_contradiction_classification_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 classification de contradictions conditionnelles M-009: OK"
