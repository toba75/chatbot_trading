$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.knowledge_access.adapters.in_memory_vector_index import InMemoryVectorIndex
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
    PartialVectorIndexError,
    VectorIndexPoint,
    VectorIndexPublishRequest,
    VectorIndexSchema,
    index_generation_for,
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
        projection_profile_id="projection-profile-m005-t007-unit",
        chunking_profile="chunking-profile-m005-t007-unit",
        embedding_model="embedding-profile-m005-t007-unit",
        sparse_profile="sparse-profile-m005-t007-unit",
        index_schema="qdrant-index-schema-m005-t007-v1",
    )


def projection(status=ProjectionStatus.BUILDING):
    return KnowledgeProjection(
        projection_id="PROJ-M005-T007-UNIT",
        document_id="DOC-M005-T007-UNIT",
        canonical_version_id="CVER-M005-T007-UNIT-0001",
        projection_profile=projection_profile(),
        build_fingerprint=BuildFingerprint("a" * 64),
        status=status,
    )


def schema(schema_version="qdrant-index-schema-m005-t007-v1"):
    return VectorIndexSchema(
        schema_version=schema_version,
        collection_name="ka_m005_t007_unit",
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
            profile_id="dense-profile-m005-t007-unit",
            model_name="dense-model-unit",
            model_version="dense-model-version-unit",
            parameters_hash="d" * 64,
            dimensions=3,
            values=dense_values,
        ),
        sparse=SparseChunkEncoding(
            chunk_id=chunk_id,
            content_hash=content_hash,
            profile_id="sparse-profile-m005-t007-unit",
            model_name="sparse-model-unit",
            model_version="sparse-model-version-unit",
            parameters_hash="e" * 64,
            weights=(SparseTokenWeight(token=sparse_token, weight=1.0),),
        ),
    )


def encoded_projection():
    chunks = (
        encoded_chunk("KCHK-M005-T007-UNIT-001", "1" * 64, (0.1, 0.2, 0.3), "alpha"),
        encoded_chunk("KCHK-M005-T007-UNIT-002", "2" * 64, (0.4, 0.5, 0.6), "beta"),
    )
    encoding_profile = ProjectionEncodingProfile.from_payload(
        {
            "profile_id": "encoding-profile-m005-t007-unit",
            "profile_version": "encoding-profile-version-unit",
            "dense": {
                "profile_id": "dense-profile-m005-t007-unit",
                "model_name": "dense-model-unit",
                "model_version": "dense-model-version-unit",
                "dimensions": 3,
                "parameters_hash": "d" * 64,
            },
            "sparse": {
                "profile_id": "sparse-profile-m005-t007-unit",
                "model_name": "sparse-model-unit",
                "model_version": "sparse-model-version-unit",
                "parameters_hash": "e" * 64,
            },
        }
    )
    trace = ProjectionEncodingTrace(
        projection_id="PROJ-M005-T007-UNIT",
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
        projection_id="PROJ-M005-T007-UNIT",
        build_fingerprint=BuildFingerprint("b" * 64),
        encoding_profile=encoding_profile,
        encoded_chunks=chunks,
        trace=trace,
    )


base_projection = projection()
base_schema = schema()
base_encoded_projection = encoded_projection()

# Le schéma d'index est versionné et ne fournit aucune valeur implicite.
assert_equal(base_schema.schema_version, "qdrant-index-schema-m005-t007-v1", "Le schema doit être explicite.")
assert_equal(base_schema.dense_dimensions, 3, "La dimension dense doit être explicite.")
assert_raises(
    ValueError,
    "schema_version",
    lambda: VectorIndexSchema(
        schema_version="",
        collection_name="ka_m005_t007_unit",
        dense_dimensions=3,
        distance="cosine",
        payload_schema_version="ka-vector-payload-v1",
    ),
)
assert_raises(
    ValueError,
    "dense_dimensions",
    lambda: VectorIndexSchema(
        schema_version="qdrant-index-schema-m005-t007-v1",
        collection_name="ka_m005_t007_unit",
        dense_dimensions=0,
        distance="cosine",
        payload_schema_version="ka-vector-payload-v1",
    ),
)

# La génération est déterministe et dépend du schéma comme des encodages.
first_generation = index_generation_for(
    projection=base_projection,
    encoded_projection=base_encoded_projection,
    index_schema=base_schema,
)
same_generation = index_generation_for(
    projection=base_projection,
    encoded_projection=base_encoded_projection,
    index_schema=base_schema,
)
changed_generation = index_generation_for(
    projection=base_projection,
    encoded_projection=base_encoded_projection,
    index_schema=schema(schema_version="qdrant-index-schema-m005-t007-v2"),
)
assert_equal(first_generation, same_generation, "La reconstruction identique doit garder la même génération.")
assert_true(first_generation != changed_generation, "Un changement de schéma doit changer la génération.")

# Les points d'index refusent les payloads de claims et les dimensions partielles.
point = VectorIndexPoint.from_encoded_chunk(
    projection=base_projection,
    encoded_chunk=base_encoded_projection.encoded_chunks[0],
    index_schema=base_schema,
)
assert_equal(point.payload["projection_id"], base_projection.projection_id, "Le payload doit nommer la projection.")
assert_equal(point.payload["content_hash"], "1" * 64, "Le payload doit porter le hash documentaire.")
assert_false("claim" in point.payload, "Le payload documentaire ne doit pas contenir de claim.")
assert_raises(
    ValueError,
    "claim interdit",
    lambda: VectorIndexPoint(
        point_id="KCHK-M005-T007-UNIT-CLAIM",
        chunk_id="KCHK-M005-T007-UNIT-001",
        content_hash="1" * 64,
        dense_vector=(0.1, 0.2, 0.3),
        sparse_weights=(("alpha", 1.0),),
        payload={**point.payload, "claim": "résultat métier interdit"},
    ),
)
assert_raises(
    ValueError,
    "dimension dense incoherente",
    lambda: VectorIndexPoint.from_encoded_chunk(
        projection=base_projection,
        encoded_chunk=encoded_chunk(
            "KCHK-M005-T007-UNIT-003",
            "3" * 64,
            (0.1, 0.2),
            "gamma",
        ),
        index_schema=base_schema,
    ),
)

# L'adaptateur mémoire contractuel publie atomiquement une génération complète.
vector_index = InMemoryVectorIndex.empty()
points = tuple(
    VectorIndexPoint.from_encoded_chunk(
        projection=base_projection,
        encoded_chunk=chunk,
        index_schema=base_schema,
    )
    for chunk in base_encoded_projection.encoded_chunks
)
request = VectorIndexPublishRequest(
    collection_name=base_schema.collection_name,
    index_generation=first_generation,
    schema=base_schema,
    build_fingerprint=base_encoded_projection.build_fingerprint,
    points=points,
    expected_point_count=2,
)
publication = vector_index.publish_generation(request)
assert_equal(publication.published_point_count, 2, "Tous les points attendus doivent être publiés.")
assert_true(
    vector_index.generation_exists(
        collection_name=base_schema.collection_name,
        index_generation=first_generation,
    ),
    "La génération doit être consultable après publication.",
)
second_publication = vector_index.publish_generation(request)
assert_true(second_publication.idempotent, "La reconstruction identique doit être idempotente.")
assert_equal(
    vector_index.collection_point_count(
        collection_name=base_schema.collection_name,
        index_generation=first_generation,
    ),
    2,
    "La reconstruction idempotente ne doit pas dupliquer les points.",
)

partial_index = InMemoryVectorIndex.empty(omit_receipt_for_chunk_ids=("KCHK-M005-T007-UNIT-002",))
assert_raises(
    PartialVectorIndexError,
    "INDEX_PARTIAL",
    lambda: partial_index.publish_generation(request),
)
assert_false(
    partial_index.generation_exists(
        collection_name=base_schema.collection_name,
        index_generation=first_generation,
    ),
    "Une publication partielle ne doit pas être visible.",
)

# La suppression retire seulement la génération technique.
deleted = vector_index.delete_generation(
    collection_name=base_schema.collection_name,
    index_generation=first_generation,
)
assert_true(deleted.deleted, "La génération publiée doit être supprimée.")
assert_false(
    vector_index.generation_exists(
        collection_name=base_schema.collection_name,
        index_generation=first_generation,
    ),
    "La génération technique ne doit plus être servie.",
)

# Les transitions livrées par T-007 couvrent les états observables attendus.
building = base_projection
built = building.mark_built()
searchable = built.start_indexing().mark_searchable()
assert_equal(searchable.status, ProjectionStatus.SEARCHABLE, "La projection complète doit devenir SEARCHABLE.")
assert_equal(building.mark_failed().status, ProjectionStatus.FAILED, "BUILDING doit pouvoir échouer explicitement.")
assert_equal(building.mark_stale().status, ProjectionStatus.STALE, "BUILDING doit pouvoir devenir STALE.")
assert_equal(building.retire().status, ProjectionStatus.RETIRED, "BUILDING doit pouvoir être retirée explicitement.")

print("Tests unitaires T-007 index Qdrant régénérable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_qdrant_projection_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 index Qdrant régénérable M-005: OK"
