$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eAcute = [char] 0x00E9

$pythonCode = @'
import hashlib
import inspect
import json
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
from app.knowledge_access.application.encode_projection import (
    EncodeProjectionCommand,
    ProjectionEncodingHandler,
)
from app.knowledge_access.domain.chunking import HierarchicalChunkProjection, KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint
from app.knowledge_access.domain.projection_encoding import (
    DenseEncodingFailedError,
    DenseEncodingProfile,
    DenseEncodingVector,
    EncodingModelVersionMissingError,
    ProjectionEncodingProfile,
    SparseEncodingFailedError,
    SparseEncodingProfile,
    SparseEncodingVector,
    SparseTokenWeight,
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


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locator_for(text, *, item_suffix):
    return SourceLocator(
        schema_version="1.0",
        canonical_version_id="CVER-M005-T006-0001",
        document_id="DOC-M005-T006-ENCODING",
        page_pdf=1,
        item_id=f"DOC-M005-T006-ENCODING-P001-I{item_suffix}",
        bbox=(0.1, 0.1, 0.8, 0.2),
        content_hash=content_hash_for(text),
    )


def child_chunk(text, *, chunk_id, item_suffix):
    source_locator = locator_for(text, item_suffix=item_suffix)
    return KnowledgeChunk.child(
        chunk_id=chunk_id,
        parent_chunk_id="KCHK-M005-T006-PARENT",
        canonical_version_id=source_locator.canonical_version_id,
        document_id=source_locator.document_id,
        profile_id="chunking-profile-m005-t006",
        profile_version="hierarchical-v1",
        text=text,
        source_locators=(source_locator,),
    )


def chunk_projection():
    first_text = "Le passage complet Alpha contient les termes exacts et la relation economique."
    second_text = "Le passage complet Beta contient une reformulation semantique utile."
    first_chunk = child_chunk(
        first_text,
        chunk_id="KCHK-M005-T006-CHILD-001",
        item_suffix="001",
    )
    second_chunk = child_chunk(
        second_text,
        chunk_id="KCHK-M005-T006-CHILD-002",
        item_suffix="002",
    )
    return HierarchicalChunkProjection(
        canonical_version_id="CVER-M005-T006-0001",
        document_id="DOC-M005-T006-ENCODING",
        profile_id="chunking-profile-m005-t006",
        profile_version="hierarchical-v1",
        chunks=(first_chunk, second_chunk),
    )


def encoding_profile():
    return ProjectionEncodingProfile(
        profile_id="encoding-profile-m005-t006-v1",
        profile_version="encoding-profile-version-2026-06-28",
        dense=DenseEncodingProfile(
            profile_id="dense-profile-m005-t006",
            model_name="bge-m3-local",
            model_version="bge-m3-local-2026-06-28",
            dimensions=3,
            parameters_hash="d" * 64,
        ),
        sparse=SparseEncodingProfile(
            profile_id="sparse-profile-m005-t006",
            model_name="bm25-local",
            model_version="bm25-local-2026-06-28",
            parameters_hash="e" * 64,
        ),
    )


class DenseEncoderDouble:
    def __init__(self):
        self.requests = []

    def encode_dense(self, request):
        self.requests.append(request)
        if "Alpha" in request.text:
            return DenseEncodingVector(values=(0.1, 0.2, 0.3))
        return DenseEncodingVector(values=(0.4, 0.5, 0.6))


class SparseEncoderDouble:
    def __init__(self):
        self.requests = []

    def encode_sparse(self, request):
        self.requests.append(request)
        if "Alpha" in request.text:
            return SparseEncodingVector(
                weights=(
                    SparseTokenWeight(token="termes", weight=2.0),
                    SparseTokenWeight(token="exact", weight=1.0),
                )
            )
        return SparseEncodingVector(
            weights=(SparseTokenWeight(token="semantique", weight=1.5),)
        )


class DenseEncoderFailure:
    def __init__(self):
        self.requests = []

    def encode_dense(self, request):
        self.requests.append(request)
        raise RuntimeError("modele dense indisponible")


class SparseEncoderFailure:
    def __init__(self):
        self.requests = []

    def encode_sparse(self, request):
        self.requests.append(request)
        raise RuntimeError("modele sparse indisponible")


base_fingerprint = BuildFingerprint("a" * 64)
chunks = chunk_projection()
profile = encoding_profile()

# Given des chunks eligibles avec metadonnees et profil d'encodage explicite.
dense_encoder = DenseEncoderDouble()
sparse_encoder = SparseEncoderDouble()
handler = ProjectionEncodingHandler(
    dense_encoder=dense_encoder,
    sparse_encoder=sparse_encoder,
)

# When KA encode la projection.
result = handler.encode_projection(
    EncodeProjectionCommand(
        projection_id="PROJ-M005-T006-ENCODING",
        build_fingerprint=base_fingerprint,
        chunk_projection=chunks,
        encoding_profile=profile,
    )
)

# Then chaque chunk possede un resultat dense et sparse versionne, sans texte documentaire dans la trace.
assert_equal(len(result.encoded_chunks), 2, "Chaque chunk eligible doit etre encode.")
assert_true(result.build_fingerprint != base_fingerprint, "L'empreinte d'encodage doit etendre l'empreinte de build.")
assert_equal(
    tuple(chunk.chunk_id for chunk in result.encoded_chunks),
    ("KCHK-M005-T006-CHILD-001", "KCHK-M005-T006-CHILD-002"),
    "L'ordre des chunks encodes doit rester deterministe.",
)
first_encoded = result.encoded_chunks[0]
assert_equal(first_encoded.dense.model_version, "bge-m3-local-2026-06-28", "La version dense doit etre tracee.")
assert_equal(first_encoded.sparse.model_version, "bm25-local-2026-06-28", "La version sparse doit etre tracee.")
assert_equal(first_encoded.dense.dimensions, 3, "La dimension dense doit venir du profil explicite.")
assert_equal(first_encoded.sparse.term_count, 2, "Le nombre de termes sparse doit etre trace.")

trace_payload = result.to_trace_payload()
serialized_trace = json.dumps(trace_payload, ensure_ascii=False, sort_keys=True)
assert_equal(trace_payload["projection_id"], "PROJ-M005-T006-ENCODING", "La trace doit nommer la projection.")
assert_equal(trace_payload["encoded_chunk_count"], 2, "La trace doit compter les chunks encodes.")
assert_equal(trace_payload["dense_model_version"], "bge-m3-local-2026-06-28", "La version dense doit etre auditable.")
assert_equal(trace_payload["sparse_model_version"], "bm25-local-2026-06-28", "La version sparse doit etre auditable.")
assert_false("Le passage complet Alpha" in serialized_trace, "La trace ne doit pas stocker le texte documentaire complet.")
assert_false('"text"' in serialized_trace, "La trace ne doit pas exposer de champ textuel documentaire.")
assert_equal(
    tuple(request.chunk_id for request in dense_encoder.requests),
    ("KCHK-M005-T006-CHILD-001", "KCHK-M005-T006-CHILD-002"),
    "Le port dense doit etre appele pour chaque chunk.",
)
assert_equal(
    tuple(request.chunk_id for request in sparse_encoder.requests),
    ("KCHK-M005-T006-CHILD-001", "KCHK-M005-T006-CHILD-002"),
    "Le port sparse doit etre appele pour chaque chunk.",
)

# Une version de modele manquante refuse le profil, sans modele par defaut implicite.
assert_raises(
    EncodingModelVersionMissingError,
    "ENCODING_MODEL_VERSION_MISSING",
    lambda: ProjectionEncodingProfile.from_payload(
        {
            "profile_id": "encoding-profile-missing-dense-version",
            "profile_version": "encoding-profile-version-2026-06-28",
            "dense": {
                "profile_id": "dense-profile-missing-version",
                "model_name": "bge-m3-local",
                "dimensions": 3,
                "parameters_hash": "d" * 64,
            },
            "sparse": {
                "profile_id": "sparse-profile-m005-t006",
                "model_name": "bm25-local",
                "model_version": "bm25-local-2026-06-28",
                "parameters_hash": "e" * 64,
            },
        }
    ),
)

# Un echec dense bloque la projection et n'appelle pas le sparse en fallback.
dense_failure = DenseEncoderFailure()
sparse_after_dense_failure = SparseEncoderDouble()
dense_failure_handler = ProjectionEncodingHandler(
    dense_encoder=dense_failure,
    sparse_encoder=sparse_after_dense_failure,
)
dense_error = assert_raises(
    DenseEncodingFailedError,
    "DENSE_ENCODING_FAILED",
    lambda: dense_failure_handler.encode_projection(
        EncodeProjectionCommand(
            projection_id="PROJ-M005-T006-ENCODING",
            build_fingerprint=base_fingerprint,
            chunk_projection=chunks,
            encoding_profile=profile,
        )
    ),
)
assert_equal(dense_error.error_code, "DENSE_ENCODING_FAILED", "Le code d'erreur dense doit etre stable.")
assert_equal(len(sparse_after_dense_failure.requests), 0, "Le sparse ne doit pas compenser un echec dense.")

# Un echec sparse refuse le resultat partiel dense deja produit.
dense_before_sparse_failure = DenseEncoderDouble()
sparse_failure = SparseEncoderFailure()
sparse_failure_handler = ProjectionEncodingHandler(
    dense_encoder=dense_before_sparse_failure,
    sparse_encoder=sparse_failure,
)
sparse_error = assert_raises(
    SparseEncodingFailedError,
    "SPARSE_ENCODING_FAILED",
    lambda: sparse_failure_handler.encode_projection(
        EncodeProjectionCommand(
            projection_id="PROJ-M005-T006-ENCODING",
            build_fingerprint=base_fingerprint,
            chunk_projection=chunks,
            encoding_profile=profile,
        )
    ),
)
assert_equal(sparse_error.error_code, "SPARSE_ENCODING_FAILED", "Le code d'erreur sparse doit etre stable.")
assert_false(hasattr(sparse_error, "partial_result"), "Aucun resultat partiel ne doit etre publie.")

# L'orchestrateur KA ne doit pas appeler Spark pour les embeddings.
import app.knowledge_access.application.encode_projection as encode_projection_module

module_source = inspect.getsource(encode_projection_module).lower()
for forbidden_token in ("spark", "llm_gateway", "vllm"):
    assert_false(
        forbidden_token in module_source,
        f"L'encodage KA ne doit pas dependre de {forbidden_token}.",
    )

print("Test d'acceptation T-006 encodage dense sparse M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_projection_encoding_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 encodage dense sparse M-005: OK"

