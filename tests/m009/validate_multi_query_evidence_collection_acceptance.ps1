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
    DeepEvidenceSearchResult,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import (
    DeepResearchPlanningPolicy,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


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
        "strategy_parameter",
        "market_price_override",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key in forbidden_keys, f"Champ technique interdit dans {path}.{key}.")
            assert_no_forbidden_storage_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_storage_payload(child, f"{path}[{index}]")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t004-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T004-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=5,
        accepted_at="2026-07-02T10:00:00Z",
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
            "page_pdf": 1,
            "item_id": f"item-m009-t004-{suffix.lower()}",
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
            "evidence_id": f"EVS-M009-T004-{suffix}",
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


def verified_claim_ref(*, suffix, evidence):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": f"CLM-M009-T004-{suffix}",
            "claim_version": 1,
            "canonical_text": f"Claim vérifié M-009 T-004 {suffix}.",
            "scope": {"milestone": "M-009", "task": "T-004", "suffix": suffix},
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T004-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": [f"DEP-M009-T004-{suffix}"],
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=evidence.source_locator.document_id,
            canonical_version_id=evidence.source_locator.canonical_version_id,
            content_hash=evidence.source_locator.content_hash,
            item_id=evidence.source_locator.item_id,
        ),
    )


def candidate(*, suffix, document_suffix, obligations, text, trace_suffix, content_seed, span_seed):
    document_id = f"DOC-M009-T004-{document_suffix}"
    canonical_version_id = f"CVER-M009-T004-{document_suffix}"
    locator = source_locator(
        suffix=suffix,
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        content_hash=hash_for(content_seed),
    )
    evidence = evidence_ref(suffix=suffix, locator=locator, span_seed=span_seed)
    return CandidateEvidence(
        evidence_ref=evidence,
        source_text=text,
        search_trace_id=f"STRC-M009T004{trace_suffix:024d}",
        document_id=document_id,
        covered_obligations=obligations,
        evidence_polarity=("UNFAVORABLE" if "preuves_defavorables" in obligations else "FAVORABLE" if "preuves_favorables" in obligations else "NEUTRAL"),
        source_kind="PRIMARY",
    )


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
        self.requests = []

    def verified_claims_for_evidence(self, evidence_refs):
        self.requests.append(tuple(evidence_refs))
        return tuple(self.claims_by_evidence_id[evidence.evidence_id] for evidence in evidence_refs)


class FakeCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


def planned_deep_case_repository():
    payload = {
        "resolved_question": (
            "Comment comparer Kelly et volatility targeting pour une synthèse multi-sources "
            "qui conserve preuves favorables, preuves défavorables, dépendances, limites et lacunes ?"
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
        "idempotency_key": "COLLECT-DEEP-RESEARCH-M009-T004-ACCEPTANCE-0001",
        "occurred_at": "2026-07-02T10:05:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


# Given un plan approfondi contient plusieurs sous-questions et obligations de couverture.
repository, research_case_id = planned_deep_case_repository()
research_case = repository.case_for_id(research_case_id)
plan = research_case.research_plan
obligation_names = tuple(obligation.name for obligation in plan.coverage_obligations)

candidates_by_sub_question = {
    "RSQ-METHODES": candidate(
        suffix="METHODES",
        document_suffix="METHODES",
        obligations=("methodes", "dependances"),
        text="Kelly et volatility targeting reposent sur des méthodes distinctes et des dépendances explicites.",
        trace_suffix=1,
        content_seed=1,
        span_seed=5,
    ),
    "RSQ-PREUVES-FAVORABLES": candidate(
        suffix="FAVORABLES",
        document_suffix="FAVORABLES",
        obligations=("preuves_favorables",),
        text="Une preuve favorable documente la maîtrise de volatilité dans le périmètre autorisé.",
        trace_suffix=2,
        content_seed=2,
        span_seed=6,
    ),
    "RSQ-PREUVES-DEFAVORABLES": candidate(
        suffix="DEFAVORABLES",
        document_suffix="DEFAVORABLES",
        obligations=("preuves_defavorables",),
        text="Une preuve défavorable documente une condition où Kelly amplifie le risque.",
        trace_suffix=3,
        content_seed=3,
        span_seed=7,
    ),
    "RSQ-LIMITES-LACUNES": candidate(
        suffix="LIMITES",
        document_suffix="LIMITES",
        obligations=("limites", "zones_non_documentees"),
        text="Les limites et zones non documentées sont conservées comme lacunes explicites.",
        trace_suffix=4,
        content_seed=4,
        span_seed=8,
    ),
}
claims = tuple(
    verified_claim_ref(suffix=suffix, evidence=candidate.evidence_ref)
    for suffix, candidate in candidates_by_sub_question.items()
)
responses_by_sub_question_id = {
    sub_question_id: DeepEvidenceSearchResult(
        projection_version_ref=f"PROJ-M009-T004-{sub_question_id}-IDX-20260702",
        audit_trace_id=f"STRC-M009T004AUDIT{index:020d}",
        candidates=(candidates_by_sub_question[sub_question_id],),
    )
    for index, sub_question_id in enumerate(candidates_by_sub_question, start=1)
}
knowledge_search = FakeDeepKnowledgeSearch(responses_by_sub_question_id)
verified_claim_catalog = FakeVerifiedClaimCatalog(claims)
handler = CollectDeepResearchEvidenceHandler(
    research_case_repository=repository,
    knowledge_search=knowledge_search,
    verified_claim_catalog=verified_claim_catalog,
    citation_resolver=FakeCitationResolver(),
)

# When RA collecte les preuves candidates auprès de KA.
result = handler.collect(
    CollectDeepResearchEvidenceCommand(
        research_case_id=research_case_id,
        result_limit=2,
        occurred_at="2026-07-02T10:10:00Z",
    )
)

# Then chaque obligation satisfaite référence au moins une preuve traçable et aucun document ne domine l'EvidenceSet.
assert_equal(result.status, "DEEP_RESEARCH_EVIDENCE_COLLECTED", "Le statut de collecte approfondie doit être explicite.")
assert_equal(result.research_case.status, ResearchCaseStatus.EVIDENCE_ASSEMBLED, "Le cas doit porter un EvidenceSet assemblé.")
assert_equal(len(knowledge_search.requests), len(plan.sub_questions), "RA doit requêter KA par sous-question.")
assert_equal(
    tuple(request.sub_question_id for request in knowledge_search.requests),
    tuple(sub_question.sub_question_id for sub_question in plan.sub_questions),
    "L'ordre des requêtes KA doit suivre le plan approfondi.",
)
assert_equal(
    tuple(request.query_text for request in knowledge_search.requests),
    tuple(sub_question.text for sub_question in plan.sub_questions),
    "Chaque requête KA doit reprendre la sous-question autonome.",
)
assert_equal(
    tuple(request.coverage_obligations for request in knowledge_search.requests),
    tuple(sub_question.coverage_obligation_names for sub_question in plan.sub_questions),
    "Chaque requête KA doit porter les obligations de sa sous-question.",
)
assert_equal(
    tuple(request.result_limit for request in knowledge_search.requests),
    (2, 2, 2, 2),
    "Le result_limit doit être transmis explicitement à chaque requête KA.",
)
assert_equal(
    result.evidence_set.coverage_obligations,
    obligation_names,
    "L'EvidenceSet approfondi doit reprendre les obligations du plan.",
)
assert_equal(len(result.evidence_set.evidence_refs), 4, "Les quatre preuves diversifiées doivent être retenues.")
assert_equal(
    len({evidence.source_locator.document_id for evidence in result.evidence_set.evidence_refs}),
    4,
    "Aucun document ne doit dominer l'ensemble de preuves approfondi.",
)
covered_obligations = {
    obligation
    for evidence in candidates_by_sub_question.values()
    for obligation in evidence.covered_obligations
}
assert_true(set(obligation_names).issubset(covered_obligations), "Toutes les obligations doivent être couvertes.")
assert_equal(
    result.projection_version_refs,
    tuple(response.projection_version_ref for response in responses_by_sub_question_id.values()),
    "Les versions de projection consultées doivent être auditables.",
)
assert_equal(
    result.audit_trace_ids,
    tuple(response.audit_trace_id for response in responses_by_sub_question_id.values()),
    "Les traces d'audit KA doivent être conservées.",
)
assert_equal(
    tuple(event.event_type for event in result.events),
    ("DeepResearchEvidenceCollected",),
    "La collecte approfondie doit publier un événement métier dédié.",
)
assert_equal(
    verified_claim_catalog.requests[0],
    tuple(result.evidence_set.evidence_refs),
    "RA doit lire les claims vérifiés depuis les EvidenceRef retenues.",
)
assert_no_forbidden_storage_payload(result.evidence_set.to_payload())
assert_false(
    "qdrant" in repr(knowledge_search.requests).lower(),
    "RA ne doit pas exposer Qdrant dans la requête KA publiée.",
)

print("Test d'acceptation T-004 collecte multi-requêtes diversifiée M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_multi_query_evidence_collection_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 collecte multi-requêtes diversifiée M-009: OK"
