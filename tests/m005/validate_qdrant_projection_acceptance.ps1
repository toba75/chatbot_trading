$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.in_memory_vector_index import InMemoryVectorIndex
from app.knowledge_access.application.publish_projection_index import (
    MarkProjectionStaleCommand,
    PublishProjectionIndexCommand,
    PublishProjectionIndexHandler,
    RetireProjectionIndexCommand,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.knowledge_access.domain.projection_encoding import (
    DenseChunkEncoding,
    EncodedProjectionChunk,
    ProjectionEncodingProfile,
    ProjectionEncodingResult,
    ProjectionEncodingTrace,
    SparseChunkEncoding,
    SparseTokenWeight,
)
from app.knowledge_access.domain.projection_index import (
    VectorIndexSchema,
    VectorIndexUnavailableError,
    index_generation_for,
)
from app.platform.event_bus import InMemoryTransactionalOutbox
from scripts.validate_architecture_boundaries import (
    analyze_architecture,
    load_context_definitions,
    load_published_relations,
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


def assert_raises(expected_exception, expected_fragment, action):
    try:
        action()
    except expected_exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
        return exc
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_exception.__name__}")


def projection_profile():
    return ProjectionProfile(
        projection_profile_id="projection-profile-m005-t007-acceptance",
        chunking_profile="chunking-profile-m005-t007-acceptance",
        embedding_model="embedding-profile-m005-t007-acceptance",
        sparse_profile="sparse-profile-m005-t007-acceptance",
        index_schema="qdrant-index-schema-m005-t007-v1",
    )


def projection(status=ProjectionStatus.BUILDING):
    return KnowledgeProjection(
        projection_id="PROJ-M005-T007-ACCEPTANCE",
        document_id="DOC-M005-T007-ACCEPTANCE",
        canonical_version_id="CVER-M005-T007-ACCEPTANCE-0001",
        projection_profile=projection_profile(),
        build_fingerprint=BuildFingerprint("a" * 64),
        status=status,
    )


def index_schema():
    return VectorIndexSchema(
        schema_version="qdrant-index-schema-m005-t007-v1",
        collection_name="ka_m005_t007_acceptance",
        dense_dimensions=3,
        distance="cosine",
        payload_schema_version="ka-vector-payload-v1",
    )


def encoded_chunk(chunk_id, content_hash, dense_values, sparse_token):
    return EncodedProjectionChunk(
        chunk_id=chunk_id,
        content_hash=content_hash,
        dense=DenseChunkEncoding(
            chunk_id=chunk_id,
            content_hash=content_hash,
            profile_id="dense-profile-m005-t007-acceptance",
            model_name="dense-model-acceptance",
            model_version="dense-model-version-acceptance",
            parameters_hash="d" * 64,
            dimensions=3,
            values=dense_values,
        ),
        sparse=SparseChunkEncoding(
            chunk_id=chunk_id,
            content_hash=content_hash,
            profile_id="sparse-profile-m005-t007-acceptance",
            model_name="sparse-model-acceptance",
            model_version="sparse-model-version-acceptance",
            parameters_hash="e" * 64,
            weights=(SparseTokenWeight(token=sparse_token, weight=1.0),),
        ),
    )


def encoded_projection():
    chunks = (
        encoded_chunk("KCHK-M005-T007-ACCEPTANCE-001", "1" * 64, (0.1, 0.2, 0.3), "alpha"),
        encoded_chunk("KCHK-M005-T007-ACCEPTANCE-002", "2" * 64, (0.4, 0.5, 0.6), "beta"),
    )
    encoding_profile = ProjectionEncodingProfile.from_payload(
        {
            "profile_id": "encoding-profile-m005-t007-acceptance",
            "profile_version": "encoding-profile-version-acceptance",
            "dense": {
                "profile_id": "dense-profile-m005-t007-acceptance",
                "model_name": "dense-model-acceptance",
                "model_version": "dense-model-version-acceptance",
                "dimensions": 3,
                "parameters_hash": "d" * 64,
            },
            "sparse": {
                "profile_id": "sparse-profile-m005-t007-acceptance",
                "model_name": "sparse-model-acceptance",
                "model_version": "sparse-model-version-acceptance",
                "parameters_hash": "e" * 64,
            },
        }
    )
    trace = ProjectionEncodingTrace(
        projection_id="PROJ-M005-T007-ACCEPTANCE",
        build_fingerprint=BuildFingerprint("b" * 64),
        encoding_profile_id=encoding_profile.profile_id,
        encoding_profile_version=encoding_profile.profile_version,
        dense_profile_id=encoding_profile.dense.profile_id,
        dense_model_name=encoding_profile.dense.model_name,
        dense_model_version=encoding_profile.dense.model_version,
        sparse_profile_id=encoding_profile.sparse.profile_id,
        sparse_model_name=encoding_profile.sparse.model_name,
        sparse_model_version=encoding_profile.sparse.model_version,
        encoded_chunk_count=len(chunks),
    )
    return ProjectionEncodingResult(
        projection_id="PROJ-M005-T007-ACCEPTANCE",
        build_fingerprint=BuildFingerprint("b" * 64),
        encoding_profile=encoding_profile,
        encoded_chunks=chunks,
        trace=trace,
    )


def publication_command():
    return PublishProjectionIndexCommand(
        projection_id="PROJ-M005-T007-ACCEPTANCE",
        encoded_projection=encoded_projection(),
        index_schema=index_schema(),
        occurred_at="2026-06-28T10:00:00Z",
        correlation_id="CORR-M005-T007-ACCEPTANCE",
        causation_id="CMD-M005-T007-ACCEPTANCE",
    )


def handler_for(vector_index, projection_repository, outbox):
    return PublishProjectionIndexHandler(
        projection_repository=projection_repository,
        vector_index=vector_index,
        outbox=outbox,
    )


class FailingOutbox:
    def has_event(self, event_id):
        return False

    def append_many_in_transaction(self, mutations_and_events):
        tuple(mutations_and_events)
        raise ValueError("outbox indisponible")


# Given une projection encodée avec tous ses chunks attendus.
initial_projection = projection()
repository = InMemoryKnowledgeProjectionRepository(projections=(initial_projection,))
vector_index = InMemoryVectorIndex.empty()
outbox = InMemoryTransactionalOutbox.empty()
handler = handler_for(vector_index, repository, outbox)
command = publication_command()

# When KA publie l'index technique.
result = handler.publish(command)

# Then la projection devient SEARCHABLE après publication complète, avec événements outbox.
assert_equal(result.projection.status, ProjectionStatus.SEARCHABLE, "La projection complète doit devenir SEARCHABLE.")
assert_equal(result.published_point_count, 2, "Tous les chunks encodés doivent être publiés.")
expected_generation = index_generation_for(
    projection=initial_projection,
    encoded_projection=command.encoded_projection,
    index_schema=command.index_schema,
)
assert_equal(result.index_generation, expected_generation, "La génération doit être reconstructible.")
assert_true(
    vector_index.generation_exists(
        collection_name=command.index_schema.collection_name,
        index_generation=expected_generation,
    ),
    "La génération Qdrant contractuelle doit exister.",
)
assert_equal(
    repository.projection_for_id(initial_projection.projection_id).status,
    ProjectionStatus.SEARCHABLE,
    "Le repository doit refléter SEARCHABLE.",
)
events = tuple(entry.event for entry in outbox.pending_events())
assert_equal(
    tuple(event.event_type for event in events),
    ("KnowledgeProjectionBuilt", "KnowledgeProjectionBecameSearchable"),
    "Les événements de succès doivent être publiés dans l'ordre métier.",
)
searchable_payload = events[-1].payload
assert_equal(
    searchable_payload["index_generation"],
    expected_generation,
    "L'événement searchable doit porter la génération publiée.",
)
assert_false("claim" in str(searchable_payload).lower(), "L'événement ne doit pas exposer de claim EG.")

# La reconstruction identique est idempotente: même génération, pas de doublon outbox.
second_result = handler.publish(command)
assert_true(second_result.idempotent, "La reconstruction identique doit être idempotente.")
assert_equal(second_result.index_generation, expected_generation, "La génération reconstruite doit rester identique.")
assert_equal(len(outbox.pending_events()), 2, "L'outbox ne doit pas dupliquer les événements déjà publiés.")
assert_equal(
    vector_index.collection_point_count(
        collection_name=command.index_schema.collection_name,
        index_generation=expected_generation,
    ),
    2,
    "Les points ne doivent pas être dupliqués.",
)

requested_projection = projection(status=ProjectionStatus.REQUESTED)
requested_repository = InMemoryKnowledgeProjectionRepository(projections=(requested_projection,))
requested_index = InMemoryVectorIndex.empty()
requested_outbox = InMemoryTransactionalOutbox.empty()
requested_result = handler_for(requested_index, requested_repository, requested_outbox).publish(command)
assert_equal(
    requested_result.projection.status,
    ProjectionStatus.SEARCHABLE,
    "Une projection REQUESTED doit suivre REQUESTED -> BUILDING -> BUILT -> INDEXING -> SEARCHABLE.",
)
assert_equal(
    tuple(entry.event.event_type for entry in requested_outbox.pending_events()),
    ("KnowledgeProjectionBuilt", "KnowledgeProjectionBecameSearchable"),
    "Le flux REQUESTED doit publier les événements métier de construction et publication.",
)

missing_generation_repository = InMemoryKnowledgeProjectionRepository(projections=(projection(status=ProjectionStatus.SEARCHABLE),))
missing_generation_handler = handler_for(
    InMemoryVectorIndex.empty(),
    missing_generation_repository,
    InMemoryTransactionalOutbox.empty(),
)
assert_raises(
    VectorIndexUnavailableError,
    "generation SEARCHABLE absente",
    lambda: missing_generation_handler.publish(command),
)

# Une publication partielle échoue explicitement et ne rend pas la projection SEARCHABLE.
failed_projection = projection()
failed_repository = InMemoryKnowledgeProjectionRepository(projections=(failed_projection,))
partial_index = InMemoryVectorIndex.empty(omit_receipt_for_chunk_ids=("KCHK-M005-T007-ACCEPTANCE-002",))
failed_outbox = InMemoryTransactionalOutbox.empty()
failed_handler = handler_for(partial_index, failed_repository, failed_outbox)
failed_result = failed_handler.publish(command)
assert_equal(failed_result.projection.status, ProjectionStatus.FAILED, "Une publication partielle doit échouer.")
assert_equal(failed_result.public_error_code, "INDEX_PARTIAL", "L'échec partiel doit être public et stable.")
assert_false(
    partial_index.generation_exists(
        collection_name=command.index_schema.collection_name,
        index_generation=expected_generation,
    ),
    "Aucune génération partielle ne doit être servie.",
)
failed_events = tuple(entry.event for entry in failed_outbox.pending_events())
assert_equal(
    tuple(event.event_type for event in failed_events),
    ("KnowledgeProjectionBuilt", "KnowledgeProjectionFailed"),
    "L'échec d'indexation doit publier Built puis Failed, jamais Searchable.",
)
assert_equal(
    failed_events[-1].payload["public_error_code"],
    "INDEX_PARTIAL",
    "Le code public doit nommer l'index partiel.",
)

# Une projection SEARCHABLE peut devenir STALE puis RETIRED sans supprimer la source canonique.
canonical_store = {"CVER-M005-T007-ACCEPTANCE-0001": {"canonical": True}}
stale_result = handler.mark_stale(
    MarkProjectionStaleCommand(
        projection_id=initial_projection.projection_id,
        stale_reason="CANONICAL_VERSION_SUPERSEDED",
        superseding_input_ref="CVER-M005-T007-ACCEPTANCE-0002",
        occurred_at="2026-06-28T10:05:00Z",
        correlation_id="CORR-M005-T007-STALE",
        causation_id="EVT-M005-T007-SUPERSEDED",
    )
)
assert_equal(stale_result.projection.status, ProjectionStatus.STALE, "La projection doit devenir STALE.")
retired_result = handler.retire(
    RetireProjectionIndexCommand(
        projection_id=initial_projection.projection_id,
        collection_name=command.index_schema.collection_name,
        index_generation=expected_generation,
        retired_reason="PROJECTION_REPLACED",
        occurred_at="2026-06-28T10:10:00Z",
        correlation_id="CORR-M005-T007-RETIRED",
        causation_id="CMD-M005-T007-RETIRED",
    )
)
assert_equal(retired_result.projection.status, ProjectionStatus.RETIRED, "La projection doit devenir RETIRED.")
assert_equal(
    canonical_store,
    {"CVER-M005-T007-ACCEPTANCE-0001": {"canonical": True}},
    "La suppression d'index ne doit jamais supprimer la source canonique.",
)
assert_false(
    vector_index.generation_exists(
        collection_name=command.index_schema.collection_name,
        index_generation=expected_generation,
    ),
    "La génération retirée ne doit plus être servie.",
)
assert_equal(
    tuple(entry.event.event_type for entry in outbox.pending_events()),
    (
        "KnowledgeProjectionBuilt",
        "KnowledgeProjectionBecameSearchable",
        "KnowledgeProjectionBecameStale",
        "KnowledgeProjectionRetired",
    ),
    "Les transitions STALE et RETIRED doivent publier leurs événements.",
)

outbox_failure_projection = projection()
outbox_failure_repository = InMemoryKnowledgeProjectionRepository(projections=(outbox_failure_projection,))
outbox_failure_index = InMemoryVectorIndex.empty()
outbox_failure_handler = handler_for(
    outbox_failure_index,
    outbox_failure_repository,
    FailingOutbox(),
)
assert_raises(
    ValueError,
    "outbox indisponible",
    lambda: outbox_failure_handler.publish(command),
)
assert_equal(
    outbox_failure_repository.projection_for_id(outbox_failure_projection.projection_id).status,
    ProjectionStatus.BUILDING,
    "Une panne outbox ne doit pas persister SEARCHABLE sans evenement.",
)

# RA et EG ne doivent pas pouvoir dépendre directement du client Qdrant.
repo_root = Path(sys.argv[1])
with tempfile.TemporaryDirectory(prefix="ost_m005_t007_architecture_") as temp_dir:
    app_root = Path(temp_dir) / "app"
    for module in (
        "source_processing",
        "knowledge_access",
        "evidence_governance",
        "research_answering",
        "conversation",
        "strategy_design",
        "experimentation",
    ):
        for layer in ("domain", "application", "adapters"):
            package = app_root / module / layer
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
        (app_root / module / "__init__.py").write_text("", encoding="utf-8")
    for module in ("contracts", "platform"):
        package = app_root / module
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "evidence_governance" / "adapters" / "direct_qdrant.py").write_text(
        "from qdrant_client import QdrantClient\n",
        encoding="utf-8",
    )
    (app_root / "research_answering" / "application" / "direct_qdrant.py").write_text(
        "import qdrant_client\n",
        encoding="utf-8",
    )
    _, contexts_by_module = load_context_definitions(repo_root / "app" / "context_registry.json")
    relations = load_published_relations(
        repo_root / "docs" / "specs" / "m001_frontieres_ddd_contrats_publies.md"
    )
    violations, _, _ = analyze_architecture(
        app_root=app_root,
        contexts_by_module=contexts_by_module,
        relations=relations,
    )
    joined_violations = "\n".join(violations)
    assert_true("Qdrant interdit" in joined_violations, joined_violations)
    assert_true("consommateur EG" in joined_violations, joined_violations)
    assert_true("consommateur RA" in joined_violations, joined_violations)

print("Test d'acceptation T-007 index Qdrant régénérable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_qdrant_projection_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 index Qdrant régénérable M-005: OK"
