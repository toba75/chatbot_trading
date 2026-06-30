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
from app.research_answering.domain.answer import (
    AnswerStatus,
    AssertionEvaluationStatus,
    AssertionOriginType,
)
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
FIRST_CONTENT_HASH = "3" * 64
SECOND_CONTENT_HASH = "4" * 64
FIRST_SPAN_HASH = "5" * 64
SECOND_SPAN_HASH = "6" * 64


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T006-ACCEPTANCE",
        document_id="DOC-M007-T006-ACCEPTANCE",
        canonical_version_id="CVER-M007-T006-ACCEPTANCE",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=3,
        accepted_at="2026-06-30T13:00:00Z",
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
                "item-m007-t006-acceptance-drawdown": FIRST_CONTENT_HASH,
                "item-m007-t006-acceptance-rebalance": SECOND_CONTENT_HASH,
            },
        },
    )


def source_locator(*, item_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T006-ACCEPTANCE",
            "document_id": "DOC-M007-T006-ACCEPTANCE",
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


def verified_claim_ref_for(evidence_ref, *, claim_id, canonical_text):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": claim_id,
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuilles convexes antifragiles",
                "horizon": "cycle documentaire stable",
                "metric": "risque",
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
        source_text="Passage documentaire retenu pour rédiger une réponse vérifiée.",
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


class FakeAnswerGenerator:
    def __init__(self, claim_ids):
        self.claim_ids = tuple(claim_ids)
        self.requests = []

    def draft(self, request):
        self.requests.append(request)
        first_claim_id, second_claim_id = self.claim_ids
        return GeneratedAnswerDraft(
            content=(
                f"[source:{first_claim_id}] La couverture de queue réduit le drawdown maximal.\n"
                f"[source:{second_claim_id}] Le rééquilibrage mensuel réduit la dérive du portefeuille.\n"
                f"[deduction:{first_claim_id},{second_claim_id}] La réponse retient une conclusion prudente issue des deux preuves."
            ),
            model_provenance="fake-answer-generator-m007-t006-v1",
        )


def planned_case_repository():
    payload = {
        "resolved_question": "Quelle réponse documentaire produire à partir des preuves scellées ?",
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
        "idempotency_key": "ANSWER-ASSERTION-M007-T006-ACCEPTANCE",
        "occurred_at": "2026-06-30T13:10:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def sealed_case_with_claims():
    drawdown_locator = source_locator(
        item_id="item-m007-t006-acceptance-drawdown",
        content_hash=FIRST_CONTENT_HASH,
    )
    rebalance_locator = source_locator(
        item_id="item-m007-t006-acceptance-rebalance",
        content_hash=SECOND_CONTENT_HASH,
    )
    drawdown_evidence = evidence_ref_for(
        drawdown_locator,
        evidence_id="EVS-M007-T006-ACCEPTANCE-DRAWDOWN",
        quoted_span_hash=FIRST_SPAN_HASH,
    )
    rebalance_evidence = evidence_ref_for(
        rebalance_locator,
        evidence_id="EVS-M007-T006-ACCEPTANCE-REBALANCE",
        quoted_span_hash=SECOND_SPAN_HASH,
    )
    drawdown_claim = verified_claim_ref_for(
        drawdown_evidence,
        claim_id="CLM-M007-T006-ACCEPTANCE-DRAWDOWN",
        canonical_text="La couverture de queue réduit le drawdown maximal.",
    )
    rebalance_claim = verified_claim_ref_for(
        rebalance_evidence,
        claim_id="CLM-M007-T006-ACCEPTANCE-REBALANCE",
        canonical_text="Le rééquilibrage mensuel réduit la dérive du portefeuille.",
    )
    repository, research_case_id = planned_case_repository()
    handler = CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch(
            candidates=(candidate_for(drawdown_evidence), candidate_for(rebalance_evidence))
        ),
        verified_claim_catalog=FakeVerifiedClaimCatalog(
            claims=(drawdown_claim, rebalance_claim)
        ),
        citation_resolver=OpeningCitationResolver(),
    )
    collected = handler.collect(
        CollectEvidenceCommand(
            research_case_id=research_case_id,
            coverage_obligations=("preuves_documentaires",),
            occurred_at="2026-06-30T13:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T13:16:00Z",
        )
    )
    return repository, sealed.research_case, drawdown_claim, rebalance_claim


# Given un jeu de preuves scellé et un brouillon contenant deux assertions factuelles et une déduction.
research_case_repository, research_case, drawdown_claim, rebalance_claim = sealed_case_with_claims()
answer_repository = InMemoryAnswerRepository.empty()
generator = FakeAnswerGenerator(claim_ids=(drawdown_claim.claim_id, rebalance_claim.claim_id))
drafted = DraftAnswerHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    answer_generator=generator,
).draft(
    DraftAnswer(
        research_case_id=research_case.research_case_id,
        evidence_set_id=research_case.evidence_set.evidence_set_id,
        occurred_at="2026-06-30T13:20:00Z",
    )
)

# When RA extrait les assertions importantes.
extracted = ExtractAnswerAssertionsHandler(
    answer_repository=answer_repository,
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
).extract(
    ExtractAnswerAssertions(
        answer_id=drafted.answer.answer_id,
        occurred_at="2026-06-30T13:21:00Z",
    )
)

# Then les assertions deviennent atomiques, portent leur origine, et aucune n'est marquée supportée avant évaluation.
assert_equal(drafted.status, "ANSWER_DRAFTED", "Le brouillon doit exposer un statut applicatif dédié.")
assert_equal(drafted.answer.status, AnswerStatus.DRAFT, "Un brouillon ne doit pas être une réponse publiée.")
assert_false(drafted.answer.is_published, "Le brouillon ne doit pas être public.")
assert_equal(extracted.status, "ANSWER_ASSERTIONS_EXTRACTED", "L'extraction doit exposer un statut observable.")
assert_equal(extracted.answer.status, AnswerStatus.ASSERTIONS_EXTRACTED, "L'Answer doit passer ASSERTIONS_EXTRACTED.")
assert_equal(len(extracted.assertions), 3, "Deux faits et une déduction doivent être visibles.")
assert_equal(
    tuple(assertion.origin.origin_type for assertion in extracted.assertions),
    (AssertionOriginType.SOURCE, AssertionOriginType.SOURCE, AssertionOriginType.DEDUCTION),
    "Chaque assertion doit conserver son origine métier.",
)
assert_equal(
    tuple(assertion.support_status for assertion in extracted.assertions),
    (
        AssertionEvaluationStatus.PENDING_EVALUATION,
        AssertionEvaluationStatus.PENDING_EVALUATION,
        AssertionEvaluationStatus.PENDING_EVALUATION,
    ),
    "Aucune assertion ne doit être supportée avant évaluation.",
)
assert_true(
    all(assertion.atomic for assertion in extracted.assertions),
    "Les assertions importantes doivent être atomiques.",
)
assert_equal(
    extracted.events[0].event_type,
    "AnswerAssertionsExtracted",
    "L'extraction doit publier AnswerAssertionsExtracted.",
)
assert_equal(
    generator.requests[0].evidence_set_version,
    research_case.evidence_set.version.value,
    "Le générateur doit recevoir la version scellée du jeu de preuves.",
)

print("Test d'acceptation T-006 extraction assertions de réponse M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_assertion_extraction_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 extraction assertions de réponse M-007: OK"
