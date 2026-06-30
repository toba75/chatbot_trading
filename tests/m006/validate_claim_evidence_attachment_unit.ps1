$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.adapters.in_memory_canonical_evidence_reader import InMemoryCanonicalEvidenceReader
from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.application.attach_evidence import (
    AttachEvidenceToClaimCommand,
    AttachEvidenceToClaimHandler,
    CanonicalEvidenceReader,
)
from app.evidence_governance.domain.claim_evidence import (
    CanonicalEvidenceSpan,
    Claim,
    ClaimStatus,
    EvidenceAdmissibilityPolicy,
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
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref(*, version_id="CVER-M006-T004-UNIT-0001", document_id="DOC-M006-T004-UNIT"):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M006-T004-UNIT",
            "document_id": document_id,
            "canonical_version_id": version_id,
            "source_sha256": "3" * 64,
            "canonical_artifact_sha256": "4" * 64,
            "page_count": 4,
            "accepted_at": "2026-06-29T13:00:00Z",
            "quality_policy_version": "canonical-quality-m006-t004-unit-v1",
        }
    )


def validation_policy_for(ref, *, status, item_id, content_hash):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: status},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item_id: content_hash,
            }
        },
    )


def locator_payload(ref, *, item_id, page_pdf, content_hash):
    return {
        "schema_version": "1.0",
        "canonical_version_id": ref.canonical_version_id,
        "document_id": ref.document_id,
        "page_pdf": page_pdf,
        "item_id": item_id,
        "bbox": (0.11, 0.21, 0.81, 0.39),
        "content_hash": content_hash,
    }


def accepted_locator_for(text, *, item_id="DOC-M006-T004-UNIT-P002-I001", page_pdf=2):
    ref = canonical_ref()
    content_hash = content_hash_for(text)
    policy = validation_policy_for(
        ref,
        status="ACCEPTED",
        item_id=item_id,
        content_hash=content_hash,
    )
    return (
        SourceLocator.from_payload(
            locator_payload(ref, item_id=item_id, page_pdf=page_pdf, content_hash=content_hash),
            validation_policy=policy,
        ),
        policy,
    )


def evidence_ref_for(source_locator, validation_policy, *, evidence_id="EVS-M006-T004-UNIT-0001", relation="SUPPORTS_DIRECTLY", quoted_span_hash=None):
    if quoted_span_hash is None:
        quoted_span_hash = content_hash_for("les couvertures de queue peuvent réduire le drawdown")
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "source_locator": source_locator.to_payload(),
            "relation": relation,
            "quoted_span_hash": quoted_span_hash,
        },
        source_locator_validation_policy=validation_policy,
    )


def draft_claim_for(source_locator):
    quoted_text = "les couvertures de queue peuvent réduire le drawdown"
    return DraftClaim(
        claim_id="CLM-M006-T004-UNIT-0001",
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
            start_char=0,
            end_char=len(quoted_text),
            source_locator=source_locator,
            quoted_span_hash=content_hash_for(quoted_text),
        ),
        evidence_chunk_id="KCHK-M006-T004-UNIT-001",
        extractor_version="deterministic-claim-extractor-m006-t004-unit-v1",
    )


source_text = "Dans les crises de volatilité, les couvertures de queue peuvent réduire le drawdown."
source_locator, validation_policy = accepted_locator_for(source_text)
evidence_ref = evidence_ref_for(source_locator, validation_policy)
reader = InMemoryCanonicalEvidenceReader(
    spans=(
        CanonicalEvidenceSpan(
            source_locator=source_locator,
            quoted_span_hash=evidence_ref.quoted_span_hash,
        ),
    )
)
policy = EvidenceAdmissibilityPolicy()

assert_true(isinstance(reader, CanonicalEvidenceReader), "Le double mémoire doit respecter le port CanonicalEvidenceReader.")

# Une preuve admissible produit une association explicite sans relation par défaut.
association = policy.association_for(
    evidence_ref=evidence_ref,
    canonical_evidence_reader=reader,
)
assert_equal(association.evidence_ref, evidence_ref, "L'association doit conserver EvidenceRef.")
assert_equal(association.relation, "SUPPORTS_DIRECTLY", "La relation doit rester explicite.")
assert_equal(association.source_locator, source_locator, "L'association doit exposer le SourceLocator.")
assert_equal(association.quoted_span_hash, evidence_ref.quoted_span_hash, "L'association doit exposer le hash du span.")

verified_claim_ref = VerifiedClaimRef.from_payload(
    {
        "schema_version": "1.0",
        "claim_id": "CLM-M006-T004-UNIT-VERIFIED-INVARIANT",
        "claim_version": 1,
        "canonical_text": "Les couvertures de queue peuvent réduire le drawdown pendant les crises de volatilité.",
        "scope": draft_claim_for(source_locator).scope.to_payload(),
        "status": "VERIFIED",
        "verification_id": "VER-M006-T004-UNIT-VERIFIED-INVARIANT",
        "evidence_refs": (evidence_ref.to_payload(),),
        "dependency_group_ids": ("DEP-M006-T004-UNIT-PRIMARY",),
    },
    source_locator_validation_policy=validation_policy,
)
assert_raises(
    "verification acceptee incomplete",
    lambda: Claim(
        claim_id="CLM-M006-T004-UNIT-VERIFIED-MISSING-DECISION",
        claim_version=1,
        status=ClaimStatus.VERIFIED,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue peuvent réduire le drawdown pendant les crises de volatilité."
        ),
        scope=draft_claim_for(source_locator).scope,
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_associations=(),
    ),
)
assert_raises(
    "preuve directe requise pour VERIFIED",
    lambda: Claim(
        claim_id="CLM-M006-T004-UNIT-VERIFIED-MISSING-EVIDENCE",
        claim_version=1,
        status=ClaimStatus.VERIFIED,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(
            "Les couvertures de queue peuvent réduire le drawdown pendant les crises de volatilité."
        ),
        scope=draft_claim_for(source_locator).scope,
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_associations=(),
        verified_claim_ref=verified_claim_ref,
        accepted_verification_id="VER-M006-T004-UNIT-VERIFIED-INVARIANT",
    ),
)

# Relation absente ou non autorisée: aucun fallback relationnel.
missing_relation_payload = evidence_ref.to_payload()
del missing_relation_payload["relation"]
assert_raises(
    "relation absent",
    lambda: EvidenceRef.from_payload(
        missing_relation_payload,
        source_locator_validation_policy=validation_policy,
    ),
)
assert_raises(
    "relation non autorisee: SUPPORTS_INDIRECTLY",
    lambda: evidence_ref_for(
        source_locator,
        validation_policy,
        evidence_id="EVS-M006-T004-UNIT-RELATION",
        relation="SUPPORTS_INDIRECTLY",
    ),
)

# SourceLocator et hash de span restent obligatoires.
missing_locator_payload = evidence_ref.to_payload()
del missing_locator_payload["source_locator"]
assert_raises(
    "source_locator absent",
    lambda: EvidenceRef.from_payload(
        missing_locator_payload,
        source_locator_validation_policy=validation_policy,
    ),
)
missing_hash_payload = evidence_ref.to_payload()
del missing_hash_payload["quoted_span_hash"]
assert_raises(
    "quoted_span_hash absent",
    lambda: EvidenceRef.from_payload(
        missing_hash_payload,
        source_locator_validation_policy=validation_policy,
    ),
)

# SourceLocator non résolvable: le lecteur canonique ne cherche pas une page voisine.
assert_raises(
    "source_locator non resolvable",
    lambda: policy.association_for(
        evidence_ref=evidence_ref,
        canonical_evidence_reader=InMemoryCanonicalEvidenceReader(spans=()),
    ),
)
neighbor_locator, _ = accepted_locator_for(
    source_text,
    item_id="DOC-M006-T004-UNIT-P003-I001",
    page_pdf=3,
)
assert_raises(
    "source_locator non resolvable",
    lambda: InMemoryCanonicalEvidenceReader(
        spans=(
            CanonicalEvidenceSpan(
                source_locator=neighbor_locator,
                quoted_span_hash=evidence_ref.quoted_span_hash,
            ),
        )
    ).resolve(source_locator),
)

# Hash incohérent: la preuve canonique résolue doit correspondre au span cité.
assert_raises(
    "quoted_span_hash incoherent",
    lambda: policy.association_for(
        evidence_ref=evidence_ref,
        canonical_evidence_reader=InMemoryCanonicalEvidenceReader(
            spans=(
                CanonicalEvidenceSpan(
                    source_locator=source_locator,
                    quoted_span_hash="a" * 64,
                ),
            )
        ),
    ),
)

# Version retirée ou en quarantaine: le contrat SourceLocator refuse la preuve publique.
retired_ref = canonical_ref(version_id="CVER-M006-T004-UNIT-RETIRED", document_id="DOC-M006-T004-UNIT")
assert_raises(
    "Version canonique indisponible: RETIRED",
    lambda: SourceLocator.from_payload(
        locator_payload(
            retired_ref,
            item_id="DOC-M006-T004-UNIT-P002-I777",
            page_pdf=2,
            content_hash=content_hash_for("preuve retirée"),
        ),
        validation_policy=validation_policy_for(
            retired_ref,
            status="RETIRED",
            item_id="DOC-M006-T004-UNIT-P002-I777",
            content_hash=content_hash_for("preuve retirée"),
        ),
    ),
)
quarantined_ref = canonical_ref(version_id="CVER-M006-T004-UNIT-QUARANTINED", document_id="DOC-M006-T004-UNIT")
assert_raises(
    "Version canonique indisponible: QUARANTINED",
    lambda: SourceLocator.from_payload(
        locator_payload(
            quarantined_ref,
            item_id="DOC-M006-T004-UNIT-P002-I778",
            page_pdf=2,
            content_hash=content_hash_for("preuve quarantaine"),
        ),
        validation_policy=validation_policy_for(
            quarantined_ref,
            status="QUARANTINED",
            item_id="DOC-M006-T004-UNIT-P002-I778",
            content_hash=content_hash_for("preuve quarantaine"),
        ),
    ),
)

# L'agrégat Claim attache la preuve une fois et refuse le doublon.
claim = Claim.from_draft(draft_claim_for(source_locator))
updated_claim, event = claim.propose_evidence(
    evidence_ref=evidence_ref,
    canonical_evidence_reader=reader,
    occurred_at="2026-06-29T13:30:00Z",
)
assert_equal(updated_claim.status, ClaimStatus.EVIDENCE_ATTACHED, "Le statut doit devenir EVIDENCE_ATTACHED.")
assert_equal(event.event_type, "EvidenceAttachedToClaim", "L'attachement doit publier l'événement dédié.")
assert_raises(
    "evidence_ref duplique",
    lambda: updated_claim.propose_evidence(
        evidence_ref=evidence_ref,
        canonical_evidence_reader=reader,
        occurred_at="2026-06-29T13:31:00Z",
    ),
)

# Une transition d'état interdite bloque l'attachement.
under_verification_claim = Claim(
    claim_id=claim.claim_id,
    claim_version=claim.claim_version,
    status=ClaimStatus.UNDER_VERIFICATION,
    claim_type=claim.claim_type,
    canonical_proposition=claim.canonical_proposition,
    scope=claim.scope,
    conditions=claim.conditions,
    limitations=claim.limitations,
    evidence_associations=(),
)
assert_raises(
    "transition claim interdite",
    lambda: under_verification_claim.propose_evidence(
        evidence_ref=evidence_ref,
        canonical_evidence_reader=reader,
        occurred_at="2026-06-29T13:32:00Z",
    ),
)

# Le handler applicatif s'appuie sur un repository mémoire strict.
repository = InMemoryClaimRepository.empty()
repository.save(claim)
handler = AttachEvidenceToClaimHandler(
    claim_repository=repository,
    canonical_evidence_reader=reader,
)
result = handler.attach(
    AttachEvidenceToClaimCommand(
        claim_id=claim.claim_id,
        evidence_ref=evidence_ref,
        occurred_at="2026-06-29T13:40:00Z",
    )
)
assert_equal(result.status, "CLAIM_EVIDENCE_ATTACHED", "Le handler doit retourner un statut explicite.")
assert_equal(repository.claim_for_id(claim.claim_id).status, ClaimStatus.EVIDENCE_ATTACHED, "Le repository doit conserver l'agrégat mis à jour.")
assert_false("verified_claim_ref" in repr(result.claim.to_payload()).lower(), "Le handler ne doit pas vérifier le claim.")

print("Tests unitaires T-004 attachement preuve claim M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_evidence_attachment_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 attachement preuve claim M-006: OK"
