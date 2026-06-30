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
    ExtractClaimsFromEvidenceCommand,
    ExtractClaimsFromEvidenceHandler,
)
from app.evidence_governance.domain.claim_extraction import DraftClaimStatus, EvidenceCandidate


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M006-T003-ACCEPTANCE",
            "document_id": "DOC-M006-T003-ACCEPTANCE",
            "canonical_version_id": "CVER-M006-T003-ACCEPTANCE-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 4,
            "accepted_at": "2026-06-29T10:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t003-v1",
        }
    )


def locator_for(text):
    ref = canonical_ref()
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": 2,
            "item_id": "DOC-M006-T003-ACCEPTANCE-P002-I001",
            "bbox": (0.10, 0.18, 0.84, 0.36),
            "content_hash": content_hash_for(text),
        },
        validation_policy=SourceLocatorValidationPolicy(
            canonical_sources_by_version_id={ref.canonical_version_id: ref},
            version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
            resolvable_item_ids_by_version_id={
                ref.canonical_version_id: {
                    "DOC-M006-T003-ACCEPTANCE-P002-I001": content_hash_for(text),
                }
            },
        ),
    )


source_text = (
    "Dans les crises de volatilité, les couvertures de queue peuvent réduire le drawdown. "
    "Elles peuvent aussi augmenter le coût de portage. "
    "Limite: le résultat suppose une liquidité quotidienne."
)
source_locator = locator_for(source_text)
candidate = EvidenceCandidate(
    chunk_id="KCHK-M006-T003-ACCEPTANCE-001",
    text=source_text,
    source_locator=source_locator,
    content_hash=source_locator.content_hash,
)

extractor = DeterministicClaimExtractor(
    extractor_version="deterministic-claim-extractor-m006-t003-v1",
    proposals_by_chunk_id={
        candidate.chunk_id: (
            {
                "claim_type": "EMPIRICAL_EFFECT",
                "canonical_text": (
                    "Les couvertures de queue peuvent réduire le drawdown dans les crises de volatilité "
                    "si la liquidité est quotidienne."
                ),
                "source_text": "les couvertures de queue peuvent réduire le drawdown",
                "scope": {
                    "universe": "portefeuille avec couvertures de queue",
                    "horizon": "crises de volatilité",
                    "metric": "drawdown",
                    "frequency": "quotidienne",
                },
                "conditions": ("liquidité quotidienne",),
                "limitations": ("résultat limité aux crises de volatilité citées par la preuve",),
                "evidence_span": {
                    "quoted_text": "les couvertures de queue peuvent réduire le drawdown",
                    "start_char": 33,
                    "end_char": 90,
                },
            },
            {
                "claim_type": "EMPIRICAL_EFFECT",
                "canonical_text": (
                    "Les couvertures de queue peuvent augmenter le coût de portage dans les crises de volatilité "
                    "si la liquidité est quotidienne."
                ),
                "source_text": "Elles peuvent aussi augmenter le coût de portage",
                "scope": {
                    "universe": "portefeuille avec couvertures de queue",
                    "horizon": "crises de volatilité",
                    "metric": "coût de portage",
                    "frequency": "quotidienne",
                },
                "conditions": ("liquidité quotidienne",),
                "limitations": ("résultat limité aux crises de volatilité citées par la preuve",),
                "evidence_span": {
                    "quoted_text": "Elles peuvent aussi augmenter le coût de portage",
                    "start_char": 92,
                    "end_char": 140,
                },
            },
        )
    },
)
repository = InMemoryClaimDraftRepository.empty()
handler = ExtractClaimsFromEvidenceHandler(
    extractor=extractor,
    draft_repository=repository,
)

# Given un passage source publié contient deux conclusions et une limitation explicite.
command = ExtractClaimsFromEvidenceCommand(
    evidence_candidates=(candidate,),
    extraction_schema_version="claim-extraction-m006-t003-v1",
    requested_by_context="EG",
    idempotency_key="CLAIM-EXTRACTION-M006-T003-ACCEPTANCE-0001",
    occurred_at="2026-06-29T10:30:00Z",
)

# When EG extrait les claims candidats.
result = handler.extract(command)

# Then deux claims DRAFT atomiques sont créés avec portée, limitation et span, sans statut VERIFIED.
assert_equal(result.status, "CLAIM_EXTRACTION_ACCEPTED", "L'extraction doit être acceptée explicitement.")
assert_equal(len(result.draft_claims), 2, "Deux claims atomiques doivent être créés.")
assert_equal(repository.draft_count(), 2, "Les brouillons doivent être enregistrés dans le repository EG.")
assert_equal(tuple(event.event_type for event in result.events), ("ClaimDrafted", "ClaimDrafted"), "Chaque brouillon doit publier ClaimDrafted.")
assert_equal(tuple(draft.status for draft in result.draft_claims), (DraftClaimStatus.DRAFT, DraftClaimStatus.DRAFT), "Les claims extraits doivent rester DRAFT.")
assert_equal(tuple(draft.claim_version for draft in result.draft_claims), (1, 1), "Chaque brouillon démarre à la version métier 1.")
assert_true(result.draft_claims[0].claim_id.startswith("CLM-"), "Un identifiant de claim EG doit être créé.")
assert_true(result.draft_claims[1].claim_id.startswith("CLM-"), "Un identifiant de claim EG doit être créé.")
assert_false(result.draft_claims[0].claim_id == result.draft_claims[1].claim_id, "Deux conclusions produisent deux claims distincts.")
assert_true("peuvent réduire" in result.draft_claims[0].canonical_proposition.text, "La modalité du premier claim doit être conservée.")
assert_true("peuvent augmenter" in result.draft_claims[1].canonical_proposition.text, "La modalité du second claim doit être conservée.")
assert_equal(tuple(condition.text for condition in result.draft_claims[0].conditions), ("liquidité quotidienne",), "La condition explicite doit être conservée.")
assert_equal(tuple(limitation.text for limitation in result.draft_claims[1].limitations), ("résultat limité aux crises de volatilité citées par la preuve",), "La limitation doit être conservée.")
assert_equal(result.draft_claims[0].scope.metric, "drawdown", "La portée doit conserver la métrique du premier claim.")
assert_equal(result.draft_claims[1].scope.metric, "coût de portage", "La portée doit conserver la métrique du second claim.")
assert_equal(result.draft_claims[0].evidence_span.source_locator.content_hash, source_locator.content_hash, "Le span doit rester rattaché au SourceLocator publié.")
assert_equal(result.draft_claims[1].evidence_span.quoted_span_hash, content_hash_for("Elles peuvent aussi augmenter le coût de portage"), "Le hash de span doit être dérivé du texte cité.")

for draft in result.draft_claims:
    payload = draft.to_payload()
    assert_equal(payload["status"], "DRAFT", "Aucun brouillon extrait ne doit être vérifié.")
    assert_false("verification_id" in payload, "L'extracteur ne doit pas créer de vérification.")
    assert_false("verified_claim_ref" in payload, "L'extracteur ne doit pas publier de VerifiedClaimRef.")
    assert_true(payload["evidence_span"]["source_locator"]["item_id"] == source_locator.item_id, "Le span source doit être publié.")

event_payloads = tuple(event.to_payload() for event in result.events)
assert_equal(event_payloads[0]["payload"]["extractor_version"], "deterministic-claim-extractor-m006-t003-v1", "La version d'extracteur doit être tracée.")
assert_false("Les couvertures de queue peuvent réduire" in repr(event_payloads[0]), "L'événement ne doit pas stocker le texte complet du claim.")

print("Test d'acceptation T-003 extraction claims atomiques M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_extraction_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 extraction claims atomiques M-006: OK"
