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
    ClaimSubmittedForVerification,
    ClaimVerificationPolicy,
    IndependentVerificationReport,
    ReasonCode,
    ScopePreservationPolicy,
    VerificationCase,
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
            "canonical_source_id": "CSRC-M006-T005-UNIT",
            "document_id": "DOC-M006-T005-UNIT",
            "canonical_version_id": "CVER-M006-T005-UNIT-0001",
            "source_sha256": "7" * 64,
            "canonical_artifact_sha256": "8" * 64,
            "page_count": 5,
            "accepted_at": "2026-06-29T15:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t005-unit-v1",
        }
    )


def validation_policy_for(ref, *, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )


def locator_for(text):
    ref = canonical_ref()
    item_id = "DOC-M006-T005-UNIT-P002-I001"
    content_hash = content_hash_for(text)
    return (
        SourceLocator.from_payload(
            {
                "schema_version": "1.0",
                "canonical_version_id": ref.canonical_version_id,
                "document_id": ref.document_id,
                "page_pdf": 2,
                "item_id": item_id,
                "bbox": (0.18, 0.28, 0.78, 0.44),
                "content_hash": content_hash,
            },
            validation_policy=validation_policy_for(ref, item_id=item_id, content_hash=content_hash),
        ),
        validation_policy_for(ref, item_id=item_id, content_hash=content_hash),
    )


def draft_claim_for(source_locator, *, claim_id="CLM-M006-T005-UNIT-0001", scope=None):
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
        evidence_chunk_id="KCHK-M006-T005-UNIT-001",
        extractor_version="deterministic-claim-extractor-m006-t005-unit-v1",
    )


def evidence_ref_for(source_locator, validation_policy, *, evidence_id="EVS-M006-T005-UNIT-0001"):
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


def attached_claim():
    source_text = "les couvertures de queue réduisent le drawdown pendant les crises de volatilité."
    source_locator, validation_policy = locator_for(source_text)
    claim = Claim.from_draft(draft_claim_for(source_locator))
    evidence_ref = evidence_ref_for(source_locator, validation_policy)
    reader = InMemoryCanonicalEvidenceReader(
        spans=(
            CanonicalEvidenceSpan(
                source_locator=source_locator,
                quoted_span_hash=evidence_ref.quoted_span_hash,
            ),
        )
    )
    repository = InMemoryClaimRepository(claims=(claim,))
    return (
        AttachEvidenceToClaimHandler(
            claim_repository=repository,
            canonical_evidence_reader=reader,
        ).attach(
            AttachEvidenceToClaimCommand(
                claim_id=claim.claim_id,
                evidence_ref=evidence_ref,
                occurred_at="2026-06-29T15:05:00Z",
            )
        ).claim,
        evidence_ref,
    )


def entailed_report(claim, evidence_ref, *, score=0.91):
    return IndependentVerificationReport(
        verdict=VerificationVerdict.ENTAILED,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=("DEP-M006-T005-UNIT-PRIMARY",),
        model_version="nli-verifier-m006-t005-unit-v1",
        prompt_version="claim-verification-prompt-m006-t005-unit-v1",
        policy_version="claim-verification-policy-m006-t005-unit-v1",
        verifier_profile_id="independent-verifier-m006-t005-unit",
        calibrated_score=score,
    )


class StubVerifier:
    def __init__(self, report):
        self.report = report

    def verify(self, *, claim, verification_case, policy_version, verifier_profile_id):
        return self.report


claim, evidence_ref = attached_claim()
report = entailed_report(claim, evidence_ref)

# La commande de soumission exige un claim, un cas, une politique, un profil et un instant explicites.
command = SubmitClaimForVerification(
    claim_id=claim.claim_id,
    verification_case_id="VER-M006-T005-UNIT-0001",
    verification_policy_version="claim-verification-policy-m006-t005-unit-v1",
    verifier_profile_id="independent-verifier-m006-t005-unit",
    occurred_at="2026-06-29T15:10:00Z",
)
assert_raises(
    "verification_policy_version vide",
    lambda: SubmitClaimForVerification(
        claim_id=claim.claim_id,
        verification_case_id="VER-M006-T005-UNIT-0002",
        verification_policy_version="",
        verifier_profile_id="independent-verifier-m006-t005-unit",
        occurred_at="2026-06-29T15:10:00Z",
    ),
)

# La soumission refuse DRAFT -> UNDER_VERIFICATION.
draft_claim = Claim.from_draft(draft_claim_for(evidence_ref.source_locator, claim_id="CLM-M006-T005-UNIT-DRAFT"))
assert_raises(
    "transition claim interdite: DRAFT",
    lambda: VerifyClaimHandler(
        claim_repository=InMemoryClaimRepository(claims=(draft_claim,)),
        verification_case_repository=InMemoryVerificationCaseRepository.empty(),
        verifier=StubVerifier(report),
    ).verify(
        SubmitClaimForVerification(
            claim_id=draft_claim.claim_id,
            verification_case_id="VER-M006-T005-UNIT-DRAFT",
            verification_policy_version="claim-verification-policy-m006-t005-unit-v1",
            verifier_profile_id="independent-verifier-m006-t005-unit",
            occurred_at="2026-06-29T15:11:00Z",
        )
    ),
)

# L'événement de soumission porte uniquement l'identité, la version, le cas et la politique.
submitted_claim = Claim(
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    status=ClaimStatus.UNDER_VERIFICATION,
    claim_type=claim.claim_type,
    canonical_proposition=claim.canonical_proposition,
    scope=claim.scope,
    conditions=claim.conditions,
    limitations=claim.limitations,
    evidence_associations=claim.evidence_associations,
)
submitted_event = ClaimSubmittedForVerification.from_claim(
    claim=submitted_claim,
    verification_case_id="VER-M006-T005-UNIT-0001",
    policy_version="claim-verification-policy-m006-t005-unit-v1",
    occurred_at="2026-06-29T15:12:00Z",
)
assert_equal(submitted_event.event_type, "ClaimSubmittedForVerification", "L'événement de soumission doit être nommé.")
assert_equal(submitted_event.to_payload()["payload"]["verification_case_id"], "VER-M006-T005-UNIT-0001", "Le cas de vérification doit être publié.")
assert_false("canonical_text" in repr(submitted_event.to_payload()), "L'événement de soumission ne doit pas porter le texte complet.")

# Le rapport indépendant exige verdict, métadonnées modèle/prompt/politique et groupes de dépendance.
assert_raises(
    "verdict verification invalide",
    lambda: IndependentVerificationReport(
        verdict=None,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=("DEP-M006-T005-UNIT-PRIMARY",),
        model_version="nli-verifier-m006-t005-unit-v1",
        prompt_version="claim-verification-prompt-m006-t005-unit-v1",
        policy_version="claim-verification-policy-m006-t005-unit-v1",
        verifier_profile_id="independent-verifier-m006-t005-unit",
        calibrated_score=0.99,
    ),
)
assert_raises(
    "model_version vide",
    lambda: IndependentVerificationReport(
        verdict=VerificationVerdict.ENTAILED,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=("DEP-M006-T005-UNIT-PRIMARY",),
        model_version="",
        prompt_version="claim-verification-prompt-m006-t005-unit-v1",
        policy_version="claim-verification-policy-m006-t005-unit-v1",
        verifier_profile_id="independent-verifier-m006-t005-unit",
        calibrated_score=0.99,
    ),
)
assert_raises(
    "dependency_group_ids vides",
    lambda: IndependentVerificationReport(
        verdict=VerificationVerdict.ENTAILED,
        reason_codes=(),
        accepted_evidence_ids=(evidence_ref.evidence_id,),
        evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
        dependency_group_ids=(),
        model_version="nli-verifier-m006-t005-unit-v1",
        prompt_version="claim-verification-prompt-m006-t005-unit-v1",
        policy_version="claim-verification-policy-m006-t005-unit-v1",
        verifier_profile_id="independent-verifier-m006-t005-unit",
        calibrated_score=0.99,
    ),
)

# La politique de portée exige une correspondance explicite entre claim et preuve.
scope_policy = ScopePreservationPolicy()
scope_policy.ensure_scope_preserved(
    claim_scope=claim.scope,
    evidence_scopes=(claim.scope,),
)
assert_raises(
    "CLAIM_SCOPE_EXCEEDS_EVIDENCE",
    lambda: scope_policy.ensure_scope_preserved(
        claim_scope=claim.scope,
        evidence_scopes=(
            ClaimScope(
                universe="portefeuille différent",
                horizon=claim.scope.horizon,
                metric=claim.scope.metric,
                frequency=claim.scope.frequency,
            ),
        ),
    ),
)

# Un score élevé ne peut pas remplacer un verdict métier ENTAILED.
score_only_report = IndependentVerificationReport(
    verdict=VerificationVerdict.NOT_ENTAILED,
    reason_codes=(ReasonCode.VERDICT_NOT_AUTHORIZED,),
    accepted_evidence_ids=(evidence_ref.evidence_id,),
    evidence_scopes={evidence_ref.evidence_id: claim.scope.to_payload()},
    dependency_group_ids=("DEP-M006-T005-UNIT-PRIMARY",),
    model_version="nli-verifier-m006-t005-unit-v1",
    prompt_version="claim-verification-prompt-m006-t005-unit-v1",
    policy_version="claim-verification-policy-m006-t005-unit-v1",
    verifier_profile_id="independent-verifier-m006-t005-unit",
    calibrated_score=0.999,
)
decision = ClaimVerificationPolicy().decision_for(
    claim=claim,
    report=score_only_report,
    expected_policy_version="claim-verification-policy-m006-t005-unit-v1",
)
assert_equal(decision.target_status, ClaimStatus.REJECTED, "Un score élevé sans ENTAILED doit être rejeté.")
assert_true(ReasonCode.VERDICT_NOT_AUTHORIZED in decision.reason_codes, "Le rejet doit porter une raison métier.")
assert_equal(decision.verified_claim_ref, None, "La politique ne doit pas publier de VerifiedClaimRef sur score seul.")

# Les cas de vérification enregistrent une décision immuable.
case = VerificationCase.opened(
    verification_case_id="VER-M006-T005-UNIT-CASE",
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    policy_version="claim-verification-policy-m006-t005-unit-v1",
    submitted_at="2026-06-29T15:20:00Z",
)
recorded_case, decision_event = case.record_decision(
    decision=decision.decision,
    occurred_at="2026-06-29T15:21:00Z",
)
assert_equal(decision_event.event_type, "VerificationDecisionRecorded", "La décision doit publier son événement.")
assert_equal(recorded_case.decision.model_version, "nli-verifier-m006-t005-unit-v1", "La décision doit garder la version modèle.")
assert_raises(
    "verification_case deja decide",
    lambda: recorded_case.record_decision(
        decision=decision.decision,
        occurred_at="2026-06-29T15:22:00Z",
    ),
)

# Le handler vérifie les ports requis et publie seulement après une décision admissible.
verifier = StubVerifier(report)
assert_true(isinstance(verifier, IndependentClaimVerifier), "Le double doit respecter le port IndependentClaimVerifier.")
handler = VerifyClaimHandler(
    claim_repository=InMemoryClaimRepository(claims=(claim,)),
    verification_case_repository=InMemoryVerificationCaseRepository.empty(),
    verifier=verifier,
)
result = handler.verify(command)
assert_equal(result.claim.status, ClaimStatus.VERIFIED, "Le handler doit appliquer la transition VERIFIED admissible.")
assert_true(result.verified_claim_ref is not None, "Le handler doit publier la référence vérifiée seulement après décision.")
assert_raises(
    "verifier sans verify",
    lambda: VerifyClaimHandler(
        claim_repository=InMemoryClaimRepository(claims=(claim,)),
        verification_case_repository=InMemoryVerificationCaseRepository.empty(),
        verifier=object(),
    ),
)

print("Tests unitaires T-005 vérification claim preuve directe M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_verification_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-005 vérification claim preuve directe M-006: OK"
