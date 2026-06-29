$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef
from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.projection_http import (
    HttpRequest,
    KnowledgeProjectionHttpAdapter,
)
from app.knowledge_access.application.request_projection import (
    CanonicalSourceForProjection,
    RequestKnowledgeProjectionCommand,
    RequestKnowledgeProjectionHandler,
)
from app.knowledge_access.domain.knowledge_projection import ProjectionProfile, ProjectionStatus
from app.platform.event_bus import InMemoryTransactionalOutbox


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
        return exc
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_exception.__name__}")


def assert_absent(mapping, forbidden_key, message):
    if forbidden_key in mapping:
        raise AssertionError(message)


def canonical_ref(document_suffix, version_suffix):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M005-T003-{document_suffix}",
            "document_id": f"DOC-M005-T003-{document_suffix}",
            "canonical_version_id": f"CVER-M005-T003-{version_suffix}",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 3,
            "accepted_at": "2026-06-27T12:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t003-v1",
        }
    )


def profile_body():
    return {
        "projection_profile_id": "projection-profile-m005-t003-v1",
        "chunking_profile": "chunking-pagewise-m005-v1",
        "embedding_model": "embedding-bge-m3-m005-v1",
        "sparse_profile": "sparse-bm25-m005-v1",
        "index_schema": "knowledge-index-m005-v1",
    }


def projection_profile():
    return ProjectionProfile.from_payload(profile_body())


class RecordingCanonicalSourceReader:
    def __init__(self, records):
        self.records = dict(records)
        self.read_document_ids = []
        self.mutation_attempts = []

    def find_projection_source_by_document_id(self, document_id):
        self.read_document_ids.append(document_id)
        return self.records.get(document_id)

    def mutate_source_processing(self, document_id):
        self.mutation_attempts.append(document_id)


class FailingOutbox:
    def has_event(self, event_id):
        return False

    def append_many_in_transaction(self, mutations_and_events):
        tuple(mutations_and_events)
        raise ValueError("outbox indisponible")


def build_adapter(records):
    reader = RecordingCanonicalSourceReader(records)
    repository = InMemoryKnowledgeProjectionRepository.empty()
    outbox = InMemoryTransactionalOutbox.empty()
    handler = RequestKnowledgeProjectionHandler(
        canonical_source_reader=reader,
        projection_repository=repository,
        outbox=outbox,
    )
    adapter = KnowledgeProjectionHttpAdapter(projection_commands=handler)
    return adapter, reader, repository, outbox


def post_index(adapter, document_id, body):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path=f"/v1/documents/{document_id}/index",
            body=body,
            authenticated_context="KA",
        )
    )


# Given une CanonicalSource publiee et non mise en quarantaine.
published_ref = canonical_ref("PUBLISHED", "PUBLISHED-0001")
adapter, reader, repository, outbox = build_adapter(
    {
        published_ref.document_id: CanonicalSourceForProjection(
            document_id=published_ref.document_id,
            canonical_ref=published_ref,
            canonical_status="ACCEPTED",
            quarantine_reason=None,
        )
    }
)

# When KA recoit POST /v1/documents/{document_id}/index avec un profil explicite.
accepted = post_index(adapter, published_ref.document_id, profile_body())

# Then une KnowledgeProjection REQUESTED est creee sans mutation SP ni donnees internes.
assert_equal(accepted.status_code, 202, "L'indexation KA doit retourner 202 pour une version publiee.")
assert_equal(accepted.body["document_id"], published_ref.document_id, "La reponse doit nommer le document.")
assert_equal(
    tuple(entry.event.event_type for entry in outbox.pending_events()),
    ("KnowledgeProjectionRequested",),
    "La demande de projection acceptée doit publier KnowledgeProjectionRequested.",
)
assert_equal(accepted.body["canonical_version_id"], published_ref.canonical_version_id, "La reponse doit nommer la version canonique.")
assert_equal(accepted.body["projection_status"], "REQUESTED", "La projection doit naitre REQUESTED.")
assert_true(str(accepted.body["projection_id"]).startswith("PROJ-"), "La reponse doit exposer un ProjectionId public.")
for forbidden in (
    "source_sha256",
    "canonical_artifact_sha256",
    "qdrant_collection",
    "job_id",
    "artifact_ref",
):
    assert_absent(accepted.body, forbidden, f"La reponse KA ne doit pas exposer {forbidden}.")

assert_equal(repository.projection_count(), 1, "Une seule projection doit etre persistee.")
stored_projection = repository.projection_for_id(accepted.body["projection_id"])
assert_equal(stored_projection.status, ProjectionStatus.REQUESTED, "La projection stockee doit rester REQUESTED.")
assert_equal(stored_projection.canonical_version_id, published_ref.canonical_version_id, "La projection doit viser la version canonique.")
assert_equal(reader.mutation_attempts, [], "KA ne doit pas muter SP.")

failing_reader = RecordingCanonicalSourceReader(
    {
        published_ref.document_id: CanonicalSourceForProjection(
            document_id=published_ref.document_id,
            canonical_ref=published_ref,
            canonical_status="ACCEPTED",
            quarantine_reason=None,
        )
    }
)
failing_repository = InMemoryKnowledgeProjectionRepository.empty()
failing_handler = RequestKnowledgeProjectionHandler(
    canonical_source_reader=failing_reader,
    projection_repository=failing_repository,
    outbox=FailingOutbox(),
)
assert_raises(
    ValueError,
    "outbox indisponible",
    lambda: failing_handler.request_projection(
        RequestKnowledgeProjectionCommand(
            document_id=published_ref.document_id,
            projection_profile=projection_profile(),
        )
    ),
)
assert_equal(
    failing_repository.projection_count(),
    0,
    "Une panne outbox ne doit pas laisser une projection REQUESTED sans evenement.",
)

# Given la meme demande est rejouee.
duplicate = post_index(adapter, published_ref.document_id, profile_body())

# Then l'idempotence refuse le doublon sans creer une seconde projection.
assert_equal(duplicate.status_code, 409, "Une projection identique deja demandee doit retourner 409.")
assert_equal(duplicate.body["error_code"], "PROJECTION_ALREADY_REQUESTED", "Le doublon doit avoir un code public stable.")
assert_equal(repository.projection_count(), 1, "Le doublon ne doit pas creer de projection supplementaire.")

# Given une source est explicitement en quarantaine.
quarantined_document_id = "DOC-M005-T003-QUARANTINED"
quarantined_adapter, _, quarantined_repository, _ = build_adapter(
    {
        quarantined_document_id: CanonicalSourceForProjection(
            document_id=quarantined_document_id,
            canonical_ref=None,
            canonical_status="QUARANTINED",
            quarantine_reason="Refus QA canonique.",
        )
    }
)
quarantined = post_index(quarantined_adapter, quarantined_document_id, profile_body())
assert_equal(quarantined.status_code, 409, "Une source en quarantaine doit retourner 409.")
assert_equal(quarantined.body, {"error_code": "SOURCE_QUARANTINED", "document_id": quarantined_document_id}, "Le refus de quarantaine doit rester public.")
assert_equal(quarantined_repository.projection_count(), 0, "Une source en quarantaine ne doit creer aucune projection.")

# Given une source connue ne porte aucune version canonique publiee.
non_canonical_document_id = "DOC-M005-T003-NONCANONICAL"
non_canonical_adapter, _, non_canonical_repository, _ = build_adapter(
    {
        non_canonical_document_id: CanonicalSourceForProjection(
            document_id=non_canonical_document_id,
            canonical_ref=None,
            canonical_status="REJECTED",
            quarantine_reason=None,
        )
    }
)
non_canonical = post_index(non_canonical_adapter, non_canonical_document_id, profile_body())
assert_equal(non_canonical.status_code, 409, "Une source non canonique doit retourner 409.")
assert_equal(non_canonical.body["error_code"], "SOURCE_NOT_CANONICAL", "Le refus non canonique doit etre stable.")
assert_equal(non_canonical_repository.projection_count(), 0, "Une source non canonique ne doit creer aucune projection.")

# Given le client envoie un corps ambigu ou incomplet.
ambiguous = post_index(
    adapter,
    published_ref.document_id,
    {**profile_body(), "profile": {"name": "ambiguous"}},
)
assert_equal(ambiguous.status_code, 400, "Un corps ambigu doit retourner 400.")
assert_equal(ambiguous.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le corps ambigu doit etre refuse explicitement.")

missing_sparse_profile_body = dict(profile_body())
del missing_sparse_profile_body["sparse_profile"]
missing_sparse = post_index(adapter, published_ref.document_id, missing_sparse_profile_body)
assert_equal(missing_sparse.status_code, 422, "Un profil incomplet doit retourner 422.")
assert_equal(missing_sparse.body["error_code"], "PROJECTION_PROFILE_INVALID", "Aucun profil ne doit etre complete par defaut.")

print("Test d'acceptation T-003 projection de connaissance M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_knowledge_projection_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 projection de connaissance M-005: OK"
