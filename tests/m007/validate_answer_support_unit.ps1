$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from dataclasses import FrozenInstanceError, replace

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
    SupersedeAnswer,
    SupersedeAnswerHandler,
)
from app.research_answering.domain.answer import (
    AnswerFreshnessPolicy,
    AnswerStatus,
    AssertionPublicationStatus,
    VerifiedAnswerVersion,
)
from app.research_answering.domain.contradiction_assessment import (
    ClaimRef,
    ContradictionAssessment,
    ContradictionClassification,
    SupportStatus,
)
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)
from app.research_answering.domain.research_case import ResearchCaseStatus


SOURCE_HASH = "5" * 64
ARTIFACT_HASH = "6" * 64
CONTENT_HASH = "7" * 64
SPAN_HASH = "8" * 64
SUPPORTED_CLAIM_ID = "CLM-M007-T007-UNIT-SUPPORTED"
OTHER_CLAIM_ID = "CLM-M007-T007-UNIT-OTHER"
UNSUPPORTED_CLAIM_ID = "CLM-M007-T007-UNIT-UNSUPPORTED"
CANONICAL_VERSION_ID = "CVER-M007-T007-UNIT"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action, accepted=(ValueError,)):
    try:
        action()
    except accepted as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T007-UNIT",
        document_id="DOC-M007-T007-UNIT",
        canonical_version_id=CANONICAL_VERSION_ID,
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=2,
        accepted_at="2026-06-30T16:00:00Z",
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
            ref.canonical_version_id: {"item-m007-t007-unit": CONTENT_HASH},
        },
    )


def source_locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": CANONICAL_VERSION_ID,
            "document_id": "DOC-M007-T007-UNIT",
            "page_pdf": 1,
            "item_id": "item-m007-t007-unit",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": CONTENT_HASH,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref(locator):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M007-T007-UNIT-0001",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": SPAN_HASH,
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def verified_claim_ref(ref, *, claim_id=SUPPORTED_CLAIM_ID, canonical_text="La couverture de queue réduit le drawdown maximal."):
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
            "evidence_refs": [ref.to_payload()],
            "dependency_group_ids": [f"DEP-{claim_id.removeprefix('CLM-')}"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(ref):
    return CandidateEvidence(
        evidence_ref=ref,
        source_text="Passage documentaire retenu pour un test unitaire RA.",
        search_trace_id="STRC-M007-T007-UNIT-0001",
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


class BrokenCitationResolver:
    def resolve(self, citation):
        return None


class StaticAnswerGenerator:
    def __init__(self, content):
        self.content = content

    def draft(self, request):
        return GeneratedAnswerDraft(
            content=self.content,
            model_provenance="static-answer-generator-m007-t007-unit-v1",
        )


def prepared_repositories(answer_content, *, claim_ids=(SUPPORTED_CLAIM_ID,)):
    payload = {
        "resolved_question": "Quelle réponse documentaire vérifier ?",
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
        "idempotency_key": "ANSWER-SUPPORT-M007-T007-UNIT",
        "occurred_at": "2026-06-30T16:10:00Z",
    }
    locator = source_locator()
    ref = evidence_ref(locator)
    claims = tuple(
        verified_claim_ref(
            ref,
            claim_id=claim_id,
            canonical_text=(
                "La couverture de queue réduit le drawdown maximal."
                if claim_id == SUPPORTED_CLAIM_ID
                else "Le rééquilibrage mensuel réduit la dérive du portefeuille."
            ),
        )
        for claim_id in claim_ids
    )
    research_case_repository = InMemoryResearchCaseRepository.empty()
    opened = OpenResearchCaseHandler(
        research_case_repository=research_case_repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    handler = CollectEvidenceHandler(
        research_case_repository=research_case_repository,
        knowledge_search=FakeKnowledgeSearch(candidates=(candidate_for(ref),)),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims=claims),
        citation_resolver=OpeningCitationResolver(),
    )
    collected = handler.collect(
        CollectEvidenceCommand(
            research_case_id=opened.research_case_id,
            coverage_obligations=("preuves_documentaires",),
            result_limit=2,
            occurred_at="2026-06-30T16:15:00Z",
        )
    )
    sealed = handler.seal(
        SealEvidenceSetCommand(
            research_case_id=opened.research_case_id,
            evidence_set_id=collected.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T16:16:00Z",
        )
    )
    answer_repository = InMemoryAnswerRepository.empty()
    drafted = DraftAnswerHandler(
        research_case_repository=research_case_repository,
        answer_repository=answer_repository,
        answer_generator=StaticAnswerGenerator(answer_content),
    ).draft(
        DraftAnswer(
            research_case_id=sealed.research_case.research_case_id,
            evidence_set_id=sealed.research_case.evidence_set.evidence_set_id,
            occurred_at="2026-06-30T16:20:00Z",
        )
    )
    extracted = ExtractAnswerAssertionsHandler(
        answer_repository=answer_repository,
        answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
    ).extract(
        ExtractAnswerAssertions(
            answer_id=drafted.answer.answer_id,
            occurred_at="2026-06-30T16:21:00Z",
        )
    )
    return research_case_repository, answer_repository, sealed.research_case, extracted.answer


def evaluate(answer_content, *, resolver=OpeningCitationResolver(), research_case_mutator=None):
    research_case_repository, answer_repository, research_case, answer = prepared_repositories(answer_content)
    if research_case_mutator is not None:
        research_case = research_case_mutator(research_case)
        research_case_repository.update(research_case)
    return EvaluateAnswerSupportHandler(
        research_case_repository=research_case_repository,
        answer_repository=answer_repository,
        citation_resolver=resolver,
    ).evaluate(
        EvaluateAnswerSupport(
            research_case_id=research_case.research_case_id,
            answer_id=answer.answer_id,
            support_policy_version="answer-support-m007-v1",
            citation_policy_version="citation-integrity-m007-v1",
            freshness_policy_version="answer-freshness-m007-v1",
            occurred_at="2026-06-30T16:22:00Z",
        )
    )


def blocking_conflict_case(research_case):
    assessment = ContradictionAssessment(
        contradiction_id="REL-M007-T007-UNIT-CONFLICT",
        relation_id="REL-M007-T007-UNIT-CONFLICT",
        source_claim_ref=ClaimRef(claim_id=SUPPORTED_CLAIM_ID, claim_version=1),
        target_claim_ref=ClaimRef(claim_id=OTHER_CLAIM_ID, claim_version=1),
        classification=ContradictionClassification.DIRECT_CONFLICT,
        reason_code="UNRESOLVED_DIRECT_CONFLICT",
        public_reason="Claims vérifiés opposés sur une portée comparable.",
        policy_version="contradiction-classification-m007-v1",
        requires_public_explanation=True,
        blocks_general_supported_status=True,
        blocks_publication=True,
    )
    return replace(
        research_case,
        contradiction_assessments=research_case.contradiction_assessments + (assessment,),
    )


def insufficient_evidence_case(research_case):
    updated_case, _, _ = research_case.declare_insufficient_evidence(
        missing_obligations=("preuves_documentaires",),
        reason_codes=("ANSWER_ASSERTION_UNSUPPORTED",),
        occurred_at="2026-06-30T16:20:00Z",
    )
    return updated_case


supported_content = f"[source:{SUPPORTED_CLAIM_ID}] La couverture de queue réduit le drawdown maximal."
unsupported_content = (
    f"[source:{SUPPORTED_CLAIM_ID}] La couverture de queue réduit le drawdown maximal.\n"
    f"[source:{UNSUPPORTED_CLAIM_ID}] Le portefeuille bat systématiquement le marché."
)
indirect_content = f"[deduction:{SUPPORTED_CLAIM_ID}] La conclusion prudente dépend d'une preuve indirecte."


# Une assertion importante sans claim vérifié reste tracée et empêche SUPPORTED.
partial = evaluate(unsupported_content)
assert_equal(partial.support_status, SupportStatus.PARTIALLY_SUPPORTED, "Le statut doit être qualifié.")
unsupported_decisions = tuple(
    decision for decision in partial.verified_answer_version.assertion_decisions
    if UNSUPPORTED_CLAIM_ID in decision.basis_refs
)
assert_equal(len(unsupported_decisions), 1, "La décision non supportée doit être tracée.")
assert_equal(
    unsupported_decisions[0].publication_status,
    AssertionPublicationStatus.QUALIFIED,
    "Une assertion conservée sans support doit être qualifiée.",
)

# Une citation non ouvrable bloque la publication supportée.
assert_raises(
    "ANSWER_CITATION_UNRESOLVABLE",
    lambda: evaluate(supported_content, resolver=BrokenCitationResolver()),
)

# Un conflit direct non résolu n'est pas masqué par un statut global optimiste.
conflicting = evaluate(supported_content, research_case_mutator=blocking_conflict_case)
assert_equal(
    conflicting.support_status,
    SupportStatus.CONFLICTING_EVIDENCE,
    "Le conflit direct doit publier CONFLICTING_EVIDENCE.",
)
assert_equal(
    conflicting.answer.status,
    AnswerStatus.CONFLICTING_EVIDENCE,
    "L'Answer doit porter le statut bloquant publié.",
)
assert_equal(
    tuple(event.event_type for event in conflicting.events),
    ("AnswerSupportEvaluated", "AnswerPublicationBlocked"),
    "La publication conflictuelle doit exposer un événement bloquant.",
)
assert_equal(
    len(conflicting.verified_research_outcome.unresolved_conflicts),
    1,
    "Le conflit non résolu doit rester visible dans le contrat public.",
)

# Une absence totale de claim supporté devient publiable seulement avec une lacune explicite.
insufficient = evaluate(
    f"[source:{UNSUPPORTED_CLAIM_ID}] Le portefeuille bat systématiquement le marché.",
    research_case_mutator=insufficient_evidence_case,
)
assert_equal(
    insufficient.support_status,
    SupportStatus.INSUFFICIENT_EVIDENCE,
    "La lacune explicite doit publier INSUFFICIENT_EVIDENCE.",
)

# Une preuve indirecte seule ne suffit pas pour SUPPORTED.
indirect = evaluate(indirect_content)
assert_equal(indirect.support_status, SupportStatus.PARTIALLY_SUPPORTED, "La déduction doit rester qualifiée.")
assert_equal(
    indirect.verified_answer_version.assertion_decisions[0].publication_status,
    AssertionPublicationStatus.QUALIFIED,
    "Une preuve indirecte seule ne doit pas être publiée comme fait supporté.",
)

# Le chemin nominal publie une version SUPPORTED immuable.
supported = evaluate(supported_content)
assert_equal(supported.support_status, SupportStatus.SUPPORTED, "L'assertion directement citée doit être supportée.")
assert_equal(supported.answer.status, AnswerStatus.VERIFIED, "L'Answer supporté doit être VERIFIED.")
assert_equal(
    tuple(event.event_type for event in supported.events),
    ("AnswerSupportEvaluated", "AnswerVerified"),
    "La publication supportée doit exposer les événements attendus.",
)
assert_raises(
    "cannot assign to field",
    lambda: setattr(supported.verified_answer_version, "answer_text", "mutation interdite"),
    accepted=(FrozenInstanceError,),
)

research_case_repository, answer_repository, research_case, answer = prepared_repositories(supported_content)
EvaluateAnswerSupportHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    citation_resolver=OpeningCitationResolver(),
).evaluate(
    EvaluateAnswerSupport(
        research_case_id=research_case.research_case_id,
        answer_id=answer.answer_id,
        support_policy_version="answer-support-m007-v1",
        citation_policy_version="citation-integrity-m007-v1",
        freshness_policy_version="answer-freshness-m007-v1",
        occurred_at="2026-06-30T16:24:00Z",
    )
)
completed_case = research_case_repository.case_for_id(research_case.research_case_id)
assert_equal(
    completed_case.status,
    ResearchCaseStatus.COMPLETED,
    "Le ResearchCase doit devenir terminal après publication.",
)
assert_raises(
    "evidence_set non scelle",
    lambda: completed_case.record_contradiction_assessments(
        (),
        occurred_at="2026-06-30T16:24:30Z",
    ),
)

# Une source devenue obsolète impose revalidation ou supersession explicite.
freshness_policy = AnswerFreshnessPolicy(
    policy_version="answer-freshness-m007-v1",
    current_support_policy_version="answer-support-m007-v1",
    accepted_canonical_version_ids=("CVER-OTHER",),
)
assert_raises(
    "ANSWER_SOURCE_OBSOLETE",
    lambda: freshness_policy.ensure_fresh(
        evidence_set=supported.answer.verified_answer_version.evidence_set_snapshot,
        support_policy_version="answer-support-m007-v1",
    ),
)

# Une politique de support obsolète refuse la réutilisation.
freshness_policy = AnswerFreshnessPolicy(
    policy_version="answer-freshness-m007-v1",
    current_support_policy_version="answer-support-m007-v2",
    accepted_canonical_version_ids=(CANONICAL_VERSION_ID,),
)
assert_raises(
    "ANSWER_POLICY_OBSOLETE",
    lambda: freshness_policy.ensure_fresh(
        evidence_set=supported.answer.verified_answer_version.evidence_set_snapshot,
        support_policy_version="answer-support-m007-v1",
    ),
)

# La supersession d'une réponse publiée est explicite et événementielle.
research_case_repository, answer_repository, research_case, answer = prepared_repositories(supported_content)
published = EvaluateAnswerSupportHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    citation_resolver=OpeningCitationResolver(),
).evaluate(
    EvaluateAnswerSupport(
        research_case_id=research_case.research_case_id,
        answer_id=answer.answer_id,
        support_policy_version="answer-support-m007-v1",
        citation_policy_version="citation-integrity-m007-v1",
        freshness_policy_version="answer-freshness-m007-v1",
        occurred_at="2026-06-30T16:25:00Z",
    )
)
superseded = SupersedeAnswerHandler(answer_repository=answer_repository).supersede(
    SupersedeAnswer(
        answer_id=published.answer.answer_id,
        new_answer_ref="ANS-M007-T007-UNIT-REPLACEMENT@1",
        supersession_reason="SOURCE_OBSOLETE",
        occurred_at="2026-06-30T16:30:00Z",
    )
)
assert_equal(superseded.events[0].event_type, "AnswerSuperseded", "La supersession doit publier AnswerSuperseded.")
assert_equal(
    superseded.answer.superseded_by,
    "ANS-M007-T007-UNIT-REPLACEMENT@1",
    "La référence remplaçante doit être explicite.",
)

# Sans lacune explicite, aucun claim supporté ne peut être projeté silencieusement.
assert_raises(
    "INSUFFICIENT_EVIDENCE",
    lambda: evaluate(f"[source:{UNSUPPORTED_CLAIM_ID}] Le portefeuille bat systématiquement le marché."),
)

# Une version publiée ne peut pas omettre silencieusement la décision d'une assertion importante.
assert_raises(
    "answer_assertion sans decision",
    lambda: VerifiedAnswerVersion(
        answer_id=supported.answer.answer_id,
        answer_version=2,
        research_case_id=supported.answer.research_case_id,
        evidence_set_id=supported.answer.evidence_set_id,
        evidence_set_version=supported.answer.evidence_set_version,
        evidence_set_snapshot=supported.answer.verified_answer_version.evidence_set_snapshot,
        support_status=SupportStatus.SUPPORTED,
        answer_text=supported.answer.draft.content,
        source_assertions=supported.answer.assertions,
        assertion_decisions=(),
        citations=supported.answer.verified_answer_version.citations,
        claim_refs=supported.answer.verified_answer_version.claim_refs,
        policy_version="answer-support-m007-v1",
        published_at="2026-06-30T16:35:00Z",
    ),
)

print("Tests unitaires T-007 support et citations de réponse M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_support_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 support et citations de réponse M-007: OK"
