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
from app.evidence_governance.adapters.claim_http import ClaimHttpAdapter, HttpRequest
from app.evidence_governance.adapters.deterministic_claim_extractor import DeterministicClaimExtractor
from app.evidence_governance.adapters.in_memory_canonical_evidence_reader import InMemoryCanonicalEvidenceReader
from app.evidence_governance.adapters.in_memory_claim_draft_repository import InMemoryClaimDraftRepository
from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.adapters.in_memory_verification_case_repository import InMemoryVerificationCaseRepository
from app.evidence_governance.application.attach_evidence import AttachEvidenceToClaimCommand, AttachEvidenceToClaimHandler
from app.evidence_governance.application.extract_claims import ExtractClaimsFromEvidenceHandler
from app.evidence_governance.application.verify_claim import VerifyClaimHandler
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
from app.evidence_governance.domain.claim_verification import IndependentVerificationReport, VerificationVerdict


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_not_contains(container, forbidden, message):
    if forbidden.lower() in repr(container).lower():
        raise AssertionError(f"{message} Élément interdit: {forbidden}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SOURCE_TEXT = (
    "Dans les crises de volatilité, les couvertures de queue réduisent le drawdown quotidien. "
    "La conclusion reste limitée au portefeuille étudié."
)
QUOTED_TEXT = "les couvertures de queue réduisent le drawdown quotidien"
CANONICAL_TEXT = "Les couvertures de queue réduisent le drawdown quotidien pendant les crises de volatilité."


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M006-T009-ACCEPTANCE",
            "document_id": "DOC-M006-T009-ACCEPTANCE",
            "canonical_version_id": "CVER-M006-T009-ACCEPTANCE-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 4,
            "accepted_at": "2026-06-29T22:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t009-v1",
        }
    )


def source_locator_policy(ref, *, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={ref.canonical_version_id: {item_id: content_hash}},
    )


def source_locator_for(text=SOURCE_TEXT):
    ref = canonical_ref()
    item_id = "DOC-M006-T009-ACCEPTANCE-P002-I001"
    content_hash = content_hash_for(text)
    policy = source_locator_policy(ref, item_id=item_id, content_hash=content_hash)
    return (
        SourceLocator.from_payload(
            {
                "schema_version": "1.0",
                "canonical_version_id": ref.canonical_version_id,
                "document_id": ref.document_id,
                "page_pdf": 2,
                "item_id": item_id,
                "bbox": (0.12, 0.24, 0.82, 0.41),
                "content_hash": content_hash,
            },
            validation_policy=policy,
        ),
        policy,
    )


def scope_payload():
    return {
        "universe": "portefeuille avec couvertures de queue",
        "horizon": "crises de volatilité",
        "metric": "drawdown quotidien",
        "frequency": "quotidienne",
    }


def proposal_payload():
    start = SOURCE_TEXT.index(QUOTED_TEXT)
    return {
        "claim_type": "EMPIRICAL_EFFECT",
        "canonical_text": CANONICAL_TEXT,
        "source_text": QUOTED_TEXT,
        "scope": scope_payload(),
        "conditions": ("crises de volatilité",),
        "limitations": ("résultat limité au portefeuille étudié",),
        "evidence_span": {
            "quoted_text": QUOTED_TEXT,
            "start_char": start,
            "end_char": start + len(QUOTED_TEXT),
        },
    }


def evidence_candidate_payload(source_locator):
    return {
        "chunk_id": "KCHK-M006-T009-ACCEPTANCE-001",
        "text": SOURCE_TEXT,
        "source_locator": source_locator.to_payload(),
        "content_hash": source_locator.content_hash,
    }


def draft_claim_for(source_locator, *, claim_id):
    start = SOURCE_TEXT.index(QUOTED_TEXT)
    return DraftClaim(
        claim_id=claim_id,
        claim_version=1,
        status=DraftClaimStatus.DRAFT,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(CANONICAL_TEXT),
        scope=ClaimScope.from_payload(scope_payload()),
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au portefeuille étudié"),),
        evidence_span=EvidenceSpan(
            quoted_text=QUOTED_TEXT,
            start_char=start,
            end_char=start + len(QUOTED_TEXT),
            source_locator=source_locator,
            quoted_span_hash=content_hash_for(QUOTED_TEXT),
        ),
        evidence_chunk_id="KCHK-M006-T009-ACCEPTANCE-001",
        extractor_version="deterministic-claim-extractor-m006-t009-v1",
    )


def evidence_ref_for(source_locator, validation_policy):
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": "EVS-M006-T009-ACCEPTANCE-0001",
            "source_locator": source_locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": content_hash_for(QUOTED_TEXT),
        },
        source_locator_validation_policy=validation_policy,
    )


class StubIndependentClaimVerifier:
    def __init__(self, evidence_ref):
        self.evidence_ref = evidence_ref
        self.calls = []

    def verify(self, *, claim, verification_case, policy_version, verifier_profile_id):
        self.calls.append({"claim_status": claim.status, "verification_case_id": verification_case.verification_case_id})
        return IndependentVerificationReport(
            verdict=VerificationVerdict.ENTAILED,
            reason_codes=(),
            accepted_evidence_ids=(self.evidence_ref.evidence_id,),
            evidence_scopes={self.evidence_ref.evidence_id: claim.scope.to_payload()},
            dependency_group_ids=("DEP-M006-T009-ACCEPTANCE-PRIMARY",),
            model_version="nli-verifier-m006-t009-v1",
            prompt_version="prompt-interne-m006-t009-ne-doit-pas-sortir",
            policy_version=policy_version,
            verifier_profile_id=verifier_profile_id,
            calibrated_score=0.97,
        )


class PublicClaimReader:
    def __init__(self, repository):
        self.repository = repository

    def read_claim(self, claim_id):
        return self.repository.claim_for_id(claim_id)


def attached_claim_repository(source_locator, evidence_ref):
    draft = draft_claim_for(source_locator, claim_id="CLM-M006-T009-ACCEPTANCE-VERIFIED")
    claim = Claim.from_draft(draft)
    reader = InMemoryCanonicalEvidenceReader(
        spans=(CanonicalEvidenceSpan(source_locator=source_locator, quoted_span_hash=evidence_ref.quoted_span_hash),)
    )
    repository = InMemoryClaimRepository(claims=(claim,))
    attached_claim = AttachEvidenceToClaimHandler(
        claim_repository=repository,
        canonical_evidence_reader=reader,
    ).attach(
        AttachEvidenceToClaimCommand(
            claim_id=claim.claim_id,
            evidence_ref=evidence_ref,
            occurred_at="2026-06-29T22:10:00Z",
        )
    ).claim
    return InMemoryClaimRepository(claims=(attached_claim,)), reader


def adapter_for(repository, reader, validation_policy, *, draft_repository=None, verifier=None):
    if draft_repository is None:
        draft_repository = InMemoryClaimDraftRepository.empty()
    if verifier is None:
        verifier = StubIndependentClaimVerifier(evidence_ref)
    extractor = DeterministicClaimExtractor(
        extractor_version="deterministic-claim-extractor-m006-t009-v1",
        proposals_by_chunk_id={"KCHK-M006-T009-ACCEPTANCE-001": (proposal_payload(),)},
    )
    return (
        ClaimHttpAdapter(
            extract_claims_handler=ExtractClaimsFromEvidenceHandler(
                extractor=extractor,
                draft_repository=draft_repository,
            ),
            verify_claim_handler=VerifyClaimHandler(
                claim_repository=repository,
                verification_case_repository=InMemoryVerificationCaseRepository.empty(),
                verifier=verifier,
            ),
            claim_reader=PublicClaimReader(repository),
            canonical_evidence_reader=reader,
            source_locator_validation_policy=validation_policy,
        ),
        draft_repository,
        verifier,
    )


def extract_body(source_locator):
    return {
        "evidence_candidates": (evidence_candidate_payload(source_locator),),
        "extraction_schema_version": "claim-extraction-schema-m006-t009-v1",
        "requested_by_context": "EG",
        "idempotency_key": "claim-extract-m006-t009-acceptance",
        "occurred_at": "2026-06-29T22:15:00Z",
    }


def verify_body():
    return {
        "verification_policy_version": "claim-verification-policy-m006-t009-v1",
        "verifier_profile_id": "independent-verifier-m006-t009",
        "idempotency_key": "claim-verify-m006-t009-acceptance",
        "occurred_at": "2026-06-29T22:30:00Z",
    }


def request(method, path, body=None):
    return HttpRequest(method=method, path=path, body=body or {}, authenticated_context="EG")


source_locator, validation_policy = source_locator_for()
evidence_ref = evidence_ref_for(source_locator, validation_policy)
claim_repository, canonical_reader = attached_claim_repository(source_locator, evidence_ref)
adapter, draft_repository, verifier = adapter_for(claim_repository, canonical_reader, validation_policy)

extraction = adapter.handle(request("POST", "/v1/claims/extract", extract_body(source_locator)))
assert_equal(extraction.status_code, 202, "L'extraction publique doit retourner 202.")
assert_equal(set(extraction.body.keys()), {"request_id", "draft_claims", "rejected_candidates", "trace_id"}, "La réponse d'extraction doit rester le contrat public EG.")
assert_equal(len(extraction.body["draft_claims"]), 1, "Une proposition atomique doit produire un brouillon.")
assert_equal(extraction.body["draft_claims"][0]["state"], "DRAFT", "L'extraction ne doit jamais vérifier le claim.")
assert_equal(draft_repository.draft_count(), 1, "L'extraction idempotente ne doit créer qu'un brouillon.")
second_extraction = adapter.handle(request("POST", "/v1/claims/extract", extract_body(source_locator)))
assert_equal(second_extraction.status_code, 202, "La répétition de la commande doit rester acceptée.")
assert_equal(draft_repository.draft_count(), 1, "La répétition idempotente ne doit pas dupliquer le brouillon.")
for forbidden in ("prompt", "qdrant", "repository", "verified_claim_ref", "calibrated_score"):
    assert_not_contains(extraction.body, forbidden, "L'extraction publique ne doit pas exposer de détail interne.")

verify_response = adapter.handle(
    request("POST", "/v1/claims/CLM-M006-T009-ACCEPTANCE-VERIFIED/verify", verify_body())
)
assert_equal(verify_response.status_code, 200, "La vérification publique doit retourner 200.")
assert_equal(verify_response.body["status"], "CLAIM_VERIFICATION_RECORDED", "La décision doit être enregistrée.")
assert_equal(verify_response.body["claim_id"], "CLM-M006-T009-ACCEPTANCE-VERIFIED", "La réponse doit nommer le claim.")
assert_equal(verify_response.body["state"], "VERIFIED", "Le claim doit devenir VERIFIED.")
assert_true(verify_response.body["verification_case_id"].startswith("VER-"), "Le cas de vérification doit être public.")
assert_equal(verify_response.body["verdict"], "ENTAILED", "Le verdict public doit être exposé.")
assert_true(verify_response.body["verified_claim_ref"] is not None, "La référence vérifiée doit être publiée.")
assert_equal(verifier.calls[0]["claim_status"], ClaimStatus.UNDER_VERIFICATION, "Le vérificateur doit recevoir le claim via le handler applicatif.")
for forbidden in ("prompt", "model_version", "calibrated_score", "repository", "qdrant"):
    assert_not_contains(verify_response.body, forbidden, "La vérification publique ne doit pas exposer de détail interne.")

claim_read = adapter.handle(request("GET", "/v1/claims/CLM-M006-T009-ACCEPTANCE-VERIFIED"))
assert_equal(claim_read.status_code, 200, "La lecture du claim vérifié doit retourner 200.")
assert_equal(
    set(claim_read.body.keys()),
    {"claim_id", "claim_version", "state", "canonical_proposition", "scope", "superseded_by", "verified_claim_ref"},
    "La lecture du claim doit rester limitée au contrat public.",
)
assert_equal(claim_read.body["state"], "VERIFIED", "La lecture doit conserver l'état vérifié.")

evidence_read = adapter.handle(request("GET", "/v1/claims/CLM-M006-T009-ACCEPTANCE-VERIFIED/evidence"))
assert_equal(evidence_read.status_code, 200, "La lecture des preuves doit retourner 200.")
assert_equal(
    set(evidence_read.body.keys()),
    {"claim_id", "claim_version", "evidence_refs", "dependency_groups", "verification_cases"},
    "La lecture de preuves doit rester limitée au contrat public.",
)
assert_equal(len(evidence_read.body["evidence_refs"]), 1, "La preuve directe doit être publiée.")
assert_equal(evidence_read.body["evidence_refs"][0]["relation"], "SUPPORTS_DIRECTLY", "La relation de preuve doit rester explicite.")
assert_equal(evidence_read.body["dependency_groups"], ("DEP-M006-T009-ACCEPTANCE-PRIMARY",), "Les groupes de dépendance publics doivent venir de VerifiedClaimRef.")
assert_equal(evidence_read.body["verification_cases"], (verify_response.body["verification_case_id"],), "La preuve doit référencer le cas de vérification accepté.")
for forbidden in ("prompt", "model_version", "repository", "qdrant", "canonical_span"):
    assert_not_contains(evidence_read.body, forbidden, "La lecture de preuve ne doit pas exposer de détail interne.")

missing_verify = adapter.handle(
    request("POST", "/v1/claims/CLM-M006-T009-ACCEPTANCE-MISSING/verify", verify_body())
)
assert_equal(missing_verify.status_code, 404, "Un claim inconnu doit retourner 404.")
assert_equal(missing_verify.body["error_code"], "CLAIM_NOT_FOUND", "L'erreur publique doit être stable.")
assert_equal(draft_repository.draft_count(), 1, "verify ne doit pas extraire un claim inconnu en fallback.")

invalid_extract = adapter.handle(
    request("POST", "/v1/claims/extract", {**extract_body(source_locator), "prompt_override": "interdit"})
)
assert_equal(invalid_extract.status_code, 400, "Un prompt_override public doit être refusé.")
assert_equal(invalid_extract.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le refus de payload doit être stable.")

invalid_verify = adapter.handle(
    request("POST", "/v1/claims/CLM-M006-T009-ACCEPTANCE-VERIFIED/verify", {**verify_body(), "qdrant_point_id": "private"})
)
assert_equal(invalid_verify.status_code, 400, "Un qdrant_point_id public doit être refusé.")
assert_equal(invalid_verify.body["error_code"], "HTTP_REQUEST_INVALID", "Le code de payload invalide doit être stable.")

draft_claim = Claim.from_draft(draft_claim_for(source_locator, claim_id="CLM-M006-T009-ACCEPTANCE-DRAFT"))
draft_repository_for_read = InMemoryClaimRepository(claims=(draft_claim,))
draft_adapter, _, _ = adapter_for(draft_repository_for_read, canonical_reader, validation_policy)
draft_read = draft_adapter.handle(request("GET", "/v1/claims/CLM-M006-T009-ACCEPTANCE-DRAFT"))
assert_equal(draft_read.status_code, 409, "Un état non publiable doit retourner 409.")
assert_equal(draft_read.body["error_code"], "CLAIM_PUBLICATION_FORBIDDEN", "L'erreur de publication doit être stable.")

unresolvable_adapter, _, _ = adapter_for(claim_repository, InMemoryCanonicalEvidenceReader(spans=()), validation_policy)
unresolvable = unresolvable_adapter.handle(request("GET", "/v1/claims/CLM-M006-T009-ACCEPTANCE-VERIFIED/evidence"))
assert_equal(unresolvable.status_code, 422, "Une preuve non résoluble doit retourner 422.")
assert_equal(unresolvable.body["error_code"], "CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", "Le code de preuve non résoluble doit être stable.")

wrong_endpoint = adapter.handle(request("POST", "/v1/research/deep", verify_body()))
assert_equal(wrong_endpoint.status_code, 404, "T-009 ne doit pas router RA.")
assert_equal(wrong_endpoint.body["error_code"], "ENDPOINT_NOT_FOUND", "Le mauvais endpoint doit être explicite.")

print("Test d'acceptation T-009 contrat HTTP claims evidence M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_http_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 contrat HTTP claims evidence M-006: OK"
