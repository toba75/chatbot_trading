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
from app.research_answering.adapters.in_memory_research_case_repository import (
    InMemoryResearchCaseRepository,
)
from app.research_answering.application.collect_evidence import (
    CandidateEvidence,
    CollectDeepResearchEvidenceCommand,
    CollectDeepResearchEvidenceHandler,
    DeepEvidenceSearchRequest,
    DeepEvidenceSearchResult,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.research_planning import (
    DeepResearchPlanningPolicy,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash):
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T004-UNIT-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=5,
        accepted_at="2026-07-02T10:30:00Z",
        quality_policy_version="canonical-quality-m004-v1",
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={canonical_source.canonical_version_id: canonical_source},
        version_statuses_by_version_id={
            canonical_source.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            canonical_source.canonical_version_id: {f"item-m009-t004-unit-{suffix.lower()}": content_hash},
        },
    )


def source_locator(*, suffix, document_id, canonical_version_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id,
            "document_id": document_id,
            "page_pdf": 1,
            "item_id": f"item-m009-t004-unit-{suffix.lower()}",
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


def evidence_ref(*, suffix, locator, span_seed):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T004-UNIT-{suffix}",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": hash_for(span_seed),
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=locator.document_id,
            canonical_version_id=locator.canonical_version_id,
            content_hash=locator.content_hash,
        ),
    )


def verified_claim_ref(*, suffix, evidence):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": f"CLM-M009-T004-UNIT-{suffix}",
            "claim_version": 1,
            "canonical_text": f"Claim unitaire M-009 T-004 {suffix}.",
            "scope": {"milestone": "M-009", "task": "T-004", "suffix": suffix},
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T004-UNIT-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": [f"DEP-M009-T004-UNIT-{suffix}"],
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=evidence.source_locator.document_id,
            canonical_version_id=evidence.source_locator.canonical_version_id,
            content_hash=evidence.source_locator.content_hash,
        ),
    )


def candidate(*, suffix, document_suffix, obligations, content_seed, span_seed):
    document_id = f"DOC-M009-T004-UNIT-{document_suffix}"
    canonical_version_id = f"CVER-M009-T004-UNIT-{document_suffix}"
    locator = source_locator(
        suffix=suffix,
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        content_hash=hash_for(content_seed),
    )
    evidence = evidence_ref(suffix=suffix, locator=locator, span_seed=span_seed)
    return CandidateEvidence(
        evidence_ref=evidence,
        source_text=f"Preuve unitaire M-009 T-004 {suffix}.",
        search_trace_id=f"STRC-M009T004UNIT{content_seed:020d}",
        document_id=document_id,
        covered_obligations=obligations,
    )


class EvidenceRefWithoutLocator:
    evidence_id = "EVS-M009-T004-UNIT-NO-LOCATOR"
    source_locator = None


class CandidateWithoutLocator:
    evidence_ref = EvidenceRefWithoutLocator()
    document_id = "DOC-M009-T004-UNIT-NO-LOCATOR"
    covered_obligations = ("methodes",)


class FakeDeepKnowledgeSearch:
    def __init__(self, responses_by_sub_question_id):
        self.responses_by_sub_question_id = dict(responses_by_sub_question_id)
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return self.responses_by_sub_question_id[request.sub_question_id]


class FakeVerifiedClaimCatalog:
    def __init__(self, claim_refs):
        self.claims_by_evidence_id = {
            claim.evidence_refs[0].evidence_id: claim
            for claim in claim_refs
        }

    def verified_claims_for_evidence(self, evidence_refs):
        return tuple(self.claims_by_evidence_id[evidence.evidence_id] for evidence in evidence_refs)


class FakeCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


def planned_deep_case_repository():
    payload = {
        "resolved_question": (
            "Comment comparer Kelly et volatility targeting sans confondre répétition documentaire "
            "et indépendance des preuves ?"
        ),
        "research_mandate": {
            "allowed_universe": (
                "Kelly",
                "volatility targeting",
                "portefeuille convexe documenté",
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
                "extension hors mandat utilisateur",
            ),
            "language": "fr",
            "detail_level": "synthese approfondie multi-sources",
        },
        "requested_mode": "DEEP_RESEARCH",
        "requested_by_context": "CV",
        "idempotency_key": "COLLECT-DEEP-RESEARCH-M009-T004-UNIT-0001",
        "occurred_at": "2026-07-02T10:35:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def deep_result(*, projection_suffix, candidates):
    return DeepEvidenceSearchResult(
        projection_version_ref=f"PROJ-M009-T004-UNIT-{projection_suffix}-IDX-20260702",
        audit_trace_id=f"STRC-M009T004UNITAUDIT{len(projection_suffix):016d}",
        candidates=tuple(candidates),
    )


def collect_with_candidates(candidates_by_sub_question, *, result_limit=2):
    repository, research_case_id = planned_deep_case_repository()
    responses = {
        sub_question_id: deep_result(projection_suffix=sub_question_id, candidates=candidates)
        for sub_question_id, candidates in candidates_by_sub_question.items()
    }
    all_candidates = tuple(
        candidate
        for candidates in candidates_by_sub_question.values()
        for candidate in candidates
        if isinstance(candidate, CandidateEvidence)
    )
    claims = tuple(
        verified_claim_ref(suffix=candidate.evidence_ref.evidence_id.removeprefix("EVS-"), evidence=candidate.evidence_ref)
        for candidate in all_candidates
    )
    handler = CollectDeepResearchEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeDeepKnowledgeSearch(responses),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims),
        citation_resolver=FakeCitationResolver(),
    )
    return handler.collect(
        CollectDeepResearchEvidenceCommand(
            research_case_id=research_case_id,
            result_limit=result_limit,
            occurred_at="2026-07-02T10:40:00Z",
        )
    )


methodes = candidate(
    suffix="METHODES",
    document_suffix="METHODES",
    obligations=("methodes", "dependances"),
    content_seed=1,
    span_seed=5,
)
favorables = candidate(
    suffix="FAVORABLES",
    document_suffix="FAVORABLES",
    obligations=("preuves_favorables",),
    content_seed=2,
    span_seed=6,
)
defavorables = candidate(
    suffix="DEFAVORABLES",
    document_suffix="DEFAVORABLES",
    obligations=("preuves_defavorables",),
    content_seed=3,
    span_seed=7,
)
limites = candidate(
    suffix="LIMITES",
    document_suffix="LIMITES",
    obligations=("limites", "zones_non_documentees"),
    content_seed=4,
    span_seed=8,
)

valid_candidates_by_sub_question = {
    "RSQ-METHODES": (methodes,),
    "RSQ-PREUVES-FAVORABLES": (favorables,),
    "RSQ-PREUVES-DEFAVORABLES": (defavorables,),
    "RSQ-LIMITES-LACUNES": (limites,),
}

# Requête sans sous-question refusée avant appel KA.
assert_raises(
    "sub_question_id",
    lambda: DeepEvidenceSearchRequest(
        research_case_id="RSC-M009-T004-UNIT",
        sub_question_id="",
        query_text="Quelle preuve couvre la méthode ?",
        coverage_obligations=("methodes",),
        result_limit=2,
        requested_by_context="RA",
        occurred_at="2026-07-02T10:41:00Z",
    ),
)

# Projection absente ou trace d'audit absente refusée.
assert_raises(
    "projection_version_ref",
    lambda: DeepEvidenceSearchResult(
        projection_version_ref="",
        audit_trace_id="STRC-M009T004UNITAUDIT000000000001",
        candidates=(methodes,),
    ),
)
assert_raises(
    "audit_trace_id",
    lambda: DeepEvidenceSearchResult(
        projection_version_ref="PROJ-M009-T004-UNIT-IDX-20260702",
        audit_trace_id="",
        candidates=(methodes,),
    ),
)

# SourceLocator obligatoire.
assert_raises(
    "source_locator absent",
    lambda: collect_with_candidates({"RSQ-METHODES": (CandidateWithoutLocator(),)}),
)

# Le result_limit doit être respecté par chaque réponse KA.
assert_raises(
    "result_limit",
    lambda: collect_with_candidates(
        {"RSQ-METHODES": (methodes, favorables)},
        result_limit=1,
    ),
)

# Les doublons de preuve et de localisateur sont refusés.
assert_raises(
    "evidence_ref duplique",
    lambda: collect_with_candidates({"RSQ-METHODES": (methodes, methodes)}),
)

same_locator_other_evidence = CandidateEvidence(
    evidence_ref=EvidenceRef(
        schema_version=methodes.evidence_ref.schema_version,
        evidence_id="EVS-M009-T004-UNIT-SAME-LOCATOR",
        source_locator=methodes.evidence_ref.source_locator,
        relation=methodes.evidence_ref.relation,
        quoted_span_hash=hash_for(9),
    ),
    source_text="Autre preuve pointant vers le même localisateur.",
    search_trace_id="STRC-M009T004UNIT000000000009",
    document_id=methodes.document_id,
    covered_obligations=("dependances",),
)
assert_raises(
    "source_locator duplique",
    lambda: collect_with_candidates({"RSQ-METHODES": (methodes, same_locator_other_evidence)}),
)

# Un document ne peut pas dominer le pool approfondi.
same_document_other_locator = candidate(
    suffix="METHODES-AUTRE-PAGE",
    document_suffix="METHODES",
    obligations=("dependances",),
    content_seed=9,
    span_seed=10,
)
assert_raises(
    "document dominant",
    lambda: collect_with_candidates({"RSQ-METHODES": (methodes, same_document_other_locator)}),
)

# Une obligation planifiée non couverte est déclarée explicitement.
assert_raises(
    "coverage_obligation non couverte",
    lambda: collect_with_candidates(
        {
            "RSQ-METHODES": (methodes,),
            "RSQ-PREUVES-FAVORABLES": (favorables,),
            "RSQ-PREUVES-DEFAVORABLES": (defavorables,),
        }
    ),
)

# L'ordre d'assemblage suit le plan même si les fixtures de réponses sont enregistrées dans un ordre permuté.
permuted_candidates = {
    "RSQ-LIMITES-LACUNES": (limites,),
    "RSQ-PREUVES-DEFAVORABLES": (defavorables,),
    "RSQ-PREUVES-FAVORABLES": (favorables,),
    "RSQ-METHODES": (methodes,),
}
result = collect_with_candidates(permuted_candidates)
assert_equal(
    tuple(evidence.evidence_id for evidence in result.evidence_set.evidence_refs),
    (
        methodes.evidence_ref.evidence_id,
        favorables.evidence_ref.evidence_id,
        defavorables.evidence_ref.evidence_id,
        limites.evidence_ref.evidence_id,
    ),
    "L'ordre des preuves doit rester celui des sous-questions du plan.",
)

print("Tests unitaires T-004 collecte multi-requêtes diversifiée M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_multi_query_evidence_collection_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 collecte multi-requêtes diversifiée M-009: OK"
