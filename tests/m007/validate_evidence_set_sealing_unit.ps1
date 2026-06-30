$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from dataclasses import dataclass

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
    CollectEvidenceCommand,
    CollectEvidenceHandler,
    SealEvidenceSetCommand,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.evidence_set import (
    EvidenceCoveragePolicy,
    EvidenceDiversificationPolicy,
)
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
CONTENT_HASH = "3" * 64
SECOND_CONTENT_HASH = "4" * 64
SPAN_HASH = "5" * 64
SECOND_SPAN_HASH = "6" * 64


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
        canonical_source_id="CSRC-M007-T004-UNIT",
        document_id="DOC-M007-T004-UNIT",
        canonical_version_id="CVER-M007-T004-UNIT",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=4,
        accepted_at="2026-06-30T10:00:00Z",
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
                "item-m007-t004-unit-primary": CONTENT_HASH,
                "item-m007-t004-unit-secondary": SECOND_CONTENT_HASH,
            },
        },
    )


def source_locator(*, item_id="item-m007-t004-unit-primary", content_hash=CONTENT_HASH):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T004-UNIT",
            "document_id": "DOC-M007-T004-UNIT",
            "page_pdf": 2,
            "item_id": item_id,
            "bbox": [0.2, 0.2, 0.7, 0.7],
            "content_hash": content_hash,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref_for(locator, *, evidence_id="EVS-M007-T004-UNIT-0001", quoted_span_hash=SPAN_HASH):
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


def verified_claim_ref_for(
    evidence_ref,
    *,
    claim_id="CLM-M007-T004-UNIT-0001",
    dependency_group_id="DEP-M007-T004-UNIT-PRIMARY",
):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": claim_id,
            "claim_version": 1,
            "canonical_text": "Une réponse vérifiée utilise seulement des preuves ouvrables.",
            "scope": {"instrument": "portfolio", "horizon": "documentary"},
            "status": "VERIFIED",
            "verification_id": "VER-M007-T004-UNIT-0001",
            "evidence_refs": [evidence_ref.to_payload()],
            "dependency_group_ids": [dependency_group_id],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def candidate_for(
    evidence_ref,
    *,
    source_text="Passage documentaire retenu pour la réponse.",
    covered_obligations=("preuves_documentaires",),
):
    return CandidateEvidence(
        evidence_ref=evidence_ref,
        source_text=source_text,
        search_trace_id="STRC-M007T004UNIT00000000000000000001",
        document_id=evidence_ref.source_locator.document_id,
        covered_obligations=covered_obligations,
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


class FailingCitationResolver:
    def resolve(self, citation):
        raise ValueError("source_locator non resolvable")


class DirectQdrantSearch:
    def __init__(self):
        self.qdrant_collection = "knowledge_access"

    def search(self, request):
        return ()


class DirectEgRepositoryCatalog:
    def __init__(self):
        self.claim_repository = object()

    def verified_claims_for_evidence(self, evidence_refs):
        return ()


@dataclass(frozen=True)
class EvidenceWithoutLocator:
    evidence_id: str = "EVS-M007-T004-UNIT-NO-LOCATOR"
    source_locator: object = None
    quoted_span_hash: str = SPAN_HASH


@dataclass(frozen=True)
class UnverifiedClaimRef:
    claim_id: str
    status: str
    evidence_refs: tuple


def planned_case_repository(*, idempotency_key="COLLECT-EVIDENCE-M007-T004-UNIT"):
    payload = {
        "resolved_question": "Quels éléments documentaires peuvent être cités ?",
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
        "idempotency_key": idempotency_key,
        "occurred_at": "2026-06-30T10:15:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


def handler_for(repository, *, candidates, claims, citation_resolver=None):
    return CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch(candidates),
        verified_claim_catalog=FakeVerifiedClaimCatalog(claims),
        citation_resolver=citation_resolver or OpeningCitationResolver(),
    )


def collect_command(research_case_id):
    return CollectEvidenceCommand(
        research_case_id=research_case_id,
        coverage_obligations=("preuves_documentaires",),
        occurred_at="2026-06-30T10:20:00Z",
    )


def seal_command(research_case_id, evidence_set_id):
    return SealEvidenceSetCommand(
        research_case_id=research_case_id,
        evidence_set_id=evidence_set_id,
        occurred_at="2026-06-30T10:21:00Z",
    )


primary_locator = source_locator()
primary_evidence = evidence_ref_for(primary_locator)
primary_candidate = candidate_for(primary_evidence)
primary_claim = verified_claim_ref_for(primary_evidence)

# Une preuve sans SourceLocator est refusée avant assemblage.
assert_raises(
    "source_locator absent",
    lambda: CandidateEvidence(
        evidence_ref=EvidenceWithoutLocator(),
        source_text="preuve sans locator",
        search_trace_id="STRC-M007T004UNIT00000000000000000002",
        document_id="DOC-M007-T004-UNIT",
        covered_obligations=("preuves_documentaires",),
    ),
)

# Les politiques RA refusent doublon et couverture incomplète.
assert_raises(
    "evidence_ref duplique",
    lambda: EvidenceDiversificationPolicy(policy_version="evidence-diversification-m007-v1").validate(
        (primary_candidate, primary_candidate)
    ),
)
assert_raises(
    "coverage_obligation non couverte",
    lambda: EvidenceCoveragePolicy(
        required_obligations=("preuves_documentaires",),
        policy_version="evidence-coverage-m007-v1",
    ).validate((candidate_for(primary_evidence, covered_obligations=("question_autonome",)),)),
)

# Les ports techniques directs vers Qdrant ou le repository EG sont refusés au montage du handler.
repository, research_case_id = planned_case_repository(idempotency_key="M007-T004-UNIT-QDRANT")
assert_raises(
    "acces direct Qdrant interdit",
    lambda: CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=DirectQdrantSearch(),
        verified_claim_catalog=FakeVerifiedClaimCatalog((primary_claim,)),
        citation_resolver=OpeningCitationResolver(),
    ),
)
assert_raises(
    "acces direct repository EG interdit",
    lambda: CollectEvidenceHandler(
        research_case_repository=repository,
        knowledge_search=FakeKnowledgeSearch((primary_candidate,)),
        verified_claim_catalog=DirectEgRepositoryCatalog(),
        citation_resolver=OpeningCitationResolver(),
    ),
)

# Un claim non vérifié ne peut pas sceller un jeu de preuves.
repository, research_case_id = planned_case_repository(idempotency_key="M007-T004-UNIT-UNVERIFIED")
handler = handler_for(
    repository,
    candidates=(primary_candidate,),
    claims=(UnverifiedClaimRef("CLM-M007-T004-UNIT-REJECTED", "REJECTED", (primary_evidence,)),),
)
assert_raises("claim non verifie", lambda: handler.collect(collect_command(research_case_id)))

# Une citation non ouvrable bloque le scellement.
repository, research_case_id = planned_case_repository(idempotency_key="M007-T004-UNIT-CITATION")
handler = handler_for(
    repository,
    candidates=(primary_candidate,),
    claims=(primary_claim,),
    citation_resolver=FailingCitationResolver(),
)
collected = handler.collect(collect_command(research_case_id))
assert_raises(
    "citation non resolvable",
    lambda: handler.seal(seal_command(research_case_id, collected.evidence_set.evidence_set_id)),
)

# Le scellement rend le jeu de preuves immuable et versionné.
repository, research_case_id = planned_case_repository(idempotency_key="M007-T004-UNIT-SEAL")
secondary_locator = source_locator(
    item_id="item-m007-t004-unit-secondary",
    content_hash=SECOND_CONTENT_HASH,
)
secondary_evidence = evidence_ref_for(
    secondary_locator,
    evidence_id="EVS-M007-T004-UNIT-0002",
    quoted_span_hash=SECOND_SPAN_HASH,
)
secondary_candidate = candidate_for(secondary_evidence)
secondary_claim = verified_claim_ref_for(
    secondary_evidence,
    claim_id="CLM-M007-T004-UNIT-0002",
    dependency_group_id="DEP-M007-T004-UNIT-SECONDARY",
)
handler = handler_for(
    repository,
    candidates=(primary_candidate, secondary_candidate),
    claims=(primary_claim, secondary_claim),
)
collected = handler.collect(collect_command(research_case_id))
sealed = handler.seal(seal_command(research_case_id, collected.evidence_set.evidence_set_id))
assert_equal(sealed.evidence_set.version.value, 1, "La version initiale doit être 1.")
assert_true(sealed.evidence_set.sealed, "Le jeu de preuves doit être scellé.")
assert_raises("evidence_set scelle", lambda: sealed.evidence_set.add_evidence(secondary_candidate))
assert_raises("cannot assign", lambda: setattr(sealed.evidence_set, "sealed", False))

print("Tests unitaires T-004 EvidenceSet scellé M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_evidence_set_sealing_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 EvidenceSet scellé M-007: OK"
