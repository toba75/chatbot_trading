$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eAcute = [char] 0x00E9

$pythonCode = @'
import hashlib
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
    DenseChunkEncoding,
    DenseEncodingProfile,
    DenseEncodingVector,
    EncodingModelVersionMissingError,
    ProjectionEncodingProfile,
    SparseChunkEncoding,
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


def source_locator(text):
    return SourceLocator(
        schema_version="1.0",
        canonical_version_id="CVER-M005-T006-UNIT-0001",
        document_id="DOC-M005-T006-UNIT",
        page_pdf=1,
        item_id="DOC-M005-T006-UNIT-P001-I001",
        bbox=(0.1, 0.1, 0.8, 0.2),
        content_hash=content_hash_for(text),
    )


def knowledge_chunk():
    text = "Un chunk unitaire encode dense et sparse."
    locator = source_locator(text)
    return KnowledgeChunk.child(
        chunk_id="KCHK-M005-T006-UNIT-001",
        parent_chunk_id="KCHK-M005-T006-UNIT-PARENT",
        canonical_version_id=locator.canonical_version_id,
        document_id=locator.document_id,
        profile_id="chunking-profile-m005-t006-unit",
        profile_version="hierarchical-v1",
        text=text,
        source_locators=(locator,),
    )


def chunk_projection():
    chunk = knowledge_chunk()
    return HierarchicalChunkProjection(
        canonical_version_id=chunk.canonical_version_id,
        document_id=chunk.document_id,
        profile_id=chunk.profile_id,
        profile_version=chunk.profile_version,
        chunks=(chunk,),
    )


def dense_profile(model_version="dense-version-unit-v1"):
    return DenseEncodingProfile(
        profile_id="dense-profile-m005-t006-unit",
        model_name="dense-model-unit",
        model_version=model_version,
        dimensions=3,
        parameters_hash="1" * 64,
    )


def sparse_profile(model_version="sparse-version-unit-v1"):
    return SparseEncodingProfile(
        profile_id="sparse-profile-m005-t006-unit",
        model_name="sparse-model-unit",
        model_version=model_version,
        parameters_hash="2" * 64,
    )


def encoding_profile(model_version="dense-version-unit-v1"):
    return ProjectionEncodingProfile(
        profile_id="encoding-profile-m005-t006-unit",
        profile_version="encoding-profile-version-unit-v1",
        dense=dense_profile(model_version=model_version),
        sparse=sparse_profile(),
    )


class DenseEncoderUnitDouble:
    def encode_dense(self, request):
        assert_equal(request.profile, dense_profile(), "La requete dense doit porter le profil dense.")
        assert_equal(request.chunk_id, "KCHK-M005-T006-UNIT-001", "La requete dense doit porter le chunk.")
        return DenseEncodingVector(values=(0.1, 0.2, 0.3))


class SparseEncoderUnitDouble:
    def encode_sparse(self, request):
        assert_equal(request.profile, sparse_profile(), "La requete sparse doit porter le profil sparse.")
        assert_equal(request.content_hash, knowledge_chunk().content_hash, "La requete sparse doit porter le hash.")
        return SparseEncodingVector(weights=(SparseTokenWeight(token="chunk", weight=1.0),))


# Les profils d'encodage exigent les versions et parametres sans valeur par defaut.
assert_raises(
    EncodingModelVersionMissingError,
    "ENCODING_MODEL_VERSION_MISSING",
    lambda: DenseEncodingProfile(
        profile_id="dense-profile-missing-version",
        model_name="dense-model-unit",
        model_version="",
        dimensions=3,
        parameters_hash="1" * 64,
    ),
)
assert_raises(
    EncodingModelVersionMissingError,
    "ENCODING_MODEL_VERSION_MISSING",
    lambda: SparseEncodingProfile.from_payload(
        {
            "profile_id": "sparse-profile-missing-version",
            "model_name": "sparse-model-unit",
            "parameters_hash": "2" * 64,
        }
    ),
)
assert_raises(
    ValueError,
    "dimensions invalide",
    lambda: DenseEncodingProfile(
        profile_id="dense-profile-invalid-dimension",
        model_name="dense-model-unit",
        model_version="dense-version-unit-v1",
        dimensions=0,
        parameters_hash="1" * 64,
    ),
)

# Le fingerprint d'encodage depend des versions de modeles et parametres.
base_fingerprint = BuildFingerprint("a" * 64)
first_fingerprint = base_fingerprint.extend_with_payload(
    scope="projection_encoding",
    payload=encoding_profile().to_fingerprint_payload(),
)
same_fingerprint = base_fingerprint.extend_with_payload(
    scope="projection_encoding",
    payload=encoding_profile().to_fingerprint_payload(),
)
changed_dense_version = base_fingerprint.extend_with_payload(
    scope="projection_encoding",
    payload=encoding_profile(model_version="dense-version-unit-v2").to_fingerprint_payload(),
)
assert_equal(first_fingerprint, same_fingerprint, "La meme version d'encodage doit produire la meme empreinte.")
assert_true(
    first_fingerprint != changed_dense_version,
    "Un changement de version dense doit changer l'empreinte.",
)

# Les resultats dense et sparse portent les versions de profil et valident leurs formes.
dense_encoding = DenseChunkEncoding.from_vector(
    chunk=knowledge_chunk(),
    profile=dense_profile(),
    vector=DenseEncodingVector(values=(0.1, 0.2, 0.3)),
)
assert_equal(dense_encoding.model_version, "dense-version-unit-v1", "La version dense doit etre copiee.")
assert_equal(dense_encoding.dimensions, 3, "La dimension dense doit etre tracee.")
assert_raises(
    ValueError,
    "dimension dense incoherente",
    lambda: DenseChunkEncoding.from_vector(
        chunk=knowledge_chunk(),
        profile=dense_profile(),
        vector=DenseEncodingVector(values=(0.1, 0.2)),
    ),
)

sparse_encoding = SparseChunkEncoding.from_vector(
    chunk=knowledge_chunk(),
    profile=sparse_profile(),
    vector=SparseEncodingVector(weights=(SparseTokenWeight(token="chunk", weight=1.0),)),
)
assert_equal(sparse_encoding.model_version, "sparse-version-unit-v1", "La version sparse doit etre copiee.")
assert_equal(sparse_encoding.term_count, 1, "Le nombre de termes sparse doit etre trace.")
assert_raises(
    ValueError,
    "poids sparse absents",
    lambda: SparseEncodingVector(weights=()),
)
assert_raises(
    ValueError,
    "poids sparse invalide",
    lambda: SparseTokenWeight(token="chunk", weight=0.0),
)

# Le handler construit un resultat complet et refuse les encoders qui ne publient pas le port attendu.
handler = ProjectionEncodingHandler(
    dense_encoder=DenseEncoderUnitDouble(),
    sparse_encoder=SparseEncoderUnitDouble(),
)
result = handler.encode_projection(
    EncodeProjectionCommand(
        projection_id="PROJ-M005-T006-UNIT",
        build_fingerprint=base_fingerprint,
        chunk_projection=chunk_projection(),
        encoding_profile=encoding_profile(),
    )
)
assert_equal(len(result.encoded_chunks), 1, "Le handler doit encoder le chunk unique.")
assert_equal(result.encoded_chunks[0].chunk_id, "KCHK-M005-T006-UNIT-001", "Le chunk encode doit rester identifiable.")
assert_equal(result.trace.encoded_chunk_count, 1, "La trace doit compter les chunks encodes.")
assert_equal(result.trace.dense_model_version, "dense-version-unit-v1", "La trace doit porter la version dense.")
assert_equal(result.trace.sparse_model_version, "sparse-version-unit-v1", "La trace doit porter la version sparse.")
assert_true(result.build_fingerprint != base_fingerprint, "Le fingerprint doit integrer le profil d'encodage.")

assert_raises(
    ValueError,
    "dense_encoder sans encode_dense",
    lambda: ProjectionEncodingHandler(
        dense_encoder=object(),
        sparse_encoder=SparseEncoderUnitDouble(),
    ),
)
assert_raises(
    ValueError,
    "sparse_encoder sans encode_sparse",
    lambda: ProjectionEncodingHandler(
        dense_encoder=DenseEncoderUnitDouble(),
        sparse_encoder=object(),
    ),
)

print("Tests unitaires T-006 encodage dense sparse M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_projection_encoding_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 encodage dense sparse M-005: OK"

