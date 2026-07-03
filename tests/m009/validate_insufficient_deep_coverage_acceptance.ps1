$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from types import SimpleNamespace

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
from app.research_answering.application.classify_contradictions import (
    DeclareInsufficientDeepCoverage,
    DeclareInsufficientDeepCoverageHandler,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.contradiction_assessment import (
    KnowledgeGapType,
    SupportStatus,
)
from app.research_answering.domain.evidence_set import DeepCoverageRequirement
from app.research_answering.domain.research_case import ResearchCaseStatus, ResearchMode
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


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t007-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T007-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=4,
        accepted_at="2026-07-02T13:00:00Z",
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


def source_locator(*, suffix, content_seed):
    document_id = f"DOC-M009-T007-{suffix}"
    canonical_version_id = f"CVER-M009-T007-{suffix}"
    content_hash = hash_for(content_seed)
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id,
            "document_id": document_id,
            "page_pdf": 2,
            "item_id": f"item-m009-t007-{suffix.lower()}",
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


def evidence_ref(*, suffix, content_seed, span_seed):
    locator = source_locator(suffix=suffix, content_seed=content_seed)
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T007-{suffix}",
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
            "claim_id": f"CLM-M009-T007-{suffix}",
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuille convexe documente",
                "horizon": "connaissances documentaires stables",
                "metric": "couverture documentaire",
                "frequency": "evenementielle",
            },
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T007-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": [f"DEP-M009-T007-{suffix}"],
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=evidence.source_locator.document_id,
            canonical_version_id=evidence.source_locator.canonical_version_id,
            content_hash=evidence.source_locator.content_hash,
            item_id=evidence.source_locator.item_id,
        ),
    )


def candidate_for(*, suffix, obligations, polarity, source_kind, text, content_seed, span_seed):
    evidence = evidence_ref(suffix=suffix, content_seed=content_seed, span_seed=span_seed)
    return SimpleNamespace(
        evidence_ref=evidence,
        source_text=text,
        search_trace_id=f"STRC-M009T007{content_seed:024d}",
        document_id=evidence.source_locator.document_id,
        covered_obligations=obligations,
        evidence_polarity=polarity,
        source_kind=source_kind,
    )


class OpeningCitationResolver:
    def resolve(self, citation):
        return {"opened": citation.source_locator.item_id}


def planned_deep_case_repository():
    payload = {
        "resolved_question": (
            "Comparer Kelly et volatility targeting sans publier une synthese supportee "
            "quand la couverture documentaire approfondie reste insuffisante."
        ),
        "research_mandate": {
            "allowed_universe": (
                "Kelly",
                "volatility targeting",
                "portefeuille convexe documente",
            ),
            "horizon": "connaissances documentaires stables",
            "data_requirements": (
                "methodes",
                "preuves favorables",
                "preuves defavorables",
                "dependances",
                "limites",
                "zones non documentees",
            ),
            "exclusions": (
                "donnees de marche actuelles",
                "parametre de strategie invente",
            ),
            "language": "fr",
            "detail_level": "synthese approfondie multi-sources",
        },
        "requested_mode": "DEEP_RESEARCH",
        "requested_by_context": "CV",
        "idempotency_key": "INSUFFICIENT-DEEP-COVERAGE-M009-T007-ACCEPTANCE",
        "occurred_at": "2026-07-02T13:05:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def coverage_requirements():
    return (
        DeepCoverageRequirement(
            obligation_name="methodes",
            critical=True,
            required_polarity="ANY",
            requires_primary_source=True,
            reason_code="PRIMARY_SOURCE_MISSING",
            public_reason="Aucune source primaire admissible ne documente les methodes comparees.",
        ),
        DeepCoverageRequirement(
            obligation_name="preuves_favorables",
            critical=True,
            required_polarity="FAVORABLE",
            requires_primary_source=False,
            reason_code="FAVORABLE_EVIDENCE_MISSING",
            public_reason="Aucune preuve favorable admissible n'est disponible.",
        ),
        DeepCoverageRequirement(
            obligation_name="preuves_defavorables",
            critical=True,
            required_polarity="UNFAVORABLE",
            requires_primary_source=False,
            reason_code="UNFAVORABLE_EVIDENCE_MISSING",
            public_reason="Aucune preuve defavorable admissible ne couvre le mandat.",
        ),
        DeepCoverageRequirement(
            obligation_name="dependances",
            critical=True,
            required_polarity="ANY",
            requires_primary_source=False,
            reason_code="DEPENDENCY_COVERAGE_MISSING",
            public_reason="Les dependances documentaires ne sont pas couvertes.",
        ),
        DeepCoverageRequirement(
            obligation_name="limites",
            critical=False,
            required_polarity="ANY",
            requires_primary_source=False,
            reason_code="LIMIT_COVERAGE_MISSING",
            public_reason="Les limites documentaires doivent qualifier la synthese.",
        ),
        DeepCoverageRequirement(
            obligation_name="zones_non_documentees",
            critical=False,
            required_polarity="ANY",
            requires_primary_source=False,
            reason_code="DOCUMENTARY_ZONE_UNCOVERED",
            public_reason="Les zones non documentees doivent rester visibles dans la reponse.",
        ),
    )


# Given un plan approfondi exige preuves defavorables, sources primaires et zones non documentees.
repository, research_case_id = planned_deep_case_repository()
methodes = candidate_for(
    suffix="METHODES",
    obligations=("methodes", "dependances"),
    polarity="FAVORABLE",
    source_kind="SECONDARY",
    text="Une source secondaire compare les methodes sans source primaire.",
    content_seed=1,
    span_seed=5,
)
favorables = candidate_for(
    suffix="FAVORABLES",
    obligations=("preuves_favorables",),
    polarity="FAVORABLE",
    source_kind="SECONDARY",
    text="Une source secondaire favorable soutient volatility targeting.",
    content_seed=2,
    span_seed=6,
)
limites = candidate_for(
    suffix="LIMITES",
    obligations=("limites",),
    polarity="NEUTRAL",
    source_kind="SECONDARY",
    text="Une source secondaire borne la comparaison sans couvrir les zones non documentees.",
    content_seed=3,
    span_seed=7,
)
candidates = (methodes, favorables, limites)
claims = tuple(
    verified_claim_ref(
        suffix=candidate.evidence_ref.evidence_id.removeprefix("EVS-M009-T007-"),
        evidence=candidate.evidence_ref,
        canonical_text=candidate.source_text,
    )
    for candidate in candidates
)

# When la collecte ne couvre que des sources secondaires favorables et neutres.
result = DeclareInsufficientDeepCoverageHandler(
    research_case_repository=repository,
    citation_resolver=OpeningCitationResolver(),
).declare(
    DeclareInsufficientDeepCoverage(
        research_case_id=research_case_id,
        candidates=candidates,
        verified_claim_refs=claims,
        coverage_requirements=coverage_requirements(),
        decision_basis="COVERAGE_OBLIGATION_ASSESSMENT",
        coverage_policy_version="deep-evidence-coverage-m009-v1",
        diversification_policy_version="deep-evidence-diversification-m009-v1",
        occurred_at="2026-07-02T13:15:00Z",
    )
)

# Then RA publie INSUFFICIENT_EVIDENCE avec lacunes rattachees aux obligations, sans fallback ni statut SUPPORTED.
assert_equal(result.status, "INSUFFICIENT_EVIDENCE", "Le statut applicatif doit etre explicite.")
assert_equal(result.support_status, SupportStatus.INSUFFICIENT_EVIDENCE, "Le support public doit etre INSUFFICIENT_EVIDENCE.")
assert_equal(
    result.research_case.status,
    ResearchCaseStatus.INSUFFICIENT_EVIDENCE,
    "Le ResearchCase doit passer en terminal INSUFFICIENT_EVIDENCE.",
)
assert_equal(
    result.research_case.requested_mode,
    ResearchMode.DEEP_RESEARCH,
    "La recherche approfondie ne doit pas retomber vers le mode documentaire simple.",
)
assert_equal(
    result.coverage_evaluation.critical_missing_obligations,
    ("methodes", "preuves_defavorables"),
    "Les obligations critiques manquantes doivent rester distinguees.",
)
assert_equal(
    result.coverage_evaluation.qualified_obligations,
    ("zones_non_documentees",),
    "Une obligation non critique manquante doit qualifier la sortie.",
)
assert_equal(
    tuple(gap.affected_obligation for gap in result.knowledge_gaps),
    ("methodes", "preuves_defavorables", "zones_non_documentees"),
    "Chaque lacune doit etre rattachee a son obligation.",
)
assert_equal(
    tuple(gap.gap_type for gap in result.knowledge_gaps),
    (
        KnowledgeGapType.COVERAGE_OBLIGATION_MISSING,
        KnowledgeGapType.COVERAGE_OBLIGATION_MISSING,
        KnowledgeGapType.COVERAGE_OBLIGATION_MISSING,
    ),
    "La couverture documentaire insuffisante ne doit pas devenir CURRENT_DATA_REQUIRED.",
)
assert_false(
    any(gap.reason_code == "CURRENT_DATA_REQUIRED" for gap in result.knowledge_gaps),
    "CURRENT_DATA_REQUIRED doit rester separe de la couverture documentaire insuffisante.",
)
assert_true(
    all(gap.public_reason for gap in result.knowledge_gaps),
    "Chaque lacune doit porter une raison publique.",
)
assert_equal(
    tuple(event.event_type for event in result.events),
    (
        "EvidenceCollectionCompleted",
        "EvidenceSetSealed",
        "KnowledgeGapRecorded",
        "KnowledgeGapRecorded",
        "KnowledgeGapRecorded",
        "ResearchEvidenceFoundInsufficient",
    ),
    "La declaration doit publier les evenements utiles de collecte, scellement et insuffisance.",
)
terminal_payload = result.events[-1].to_payload()["payload"]
assert_equal(
    terminal_payload["support_status"],
    "INSUFFICIENT_EVIDENCE",
    "L'evenement terminal doit exposer le statut de support public.",
)
assert_equal(
    terminal_payload["public_reasons"],
    tuple(gap.public_reason for gap in result.knowledge_gaps),
    "L'evenement terminal doit exposer les raisons publiques des lacunes.",
)
for event, gap in zip(result.events[2:5], result.knowledge_gaps, strict=True):
    assert_equal(
        event.to_payload()["payload"]["public_reason"],
        gap.public_reason,
        "KnowledgeGapRecorded doit exposer la raison publique de la lacune.",
    )
assert_raises(
    "support_status SUPPORTED interdit",
    lambda: result.research_case.ensure_support_status_allowed(SupportStatus.SUPPORTED),
)
result.research_case.ensure_support_status_allowed(SupportStatus.PARTIALLY_SUPPORTED)
assert_true(
    all(candidate.source_kind == "SECONDARY" for candidate in candidates),
    "Le scenario doit rester limite a des sources secondaires.",
)

print("Test d'acceptation T-007 couverture approfondie insuffisante M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_insufficient_deep_coverage_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 couverture approfondie insuffisante M-009: OK"
