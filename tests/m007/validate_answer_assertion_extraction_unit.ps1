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
    Answer,
    AnswerAssertion,
    AnswerDraft,
    AssertionEvaluationStatus,
    AssertionOrigin,
    AssertionOriginType,
)
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "7" * 64
ARTIFACT_HASH = "8" * 64
CONTENT_HASH = "9" * 64
SPAN_HASH = "a" * 64


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


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T006-UNIT",
        document_id="DOC-M007-T006-UNIT",
        canonical_version_id="CVER-M007-T006-UNIT",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=2,
        accepted_at="2026-06-30T14:00:00Z",
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
            ref.canonical_version_id: {"item-m007-t006-unit": CONTENT_HASH},
        },
    )


def source_locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T006-UNIT",
            "document_id": "DOC-M007-T006-UNIT",
            "page_pdf": 1,
            "item_id": "item-m007-t006-unit",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": CONTENT_HASH,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref(locator):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M007-T006-UNIT-0001",
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
            "claim_id": "CLM-M007-T006-UNIT-0001",
            "claim_version": 1,
            "canonical_text": "La couverture de queue réduit le drawdown maximal.",
            "scope": {
                "universe": "portefeuilles convexes antifragiles",
                "horizon": "cycle documentaire stable",
                "metric": "risque",
                "frequency": "mensuelle",
            },
            "status": "VERIFIED",
            "verification_id": "VER-M007-T006-UNIT-0001",
            "evidence_refs": [ref.to_payload()],
            "dependency_group_ids": ["DEP-M007-T006-UNIT-0001"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(ref):
    return CandidateEvidence(
        evidence_ref=ref,
        source_text="Passage documentaire retenu pour un test unitaire RA.",
        search_trace_id="STRC-M007-T006-UNIT-0001",
        document_id=ref.source_locator.document_id,
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


class ValidAnswerGenerator:
    def __init__(self, claim_id):
        self.claim_id = claim_id

    def draft(self, request):
        return GeneratedAnswerDraft(
            content=f"[source:{self.claim_id}] La couverture de queue réduit le drawdown maximal.",
            model_provenance="valid-generator-m007-t006-unit-v1",
        )


class GeneratorTryingToSupport:
    def __init__(self, claim_id):
        self.claim_id = claim_id

    def draft(self, request):
        claim_id = self.claim_id

        class GeneratedDraftWithStatus:
            content = f"[source:{claim_id}] La couverture de queue réduit le drawdown maximal."
            model_provenance = "invalid-generator-m007-t006-unit-v1"
            support_status = "SUPPORTED"

        return GeneratedDraftWithStatus()


def sealed_case_repository():
    payload = {
        "resolved_question": "Quelle assertion extraire du brouillon ?",
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
        "idempotency_key": "ANSWER-ASSERTION-M007-T006-UNIT",
        "occurred_at": "2026-06-30T14:10:00Z",
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
            occurred_at="2026-06-30T14:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=opened.research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T14:16:00Z",
        )
    )
    return repository, sealed.research_case, claim


def source_origin():
    return AssertionOrigin(
        origin_type=AssertionOriginType.SOURCE,
        basis_refs=("CLM-M007-T006-UNIT-0001",),
        rationale="Assertion issue d'un claim vérifié.",
    )


# Le brouillon vide est refusé explicitement.
assert_raises(
    "answer_draft vide",
    lambda: AnswerDraft(
        draft_version=1,
        content="",
        model_provenance="unit-generator-v1",
    ),
)

# Une assertion composite n'est pas testable.
assert_raises(
    "assertion composite non testable",
    lambda: AnswerAssertion.from_extracted(
        answer_id="ANS-M007-T006-UNIT",
        draft_version=1,
        sequence=1,
        text="La couverture réduit le risque et le rééquilibrage améliore la liquidité.",
        origin=source_origin(),
    ),
)

# L'origine d'une assertion importante est obligatoire.
assert_raises(
    "assertion_origin absent",
    lambda: AnswerAssertion.from_extracted(
        answer_id="ANS-M007-T006-UNIT",
        draft_version=1,
        sequence=1,
        text="La couverture de queue réduit le drawdown maximal.",
        origin=None,
    ),
)

# Une assertion factuelle non balisée n'est pas ignorée par l'extracteur local.
assert_raises(
    "assertion importante non extraite",
    lambda: LocalDeterministicAnswerAssertionExtractor.for_m007().extract(
        AnswerDraft(
            draft_version=1,
            content="La couverture de queue réduit le drawdown maximal.",
            model_provenance="unit-generator-v1",
        )
    ),
)

# Une déduction sans prémisses est refusée.
assert_raises(
    "premisses absentes",
    lambda: LocalDeterministicAnswerAssertionExtractor.for_m007().extract(
        AnswerDraft(
            draft_version=1,
            content="[deduction:] La conclusion prudente est retenue.",
            model_provenance="unit-generator-v1",
        )
    ),
)

# Une version de brouillon déjà extraite ne peut plus être mutée silencieusement.
answer = Answer.create_draft(
    answer_id="ANS-M007-T006-UNIT",
    research_case_id="RSC-M007-T006-UNIT",
    evidence_set_id="EVS-M007-T006-UNIT",
    evidence_set_version=1,
    draft=AnswerDraft(
        draft_version=1,
        content="[source:CLM-M007-T006-UNIT-0001] La couverture de queue réduit le drawdown maximal.",
        model_provenance="unit-generator-v1",
    ),
    occurred_at="2026-06-30T14:20:00Z",
)
assertions = LocalDeterministicAnswerAssertionExtractor.for_m007().extract(answer.draft)
extracted_answer, event = answer.extract_assertions(
    assertions=assertions,
    extractor_version="answer-assertion-extractor-m007-v1",
    occurred_at="2026-06-30T14:21:00Z",
)
assert_equal(event.event_type, "AnswerAssertionsExtracted", "L'événement d'extraction doit être publié.")
assert_raises(
    "draft version publiee non modifiable",
    lambda: extracted_answer.replace_draft(
        AnswerDraft(
            draft_version=2,
            content="[source:CLM-M007-T006-UNIT-0001] Une nouvelle phrase remplace le brouillon.",
            model_provenance="unit-generator-v2",
        )
    ),
)

# Le générateur ne peut pas fixer un statut final.
research_case_repository, research_case, claim = sealed_case_repository()
answer_repository = InMemoryAnswerRepository.empty()
assert_raises(
    "support_status fourni par le generateur",
    lambda: DraftAnswerHandler(
        research_case_repository=research_case_repository,
        answer_repository=answer_repository,
        answer_generator=GeneratorTryingToSupport(claim.claim_id),
    ).draft(
        DraftAnswer(
            research_case_id=research_case.research_case_id,
            evidence_set_id=research_case.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T14:25:00Z",
        )
    ),
)

# Le chemin nominal conserve PENDING_EVALUATION.
drafted = DraftAnswerHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    answer_generator=ValidAnswerGenerator(claim.claim_id),
).draft(
    DraftAnswer(
        research_case_id=research_case.research_case_id,
        evidence_set_id=research_case.evidence_set.evidence_set_id,
        occurred_at="2026-06-30T14:26:00Z",
    )
)
extracted = ExtractAnswerAssertionsHandler(
    answer_repository=answer_repository,
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
).extract(
    ExtractAnswerAssertions(
        answer_id=drafted.answer.answer_id,
        occurred_at="2026-06-30T14:27:00Z",
    )
)
assert_equal(
    extracted.assertions[0].support_status,
    AssertionEvaluationStatus.PENDING_EVALUATION,
    "L'extraction ne doit pas supporter l'assertion.",
)

print("Tests unitaires T-006 extraction assertions de réponse M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_assertion_extraction_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 extraction assertions de réponse M-007: OK"
