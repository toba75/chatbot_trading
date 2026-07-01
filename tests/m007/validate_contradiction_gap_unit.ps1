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
from app.research_answering.application.collect_evidence import (
    CandidateEvidence,
    CollectEvidenceCommand,
    CollectEvidenceHandler,
    SealEvidenceSetCommand,
)
from app.research_answering.application.classify_contradictions import (
    DeclareConflictingEvidence,
    DeclareInsufficientEvidence,
    RecordContradictionAssessment,
    RecordContradictionAssessmentHandler,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.contradiction_assessment import (
    ContradictionClassification,
    ContradictionClassificationPolicy,
    KnowledgeGapType,
    SupportStatus,
)
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
FIRST_CONTENT_HASH = "3" * 64
SECOND_CONTENT_HASH = "4" * 64
FIRST_SPAN_HASH = "5" * 64
SECOND_SPAN_HASH = "6" * 64
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


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T005-UNIT",
        document_id="DOC-M007-T005-UNIT",
        canonical_version_id="CVER-M007-T005-UNIT",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=4,
        accepted_at="2026-06-30T12:00:00Z",
        quality_policy_version="canonical-quality-m004-v1",
    )


def source_locator_policy():
    ref = canonical_source_ref()
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={
            ref.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                "item-m007-t005-unit-source": FIRST_CONTENT_HASH,
                "item-m007-t005-unit-target": SECOND_CONTENT_HASH,
            },
        },
    )


def source_locator(*, item_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T005-UNIT",
            "document_id": "DOC-M007-T005-UNIT",
            "page_pdf": 2,
            "item_id": item_id,
            "bbox": [0.2, 0.2, 0.7, 0.7],
            "content_hash": content_hash,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref_for(locator, *, evidence_id, quoted_span_hash):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": quoted_span_hash,
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def verified_claim_ref_for(evidence_ref, *, claim_id, canonical_text, horizon, metric="rendement"):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": claim_id,
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuilles convexes antifragiles",
                "horizon": horizon,
                "metric": metric,
                "frequency": "mensuelle",
            },
            "status": "VERIFIED",
            "verification_id": f"VER-{claim_id.removeprefix('CLM-')}",
            "evidence_refs": [evidence_ref.to_payload()],
            "dependency_group_ids": [f"DEP-{claim_id.removeprefix('CLM-')}"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(evidence_ref):
    return CandidateEvidence(
        evidence_ref=evidence_ref,
        source_text="Passage documentaire retenu pour classifier les contradictions.",
        search_trace_id=f"STRC-{evidence_ref.evidence_id.removeprefix('EVS-')}",
        document_id=evidence_ref.source_locator.document_id,
        covered_obligations=("preuves_documentaires",),
    )


class FakeKnowledgeSearch:
    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    def search(self, request):
        return self.candidates


class FakeVerifiedClaimCatalog:
    def __init__(self, claims):
        self.claims = tuple(claims)

    def verified_claims_for_evidence(self, evidence_refs):
        return self.claims


class OpeningCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


def planned_case_repository(*, idempotency_key):
    payload = {
        "resolved_question": "Comment qualifier les preuves contradictoires ?",
        "research_mandate": {
            "allowed_universe": ("documents canoniques OSTrading",),
            "horizon": "connaissances documentaires stables",
            "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
            "exclusions": ("données de marché actuelles non autorisées",),
            "language": "fr",
            "detail_level": "synthèse vérifiée",
        },
        "requested_mode": "DOCUMENTARY_SIMPLE",
        "requested_by_context": "CV",
        "idempotency_key": idempotency_key,
        "occurred_at": "2026-06-30T12:10:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def sealed_case_with_claims(*, idempotency_key):
    source_locator_ref = source_locator(
        item_id="item-m007-t005-unit-source",
        content_hash=FIRST_CONTENT_HASH,
    )
    target_locator_ref = source_locator(
        item_id="item-m007-t005-unit-target",
        content_hash=SECOND_CONTENT_HASH,
    )
    source_evidence = evidence_ref_for(
        source_locator_ref,
        evidence_id="EVS-M007-T005-UNIT-SOURCE",
        quoted_span_hash=FIRST_SPAN_HASH,
    )
    target_evidence = evidence_ref_for(
        target_locator_ref,
        evidence_id="EVS-M007-T005-UNIT-TARGET",
        quoted_span_hash=SECOND_SPAN_HASH,
    )
    source_claim = verified_claim_ref_for(
        source_evidence,
        claim_id="CLM-M007-T005-UNIT-SOURCE",
        canonical_text="La couverture de queue améliore le rendement pendant un mois de crise.",
        horizon="mois de crise",
    )
    target_claim = verified_claim_ref_for(
        target_evidence,
        claim_id="CLM-M007-T005-UNIT-TARGET",
        canonical_text="La couverture de queue détériore le rendement sur un cycle complet.",
        horizon="cycle complet 2008-2024",
    )
    repository, research_case_id = planned_case_repository(idempotency_key=idempotency_key)
    handler = CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch(
            candidates=(candidate_for(source_evidence), candidate_for(target_evidence))
        ),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims=(source_claim, target_claim)),
        citation_resolver=OpeningCitationResolver(),
    )
    collected = handler.collect(
        CollectEvidenceCommand(
            research_case_id=research_case_id,
            coverage_obligations=("preuves_documentaires",),
            result_limit=2,
            occurred_at="2026-06-30T12:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T12:16:00Z",
        )
    )
    return repository, sealed.research_case, source_claim, target_claim


def relation_for(*, relation_id, source_claim, target_claim, relation_type, compatibility):
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
        relation_basis="EXPLICIT_SCOPE_COMPARISON",
        policy_version="claim-relation-policy-m006-t007-v1",
        recorded_at="2026-06-30T12:17:00Z",
        cycle_justification=None,
    )


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


def handler_for(repository):
    return RecordContradictionAssessmentHandler(research_case_repository=repository)


def record_command(research_case_id, relations, *, qualified_relation_ids=()):
    return RecordContradictionAssessment(
        research_case_id=research_case_id,
        claim_relations=relations,
        qualified_relation_ids=qualified_relation_ids,
        classification_basis="EG_SCOPE_RELATION",
        occurred_at="2026-06-30T12:20:00Z",
    )


# La politique refuse les décisions par fréquence brute.
repository, research_case, source_claim, target_claim = sealed_case_with_claims(
    idempotency_key="M007-T005-UNIT-FREQUENCY"
)
direct_relation = relation_for(
    relation_id="REL-M007-T005-UNIT-FREQUENCY",
    source_claim=source_claim,
    target_claim=target_claim,
    relation_type=ClaimRelationType.CONTRADICTS,
    compatibility=comparable_scope(),
)
assert_raises(
    "consensus par frequence interdit",
    lambda: RecordContradictionAssessment(
        research_case_id=research_case.research_case_id,
        claim_relations=(direct_relation,),
        qualified_relation_ids=(),
        classification_basis="FREQUENCY_CONSENSUS",
        occurred_at="2026-06-30T12:20:00Z",
    ),
)

# Un conflit terminal ne peut pas référencer une contradiction non enregistrée.
assert_raises(
    "contradiction non enregistree",
    lambda: handler_for(repository).declare_conflicting(
        DeclareConflictingEvidence(
            research_case_id=research_case.research_case_id,
            contradiction_ids=("REL-M007-T005-UNIT-UNKNOWN",),
            reason_codes=("UNRESOLVED_DIRECT_CONFLICT",),
            decision_basis="RECORDED_CONTRADICTION_ASSESSMENT",
            occurred_at="2026-06-30T12:21:00Z",
        )
    ),
)

# Les horizons différents sont conservés comme différence d'horizon explicable.
policy = ContradictionClassificationPolicy(policy_version="contradiction-classification-m007-v1")
horizon_assessment = policy.classify(
    relation_for(
        relation_id="REL-M007-T005-UNIT-HORIZON",
        source_claim=source_claim,
        target_claim=target_claim,
        relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
        compatibility=non_comparable_scope("SCOPE_HORIZON_MISMATCH"),
    ),
    qualified_relation_ids=(),
)
assert_equal(
    horizon_assessment.classification,
    ContradictionClassification.DIFFERENT_HORIZON,
    "Une opposition d'horizon ne doit pas devenir un conflit absolu.",
)
assert_true(horizon_assessment.requires_public_explanation, "L'horizon différent doit être expliqué.")
assert_true(horizon_assessment.blocks_general_supported_status, "SUPPORTED général doit être bloqué.")

# Les métriques différentes sont classées séparément des horizons.
metric_assessment = policy.classify(
    relation_for(
        relation_id="REL-M007-T005-UNIT-METRIC",
        source_claim=source_claim,
        target_claim=target_claim,
        relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
        compatibility=non_comparable_scope("SCOPE_METRIC_MISMATCH"),
    ),
    qualified_relation_ids=(),
)
assert_equal(
    metric_assessment.classification,
    ContradictionClassification.DIFFERENT_METRIC,
    "Une métrique différente doit être visible.",
)

# Une contradiction directe explicitement qualifiée ne déclenche pas un conflit terminal.
repository, research_case, source_claim, target_claim = sealed_case_with_claims(
    idempotency_key="M007-T005-UNIT-QUALIFIED"
)
qualified_relation = relation_for(
    relation_id="REL-M007-T005-UNIT-QUALIFIED",
    source_claim=source_claim,
    target_claim=target_claim,
    relation_type=ClaimRelationType.CONTRADICTS,
    compatibility=comparable_scope(),
)
qualified_result = handler_for(repository).record(
    record_command(
        research_case.research_case_id,
        (qualified_relation,),
        qualified_relation_ids=(qualified_relation.relation_id,),
    )
)
assert_equal(
    qualified_result.assessments[0].classification,
    ContradictionClassification.RESOLVED_BY_QUALIFICATION,
    "Une qualification explicite doit résoudre la contradiction pour la synthèse.",
)
assert_false(
    qualified_result.assessments[0].blocks_publication,
    "Une contradiction qualifiée ne doit pas bloquer toute publication.",
)
assert_raises(
    "support_status SUPPORTED interdit",
    lambda: qualified_result.research_case.ensure_support_status_allowed(SupportStatus.SUPPORTED),
)
qualified_result.research_case.ensure_support_status_allowed(SupportStatus.PARTIALLY_SUPPORTED)

# Une lacune d'obligation produit KnowledgeGapRecorded puis INSUFFICIENT_EVIDENCE explicite.
repository, research_case, source_claim, target_claim = sealed_case_with_claims(
    idempotency_key="M007-T005-UNIT-INSUFFICIENT"
)
insufficient_result = handler_for(repository).declare_insufficient(
    DeclareInsufficientEvidence(
        research_case_id=research_case.research_case_id,
        missing_obligations=("mandat_documentaire",),
        reason_codes=("COVERAGE_OBLIGATION_MISSING",),
        decision_basis="COVERAGE_OBLIGATION_ASSESSMENT",
        occurred_at="2026-06-30T12:22:00Z",
    )
)
assert_equal(
    insufficient_result.status,
    "INSUFFICIENT_EVIDENCE",
    "Les preuves insuffisantes doivent exposer un statut terminal.",
)
assert_equal(
    insufficient_result.research_case.status,
    ResearchCaseStatus.INSUFFICIENT_EVIDENCE,
    "Le ResearchCase doit passer INSUFFICIENT_EVIDENCE.",
)
assert_equal(
    insufficient_result.knowledge_gaps[0].gap_type,
    KnowledgeGapType.COVERAGE_OBLIGATION_MISSING,
    "La lacune doit nommer l'obligation manquante.",
)
assert_equal(
    insufficient_result.events[0].event_type,
    "KnowledgeGapRecorded",
    "Une lacune doit publier KnowledgeGapRecorded.",
)
assert_equal(
    insufficient_result.events[1].event_type,
    "ResearchEvidenceFoundInsufficient",
    "Les preuves insuffisantes doivent publier ResearchEvidenceFoundInsufficient.",
)

# Une contradiction directe non qualifiée transitionne vers CONFLICTING_EVIDENCE.
repository, research_case, source_claim, target_claim = sealed_case_with_claims(
    idempotency_key="M007-T005-UNIT-CONFLICTING"
)
conflicting_relation = relation_for(
    relation_id="REL-M007-T005-UNIT-CONFLICTING",
    source_claim=source_claim,
    target_claim=target_claim,
    relation_type=ClaimRelationType.CONTRADICTS,
    compatibility=comparable_scope(),
)
recorded = handler_for(repository).record(
    record_command(research_case.research_case_id, (conflicting_relation,))
)
assert_equal(
    recorded.assessments[0].classification,
    ContradictionClassification.DIRECT_CONFLICT,
    "Une contradiction comparable non qualifiée reste bloquante.",
)
conflicting_result = handler_for(repository).declare_conflicting(
    DeclareConflictingEvidence(
        research_case_id=research_case.research_case_id,
        contradiction_ids=(conflicting_relation.relation_id,),
        reason_codes=("UNRESOLVED_DIRECT_CONFLICT",),
        decision_basis="RECORDED_CONTRADICTION_ASSESSMENT",
        occurred_at="2026-06-30T12:23:00Z",
    )
)
assert_equal(
    conflicting_result.status,
    "CONFLICTING_EVIDENCE",
    "Le conflit non résolu doit exposer le statut terminal.",
)
assert_equal(
    conflicting_result.research_case.status,
    ResearchCaseStatus.CONFLICTING_EVIDENCE,
    "Le ResearchCase doit passer CONFLICTING_EVIDENCE.",
)
assert_equal(
    conflicting_result.events[0].event_type,
    "ResearchEvidenceFoundConflicting",
    "Un conflit terminal doit publier ResearchEvidenceFoundConflicting.",
)

print("Tests unitaires T-005 contradictions et lacunes M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_contradiction_gap_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-005 contradictions et lacunes M-007: OK"
