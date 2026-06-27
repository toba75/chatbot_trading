$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import EventEnvelope
from app.contracts.source_references import CanonicalSourceRef
from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
    InMemoryProjectionEventRegistry,
)
from app.knowledge_access.application.request_projection import (
    CanonicalSourceForProjection,
    CanonicalSourcePublishedProjectionConsumer,
    ProjectionAlreadyRequestedError,
    ProjectionEligibilityPolicy,
    SourceNotCanonicalError,
    SourceQuarantinedError,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_exception, expected_fragment, action):
    try:
        action()
    except expected_exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_exception.__name__}")


def canonical_ref(document_suffix, version_suffix, artifact_hash):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M005-T003-{document_suffix}",
            "document_id": f"DOC-M005-T003-{document_suffix}",
            "canonical_version_id": f"CVER-M005-T003-{version_suffix}",
            "source_sha256": "1" * 64,
            "canonical_artifact_sha256": artifact_hash,
            "page_count": 5,
            "accepted_at": "2026-06-27T13:00:00Z",
            "quality_policy_version": "canonical-quality-m005-unit-v1",
        }
    )


def projection_profile(profile_suffix):
    return ProjectionProfile(
        projection_profile_id=f"projection-profile-{profile_suffix}",
        chunking_profile=f"chunking-{profile_suffix}",
        embedding_model=f"embedding-{profile_suffix}",
        sparse_profile=f"sparse-{profile_suffix}",
        index_schema=f"index-schema-{profile_suffix}",
    )


def publication_event(canonical_ref):
    return EventEnvelope.from_payload(
        {
            "event_id": f"EVT-CANONICAL-SOURCE-PUBLISHED-{canonical_ref.canonical_version_id}",
            "event_type": "CanonicalSourcePublished",
            "event_version": 1,
            "occurred_at": canonical_ref.accepted_at,
            "aggregate_type": "CanonicalSource",
            "aggregate_id": canonical_ref.canonical_source_id,
            "aggregate_version": 1,
            "correlation_id": "CORR-M005-T003-UNIT",
            "causation_id": "CMD-M005-T003-UNIT",
            "producer_context": "SP",
            "payload": canonical_ref.to_payload(),
        }
    )


published_ref = canonical_ref("UNIT", "UNIT-0001", "2" * 64)
profile = projection_profile("m005-unit-v1")

# ProjectionProfile exige chaque profil sans valeur par defaut implicite.
assert_raises(
    ValueError,
    "sparse_profile",
    lambda: ProjectionProfile.from_payload(
        {
            "projection_profile_id": "projection-profile-invalid",
            "chunking_profile": "chunking-valid",
            "embedding_model": "embedding-valid",
            "index_schema": "index-valid",
        }
    ),
)
assert_raises(
    ValueError,
    "embedding_model",
    lambda: ProjectionProfile(
        projection_profile_id="projection-profile-invalid",
        chunking_profile="chunking-valid",
        embedding_model="",
        sparse_profile="sparse-valid",
        index_schema="index-valid",
    ),
)

# BuildFingerprint est deterministe et couvre la version canonique comme les profils.
fingerprint = BuildFingerprint.from_inputs(canonical_ref=published_ref, projection_profile=profile)
same_fingerprint = BuildFingerprint.from_inputs(canonical_ref=published_ref, projection_profile=profile)
changed_profile_fingerprint = BuildFingerprint.from_inputs(
    canonical_ref=published_ref,
    projection_profile=projection_profile("m005-unit-v2"),
)
changed_artifact_fingerprint = BuildFingerprint.from_inputs(
    canonical_ref=canonical_ref("UNIT", "UNIT-0001", "3" * 64),
    projection_profile=profile,
)
assert_equal(fingerprint, same_fingerprint, "La meme entree de build doit produire la meme empreinte.")
assert_true(fingerprint != changed_profile_fingerprint, "Un changement de profil doit changer l'empreinte.")
assert_true(fingerprint != changed_artifact_fingerprint, "Un changement d'artefact canonique doit changer l'empreinte.")

# KnowledgeProjection nait REQUESTED et interdit SEARCHABLE sans publication d'index.
projection = KnowledgeProjection.request(canonical_ref=published_ref, projection_profile=profile)
assert_equal(projection.status, ProjectionStatus.REQUESTED, "La projection doit naitre REQUESTED.")
assert_true(projection.projection_id.startswith("PROJ-"), "La projection doit porter un ProjectionId public.")
assert_equal(projection.build_fingerprint, fingerprint, "La projection doit stocker l'empreinte de build.")
assert_raises(
    ValueError,
    "transition",
    projection.mark_searchable,
)
building = projection.start_build()
built = building.mark_built()
indexing = built.start_indexing()
searchable = indexing.mark_searchable()
assert_equal(searchable.status, ProjectionStatus.SEARCHABLE, "SEARCHABLE n'est atteint qu'apres INDEXING.")

# ProjectionEligibilityPolicy refuse la quarantaine et les sources non canoniques.
policy = ProjectionEligibilityPolicy()
accepted_read = CanonicalSourceForProjection(
    document_id=published_ref.document_id,
    canonical_ref=published_ref,
    canonical_status="ACCEPTED",
    quarantine_reason=None,
)
assert_equal(policy.require_eligible(accepted_read), published_ref, "Une version ACCEPTED doit etre eligible.")
assert_raises(
    SourceQuarantinedError,
    "source en quarantaine",
    lambda: policy.require_eligible(
        CanonicalSourceForProjection(
            document_id="DOC-M005-T003-QUARANTINE-UNIT",
            canonical_ref=None,
            canonical_status="QUARANTINED",
            quarantine_reason="QA bloquante.",
        )
    ),
)
assert_raises(
    SourceNotCanonicalError,
    "source non canonique",
    lambda: policy.require_eligible(
        CanonicalSourceForProjection(
            document_id="DOC-M005-T003-REJECTED-UNIT",
            canonical_ref=None,
            canonical_status="REJECTED",
            quarantine_reason=None,
        )
    ),
)
assert_raises(
    SourceNotCanonicalError,
    "source non canonique",
    lambda: policy.require_eligible(
        CanonicalSourceForProjection(
            document_id="DOC-M005-T003-OTHER",
            canonical_ref=published_ref,
            canonical_status="ACCEPTED",
            quarantine_reason=None,
        )
    ),
)

# Le repository KA empeche les projections identiques sans muter l'existante.
repository = InMemoryKnowledgeProjectionRepository.empty()
first_decision = repository.save_if_absent(projection)
second_decision = repository.save_if_absent(KnowledgeProjection.request(canonical_ref=published_ref, projection_profile=profile))
assert_true(first_decision.created, "La premiere projection doit etre creee.")
assert_true(not second_decision.created, "La seconde projection identique doit etre idempotente.")
assert_equal(repository.projection_count(), 1, "Le repository ne doit contenir qu'une projection.")
assert_equal(second_decision.projection, projection, "Le repository doit retourner la projection existante.")

# Une commande applicative doit transformer le doublon en refus public stable.
assert_raises(
    ProjectionAlreadyRequestedError,
    "projection deja demandee",
    lambda: repository.require_absent_build_fingerprint(projection.build_fingerprint),
)

# La consommation de CanonicalSourcePublished est idempotente par event_id.
event_repository = InMemoryKnowledgeProjectionRepository.empty()
event_registry = InMemoryProjectionEventRegistry.empty()
consumer = CanonicalSourcePublishedProjectionConsumer(
    projection_repository=event_repository,
    processed_events=event_registry,
)
event = publication_event(published_ref)
first_consumption = consumer.consume(event=event, projection_profile=profile)
second_consumption = consumer.consume(event=event, projection_profile=profile)
assert_true(first_consumption.created, "Le premier evenement doit creer une projection.")
assert_true(not first_consumption.duplicate, "Le premier evenement ne doit pas etre un doublon.")
assert_true(second_consumption.duplicate, "Le deuxieme evenement doit etre marque doublon.")
assert_true(not second_consumption.created, "Le doublon d'evenement ne doit pas recreer la projection.")
assert_equal(event_repository.projection_count(), 1, "Le doublon d'evenement ne doit pas dupliquer la projection.")
assert_equal(event_registry.processed_event_ids(), (event.event_id,), "L'event_id doit etre traite une seule fois.")
assert_equal(event_registry.duplicate_event_ids(), (event.event_id,), "Le doublon doit etre trace explicitement.")

print("Tests unitaires T-003 projection de connaissance M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_knowledge_projection_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 projection de connaissance M-005: OK"
