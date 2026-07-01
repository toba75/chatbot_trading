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
    CollectEvidenceCommand,
    CollectEvidenceHandler,
    SealEvidenceSetCommand,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.evidence_set import EvidenceSetSealed
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
)


SOURCE_HASH = "a" * 64
ARTIFACT_HASH = "b" * 64
CONTENT_HASH = "c" * 64
SPAN_HASH = "d" * 64


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


def canonical_source_ref():
    return CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M007-T004-ACCEPTANCE",
        document_id="DOC-M007-T004-ACCEPTANCE",
        canonical_version_id="CVER-M007-T004-ACCEPTANCE",
        source_sha256=SOURCE_HASH,
        canonical_artifact_sha256=ARTIFACT_HASH,
        page_count=3,
        accepted_at="2026-06-30T09:00:00Z",
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
            ref.canonical_version_id: {"item-m007-t004-acceptance": CONTENT_HASH},
        },
    )


def source_locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T004-ACCEPTANCE",
            "document_id": "DOC-M007-T004-ACCEPTANCE",
            "page_pdf": 1,
            "item_id": "item-m007-t004-acceptance",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": CONTENT_HASH,
        },
        validation_policy=source_locator_policy(),
    )


def evidence_ref(locator):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M007-T004-ACCEPTANCE-0001",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": SPAN_HASH,
        },
        source_locator_validation_policy=source_locator_policy(),
    )


def verified_claim_ref(locator):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": "CLM-M007-T004-ACCEPTANCE-0001",
            "claim_version": 1,
            "canonical_text": "La convexité documentaire exige une preuve ouvrable avant réponse.",
            "scope": {"instrument": "portfolio", "horizon": "documentary"},
            "status": "VERIFIED",
            "verification_id": "VER-M007-T004-ACCEPTANCE-0001",
            "evidence_refs": [evidence_ref(locator).to_payload()],
            "dependency_group_ids": ["DEP-M007-T004-ACCEPTANCE-PRIMARY"],
        },
        source_locator_validation_policy=source_locator_policy(),
    )


class FakeKnowledgeSearch:
    def __init__(self, candidates):
        self.candidates = tuple(candidates)
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return self.candidates


class FakeVerifiedClaimCatalog:
    def __init__(self, claims_by_evidence_id):
        self.claims_by_evidence_id = {
            evidence_id: tuple(claims)
            for evidence_id, claims in claims_by_evidence_id.items()
        }
        self.requests = []

    def verified_claims_for_evidence(self, evidence_refs):
        self.requests.append(tuple(evidence_refs))
        return tuple(
            claim
            for evidence_ref in evidence_refs
            for claim in self.claims_by_evidence_id.get(evidence_ref.evidence_id, ())
        )


class FakeCitationResolver:
    def __init__(self):
        self.resolved = []

    def resolve(self, citation):
        self.resolved.append(citation)
        return {"opened": citation.source_locator.item_id}


def planned_case_repository():
    payload = {
        "resolved_question": "Quelles preuves supportent une réponse documentaire vérifiée ?",
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
        "idempotency_key": "COLLECT-EVIDENCE-M007-T004-ACCEPTANCE-0001",
        "occurred_at": "2026-06-30T09:15:00Z",
    }
    repository = InMemoryResearchCaseRepository.empty()
    result = OpenResearchCaseHandler(
        research_case_repository=repository,
        planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
    ).open_and_plan(OpenResearchCaseCommand.from_payload(payload))
    return repository, result.research_case_id


# Given un cas de recherche PLANNED et des preuves candidates KA avec claims EG vérifiés.
locator = source_locator()
candidate = CandidateEvidence(
    evidence_ref=evidence_ref(locator),
    source_text="La preuve documentaire citée reste ouvrable et versionnée.",
    search_trace_id="STRC-M007T004ACCEPTANCE00000000000001",
    document_id=locator.document_id,
    covered_obligations=("preuves_documentaires",),
)
claim_ref = verified_claim_ref(locator)
case_repository, research_case_id = planned_case_repository()
knowledge_search = FakeKnowledgeSearch(candidates=(candidate,))
verified_claim_catalog = FakeVerifiedClaimCatalog(
    claims_by_evidence_id={candidate.evidence_ref.evidence_id: (claim_ref,)},
)
citation_resolver = FakeCitationResolver()
handler = CollectEvidenceHandler(
    research_case_repository=case_repository,
    knowledge_search=knowledge_search,
    verified_claim_catalog=verified_claim_catalog,
    citation_resolver=citation_resolver,
)

# When RA collecte puis scelle le jeu de preuves.
collected = handler.collect(
    CollectEvidenceCommand(
        research_case_id=research_case_id,
        coverage_obligations=("preuves_documentaires",),
        result_limit=2,
        occurred_at="2026-06-30T09:20:00Z",
    )
)
sealed = handler.seal(
    SealEvidenceSetCommand(
        research_case_id=research_case_id,
        evidence_set_id=collected.evidence_set.evidence_set_id,
        occurred_at="2026-06-30T09:21:00Z",
    )
)

# Then le jeu de preuves devient immuable, versionné, et chaque citation pointe vers un SourceLocator ouvrable.
assert_equal(sealed.status, "EVIDENCE_SET_SEALED", "Le scellement doit exposer un statut stable.")
assert_equal(sealed.evidence_set.version.value, 1, "La première version d'EvidenceSet doit être explicite.")
assert_true(sealed.evidence_set.sealed, "L'EvidenceSet doit être scellé.")
assert_equal(len(sealed.evidence_set.evidence_refs), 1, "La preuve admissible doit être retenue.")
assert_equal(len(sealed.evidence_set.verified_claim_refs), 1, "Le claim vérifié doit être retenu.")
assert_equal(len(sealed.evidence_set.citations), 1, "Chaque preuve publique doit publier une citation.")
assert_equal(
    sealed.evidence_set.citations[0].source_locator,
    locator,
    "La citation doit conserver le SourceLocator ouvrable.",
)
assert_equal(len(citation_resolver.resolved), 1, "Le resolver doit ouvrir la citation avant scellement.")
assert_equal(tuple(type(event) for event in sealed.events), (EvidenceSetSealed,), "L'événement de scellement doit être publié.")
assert_false(
    "qdrant" in repr(knowledge_search.requests).lower(),
    "RA ne doit pas exposer de détail Qdrant dans la requête de port KA.",
)
assert_false(
    "repository" in repr(verified_claim_catalog.requests).lower(),
    "RA ne doit pas lire le repository EG interne.",
)
assert_raises(
    "evidence_set scelle",
    lambda: sealed.evidence_set.add_evidence(candidate),
)

print("Test d'acceptation T-004 EvidenceSet scellé M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_evidence_set_sealing_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 EvidenceSet scellé M-007: OK"
