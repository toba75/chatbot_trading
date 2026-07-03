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
from app.research_answering.adapters.in_memory_answer_repository import (
    InMemoryAnswerRepository,
)
from app.research_answering.adapters.in_memory_research_case_repository import (
    InMemoryResearchCaseRepository,
)
from app.research_answering.adapters.local_answer_assertion_extractor import (
    LocalDeterministicAnswerAssertionExtractor,
)
from app.research_answering.application.collect_evidence import (
    CandidateEvidence,
    CollectEvidenceCommand,
    CollectEvidenceHandler,
    SealEvidenceSetCommand,
)
from app.research_answering.application.draft_answer import (
    DraftAnswer,
    DraftAnswerHandler,
    ExtractAnswerAssertions,
    ExtractAnswerAssertionsHandler,
    GeneratedAnswerDraft,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.application.verify_answer import (
    EvaluateAnswerSupport,
    EvaluateAnswerSupportHandler,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)
from app.research_answering.domain.research_case import ResearchCaseStatus


SOURCE_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
CONTENT_HASH = "3" * 64
SPAN_HASH = "4" * 64
STABLE_CLAIM_ID = "CLM-M007-T008-ACCEPTANCE-STABLE"
CANONICAL_VERSION_ID = "CVER-M007-T008-ACCEPTANCE"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_not_contains(text, forbidden_fragment, message):
    if forbidden_fragment in text:
        raise AssertionError(f"{message} Fragment interdit: {forbidden_fragment!r}")


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T008-ACCEPTANCE",
        document_id="DOC-M007-T008-ACCEPTANCE",
        canonical_version_id=CANONICAL_VERSION_ID,
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=2,
        accepted_at="2026-06-30T17:00:00Z",
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
            ref.canonical_version_id: {"item-m007-t008-acceptance": CONTENT_HASH},
        },
    )


def source_locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": CANONICAL_VERSION_ID,
            "document_id": "DOC-M007-T008-ACCEPTANCE",
            "page_pdf": 1,
            "item_id": "item-m007-t008-acceptance",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": CONTENT_HASH,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref(locator):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M007-T008-ACCEPTANCE-0001",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": SPAN_HASH,
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def verified_claim_ref(ref):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": STABLE_CLAIM_ID,
            "claim_version": 1,
            "canonical_text": "Une réponse de marché récente exige une source actuelle autorisée.",
            "scope": {
                "universe": "règles RA de réponse documentaire",
                "horizon": "cycle documentaire stable",
                "metric": "garde-fou",
                "frequency": "événementielle",
            },
            "status": "VERIFIED",
            "verification_id": "VER-M007-T008-ACCEPTANCE-0001",
            "evidence_refs": [ref.to_payload()],
            "dependency_group_ids": ["DEP-M007-T008-ACCEPTANCE-0001"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(ref):
    return CandidateEvidence(
        evidence_ref=ref,
        source_text="Passage documentaire: aucun prix récent ne doit être inventé sans source actuelle autorisée.",
        search_trace_id="STRC-M007-T008-ACCEPTANCE-0001",
        document_id=ref.source_locator.document_id,
        covered_obligations=("preuves_documentaires",),
        evidence_polarity="NEUTRAL",
        source_kind="PRIMARY",
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


class InventedMarketPriceAnswerGenerator:
    def draft(self, request):
        return GeneratedAnswerDraft(
            content="[design:CURRENT_MARKET_PRICE] NVDA cote 140 USD aujourd'hui.",
            model_provenance="fake-answer-generator-m007-t008-v1",
        )


def sealed_current_data_case():
    payload = {
        "resolved_question": "Quel est le prix actuel de NVDA ?",
        "research_mandate": {
            "allowed_universe": ("documents canoniques OSTrading",),
            "horizon": "prix de marché récent",
            "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
            "exclusions": (
                "données de marché actuelles non autorisées",
                "accès externe interdit",
            ),
            "language": "fr",
            "detail_level": "abstention vérifiée",
        },
        "requested_mode": "DOCUMENTARY_SIMPLE",
        "requested_by_context": "CV",
        "idempotency_key": "CURRENT-DATA-ABSTENTION-M007-T008-ACCEPTANCE",
        "occurred_at": "2026-06-30T17:10:00Z",
    }
    locator = source_locator()
    ref = evidence_ref(locator)
    claim = verified_claim_ref(ref)
    repository = InMemoryResearchCaseRepository.empty()
    opened = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    handler = CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch(candidates=(candidate_for(ref),)),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims=(claim,)),
        citation_resolver=OpeningCitationResolver(),
    )
    collected = handler.collect(
        CollectEvidenceCommand(
            research_case_id=opened.research_case_id,
            coverage_obligations=("preuves_documentaires",),
            result_limit=2,
            occurred_at="2026-06-30T17:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=opened.research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T17:16:00Z",
        )
    )
    return repository, sealed.research_case


# Given une question nécessite des prix de marché récents.
research_case_repository, research_case = sealed_current_data_case()
answer_repository = InMemoryAnswerRepository.empty()
drafted = DraftAnswerHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    answer_generator=InventedMarketPriceAnswerGenerator(),
).draft(
    DraftAnswer(
        research_case_id=research_case.research_case_id,
        evidence_set_id=research_case.evidence_set.evidence_set_id,
        occurred_at="2026-06-30T17:20:00Z",
    )
)
extracted = ExtractAnswerAssertionsHandler(
    answer_repository=answer_repository,
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
).extract(
    ExtractAnswerAssertions(
        answer_id=drafted.answer.answer_id,
        occurred_at="2026-06-30T17:21:00Z",
    )
)

# When aucun accès autorisé à des données actuelles n'est présent dans le mandat.
evaluated = EvaluateAnswerSupportHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    citation_resolver=OpeningCitationResolver(),
).evaluate(
    EvaluateAnswerSupport(
        research_case_id=research_case.research_case_id,
        answer_id=extracted.answer.answer_id,
        support_policy_version="answer-support-m007-v1",
        citation_policy_version="citation-integrity-m007-v1",
        freshness_policy_version="answer-freshness-m007-v1",
        occurred_at="2026-06-30T17:22:00Z",
    )
)

# Then RA retourne REQUIRES_CURRENT_DATA, enregistre la lacune et n'invente aucune valeur de marché.
assert_equal(
    evaluated.support_status,
    SupportStatus.REQUIRES_CURRENT_DATA,
    "Le statut documentaire doit signaler la donnée actuelle requise.",
)
assert_equal(
    evaluated.answer.status.value,
    "ABSTAINED",
    "L'agrégat Answer doit publier une abstention explicite.",
)
assert_equal(
    evaluated.verified_research_outcome.support_status,
    "REQUIRES_CURRENT_DATA",
    "Le contrat RA doit exposer REQUIRES_CURRENT_DATA.",
)
assert_equal(
    tuple(str(claim_ref) for claim_ref in evaluated.verified_research_outcome.claim_refs),
    ("CLM-M007-T008-ACCEPTANCE-STABLE@1",),
    "Une abstention doit conserver la provenance documentaire scellée.",
)
assert_not_contains(
    evaluated.verified_answer_version.answer_text,
    "USD",
    "Une abstention pour donnée actuelle absente ne doit publier aucune valeur de marché.",
)
assert_equal(
    len(evaluated.verified_research_outcome.knowledge_gaps),
    1,
    "La lacune de donnée actuelle doit être visible.",
)
gap_topic = evaluated.verified_research_outcome.knowledge_gaps[0].topic
assert_true(
    "actuelles" in gap_topic and "autoris" in gap_topic,
    "La lacune doit nommer l'autorisation de donnée actuelle.",
)
assert_true(
    "CURRENT_DATA_REQUIRED" in evaluated.verified_answer_version.answer_text,
    "L'abstention doit exposer l'erreur publique CURRENT_DATA_REQUIRED.",
)
assert_not_contains(
    evaluated.verified_answer_version.answer_text,
    "140",
    "La valeur de marché inventée par le brouillon ne doit pas être publiée.",
)
assert_not_contains(
    evaluated.verified_answer_version.answer_text,
    "USD",
    "La devise inventée par le brouillon ne doit pas être publiée.",
)
assert_equal(
    tuple(event.event_type for event in evaluated.events),
    ("AnswerSupportEvaluated", "AnswerAbstained"),
    "L'évaluation doit publier l'abstention RA explicite.",
)
recorded_case = research_case_repository.case_for_id(research_case.research_case_id)
assert_equal(
    recorded_case.status,
    ResearchCaseStatus.COMPLETED,
    "Le ResearchCase abstinent doit devenir terminal après publication.",
)
assert_equal(
    len(recorded_case.knowledge_gaps),
    1,
    "Le ResearchCase doit conserver la lacune associée.",
)
assert_equal(
    recorded_case.knowledge_gaps[0].reason_code,
    "CURRENT_DATA_REQUIRED",
    "La lacune doit porter l'erreur publique.",
)

print("Test d'acceptation T-008 abstention données actuelles M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_current_data_abstention_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 abstention données actuelles M-007: OK"
