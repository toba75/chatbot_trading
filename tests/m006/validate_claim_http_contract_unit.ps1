$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import ast
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.adapters.claim_http import (
    ClaimExtractionRequestDto,
    ClaimHttpAdapter,
    ClaimHttpRequestValidationError,
    ClaimVerificationRequestDto,
    HttpRequest,
)
from app.evidence_governance.application.extract_claims import ExtractClaimsFromEvidenceCommand
from app.evidence_governance.application.read_claims import ReadPublicClaimHandler
from app.evidence_governance.application.verify_claim import SubmitClaimForVerification
from app.evidence_governance.domain.claim_evidence import CanonicalEvidenceSpan, Claim, ClaimStatus, EvidenceAssociation
from app.evidence_governance.domain.claim_extraction import CanonicalProposition, ClaimCondition, ClaimScope, Limitation
from app.evidence_governance.domain.claim_extraction import EvidenceCandidate


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_type, expected_fragment, action):
    try:
        action()
    except expected_type as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
        return exc
    except Exception as exc:
        raise AssertionError(f"Type d'erreur inattendu: {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SOURCE_TEXT = "Les couvertures de queue réduisent le drawdown quotidien pendant les crises de volatilité."


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M006-T009-UNIT",
            "document_id": "DOC-M006-T009-UNIT",
            "canonical_version_id": "CVER-M006-T009-UNIT-0001",
            "source_sha256": "c" * 64,
            "canonical_artifact_sha256": "d" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-29T23:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t009-unit-v1",
        }
    )


def validation_policy():
    ref = canonical_ref()
    item_id = "DOC-M006-T009-UNIT-P001-I001"
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {item_id: content_hash_for(SOURCE_TEXT)}
        },
    )


def source_locator(policy):
    ref = canonical_ref()
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": 1,
            "item_id": "DOC-M006-T009-UNIT-P001-I001",
            "bbox": (0.1, 0.2, 0.8, 0.35),
            "content_hash": content_hash_for(SOURCE_TEXT),
        },
        validation_policy=policy,
    )


def valid_candidate_payload(policy):
    locator = source_locator(policy)
    return {
        "chunk_id": "KCHK-M006-T009-UNIT-001",
        "text": SOURCE_TEXT,
        "source_locator": locator.to_payload(),
        "content_hash": locator.content_hash,
    }


def valid_extract_body(policy, **overrides):
    body = {
        "evidence_candidates": (valid_candidate_payload(policy),),
        "extraction_schema_version": "claim-extraction-schema-m006-t009-unit-v1",
        "requested_by_context": "EG",
        "idempotency_key": "claim-extract-m006-t009-unit",
        "occurred_at": "2026-06-29T23:05:00Z",
    }
    body.update(overrides)
    return body


def valid_verify_body(**overrides):
    body = {
        "verification_policy_version": "claim-verification-policy-m006-t009-unit-v1",
        "verifier_profile_id": "independent-verifier-m006-t009-unit",
        "idempotency_key": "claim-verify-m006-t009-unit",
        "occurred_at": "2026-06-29T23:10:00Z",
    }
    body.update(overrides)
    return body


policy = validation_policy()

extract_dto = ClaimExtractionRequestDto.from_payload(valid_extract_body(policy), source_locator_validation_policy=policy)
extract_command = extract_dto.to_command()
assert_true(isinstance(extract_command, ExtractClaimsFromEvidenceCommand), "Le DTO doit produire la commande applicative d'extraction.")
assert_equal(extract_command.extraction_schema_version, "claim-extraction-schema-m006-t009-unit-v1", "La version de schéma doit être conservée.")
assert_equal(extract_command.requested_by_context, "EG", "Le contexte demandeur doit être explicite.")
assert_true(isinstance(extract_command.evidence_candidates[0], EvidenceCandidate), "Le DTO HTTP doit produire un candidat EG explicite.")
assert_equal(extract_command.evidence_candidates[0].chunk_id, "KCHK-M006-T009-UNIT-001", "Le candidat de preuve doit rester public.")

for field_name in ("evidence_candidates", "extraction_schema_version", "requested_by_context", "idempotency_key", "occurred_at"):
    incomplete = valid_extract_body(policy)
    del incomplete[field_name]
    assert_raises(
        ClaimHttpRequestValidationError,
        f"{field_name} absent",
        lambda body=incomplete: ClaimExtractionRequestDto.from_payload(body, source_locator_validation_policy=policy),
    )

for forbidden_field in ("prompt_override", "verified_state", "qdrant_collection"):
    assert_raises(
        ClaimHttpRequestValidationError,
        "body champ interdit",
        lambda field=forbidden_field: ClaimExtractionRequestDto.from_payload(
            valid_extract_body(policy, **{field: "interdit"}),
            source_locator_validation_policy=policy,
        ),
    )

bad_candidate = valid_candidate_payload(policy)
del bad_candidate["source_locator"]
assert_raises(
    ClaimHttpRequestValidationError,
    "source_locator absent",
    lambda: ClaimExtractionRequestDto.from_payload(
        valid_extract_body(policy, evidence_candidates=(bad_candidate,)),
        source_locator_validation_policy=policy,
    ),
)

too_many_candidates = tuple(
    valid_candidate_payload(policy) | {"chunk_id": f"KCHK-M006-T009-UNIT-{index:03d}"}
    for index in range(1, 52)
)
assert_raises(
    ClaimHttpRequestValidationError,
    "evidence_candidates trop nombreux",
    lambda: ClaimExtractionRequestDto.from_payload(
        valid_extract_body(policy, evidence_candidates=too_many_candidates),
        source_locator_validation_policy=policy,
    ),
)

too_long_candidate = valid_candidate_payload(policy)
too_long_candidate["text"] = "x" * 10001
assert_raises(
    ClaimHttpRequestValidationError,
    "text trop long",
    lambda: ClaimExtractionRequestDto.from_payload(
        valid_extract_body(policy, evidence_candidates=(too_long_candidate,)),
        source_locator_validation_policy=policy,
    ),
)

assert_raises(
    ClaimHttpRequestValidationError,
    "idempotency_key trop long",
    lambda: ClaimExtractionRequestDto.from_payload(
        valid_extract_body(policy, idempotency_key="k" * 129),
        source_locator_validation_policy=policy,
    ),
)

verify_dto = ClaimVerificationRequestDto.from_payload(valid_verify_body())
verify_command = verify_dto.to_command(claim_id="CLM-M006-T009-UNIT-VERIFY")
same_verify_command = verify_dto.to_command(claim_id="CLM-M006-T009-UNIT-VERIFY")
assert_true(isinstance(verify_command, SubmitClaimForVerification), "Le DTO doit produire la commande applicative de vérification.")
assert_equal(verify_command.claim_id, "CLM-M006-T009-UNIT-VERIFY", "Le claim_id doit venir du chemin HTTP.")
assert_true(verify_command.verification_case_id.startswith("VER-"), "Le cas de vérification doit être public.")
assert_equal(verify_command.verification_case_id, same_verify_command.verification_case_id, "La clé d'idempotence doit stabiliser le cas de vérification.")
assert_equal(verify_command.verification_policy_version, "claim-verification-policy-m006-t009-unit-v1", "La politique doit être fournie explicitement.")

for field_name in ("verification_policy_version", "verifier_profile_id", "idempotency_key", "occurred_at"):
    incomplete = valid_verify_body()
    del incomplete[field_name]
    assert_raises(ClaimHttpRequestValidationError, f"{field_name} absent", lambda body=incomplete: ClaimVerificationRequestDto.from_payload(body))

for forbidden_field in ("verdict_override", "calibrated_score_as_verdict", "qdrant_point_id"):
    assert_raises(
        ClaimHttpRequestValidationError,
        "body champ interdit",
        lambda field=forbidden_field: ClaimVerificationRequestDto.from_payload(valid_verify_body(**{field: "interdit"})),
    )

assert_raises(
    ClaimHttpRequestValidationError,
    "occurred_at invalide",
    lambda: ClaimVerificationRequestDto.from_payload(valid_verify_body(occurred_at="hier")),
)
assert_raises(
    ClaimHttpRequestValidationError,
    "verifier_profile_id trop long",
    lambda: ClaimVerificationRequestDto.from_payload(valid_verify_body(verifier_profile_id="v" * 129)),
)


class MissingClaimReader:
    def read_claim(self, claim_id):
        raise ValueError(f"claim inconnu: {claim_id}")


class UnusedExtractHandler:
    def extract(self, command):
        raise AssertionError("extract ne doit pas être appelé")


class UnusedVerifyHandler:
    def verify(self, command):
        raise AssertionError("verify ne doit pas être appelé quand le claim est absent")


class EmptyCanonicalReader:
    def resolve(self, source_locator):
        raise ValueError("source_locator non resolvable")


adapter = ClaimHttpAdapter(
    extract_claims_handler=UnusedExtractHandler(),
    verify_claim_handler=UnusedVerifyHandler(),
    claim_reader=MissingClaimReader(),
    canonical_evidence_reader=EmptyCanonicalReader(),
    source_locator_validation_policy=policy,
)
missing = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/claims/CLM-M006-T009-UNIT-MISSING/verify",
        body=valid_verify_body(),
        authenticated_context="EG",
    )
)
assert_equal(missing.status_code, 404, "Le claim absent doit retourner 404.")
assert_equal(missing.body, {"error_code": "CLAIM_NOT_FOUND", "claim_id": "CLM-M006-T009-UNIT-MISSING"}, "L'erreur ne doit pas exposer le message interne.")

invalid = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/claims/CLM-M006-T009-UNIT-MISSING/verify",
        body={**valid_verify_body(), "verdict_override": "ENTAILED"},
        authenticated_context="EG",
    )
)
assert_equal(invalid.status_code, 400, "Un payload interdit doit retourner 400 avant toute lecture.")
assert_equal(invalid.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le refus de transport doit être stable.")

forbidden_extract = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/claims/extract",
        body=valid_extract_body(policy),
        authenticated_context="RA",
    )
)
assert_equal(forbidden_extract.status_code, 403, "L'extraction doit être réservée au contexte EG authentifié.")
assert_equal(forbidden_extract.body, {"error_code": "CLAIM_CONTEXT_FORBIDDEN"}, "Le refus de contexte doit être stable.")

forbidden_extract_mismatch = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/claims/extract",
        body=valid_extract_body(policy, requested_by_context="SD"),
        authenticated_context="EG",
    )
)
assert_equal(forbidden_extract_mismatch.status_code, 403, "Le contexte demandé doit correspondre au contexte authentifié.")
assert_equal(forbidden_extract_mismatch.body, {"error_code": "CLAIM_CONTEXT_FORBIDDEN"}, "Le refus de contexte demandé doit être stable.")

forbidden_verify = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/claims/CLM-M006-T009-UNIT-MISSING/verify",
        body=valid_verify_body(),
        authenticated_context="SD",
    )
)
assert_equal(forbidden_verify.status_code, 403, "La vérification doit être réservée au contexte EG authentifié.")
assert_equal(forbidden_verify.body, {"error_code": "CLAIM_CONTEXT_FORBIDDEN"}, "Le refus de contexte de vérification doit être stable.")

wrong_endpoint = adapter.handle(HttpRequest(method="POST", path="/v1/answer?token=secret", body=valid_verify_body(), authenticated_context="EG"))
assert_equal(wrong_endpoint.status_code, 404, "L'adaptateur claims ne doit pas router RA.")
assert_equal(wrong_endpoint.body, {"error_code": "ENDPOINT_NOT_FOUND"}, "Le mauvais endpoint ne doit pas refléter le chemin brut.")


class SingleClaimReader:
    def __init__(self, claim):
        self.claim = claim

    def read_claim(self, claim_id):
        return self.claim


class CanonicalReader:
    def __init__(self, span):
        self.span = span
        self.resolved_item_ids = []

    def resolve(self, source_locator):
        self.resolved_item_ids.append(source_locator.item_id)
        return self.span


accepted_locator = source_locator(policy)
non_accepted_text = SOURCE_TEXT + " Mention non retenue par la vérification."
non_accepted_item_id = "DOC-M006-T009-UNIT-P001-I002"
non_accepted_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref().canonical_version_id: canonical_ref()},
    version_statuses_by_version_id={canonical_ref().canonical_version_id: "ACCEPTED"},
    resolvable_item_ids_by_version_id={
        canonical_ref().canonical_version_id: {
            non_accepted_item_id: content_hash_for(non_accepted_text),
        }
    },
)
non_accepted_locator = SourceLocator.from_payload(
    {
        "schema_version": "1.0",
        "canonical_version_id": canonical_ref().canonical_version_id,
        "document_id": canonical_ref().document_id,
        "page_pdf": 1,
        "item_id": non_accepted_item_id,
        "bbox": (0.1, 0.4, 0.8, 0.55),
        "content_hash": content_hash_for(non_accepted_text),
    },
    validation_policy=non_accepted_policy,
)
accepted_evidence_ref = EvidenceRef.from_payload(
    {
        "schema_version": "1.0",
        "evidence_id": "EVS-M006-T009-UNIT-ACCEPTED",
        "source_locator": accepted_locator.to_payload(),
        "relation": "SUPPORTS_DIRECTLY",
        "quoted_span_hash": content_hash_for(SOURCE_TEXT),
    },
    source_locator_validation_policy=policy,
)
non_accepted_evidence_ref = EvidenceRef.from_payload(
    {
        "schema_version": "1.0",
        "evidence_id": "EVS-M006-T009-UNIT-NON-ACCEPTED",
        "source_locator": non_accepted_locator.to_payload(),
        "relation": "SUPPORTS_DIRECTLY",
        "quoted_span_hash": content_hash_for(non_accepted_text),
    },
    source_locator_validation_policy=non_accepted_policy,
)
accepted_scope = ClaimScope(
    universe="portefeuille avec couvertures de queue",
    horizon="crises de volatilité",
    metric="drawdown quotidien",
    frequency="quotidienne",
)
verified_claim_ref = VerifiedClaimRef(
    schema_version="1.0",
    claim_id="CLM-M006-T009-UNIT-PUBLIC-READ",
    claim_version=1,
    canonical_text=SOURCE_TEXT,
    scope=accepted_scope.to_payload(),
    status="VERIFIED",
    verification_id="VER-M006-T009-UNIT-PUBLIC-READ",
    evidence_refs=(accepted_evidence_ref,),
    dependency_group_ids=("DEP-M006-T009-UNIT-ACCEPTED",),
)
claim_with_extra_association = Claim(
    claim_id="CLM-M006-T009-UNIT-PUBLIC-READ",
    claim_version=1,
    status=ClaimStatus.VERIFIED,
    claim_type="EMPIRICAL_EFFECT",
    canonical_proposition=CanonicalProposition(SOURCE_TEXT),
    scope=accepted_scope,
    conditions=(ClaimCondition("crises de volatilité"),),
    limitations=(Limitation("preuve acceptée seulement"),),
    evidence_associations=(
        EvidenceAssociation.from_evidence_ref(accepted_evidence_ref),
        EvidenceAssociation.from_evidence_ref(non_accepted_evidence_ref),
    ),
    verified_claim_ref=verified_claim_ref,
    accepted_verification_id="VER-M006-T009-UNIT-PUBLIC-READ",
)
canonical_reader = CanonicalReader(
    CanonicalEvidenceSpan(
        source_locator=accepted_locator,
        quoted_span_hash=accepted_evidence_ref.quoted_span_hash,
    )
)
public_evidence = ReadPublicClaimHandler(
    claim_reader=SingleClaimReader(claim_with_extra_association),
    canonical_evidence_reader=canonical_reader,
).read_evidence(claim_with_extra_association.claim_id)
assert_equal(
    tuple(evidence_ref.evidence_id for evidence_ref in public_evidence.evidence_refs),
    ("EVS-M006-T009-UNIT-ACCEPTED",),
    "La lecture publique doit publier seulement les preuves acceptées par VerifiedClaimRef.",
)
assert_equal(
    tuple(canonical_reader.resolved_item_ids),
    (accepted_locator.item_id,),
    "La lecture publique doit valider seulement les preuves acceptées par la vérification.",
)

adapter_path = Path(sys.argv[1]) / "app" / "evidence_governance" / "adapters" / "claim_http.py"
tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        called_name = getattr(node.func, "id", None)
        called_attr = getattr(node.func, "attr", None)
        if called_name == "print" or called_attr in {"debug", "info", "warning", "error", "exception"}:
            raise AssertionError("L'adaptateur HTTP claims ne doit pas écrire de log de payload.")
    if isinstance(node, ast.Import):
        imported_roots = {alias.name for alias in node.names}
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        imported_roots = {node.module}
    else:
        imported_roots = set()
    forbidden_imports = {
        "app.research_answering",
        "app.evidence_governance.adapters.in_memory_claim_repository",
        "app.evidence_governance.adapters.in_memory_claim_draft_repository",
        "qdrant_client",
        "logging",
        "fastapi",
        "starlette",
        "flask",
        "django",
    }
    if imported_roots & forbidden_imports:
        raise AssertionError(f"Import interdit dans claim_http.py: {sorted(imported_roots & forbidden_imports)}")

source = adapter_path.read_text(encoding="utf-8")
assert_true("ReadPublicClaimHandler" in source, "L'adaptateur HTTP doit déléguer la lecture publique au cas d'usage applicatif.")
assert_false("_ensure_claim_publication_allowed" in source, "La politique de publication ne doit pas rester dans l'adaptateur HTTP.")
for forbidden_snippet in ("prompt_override", "calibrated_score_as_verdict"):
    assert_true(forbidden_snippet in source, f"Le champ interdit {forbidden_snippet} doit être refusé explicitement.")
for forbidden_response_detail in ("prompt_version", "model_version", "calibrated_score"):
    assert_false(
        f'"{forbidden_response_detail}"' in source or f"'{forbidden_response_detail}'" in source,
        f"Le détail interne {forbidden_response_detail} ne doit pas être sérialisé en réponse publique.",
    )

print("Tests unitaires T-009 contrat HTTP claims evidence M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_http_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 contrat HTTP claims evidence M-006: OK"
