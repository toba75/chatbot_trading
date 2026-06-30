$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.adapters.in_memory_canonical_evidence_reader import InMemoryCanonicalEvidenceReader
from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.application.attach_evidence import (
    AttachEvidenceToClaimCommand,
    AttachEvidenceToClaimHandler,
)
from app.evidence_governance.domain.claim_evidence import (
    CanonicalEvidenceSpan,
    Claim,
    ClaimStatus,
)
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
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
    except ValueError as exc:
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
            "canonical_source_id": "CSRC-M006-T004-ACCEPTANCE",
            "document_id": "DOC-M006-T004-ACCEPTANCE",
            "canonical_version_id": "CVER-M006-T004-ACCEPTANCE-0001",
            "source_sha256": "1" * 64,
            "canonical_artifact_sha256": "2" * 64,
            "page_count": 5,
            "accepted_at": "2026-06-29T12:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t004-v1",
        }
    )


def source_locator_policy(ref, *, status, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: status},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )


def locator_payload(ref, *, item_id, content_hash):
    return {
        "schema_version": "1.0",
        "canonical_version_id": ref.canonical_version_id,
        "document_id": ref.document_id,
        "page_pdf": 2,
        "item_id": item_id,
        "bbox": (0.12, 0.22, 0.82, 0.40),
        "content_hash": content_hash,
    }


def accepted_locator_for(text):
    ref = canonical_ref()
    item_id = "DOC-M006-T004-ACCEPTANCE-P002-I001"
    content_hash = content_hash_for(text)
    policy = source_locator_policy(
        ref,
        status="ACCEPTED",
        item_id=item_id,
        content_hash=content_hash,
    )
    return (
        SourceLocator.from_payload(
            locator_payload(ref, item_id=item_id, content_hash=content_hash),
            validation_policy=policy,
        ),
        policy,
    )


def draft_claim_for(source_text, source_locator):
    quoted_text = "les couvertures de queue peuvent réduire le drawdown"
    return DraftClaim(
        claim_id="CLM-M006-T004-ACCEPTANCE-0001",
        claim_version=1,
        status=DraftClaimStatus.DRAFT,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue peuvent réduire le drawdown pendant les crises de volatilité."
        ),
        scope=ClaimScope(
            universe="portefeuille avec couvertures de queue",
            horizon="crises de volatilité",
            metric="drawdown",
            frequency="quotidienne",
        ),
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_span=EvidenceSpan(
            quoted_text=quoted_text,
            start_char=33,
            end_char=86,
            source_locator=source_locator,
            quoted_span_hash=content_hash_for(quoted_text),
        ),
        evidence_chunk_id="KCHK-M006-T004-ACCEPTANCE-001",
        extractor_version="deterministic-claim-extractor-m006-t004-v1",
    )


def evidence_ref_for(source_locator, validation_policy):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M006-T004-ACCEPTANCE-0001",
            "source_locator": source_locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": content_hash_for("les couvertures de queue peuvent réduire le drawdown"),
        },
        source_locator_validation_policy=validation_policy,
    )


source_text = (
    "Dans les crises de volatilité, les couvertures de queue peuvent réduire le drawdown. "
    "Le résultat dépend des coûts de portage."
)
source_locator, validation_policy = accepted_locator_for(source_text)
claim = Claim.from_draft(draft_claim_for(source_text, source_locator))
evidence_ref = evidence_ref_for(source_locator, validation_policy)
claim_repository = InMemoryClaimRepository(claims=(claim,))
canonical_evidence_reader = InMemoryCanonicalEvidenceReader(
    spans=(
        CanonicalEvidenceSpan(
            source_locator=source_locator,
            quoted_span_hash=evidence_ref.quoted_span_hash,
        ),
    )
)
handler = AttachEvidenceToClaimHandler(
    claim_repository=claim_repository,
    canonical_evidence_reader=canonical_evidence_reader,
)

# Given un claim DRAFT et une preuve candidate dont le SourceLocator pointe vers une version canonique publiée.
command = AttachEvidenceToClaimCommand(
    claim_id=claim.claim_id,
    evidence_ref=evidence_ref,
    occurred_at="2026-06-29T12:30:00Z",
)

# When la preuve est attachée avec la relation SUPPORTS_DIRECTLY.
result = handler.attach(command)

# Then le claim passe à EVIDENCE_ATTACHED et conserve le EvidenceRef complet avec son hash de span.
assert_equal(result.status, "CLAIM_EVIDENCE_ATTACHED", "L'attachement doit être accepté explicitement.")
assert_equal(result.claim.status, ClaimStatus.EVIDENCE_ATTACHED, "Le claim doit passer à EVIDENCE_ATTACHED.")
assert_equal(claim_repository.claim_for_id(claim.claim_id).status, ClaimStatus.EVIDENCE_ATTACHED, "Le repository EG doit conserver l'état attaché.")
assert_equal(len(result.claim.evidence_associations), 1, "Une association de preuve doit être créée.")
association = result.claim.evidence_associations[0]
assert_equal(association.evidence_ref, evidence_ref, "EvidenceRef doit être conservé sans mutation.")
assert_equal(association.relation, "SUPPORTS_DIRECTLY", "La relation directe doit être conservée explicitement.")
assert_equal(association.source_locator.content_hash, source_locator.content_hash, "Le SourceLocator complet doit être conservé.")
assert_equal(association.quoted_span_hash, evidence_ref.quoted_span_hash, "Le hash du span cité doit être conservé.")
assert_equal(len(result.events), 1, "Un événement de domaine doit être publié.")
event = result.events[0]
assert_equal(event.event_type, "EvidenceAttachedToClaim", "L'événement attendu doit être publié.")
event_payload = event.to_payload()
assert_equal(event_payload["payload"]["claim_id"], claim.claim_id, "L'événement doit identifier le claim.")
assert_equal(event_payload["payload"]["claim_version"], 1, "L'événement doit conserver la version de claim.")
assert_equal(event_payload["payload"]["evidence_ref"], evidence_ref.to_payload(), "L'événement doit porter EvidenceRef complet.")
assert_equal(event_payload["payload"]["evidence_relation"], "SUPPORTS_DIRECTLY", "L'événement doit porter la relation explicite.")
assert_false("verified_claim_ref" in repr(result.claim.to_payload()).lower(), "Attacher une preuve ne vérifie pas le claim.")

# Given une preuve candidate dont le SourceLocator pointe vers une version non publiée.
quarantined_ref = canonical_ref()
quarantined_text = "Cette preuve reste en quarantaine."
quarantined_hash = content_hash_for(quarantined_text)
quarantined_item_id = "DOC-M006-T004-ACCEPTANCE-P002-I999"

# When EG tente de construire la preuve publique.
# Then le localisateur non publié est refusé sans fallback vers une page voisine.
assert_raises(
    "Version canonique indisponible: QUARANTINED",
    lambda: SourceLocator.from_payload(
        locator_payload(
            quarantined_ref,
            item_id=quarantined_item_id,
            content_hash=quarantined_hash,
        ),
        validation_policy=source_locator_policy(
            quarantined_ref,
            status="QUARANTINED",
            item_id=quarantined_item_id,
            content_hash=quarantined_hash,
        ),
    ),
)

print("Test d'acceptation T-004 attachement preuve claim M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_evidence_attachment_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 attachement preuve claim M-006: OK"
