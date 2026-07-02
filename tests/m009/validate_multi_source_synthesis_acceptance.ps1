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
    CollectDeepResearchEvidenceCommand,
    CollectDeepResearchEvidenceHandler,
    DeepEvidenceSearchResult,
)
from app.research_answering.application.draft_answer import (
    GeneratedDeepResearchDraft,
    ProduceMultiSourceSynthesis,
    ProduceMultiSourceSynthesisHandler,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.answer import (
    AssertionOriginType,
    DeepResearchReportSectionName,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import DeepResearchPlanningPolicy


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_no_forbidden_strategy(value, path="payload"):
    forbidden_keys = {
        "strategy_parameter",
        "candidate_strategy",
        "kelly_fraction",
        "volatility_target",
        "rebalance_rule",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key.lower() in forbidden_keys, f"Paramètre de stratégie publié dans {path}.{key}.")
            assert_no_forbidden_strategy(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_strategy(child, f"{path}[{index}]")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t008-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T008-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=6,
        accepted_at="2026-07-02T15:00:00Z",
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
            "page_pdf": 2,
            "item_id": f"item-m009-t008-{suffix.lower()}",
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
            "evidence_id": f"EVS-M009-T008-{suffix}",
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


def verified_claim_ref(*, suffix, evidence, canonical_text):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": f"CLM-M009-T008-{suffix}",
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuille convexe documenté",
                "horizon": "connaissances documentaires stables",
                "metric": "synthèse approfondie",
                "frequency": "documentaire",
            },
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T008-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": [f"DEP-M009-T008-{suffix}"],
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=evidence.source_locator.document_id,
            canonical_version_id=evidence.source_locator.canonical_version_id,
            content_hash=evidence.source_locator.content_hash,
            item_id=evidence.source_locator.item_id,
        ),
    )


def candidate(*, suffix, obligations, text, trace_suffix, content_seed, span_seed):
    document_id = f"DOC-M009-T008-{suffix}"
    canonical_version_id = f"CVER-M009-T008-{suffix}"
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
        search_trace_id=f"STRC-M009T008{trace_suffix:024d}",
        document_id=document_id,
        covered_obligations=obligations,
    )


class FakeDeepKnowledgeSearch:
    def __init__(self, responses_by_sub_question_id):
        self.responses_by_sub_question_id = dict(responses_by_sub_question_id)

    def search(self, request):
        return self.responses_by_sub_question_id[request.sub_question_id]


class FakeVerifiedClaimCatalog:
    def __init__(self, claim_refs):
        self.claims_by_evidence_id = {
            claim.evidence_refs[0].evidence_id: claim
            for claim in claim_refs
        }

    def verified_claims_for_evidence(self, evidence_refs):
        return tuple(self.claims_by_evidence_id[evidence.evidence_id] for evidence in evidence_refs)


class OpeningCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


class StructuredDeepSynthesisGenerator:
    def draft(self, request):
        claim_ids = tuple(claim_ref.claim_id for claim_ref in request.verified_claim_refs)
        citation_ids = tuple(citation.citation_id for citation in request.citations)
        return GeneratedDeepResearchDraft(
            sections={
                "MANDATE": "Mandat retenu: comparer Kelly et volatility targeting sans stratégie candidate.",
                "DOCUMENTARY_SCOPE": "Périmètre documentaire: sources canoniques stables du mandat.",
                "METHODS": "Méthodes: Kelly dépend d'une mesure d'avantage citée.",
                "APPLICATION_CONDITIONS": "Conditions: conclusion limitée au corpus scellé.",
                "FAVORABLE_EVIDENCE": "Preuves favorables: drawdown réduit dans une source vérifiée.",
                "UNFAVORABLE_EVIDENCE": "Preuves défavorables: risque amplifié dans une source vérifiée.",
                "DEPENDENCIES": "Dépendances: les groupes EG sont distingués.",
                "CONTRADICTIONS": "Contradictions: la condition défavorable reste visible.",
                "LIMITS": "Limites: aucune donnée de marché actuelle n'est inventée.",
                "UNDOCUMENTED_ZONES": "Zones non documentées: paramètres de stratégie exclus.",
                "CONCLUSION": "Conclusion: synthèse qualifiée par les preuves contradictoires.",
                "UNCERTAINTY": "Incertitude: le support reste partiel.",
            },
            assertion_lines=(
                f"[source:{claim_ids[0]}] Kelly depend mesure avantage.",
                f"[source:{claim_ids[1]}] La preuve favorable reduit drawdown.",
                f"[source:{claim_ids[2]}] La preuve defavorable amplifie risque.",
                f"[deduction:{claim_ids[1]},{claim_ids[2]}] La conclusion reste conditionnelle.",
                "[design:DESIGN-M009-SYNTHESIS] La synthese separe faits deductions choix.",
            ),
            section_citation_ids={
                name.value: citation_ids
                for name in DeepResearchReportSectionName
            },
            model_provenance="structured-deep-synthesis-generator-m009-v1",
        )


class FailingDeepSynthesisGenerator:
    def draft(self, request):
        raise ValueError("LLM_DRAFT_FAILED")


def planned_deep_case_repository():
    payload = {
        "resolved_question": (
            "Produire une synthèse multi-sources sur Kelly et volatility targeting "
            "sans effacer preuves défavorables, contradictions ni zones non documentées."
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
                "generation de strategie candidate",
            ),
            "language": "fr",
            "detail_level": "synthese approfondie multi-sources",
        },
        "requested_mode": "DEEP_RESEARCH",
        "requested_by_context": "CV",
        "idempotency_key": "MULTI-SOURCE-SYNTHESIS-M009-T008-ACCEPTANCE",
        "occurred_at": "2026-07-02T15:05:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def sealed_deep_case():
    repository, research_case_id = planned_deep_case_repository()
    candidates_by_sub_question = {
        "RSQ-METHODES": candidate(
            suffix="METHODES",
            obligations=("methodes", "dependances"),
            text="Kelly dépend d'une méthode d'estimation explicite.",
            trace_suffix=1,
            content_seed=1,
            span_seed=5,
        ),
        "RSQ-PREUVES-FAVORABLES": candidate(
            suffix="FAVORABLE",
            obligations=("preuves_favorables",),
            text="Une preuve favorable documente un drawdown réduit.",
            trace_suffix=2,
            content_seed=2,
            span_seed=6,
        ),
        "RSQ-PREUVES-DEFAVORABLES": candidate(
            suffix="DEFAVORABLE",
            obligations=("preuves_defavorables",),
            text="Une preuve défavorable documente un risque amplifié.",
            trace_suffix=3,
            content_seed=3,
            span_seed=7,
        ),
        "RSQ-LIMITES-LACUNES": candidate(
            suffix="LIMITES",
            obligations=("limites", "zones_non_documentees"),
            text="Les zones non documentées excluent tout paramètre de stratégie.",
            trace_suffix=4,
            content_seed=4,
            span_seed=8,
        ),
    }
    claims = (
        verified_claim_ref(
            suffix="METHODES",
            evidence=candidates_by_sub_question["RSQ-METHODES"].evidence_ref,
            canonical_text="Kelly dépend d'une méthode d'estimation explicite.",
        ),
        verified_claim_ref(
            suffix="FAVORABLE",
            evidence=candidates_by_sub_question["RSQ-PREUVES-FAVORABLES"].evidence_ref,
            canonical_text="Une preuve favorable documente un drawdown réduit.",
        ),
        verified_claim_ref(
            suffix="DEFAVORABLE",
            evidence=candidates_by_sub_question["RSQ-PREUVES-DEFAVORABLES"].evidence_ref,
            canonical_text="Une preuve défavorable documente un risque amplifié.",
        ),
        verified_claim_ref(
            suffix="LIMITES",
            evidence=candidates_by_sub_question["RSQ-LIMITES-LACUNES"].evidence_ref,
            canonical_text="Les zones non documentées excluent tout paramètre de stratégie.",
        ),
    )
    responses = {
        sub_question_id: DeepEvidenceSearchResult(
            projection_version_ref=f"PROJ-M009-T008-{sub_question_id}",
            audit_trace_id=f"STRC-M009T008AUDIT{index:020d}",
            candidates=(candidates_by_sub_question[sub_question_id],),
        )
        for index, sub_question_id in enumerate(candidates_by_sub_question, start=1)
    }
    CollectDeepResearchEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeDeepKnowledgeSearch(responses),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims),
        citation_resolver=OpeningCitationResolver(),
    ).collect(
        CollectDeepResearchEvidenceCommand(
            research_case_id=research_case_id,
            result_limit=2,
            occurred_at="2026-07-02T15:10:00Z",
        )
    )
    assembled = repository.case_for_id(research_case_id)
    sealed, _ = assembled.seal_evidence_set(
        evidence_set_id=assembled.evidence_set.evidence_set_id,
        citation_resolver=OpeningCitationResolver(),
        occurred_at="2026-07-02T15:11:00Z",
    )
    repository.update(sealed)
    return repository, sealed


# Given un EvidenceSet approfondi contient preuves favorables, défavorables, dépendances et limites.
research_case_repository, research_case = sealed_deep_case()
answer_repository = InMemoryAnswerRepository.empty()

# When RA produit la synthèse multi-sources.
result = ProduceMultiSourceSynthesisHandler(
    research_case_repository=research_case_repository,
    answer_repository=answer_repository,
    deep_synthesis_generator=StructuredDeepSynthesisGenerator(),
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
    citation_resolver=OpeningCitationResolver(),
).produce(
    ProduceMultiSourceSynthesis(
        research_case_id=research_case.research_case_id,
        evidence_set_id=research_case.evidence_set.evidence_set_id,
        synthesis_policy_version="multi-source-synthesis-m009-v1",
        support_policy_version="answer-support-m009-v1",
        citation_policy_version="citation-integrity-m009-v1",
        freshness_policy_version="answer-freshness-m009-v1",
        occurred_at="2026-07-02T15:20:00Z",
    )
)

# Then la réponse finale expose chaque section obligatoire avec citations et assertions finales vérifiées.
assert_equal(result.status, "MULTI_SOURCE_SYNTHESIS_PUBLISHED", "Le statut applicatif doit être explicite.")
assert_equal(result.deep_research_report.support_status, SupportStatus.PARTIALLY_SUPPORTED, "La synthèse doit rester qualifiée.")
assert_equal(result.answer.status.value, "PARTIALLY_SUPPORTED", "L'Answer M-007 doit rester compatible.")
assert_equal(
    result.verified_research_outcome.support_status,
    "PARTIALLY_SUPPORTED",
    "Le DTO public M-007 doit rester compatible.",
)
assert_equal(
    result.deep_research_report.section_names,
    tuple(name for name in DeepResearchReportSectionName),
    "Toutes les sections obligatoires doivent être publiées dans l'ordre.",
)
assert_true(
    result.deep_research_report.has_origin_type(AssertionOriginType.SOURCE),
    "Les faits de source doivent rester distingués.",
)
assert_true(
    result.deep_research_report.has_origin_type(AssertionOriginType.DEDUCTION),
    "Les déductions doivent rester distinguées.",
)
assert_true(
    result.deep_research_report.has_origin_type(AssertionOriginType.DESIGN_CHOICE),
    "Les choix de conception doivent rester distingués.",
)
assert_true(
    all(citation.source_locator.item_id for citation in result.deep_research_report.citations),
    "Les citations finales doivent rester ouvrables.",
)
assert_equal(
    answer_repository.answer_count(),
    1,
    "Une seule réponse RA doit être publiée.",
)
assert_equal(
    research_case_repository.case_for_id(research_case.research_case_id).status,
    ResearchCaseStatus.COMPLETED,
    "Le ResearchCase doit être complété uniquement après publication vérifiée.",
)
assert_no_forbidden_strategy(result.deep_research_report.to_payload())

# Given le générateur échoue après le scellement de l'EvidenceSet.
failure_repository, failure_case = sealed_deep_case()
sealed_evidence_hash = failure_case.evidence_set.evidence_hash
sealed_plan = failure_case.research_plan
failure_answer_repository = InMemoryAnswerRepository.empty()

# When RA tente la synthèse.
failure = ProduceMultiSourceSynthesisHandler(
    research_case_repository=failure_repository,
    answer_repository=failure_answer_repository,
    deep_synthesis_generator=FailingDeepSynthesisGenerator(),
    answer_assertion_extractor=LocalDeterministicAnswerAssertionExtractor.for_m007(),
    citation_resolver=OpeningCitationResolver(),
).produce(
    ProduceMultiSourceSynthesis(
        research_case_id=failure_case.research_case_id,
        evidence_set_id=failure_case.evidence_set.evidence_set_id,
        synthesis_policy_version="multi-source-synthesis-m009-v1",
        support_policy_version="answer-support-m009-v1",
        citation_policy_version="citation-integrity-m009-v1",
        freshness_policy_version="answer-freshness-m009-v1",
        occurred_at="2026-07-02T15:25:00Z",
    )
)

# Then aucun fallback vers une réponse simple ne remplace le cas, le plan ni l'EvidenceSet scellé.
assert_equal(failure.status, "SYNTHESIS_DRAFT_FAILED", "L'échec du générateur doit être explicite.")
assert_equal(
    failure.failure_reason_code,
    "DEEP_RESEARCH_DRAFT_GENERATION_FAILED",
    "L'échec ne doit pas être masqué par un fallback.",
)
assert_equal(failure_answer_repository.answer_count(), 0, "Aucune réponse simple ne doit être créée.")
stored_failure_case = failure_repository.case_for_id(failure_case.research_case_id)
assert_equal(stored_failure_case.status, ResearchCaseStatus.EVIDENCE_SET_SEALED, "Le statut scellé doit être conservé.")
assert_equal(stored_failure_case.research_plan, sealed_plan, "Le DeepResearchPlan ne doit pas être remplacé.")
assert_equal(stored_failure_case.evidence_set.evidence_hash, sealed_evidence_hash, "L'EvidenceSet scellé ne doit pas être détruit.")
assert_equal(failure.research_case, stored_failure_case, "Le résultat d'échec doit référencer le cas inchangé.")
assert_equal(failure.evidence_set.evidence_hash, sealed_evidence_hash, "Le résultat d'échec doit exposer l'EvidenceSet scellé.")

print("Test d'acceptation T-008 synthèse multi-sources traçable M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_multi_source_synthesis_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 synthèse multi-sources traçable M-009: OK"
