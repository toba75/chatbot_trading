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
    RecordContradictionAssessment,
    RecordContradictionAssessmentHandler,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.contradiction_assessment import (
    ContradictionClassification,
    SupportStatus,
)
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "a" * 64
ARTIFACT_HASH = "b" * 64
FIRST_CONTENT_HASH = "c" * 64
SECOND_CONTENT_HASH = "d" * 64
FIRST_SPAN_HASH = "e" * 64
SECOND_SPAN_HASH = "f" * 64


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
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
        canonical_source_id="CSRC-M007-T005-ACCEPTANCE",
        document_id="DOC-M007-T005-ACCEPTANCE",
        canonical_version_id="CVER-M007-T005-ACCEPTANCE",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=3,
        accepted_at="2026-06-30T11:00:00Z",
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
                "item-m007-t005-acceptance-short": FIRST_CONTENT_HASH,
                "item-m007-t005-acceptance-long": SECOND_CONTENT_HASH,
            },
        },
    )


def source_locator(*, item_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T005-ACCEPTANCE",
            "document_id": "DOC-M007-T005-ACCEPTANCE",
            "page_pdf": 1,
            "item_id": item_id,
            "bbox": [0.1, 0.2, 0.8, 0.9],
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


def verified_claim_ref_for(evidence_ref, *, claim_id, canonical_text, horizon):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": claim_id,
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuilles convexes antifragiles",
                "horizon": horizon,
                "metric": "rendement",
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
        source_text="Passage documentaire retenu pour comparer les horizons.",
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


def planned_case_repository():
    payload = {
        "resolved_question": "La couverture de queue améliore-t-elle le rendement ?",
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
        "idempotency_key": "CLASSIFY-CONTRADICTION-M007-T005-ACCEPTANCE",
        "occurred_at": "2026-06-30T11:10:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def sealed_case_with_claims():
    short_locator = source_locator(
        item_id="item-m007-t005-acceptance-short",
        content_hash=FIRST_CONTENT_HASH,
    )
    long_locator = source_locator(
        item_id="item-m007-t005-acceptance-long",
        content_hash=SECOND_CONTENT_HASH,
    )
    short_evidence = evidence_ref_for(
        short_locator,
        evidence_id="EVS-M007-T005-ACCEPTANCE-SHORT",
        quoted_span_hash=FIRST_SPAN_HASH,
    )
    long_evidence = evidence_ref_for(
        long_locator,
        evidence_id="EVS-M007-T005-ACCEPTANCE-LONG",
        quoted_span_hash=SECOND_SPAN_HASH,
    )
    short_claim = verified_claim_ref_for(
        short_evidence,
        claim_id="CLM-M007-T005-ACCEPTANCE-SHORT",
        canonical_text="La couverture de queue améliore le rendement pendant un mois de crise.",
        horizon="mois de crise",
    )
    long_claim = verified_claim_ref_for(
        long_evidence,
        claim_id="CLM-M007-T005-ACCEPTANCE-LONG",
        canonical_text="La couverture de queue détériore le rendement sur un cycle complet.",
        horizon="cycle complet 2008-2024",
    )
    repository, research_case_id = planned_case_repository()
    handler = CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch(
            candidates=(candidate_for(short_evidence), candidate_for(long_evidence))
        ),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims=(short_claim, long_claim)),
        citation_resolver=OpeningCitationResolver(),
    )
    collected = handler.collect(
        CollectEvidenceCommand(
            research_case_id=research_case_id,
            coverage_obligations=("preuves_documentaires",),
            occurred_at="2026-06-30T11:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T11:16:00Z",
        )
    )
    return repository, sealed.research_case, short_claim, long_claim


def apparent_contradiction_between(short_claim, long_claim):
    return ClaimRelation(
        relation_id="REL-M007-T005-ACCEPTANCE-HORIZON",
        source_claim_ref=ClaimVersionRef(
            claim_id=short_claim.claim_id,
            claim_version=short_claim.claim_version,
        ),
        target_claim_ref=ClaimVersionRef(
            claim_id=long_claim.claim_id,
            claim_version=long_claim.claim_version,
        ),
        relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
        scope_compatibility=ScopeCompatibility(
            status=ScopeCompatibilityStatus.NON_COMPARABLE,
            compared_dimensions=("universe", "horizon", "metric", "frequency"),
            reason_code="SCOPE_HORIZON_MISMATCH",
        ),
        relation_basis="EXPLICIT_SCOPE_COMPARISON",
        policy_version="claim-relation-policy-m006-t007-v1",
        recorded_at="2026-06-30T11:17:00Z",
        cycle_justification=None,
    )


# Given deux claims opposés portent sur des horizons différents dans un EvidenceSet scellé.
repository, research_case, short_claim, long_claim = sealed_case_with_claims()
relation = apparent_contradiction_between(short_claim, long_claim)

# When RA analyse les contradictions du jeu de preuves scellé.
result = RecordContradictionAssessmentHandler(
    research_case_repository=repository,
).record(
    RecordContradictionAssessment(
        research_case_id=research_case.research_case_id,
        claim_relations=(relation,),
        qualified_relation_ids=(),
        classification_basis="EG_SCOPE_RELATION",
        occurred_at="2026-06-30T11:20:00Z",
    )
)

# Then la relation est classée DIFFERENT_HORIZON et la future réponse doit l'expliquer.
assert_equal(result.status, "CONTRADICTION_ASSESSMENT_RECORDED", "Le diagnostic doit exposer un statut observable.")
assert_equal(len(result.assessments), 1, "La contradiction pertinente doit être conservée.")
assessment = result.assessments[0]
assert_equal(
    assessment.classification,
    ContradictionClassification.DIFFERENT_HORIZON,
    "Deux horizons différents ne doivent pas devenir une contradiction générale.",
)
assert_true(
    assessment.requires_public_explanation,
    "La réponse future doit expliquer la différence d'horizon.",
)
assert_true(
    assessment.blocks_general_supported_status,
    "Un statut SUPPORTED général doit être interdit par simplification.",
)
assert_equal(
    result.events[0].event_type,
    "ContradictionDetected",
    "L'enregistrement doit publier ContradictionDetected.",
)
assert_equal(
    result.research_case.status,
    ResearchCaseStatus.EVIDENCE_SET_SEALED,
    "Une différence d'horizon qualifiée ne doit pas devenir un conflit terminal.",
)
assert_raises(
    "support_status SUPPORTED interdit",
    lambda: result.research_case.ensure_support_status_allowed(SupportStatus.SUPPORTED),
)

print("Test d'acceptation T-005 contradictions et lacunes M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_contradiction_gap_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 contradictions et lacunes M-007: OK"
