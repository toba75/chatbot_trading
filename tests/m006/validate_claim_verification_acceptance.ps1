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
from app.evidence_governance.application.verify_claim import (
    IndependentClaimVerifier,
    SubmitClaimForVerification,
    VerifyClaimHandler,
)
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


def canonical_ref(*, suffix):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M006-T005-ACCEPTANCE-{suffix}",
            "document_id": f"DOC-M006-T005-ACCEPTANCE-{suffix}",
            "canonical_version_id": f"CVER-M006-T005-ACCEPTANCE-{suffix}-0001",
            "source_sha256": "5" * 64,
            "canonical_artifact_sha256": "6" * 64,
            "page_count": 6,
            "accepted_at": "2026-06-29T14:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t005-v1",
        }
    )


def source_locator_policy(ref, *, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
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
        "page_pdf": 3,
        "item_id": item_id,
        "bbox": (0.14, 0.24, 0.86, 0.42),
        "content_hash": content_hash,
    }


def accepted_locator_for(text, *, suffix):
    ref = canonical_ref(suffix=suffix)
    item_id = f"DOC-M006-T005-ACCEPTANCE-{suffix}-P003-I001"
    content_hash = content_hash_for(text)
    policy = source_locator_policy(ref, item_id=item_id, content_hash=content_hash)
    return (
        SourceLocator.from_payload(
            locator_payload(ref, item_id=item_id, content_hash=content_hash),
            validation_policy=policy,
        ),
        policy,
    )


def draft_claim_for(source_text, source_locator, *, claim_id, scope=None):
    quoted_text = "les couvertures de queue réduisent le drawdown pendant les crises de volatilité"
    if scope is None:
        scope = ClaimScope(
            universe="portefeuille avec couvertures de queue",
            horizon="crises de volatilité",
            metric="drawdown",
            frequency="quotidienne",
        )
    return DraftClaim(
        claim_id=claim_id,
        claim_version=1,
        status=DraftClaimStatus.DRAFT,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue réduisent le drawdown pendant les crises de volatilité."
        ),
        scope=scope,
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
        extractor_version="deterministic-claim-extractor-m006-t005-v1",
    )


def evidence_ref_for(source_locator, validation_policy, *, evidence_id):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "source_locator": source_locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": content_hash_for("les couvertures de queue réduisent le drawdown pendant les crises de volatilité"),
        },
        source_locator_validation_policy=validation_policy,
    )


def attached_claim(*, suffix, claim_id, scope=None):
    source_text = (
        "les couvertures de queue réduisent le drawdown pendant les crises de volatilité. "
        "La conclusion dépend d'une mesure quotidienne."
    )
    source_locator, validation_policy = accepted_locator_for(source_text, suffix=suffix)
    draft = draft_claim_for(source_text, source_locator, claim_id=claim_id, scope=scope)
    claim = Claim.from_draft(draft)
    evidence_ref = evidence_ref_for(
        source_locator,
        validation_policy,
        evidence_id=f"EVS-M006-T005-ACCEPTANCE-{suffix}-0001",
    )
    reader = InMemoryCanonicalEvidenceReader(
        spans=(
            CanonicalEvidenceSpan(
                source_locator=source_locator,
                quoted_span_hash=evidence_ref.quoted_span_hash,
            ),
        )
    )
    repository = InMemoryClaimRepository(claims=(claim,))
    attached = AttachEvidenceToClaimHandler(
        claim_repository=repository,
        canonical_evidence_reader=reader,
    ).attach(
        AttachEvidenceToClaimCommand(
            claim_id=claim.claim_id,
            evidence_ref=evidence_ref,
            occurred_at="2026-06-29T14:10:00Z",
        )
    ).claim
    return attached, evidence_ref


class StubIndependentClaimVerifier:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def verify(self, *, claim, verification_case, policy_version, verifier_profile_id):
        self.calls.append(
            {
                "claim_status": claim.status,
                "verification_case_id": verification_case.verification_case_id,
                "policy_version": policy_version,
                "verifier_profile_id": verifier_profile_id,
            }
        )
        return self.report


def verified_report_for(claim, evidence_ref):
    return IndependentVerificationReport(
        verdict=VerificationVerdict.ENTAILED,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=("DEP-M006-T005-ACCEPTANCE-PRIMARY",),
        model_version="nli-verifier-m006-t005-v1",
        prompt_version="claim-verification-prompt-m006-t005-v1",
        policy_version="claim-verification-policy-m006-t005-v1",
        verifier_profile_id="independent-verifier-m006-t005",
        calibrated_score=0.97,
    )


def handler_for(claim, report):
    claim_repository = InMemoryClaimRepository(claims=(claim,))
    case_repository = InMemoryVerificationCaseRepository.empty()
    verifier = StubIndependentClaimVerifier(report)
    assert_true(isinstance(verifier, IndependentClaimVerifier), "Le double doit respecter le port IndependentClaimVerifier.")
    handler = VerifyClaimHandler(
        claim_repository=claim_repository,
        verification_case_repository=case_repository,
        verifier=verifier,
    )
    return handler, claim_repository, case_repository, verifier


def submit_command_for(claim, *, case_suffix):
    return SubmitClaimForVerification(
        claim_id=claim.claim_id,
        verification_case_id=f"VER-M006-T005-ACCEPTANCE-{case_suffix}",
        verification_policy_version="claim-verification-policy-m006-t005-v1",
        verifier_profile_id="independent-verifier-m006-t005",
        occurred_at="2026-06-29T14:30:00Z",
    )


# Given une affirmation EVIDENCE_ATTACHED avec une preuve directe admissible.
claim, evidence_ref = attached_claim(
    suffix="VERIFIED",
    claim_id="CLM-M006-T005-ACCEPTANCE-VERIFIED",
)
handler, claim_repository, case_repository, verifier = handler_for(
    claim,
    verified_report_for(claim, evidence_ref),
)

# When elle est soumise à vérification indépendante.
verified_result = handler.verify(submit_command_for(claim, case_suffix="VERIFIED"))

# Then UNDER_VERIFICATION est enregistré puis VERIFIED publie un VerifiedClaimRef contrôlé.
assert_equal(verified_result.status, "CLAIM_VERIFICATION_RECORDED", "La vérification doit être enregistrée explicitement.")
assert_equal(verifier.calls[0]["claim_status"], ClaimStatus.UNDER_VERIFICATION, "Le vérificateur doit recevoir un claim UNDER_VERIFICATION.")
assert_equal(verified_result.claim.status, ClaimStatus.VERIFIED, "Le claim doit devenir VERIFIED.")
assert_equal(claim_repository.claim_for_id(claim.claim_id).status, ClaimStatus.VERIFIED, "Le repository doit conserver l'état VERIFIED.")
assert_true(verified_result.verified_claim_ref is not None, "VerifiedClaimRef doit être publié pour un verdict admissible.")
assert_equal(verified_result.verified_claim_ref.status, "VERIFIED", "Le contrat publié doit porter le statut VERIFIED.")
assert_equal(verified_result.verified_claim_ref.verification_id, "VER-M006-T005-ACCEPTANCE-VERIFIED", "La référence publiée doit pointer vers la vérification.")
assert_equal(tuple(ref.evidence_id for ref in verified_result.verified_claim_ref.evidence_refs), (evidence_ref.evidence_id,), "Seules les preuves directes acceptées doivent être publiées.")
assert_equal(verified_result.verified_claim_ref.dependency_group_ids, ("DEP-M006-T005-ACCEPTANCE-PRIMARY",), "Les groupes de dépendance explicites doivent être conservés.")
assert_equal(
    tuple(event.event_type for event in verified_result.events),
    ("ClaimSubmittedForVerification", "VerificationDecisionRecorded", "ClaimVerified"),
    "Les événements de soumission, décision et vérification doivent être publiés.",
)
case = case_repository.case_for_id("VER-M006-T005-ACCEPTANCE-VERIFIED")
assert_equal(case.decision.model_version, "nli-verifier-m006-t005-v1", "La version de modèle doit être enregistrée.")
assert_equal(case.decision.prompt_version, "claim-verification-prompt-m006-t005-v1", "La version de prompt doit être enregistrée.")
assert_equal(case.decision.policy_version, "claim-verification-policy-m006-t005-v1", "La version de politique doit être enregistrée.")

# Given une affirmation marquée EVIDENCE_ATTACHED mais sans preuve directe admissible.
source_text = "Un claim ne peut pas être vérifié sans preuve directe."
source_locator, _ = accepted_locator_for(source_text, suffix="NOEVIDENCE")
draft_without_evidence = draft_claim_for(
    source_text,
    source_locator,
    claim_id="CLM-M006-T005-ACCEPTANCE-NOEVIDENCE",
)
claim_without_evidence = Claim(
    claim_id=draft_without_evidence.claim_id,
    claim_version=1,
    status=ClaimStatus.EVIDENCE_ATTACHED,
    claim_type=draft_without_evidence.claim_type,
    canonical_proposition=draft_without_evidence.canonical_proposition,
    scope=draft_without_evidence.scope,
    conditions=draft_without_evidence.conditions,
    limitations=draft_without_evidence.limitations,
    evidence_associations=(),
)
no_evidence_report = IndependentVerificationReport(
    verdict=VerificationVerdict.ENTAILED,
    reason_codes=(),
    accepted_evidence_ids=(),
    evidence_scopes={},
    dependency_group_ids=("DEP-M006-T005-ACCEPTANCE-NOEVIDENCE",),
    model_version="nli-verifier-m006-t005-v1",
    prompt_version="claim-verification-prompt-m006-t005-v1",
    policy_version="claim-verification-policy-m006-t005-v1",
    verifier_profile_id="independent-verifier-m006-t005",
    calibrated_score=0.99,
)
handler, claim_repository, case_repository, _ = handler_for(claim_without_evidence, no_evidence_report)

# When la vérification est demandée.
rejected_without_evidence = handler.verify(submit_command_for(claim_without_evidence, case_suffix="NOEVIDENCE"))

# Then le claim passe par UNDER_VERIFICATION, ne devient pas VERIFIED et conserve la raison publique.
assert_equal(rejected_without_evidence.claim.status, ClaimStatus.REJECTED, "Le claim sans preuve directe doit être rejeté.")
assert_true(rejected_without_evidence.verified_claim_ref is None, "Aucun VerifiedClaimRef ne doit être publié sans preuve directe.")
assert_true(ReasonCode.INSUFFICIENT_DIRECT_EVIDENCE in rejected_without_evidence.verification_case.decision.reason_codes, "La raison INSUFFICIENT_DIRECT_EVIDENCE doit être enregistrée.")
assert_equal(
    tuple(event.event_type for event in rejected_without_evidence.events),
    ("ClaimSubmittedForVerification", "VerificationDecisionRecorded", "ClaimRejected"),
    "Le rejet doit rester explicite et observable.",
)
assert_raises(
    "transition claim interdite: REJECTED",
    lambda: handler.verify(submit_command_for(rejected_without_evidence.claim, case_suffix="REOPEN")),
)

# Given une preuve directe dont la portée est plus étroite que le claim.
broader_scope = ClaimScope(
    universe="tous les portefeuilles multi-actifs",
    horizon="toutes les crises de volatilité",
    metric="drawdown",
    frequency="quotidienne",
)
wide_claim, wide_evidence_ref = attached_claim(
    suffix="SCOPE",
    claim_id="CLM-M006-T005-ACCEPTANCE-SCOPE",
    scope=broader_scope,
)
narrow_scope = ClaimScope(
    universe="portefeuille avec couvertures de queue",
    horizon="crises de volatilité américaines",
    metric="drawdown",
    frequency="quotidienne",
)
partial_report = IndependentVerificationReport(
    verdict=VerificationVerdict.PARTIALLY_ENTAILED,
    reason_codes=(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE,),
    accepted_evidence_ids=(wide_evidence_ref.evidence_id,),
    evidence_scopes={wide_evidence_ref.evidence_id: narrow_scope.to_payload()},
    dependency_group_ids=("DEP-M006-T005-ACCEPTANCE-SCOPE",),
    model_version="nli-verifier-m006-t005-v1",
    prompt_version="claim-verification-prompt-m006-t005-v1",
    policy_version="claim-verification-policy-m006-t005-v1",
    verifier_profile_id="independent-verifier-m006-t005",
    calibrated_score=0.88,
)
handler, _, _, _ = handler_for(wide_claim, partial_report)

# When le verdict PARTIALLY_ENTAILED élargit la portée.
scope_result = handler.verify(submit_command_for(wide_claim, case_suffix="SCOPE"))

# Then la portée élargie est refusée et aucune référence vérifiée n'est publiée.
assert_equal(scope_result.claim.status, ClaimStatus.REJECTED, "Le verdict partiel ne doit pas vérifier une portée élargie.")
assert_true(scope_result.verified_claim_ref is None, "Aucun VerifiedClaimRef ne doit être publié quand la portée s'élargit.")
assert_true(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE in scope_result.verification_case.decision.reason_codes, "Le refus de portée doit être enregistré.")

print("Test d'acceptation T-005 vérification claim preuve directe M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_verification_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 vérification claim preuve directe M-006: OK"
