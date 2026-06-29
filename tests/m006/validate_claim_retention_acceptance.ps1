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
from app.evidence_governance.adapters.in_memory_verification_case_repository import InMemoryVerificationCaseRepository
from app.evidence_governance.application.attach_evidence import AttachEvidenceToClaimCommand, AttachEvidenceToClaimHandler
from app.evidence_governance.application.retain_claims import SupersedeClaim, SupersedeClaimHandler
from app.evidence_governance.application.verify_claim import SubmitClaimForVerification, VerifyClaimHandler
from app.evidence_governance.domain.claim_evidence import CanonicalEvidenceSpan, Claim, ClaimStatus
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    DraftClaim,
    DraftClaimStatus,
    EvidenceSpan,
    Limitation,
)
from app.evidence_governance.domain.claim_verification import (
    IndependentVerificationReport,
    ReasonCode,
    VerificationVerdict,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
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


def canonical_ref(*, suffix):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M006-T008-ACCEPTANCE-{suffix}",
            "document_id": f"DOC-M006-T008-ACCEPTANCE-{suffix}",
            "canonical_version_id": f"CVER-M006-T008-ACCEPTANCE-{suffix}-0001",
            "source_sha256": "9" * 64,
            "canonical_artifact_sha256": "a" * 64,
            "page_count": 4,
            "accepted_at": "2026-06-29T20:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t008-v1",
        }
    )


def locator_for(text, *, suffix):
    ref = canonical_ref(suffix=suffix)
    item_id = f"DOC-M006-T008-ACCEPTANCE-{suffix}-P002-I001"
    content_hash = content_hash_for(text)
    policy = SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )
    return (
        SourceLocator.from_payload(
            {
                "schema_version": "1.0",
                "canonical_version_id": ref.canonical_version_id,
                "document_id": ref.document_id,
                "page_pdf": 2,
                "item_id": item_id,
                "bbox": (0.12, 0.22, 0.82, 0.36),
                "content_hash": content_hash,
            },
            validation_policy=policy,
        ),
        policy,
    )


def scope_for():
    return ClaimScope(
        universe="portefeuilles convexes avec couverture de queue",
        horizon="crises de volatilité",
        metric="drawdown",
        frequency="quotidienne",
    )


def draft_claim_for(source_locator, *, claim_id, text):
    quoted_text = "les couvertures de queue réduisent le drawdown pendant les crises"
    return DraftClaim(
        claim_id=claim_id,
        claim_version=1,
        status=DraftClaimStatus.DRAFT,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(text),
        scope=scope_for(),
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_span=EvidenceSpan(
            quoted_text=quoted_text,
            start_char=0,
            end_char=len(quoted_text),
            source_locator=source_locator,
            quoted_span_hash=content_hash_for(quoted_text),
        ),
        evidence_chunk_id=f"KCHK-{claim_id[4:]}-001",
        extractor_version="deterministic-claim-extractor-m006-t008-v1",
    )


def evidence_ref_for(source_locator, validation_policy, *, suffix):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M006-T008-ACCEPTANCE-{suffix}-0001",
            "source_locator": source_locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": content_hash_for("les couvertures de queue réduisent le drawdown pendant les crises"),
        },
        source_locator_validation_policy=validation_policy,
    )


def attached_claim(*, suffix, claim_id, text):
    source_text = (
        "les couvertures de queue réduisent le drawdown pendant les crises. "
        "La conclusion reste bornée à la fenêtre de volatilité."
    )
    source_locator, validation_policy = locator_for(source_text, suffix=suffix)
    draft = draft_claim_for(source_locator, claim_id=claim_id, text=text)
    evidence_ref = evidence_ref_for(source_locator, validation_policy, suffix=suffix)
    reader = InMemoryCanonicalEvidenceReader(
        spans=(
            CanonicalEvidenceSpan(
                source_locator=source_locator,
                quoted_span_hash=evidence_ref.quoted_span_hash,
            ),
        )
    )
    repository = InMemoryClaimRepository(claims=(Claim.from_draft(draft),))
    claim = AttachEvidenceToClaimHandler(
        claim_repository=repository,
        canonical_evidence_reader=reader,
    ).attach(
        AttachEvidenceToClaimCommand(
            claim_id=claim_id,
            evidence_ref=evidence_ref,
            occurred_at="2026-06-29T20:10:00Z",
        )
    ).claim
    return claim, evidence_ref


class StubVerifier:
    def __init__(self, report):
        self.report = report

    def verify(self, *, claim, verification_case, policy_version, verifier_profile_id):
        return self.report


def verified_report_for(claim, evidence_ref):
    return IndependentVerificationReport(
        verdict=VerificationVerdict.ENTAILED,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=("DEP-M006-T008-ACCEPTANCE-PRIMARY",),
        model_version="nli-verifier-m006-t008-v1",
        prompt_version="claim-verification-prompt-m006-t008-v1",
        policy_version="claim-verification-policy-m006-t008-v1",
        verifier_profile_id="independent-verifier-m006-t008",
        calibrated_score=0.96,
    )


def rejection_report():
    return IndependentVerificationReport(
        verdict=VerificationVerdict.NOT_ENTAILED,
        reason_codes=(ReasonCode.INSUFFICIENT_DIRECT_EVIDENCE,),
        accepted_evidence_ids=(),
        evidence_scopes={},
        dependency_group_ids=("DEP-M006-T008-ACCEPTANCE-REJECTED",),
        model_version="nli-verifier-m006-t008-v1",
        prompt_version="claim-verification-prompt-m006-t008-v1",
        policy_version="claim-verification-policy-m006-t008-v1",
        verifier_profile_id="independent-verifier-m006-t008",
        calibrated_score=0.21,
    )


def verify_claim(claim, report, *, case_suffix):
    repository = InMemoryClaimRepository(claims=(claim,))
    handler = VerifyClaimHandler(
        claim_repository=repository,
        verification_case_repository=InMemoryVerificationCaseRepository.empty(),
        verifier=StubVerifier(report),
    )
    result = handler.verify(
        SubmitClaimForVerification(
            claim_id=claim.claim_id,
            verification_case_id=f"VER-M006-T008-ACCEPTANCE-{case_suffix}",
            verification_policy_version="claim-verification-policy-m006-t008-v1",
            verifier_profile_id="independent-verifier-m006-t008",
            occurred_at="2026-06-29T20:20:00Z",
        )
    )
    return result, repository


# Given un claim vérifié possède une preuve directe et une version publiée.
attached, evidence_ref = attached_claim(
    suffix="SUPERSEDED",
    claim_id="CLM-M006-T008-ACCEPTANCE-SUPERSEDED",
    text="Les couvertures de queue réduisent le drawdown pendant les crises de volatilité.",
)
verified_result, _ = verify_claim(
    attached,
    verified_report_for(attached, evidence_ref),
    case_suffix="SUPERSEDED",
)
claim_repository = InMemoryClaimRepository(claims=(verified_result.claim,))

# When une meilleure formulation le supersède.
superseded = SupersedeClaimHandler(claim_repository=claim_repository).supersede(
    SupersedeClaim(
        superseded_claim_id=verified_result.claim.claim_id,
        superseded_claim_version=1,
        superseding_claim_version=2,
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue réduisent le drawdown quotidien pendant les crises de volatilité."
        ),
        scope=verified_result.claim.scope,
        conditions=verified_result.claim.conditions,
        limitations=verified_result.claim.limitations,
        supersession_reason="Formulation précisée sans effacer la version vérifiée.",
        occurred_at="2026-06-29T20:30:00Z",
    )
)

# Then l'ancien claim reste consultable avec sa décision et pointe explicitement vers la nouvelle version.
old_version = claim_repository.claim_for_version(verified_result.claim.claim_id, 1)
new_version = claim_repository.claim_for_version(verified_result.claim.claim_id, 2)
assert_equal(superseded.status, "CLAIM_SUPERSEDED", "La supersession doit être enregistrée explicitement.")
assert_equal(old_version.status, ClaimStatus.SUPERSEDED, "L'ancienne version doit devenir SUPERSEDED.")
assert_equal(old_version.superseded_by.claim_version, 2, "L'ancienne version doit pointer vers la nouvelle version.")
assert_equal(old_version.verified_claim_ref.verification_id, "VER-M006-T008-ACCEPTANCE-SUPERSEDED", "La décision vérifiée doit rester consultable.")
assert_equal(new_version.claim_version, 2, "La nouvelle version doit être conservée séparément.")
assert_equal(claim_repository.claim_for_id(verified_result.claim.claim_id).claim_version, 2, "La lecture courante doit pointer vers la dernière version.")
assert_equal(
    tuple(event.event_type for event in superseded.events),
    ("ClaimSuperseded",),
    "La supersession doit publier ClaimSuperseded.",
)
assert_raises(
    "suppression claim interdite",
    lambda: claim_repository.delete_claim_version(old_version.claim_id, old_version.claim_version),
)

# Given un claim rejeté par la politique de vérification.
rejected_candidate = Claim(
    claim_id="CLM-M006-T008-ACCEPTANCE-REJECTED",
    claim_version=1,
    status=ClaimStatus.EVIDENCE_ATTACHED,
    claim_type=attached.claim_type,
    canonical_proposition=CanonicalProposition("Une affirmation sans preuve directe doit être refusée."),
    scope=attached.scope,
    conditions=attached.conditions,
    limitations=attached.limitations,
    evidence_associations=(),
)
rejected_result, rejected_repository = verify_claim(
    rejected_candidate,
    rejection_report(),
    case_suffix="REJECTED",
)

# When la version rejetée est relue.
rejected_version = rejected_repository.claim_for_version(rejected_candidate.claim_id, 1)

# Then elle reste consultable avec sa raison et ne peut pas être supprimée ordinairement.
assert_equal(rejected_version.status, ClaimStatus.REJECTED, "Le claim rejeté doit être conservé.")
assert_equal(
    rejected_version.rejection_reason_codes,
    ("INSUFFICIENT_DIRECT_EVIDENCE",),
    "La raison publique du rejet doit être conservée.",
)
assert_equal(
    tuple(event.event_type for event in rejected_result.events),
    ("ClaimSubmittedForVerification", "VerificationDecisionRecorded", "ClaimRejected"),
    "Le rejet doit publier ClaimRejected.",
)
assert_raises(
    "suppression claim interdite",
    lambda: rejected_repository.delete_claim_version(rejected_version.claim_id, rejected_version.claim_version),
)
assert_raises(
    "claim_decision immuable",
    lambda: rejected_repository.save(
        Claim(
            claim_id=rejected_version.claim_id,
            claim_version=rejected_version.claim_version,
            status=ClaimStatus.REJECTED,
            claim_type=rejected_version.claim_type,
            canonical_proposition=CanonicalProposition("Une proposition réécrite avec le même identifiant."),
            scope=rejected_version.scope,
            conditions=rejected_version.conditions,
            limitations=rejected_version.limitations,
            evidence_associations=rejected_version.evidence_associations,
            rejection_reason_codes=rejected_version.rejection_reason_codes,
            rejected_at=rejected_version.rejected_at,
        )
    ),
)

print("Test d'acceptation T-008 conservation claims rejetés et supersédés M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_retention_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 conservation claims rejetés et supersédés M-006: OK"
