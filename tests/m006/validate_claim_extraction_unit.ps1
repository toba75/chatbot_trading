$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.adapters.deterministic_claim_extractor import DeterministicClaimExtractor
from app.evidence_governance.adapters.in_memory_claim_draft_repository import InMemoryClaimDraftRepository
from app.evidence_governance.application.extract_claims import (
    ClaimExtractor,
    ExtractClaimsFromEvidenceCommand,
    ExtractClaimsFromEvidenceHandler,
)
from app.evidence_governance.domain.claim_extraction import (
    ClaimAtomicityPolicy,
    ClaimCanonicalizationPolicy,
    ClaimCondition,
    EvidenceCandidate,
    ClaimExtractionProposal,
    ClaimScope,
    DraftClaim,
    DraftClaimStatus,
    EvidenceSpan,
    Limitation,
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


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M006-T003-UNIT",
            "document_id": "DOC-M006-T003-UNIT",
            "canonical_version_id": "CVER-M006-T003-UNIT-0001",
            "source_sha256": "d" * 64,
            "canonical_artifact_sha256": "e" * 64,
            "page_count": 3,
            "accepted_at": "2026-06-29T11:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t003-unit-v1",
        }
    )


def locator_for(text):
    ref = canonical_ref()
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": 1,
            "item_id": "DOC-M006-T003-UNIT-P001-I001",
            "bbox": (0.12, 0.16, 0.88, 0.34),
            "content_hash": content_hash_for(text),
        },
        validation_policy=SourceLocatorValidationPolicy(
            canonical_sources_by_version_id={ref.canonical_version_id: ref},
            version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
            resolvable_item_ids_by_version_id={
                ref.canonical_version_id: {
                    "DOC-M006-T003-UNIT-P001-I001": content_hash_for(text),
                }
            },
        ),
    )


def candidate_for(text):
    locator = locator_for(text)
    return EvidenceCandidate(
        chunk_id="KCHK-M006-T003-UNIT-001",
        text=text,
        source_locator=locator,
        content_hash=locator.content_hash,
    )


source_text = (
    "La couverture de queue peut réduire la perte extrême si la liquidité est quotidienne. "
    "Elle ne réduit pas le coût de portage."
)
candidate = candidate_for(source_text)
base_payload = {
    "claim_type": "EMPIRICAL_EFFECT",
    "canonical_text": "La couverture de queue peut réduire la perte extrême si la liquidité est quotidienne.",
    "source_text": "La couverture de queue peut réduire la perte extrême si la liquidité est quotidienne.",
    "scope": {
        "universe": "portefeuille avec couverture de queue",
        "horizon": "perte extrême",
        "metric": "perte extrême",
        "frequency": "quotidienne",
    },
    "conditions": ("liquidité quotidienne",),
    "limitations": ("portée limitée à la liquidité quotidienne",),
    "evidence_span": {
        "quoted_text": "La couverture de queue peut réduire la perte extrême si la liquidité est quotidienne.",
        "start_char": 0,
        "end_char": 80,
    },
}

# La proposition structurée refuse les champs absents ou ambigus.
proposal = ClaimExtractionProposal.from_payload(base_payload, evidence_candidate=candidate, extractor_version="extractor-unit-v1")
assert_equal(proposal.claim_type, "EMPIRICAL_EFFECT", "Le type de claim doit être explicite.")
assert_equal(proposal.scope.metric, "perte extrême", "La portée doit être structurée.")
assert_equal(tuple(condition.text for condition in proposal.conditions), ("liquidité quotidienne",), "La condition doit être structurée.")
assert_equal(tuple(limitation.text for limitation in proposal.limitations), ("portée limitée à la liquidité quotidienne",), "La limitation doit être structurée.")
assert_equal(proposal.evidence_span.quoted_span_hash, content_hash_for(base_payload["evidence_span"]["quoted_text"]), "Le hash de span doit être stable.")
assert_raises(
    "evidence_span absent",
    lambda: ClaimExtractionProposal.from_payload({key: value for key, value in base_payload.items() if key != "evidence_span"}, evidence_candidate=candidate, extractor_version="extractor-unit-v1"),
)
assert_raises(
    "canonical_text vide",
    lambda: ClaimExtractionProposal.from_payload({**base_payload, "canonical_text": ""}, evidence_candidate=candidate, extractor_version="extractor-unit-v1"),
)
assert_raises(
    "claim_type absent",
    lambda: ClaimExtractionProposal.from_payload({key: value for key, value in base_payload.items() if key != "claim_type"}, evidence_candidate=candidate, extractor_version="extractor-unit-v1"),
)
assert_raises(
    "quoted_text absent du texte source",
    lambda: ClaimExtractionProposal.from_payload({**base_payload, "evidence_span": {"quoted_text": "span absent", "start_char": 0, "end_char": 10}}, evidence_candidate=candidate, extractor_version="extractor-unit-v1"),
)

# Les objets-valeur refusent les états partiellement valides.
assert_raises("scope non objet", lambda: ClaimScope.from_payload("scope invalide"))
assert_raises("condition vide", lambda: ClaimCondition(""))
assert_raises("limitation vide", lambda: Limitation(""))
assert_raises("evidence_span invalide", lambda: EvidenceSpan.from_payload({"quoted_text": "La couverture", "start_char": 12, "end_char": 4}, evidence_candidate=candidate))
assert_raises(
    "evidence_span invalide",
    lambda: EvidenceSpan.from_payload(
        {"quoted_text": "La couverture", "start_char": 4, "end_char": 17},
        evidence_candidate=candidate,
    ),
)

# L'atomicité refuse les propositions composites.
ClaimAtomicityPolicy().ensure_atomic(proposal)
composite_payload = {
    **base_payload,
    "canonical_text": "La couverture de queue peut réduire la perte extrême et elle peut augmenter le coût de portage.",
    "source_text": "La couverture de queue peut réduire la perte extrême",
    "evidence_span": {
        "quoted_text": "La couverture de queue peut réduire la perte extrême",
        "start_char": 0,
        "end_char": 49,
    },
}
assert_raises(
    "claim non atomique",
    lambda: ClaimAtomicityPolicy().ensure_atomic(
        ClaimExtractionProposal.from_payload(composite_payload, evidence_candidate=candidate, extractor_version="extractor-unit-v1")
    ),
)

# La canonicalisation conserve négation, modalité, condition et limitation.
ClaimCanonicalizationPolicy().ensure_preserves_source_semantics(proposal)
assert_raises(
    "modalite perdue",
    lambda: ClaimCanonicalizationPolicy().ensure_preserves_source_semantics(
        ClaimExtractionProposal.from_payload({**base_payload, "canonical_text": "La couverture de queue réduit la perte extrême si la liquidité est quotidienne."}, evidence_candidate=candidate, extractor_version="extractor-unit-v1")
    ),
)
assert_raises(
    "condition perdue",
    lambda: ClaimCanonicalizationPolicy().ensure_preserves_source_semantics(
        ClaimExtractionProposal.from_payload({**base_payload, "canonical_text": "La couverture de queue peut réduire la perte extrême.", "conditions": ("liquidité quotidienne",)}, evidence_candidate=candidate, extractor_version="extractor-unit-v1")
    ),
)
negative_payload = {
    **base_payload,
    "canonical_text": "La couverture de queue réduit le coût de portage.",
    "source_text": "Elle ne réduit pas le coût de portage.",
    "evidence_span": {
        "quoted_text": "Elle ne réduit pas le coût de portage.",
        "start_char": 82,
        "end_char": 120,
    },
    "scope": {
        "universe": "portefeuille avec couverture de queue",
        "horizon": "coût de portage",
        "metric": "coût de portage",
        "frequency": "quotidienne",
    },
    "conditions": (),
}
assert_raises(
    "negation perdue",
    lambda: ClaimCanonicalizationPolicy().ensure_preserves_source_semantics(
        ClaimExtractionProposal.from_payload(negative_payload, evidence_candidate=candidate, extractor_version="extractor-unit-v1")
    ),
)

# Un DraftClaim reste un brouillon non vérifié et serialise uniquement le span source.
draft = DraftClaim.from_proposal(claim_id="CLM-M006-T003-UNIT-0001", proposal=proposal)
assert_equal(draft.status, DraftClaimStatus.DRAFT, "Un claim extrait doit rester DRAFT.")
draft_payload = draft.to_payload()
assert_equal(draft_payload["status"], "DRAFT", "Le payload doit rester DRAFT.")
assert_false("verification_id" in draft_payload, "Aucune vérification ne doit être créée à l'extraction.")
assert_false("verified_claim_ref" in draft_payload, "Aucun VerifiedClaimRef ne doit être créé à l'extraction.")
assert_true(draft_payload["evidence_span"]["quoted_span_hash"] == content_hash_for(base_payload["evidence_span"]["quoted_text"]), "Le span doit être auditables par hash.")

# Le port ClaimExtractor est utilisé par le handler sans auto-approval.
extractor = DeterministicClaimExtractor(
    extractor_version="extractor-unit-v1",
    proposals_by_chunk_id={candidate.chunk_id: (base_payload,)},
)
assert_true(isinstance(extractor, ClaimExtractor), "Le double déterministe doit respecter le port ClaimExtractor.")
repository = InMemoryClaimDraftRepository.empty()
handler = ExtractClaimsFromEvidenceHandler(extractor=extractor, draft_repository=repository)
result = handler.extract(
    ExtractClaimsFromEvidenceCommand(
        evidence_candidates=(candidate,),
        extraction_schema_version="claim-extraction-m006-t003-unit-v1",
        requested_by_context="EG",
        idempotency_key="CLAIM-EXTRACTION-M006-T003-UNIT-0001",
        occurred_at="2026-06-29T11:30:00Z",
    )
)
assert_equal(len(result.draft_claims), 1, "Le handler doit créer un brouillon.")
assert_equal(repository.draft_count(), 1, "Le repository de brouillons doit enregistrer le claim.")
assert_equal(result.events[0].event_type, "ClaimDrafted", "Le handler doit émettre ClaimDrafted.")
assert_false("verified" in repr(result.events[0].to_payload()).lower(), "ClaimDrafted ne doit pas auto-vérifier le claim.")
assert_raises(
    "extractor sans extract_claims",
    lambda: ExtractClaimsFromEvidenceHandler(extractor=object(), draft_repository=repository),
)
assert_raises(
    "evidence_candidates absents",
    lambda: ExtractClaimsFromEvidenceCommand(
        evidence_candidates=(),
        extraction_schema_version="claim-extraction-m006-t003-unit-v1",
        requested_by_context="EG",
        idempotency_key="CLAIM-EXTRACTION-M006-T003-UNIT-0002",
        occurred_at="2026-06-29T11:35:00Z",
    ),
)
assert_raises(
    "evidence_candidate invalide",
    lambda: ExtractClaimsFromEvidenceCommand(
        evidence_candidates=(object(),),
        extraction_schema_version="claim-extraction-m006-t003-unit-v1",
        requested_by_context="EG",
        idempotency_key="CLAIM-EXTRACTION-M006-T003-UNIT-0003",
        occurred_at="2026-06-29T11:36:00Z",
    ),
)

print("Tests unitaires T-003 extraction claims atomiques M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_extraction_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 extraction claims atomiques M-006: OK"
