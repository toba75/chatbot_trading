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
from app.research_answering.domain.answer import (
    AnswerStatus,
    AssertionPublicationStatus,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
CONTENT_HASH = "3" * 64
SPAN_HASH = "4" * 64
SUPPORTED_CLAIM_ID = "CLM-M007-T007-ACCEPTANCE-SUPPORTED"
UNSUPPORTED_CLAIM_ID = "CLM-M007-T007-ACCEPTANCE-UNSUPPORTED"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_not_equal(actual, forbidden, message):
    if actual == forbidden:
        raise AssertionError(f"{message} Valeur interdite: {actual!r}")


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T007-ACCEPTANCE",
        document_id="DOC-M007-T007-ACCEPTANCE",
        canonical_version_id="CVER-M007-T007-ACCEPTANCE",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=2,
        accepted_at="2026-06-30T15:00:00Z",
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
            ref.canonical_version_id: {"item-m007-t007-acceptance-supported": CONTENT_HASH},
        },
    )


def source_locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T007-ACCEPTANCE",
            "document_id": "DOC-M007-T007-ACCEPTANCE",
            "page_pdf": 1,
            "item_id": "item-m007-t007-acceptance-supported",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": CONTENT_HASH,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref(locator):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M007-T007-ACCEPTANCE-0001",
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
            "claim_id": SUPPORTED_CLAIM_ID,
            "claim_version": 1,
            "canonical_text": "La couverture de queue réduit le drawdown maximal.",
            "scope": {
                "universe": "portefeuilles convexes antifragiles",
                "horizon": "cycle documentaire stable",
                "metric": "risque",
                "frequency": "mensuelle",
            },
            "status": "VERIFIED",
            "verification_id": "VER-M007-T007-ACCEPTANCE-0001",
            "evidence_refs": [ref.to_payload()],
            "dependency_group_ids": ["DEP-M007-T007-ACCEPTANCE-0001"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(ref):
    return CandidateEvidence(
        evidence_ref=ref,
        source_text="Passage documentaire retenu pour vérifier une assertion.",
        search_trace_id="STRC-M007-T007-ACCEPTANCE-0001",
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


class PartiallyUnsupportedAnswerGenerator:
    def draft(self, request):
        return GeneratedAnswerDraft(
            content=(
                f"[source:{SUPPORTED_CLAIM_ID}] La couverture de queue réduit le drawdown maximal.\n"
                f"[source:{UNSUPPORTED_CLAIM_ID}] Le portefeuille bat systématiquement le marché."
            ),
            model_provenance="fake-answer-generator-m007-t007-v1",
        )


def sealed_case_with_claim():
    payload = {
        "resolved_question": "Quelle réponse documentaire publier ?",
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
        "idempotency_key": "ANSWER-SUPPORT-M007-T007-ACCEPTANCE",
        "occurred_at": "2026-06-30T15:10:00Z",
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
            occurred_at="2026-06-30T15:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=opened.research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T15:16:00Z",
        )
    )
    return repository, sealed.research_case


# Given un brouillon contient une assertion factuelle importante sans preuve admissible.
research_case_repository, research_case = sealed_case_with_claim()
answer_repository = InMemoryAnswerRepository.empty()
drafted = DraftAnswerHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    answer_generator=PartiallyUnsupportedAnswerGenerator(),
).draft(
    DraftAnswer(
        research_case_id=research_case.research_case_id,
        evidence_set_id=research_case.evidence_set.evidence_set_id,
        occurred_at="2026-06-30T15:20:00Z",
    )
)
extracted = ExtractAnswerAssertionsHandler(
    answer_repository=answer_repository,
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
).extract(
    ExtractAnswerAssertions(
        answer_id=drafted.answer.answer_id,
        occurred_at="2026-06-30T15:21:00Z",
    )
)

# When RA évalue le support de la réponse.
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
        occurred_at="2026-06-30T15:22:00Z",
    )
)

# Then l'assertion est qualifiée ou retirée, et la réponse ne reçoit pas SUPPORTED tant que le défaut subsiste.
assert_not_equal(
    evaluated.support_status,
    SupportStatus.SUPPORTED,
    "Une assertion importante non supportée ne doit pas produire SUPPORTED.",
)
assert_equal(
    evaluated.support_status,
    SupportStatus.PARTIALLY_SUPPORTED,
    "La réponse doit être publiée avec qualification explicite.",
)
assert_equal(
    evaluated.answer.status,
    AnswerStatus.PARTIALLY_SUPPORTED,
    "L'agrégat Answer doit porter le statut publié qualifié.",
)
assert_equal(
    evaluated.verified_answer_version.support_status,
    SupportStatus.PARTIALLY_SUPPORTED,
    "La version publiée doit porter le même statut documentaire.",
)
unsupported_decisions = tuple(
    decision
    for decision in evaluated.verified_answer_version.assertion_decisions
    if UNSUPPORTED_CLAIM_ID in decision.basis_refs
)
assert_equal(
    len(unsupported_decisions),
    1,
    "L'assertion non supportée doit rester tracée dans les décisions de publication.",
)
assert_true(
    unsupported_decisions[0].publication_status
    in {AssertionPublicationStatus.QUALIFIED, AssertionPublicationStatus.REMOVED},
    "L'assertion non supportée doit être qualifiée ou retirée explicitement.",
)
assert_equal(
    evaluated.verified_research_outcome.support_status,
    "PARTIALLY_SUPPORTED",
    "Le contrat VerifiedResearchOutcome doit publier le statut documentaire explicite.",
)
assert_equal(
    tuple(str(claim_ref) for claim_ref in evaluated.verified_research_outcome.claim_refs),
    (f"{SUPPORTED_CLAIM_ID}@1",),
    "Seul le claim supporté et cité doit être publié vers le contrat RA.",
)
assert_equal(
    tuple(event.event_type for event in evaluated.events),
    ("AnswerSupportEvaluated", "AnswerPartiallySupported"),
    "L'évaluation doit publier les événements métier T-007.",
)

print("Test d'acceptation T-007 support et citations de réponse M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_support_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 support et citations de réponse M-007: OK"
