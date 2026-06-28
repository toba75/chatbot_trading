$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.knowledge_access.domain.projection_metadata import EvidenceDiversificationPolicy, SearchFilter
from app.knowledge_access.domain.search import (
    HybridRetrievalPolicy,
    ParentContextExpansionPolicy,
    RetrievalCandidate,
    RetrievalDocument,
    SearchChannelHit,
    SearchRequest,
    SearchResponse,
    SearchScoreBundle,
    SearchTracePolicy,
    SearchTraceRecord,
)
from app.knowledge_access.adapters.in_memory_hybrid_search import InMemorySearchTraceStore


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
            "canonical_source_id": "CSRC-M005-T008-UNIT",
            "document_id": "DOC-M005-T008-UNIT",
            "canonical_version_id": "CVER-M005-T008-UNIT-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-28T08:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t008-unit-v1",
        }
    )


def validation_policy(*, text):
    ref = canonical_ref()
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                "DOC-M005-T008-UNIT-P001-I001": content_hash_for(text),
            }
        },
    )


def locator_for(text):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M005-T008-UNIT-0001",
            "document_id": "DOC-M005-T008-UNIT",
            "page_pdf": 1,
            "item_id": "DOC-M005-T008-UNIT-P001-I001",
            "bbox": (0.1, 0.1, 0.8, 0.2),
            "content_hash": content_hash_for(text),
        },
        validation_policy=validation_policy(text=text),
    )


def parent_policy():
    return ParentContextExpansionPolicy(enabled=True, max_parent_characters=160)


def hybrid_policy(*, result_limit=3, rrf_k=60):
    return HybridRetrievalPolicy(
        search_profile_id="hybrid-search-m005-t008-unit",
        search_profile_version="hybrid-v1",
        dense_profile_id="dense-profile-m005-t008-unit",
        dense_model_name="dense-model-unit",
        dense_model_version="dense-model-version-unit",
        sparse_profile_id="sparse-profile-m005-t008-unit",
        sparse_model_name="bm25-unit",
        sparse_model_version="sparse-model-version-unit",
        rerank_profile_id="rerank-profile-m005-t008-unit",
        rerank_model_name="cross-encoder-unit",
        rerank_model_version="rerank-model-version-unit",
        dense_limit=3,
        sparse_limit=3,
        result_limit=result_limit,
        rrf_k=rrf_k,
        rerank_required=True,
        diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
        parent_context_policy=parent_policy(),
    )


# SearchRequest rend explicites requête, profil, filtres et absence de fallback de profil.
request = SearchRequest(
    projection_id="PROJ-M005-T008-UNIT",
    query_text="convex risk",
    filters=SearchFilter.from_payload({"author": "Anne Durand"}),
    hybrid_policy=hybrid_policy(),
    occurred_at="2026-06-28T08:30:00Z",
    requested_by_context="RA",
)
assert_equal(request.query_hash, content_hash_for("convex risk"), "La requête doit être hashée sans exposer le texte dans la trace.")
assert_raises(
    "query_text vide",
    lambda: SearchRequest(
        projection_id="PROJ-M005-T008-UNIT",
        query_text="",
        filters=SearchFilter.from_payload({"author": "Anne Durand"}),
        hybrid_policy=hybrid_policy(),
        occurred_at="2026-06-28T08:30:00Z",
        requested_by_context="RA",
    ),
)

# La fusion RRF est déterministe et conserve les scores dense et sparse séparés.
dense_hits = (
    SearchChannelHit(chunk_id="KCHK-M005-T008-UNIT-A", score=0.92),
    SearchChannelHit(chunk_id="KCHK-M005-T008-UNIT-B", score=0.86),
)
sparse_hits = (
    SearchChannelHit(chunk_id="KCHK-M005-T008-UNIT-B", score=12.0),
    SearchChannelHit(chunk_id="KCHK-M005-T008-UNIT-A", score=7.0),
)
first_fusion = hybrid_policy().fuse(dense_hits=dense_hits, sparse_hits=sparse_hits)
second_fusion = hybrid_policy().fuse(dense_hits=dense_hits, sparse_hits=sparse_hits)
assert_equal(
    tuple(item.chunk_id for item in first_fusion),
    tuple(item.chunk_id for item in second_fusion),
    "La fusion RRF doit être stable pour les mêmes entrées.",
)
assert_equal(first_fusion[0].score_bundle.dense_score, 0.92, "Le score dense doit rester distinct.")
assert_equal(first_fusion[0].score_bundle.sparse_score, 7.0, "Le score sparse doit rester distinct.")
assert_true(first_fusion[0].score_bundle.fusion_score > 0, "Le score de fusion RRF doit être calculé.")
assert_raises("dense_hits absents", lambda: hybrid_policy().fuse(dense_hits=(), sparse_hits=sparse_hits))
assert_raises("sparse_hits absents", lambda: hybrid_policy().fuse(dense_hits=dense_hits, sparse_hits=()))

# Le bundle de score ne porte aucun verdict de vérité métier.
bundle = SearchScoreBundle(
    dense_score=0.92,
    sparse_score=7.0,
    fusion_score=0.032,
    rerank_score=0.81,
    diversification_rank=1,
)
payload = bundle.to_payload()
assert_equal(
    tuple(payload.keys()),
    ("dense_score", "sparse_score", "fusion_score", "rerank_score", "diversification_rank"),
    "Le payload doit nommer chaque score sans score global opaque.",
)
assert_false("truth" in repr(payload).lower(), "Un score ne doit jamais être une vérité métier.")
assert_false("verdict" in repr(payload).lower(), "Un score ne doit jamais être un verdict métier.")

# L'expansion parent est explicite et bornée.
text = "Volatilité convexe observée."
document = RetrievalDocument(
    projection_id="PROJ-M005-T008-UNIT",
    projection_profile_id="projection-profile-m005-t008-unit",
    build_fingerprint="c" * 64,
    index_generation="IDX-M005-T008-UNIT",
    chunk_id="KCHK-M005-T008-UNIT-A",
    canonical_version_id="CVER-M005-T008-UNIT-0001",
    document_id="DOC-M005-T008-UNIT",
    text=text,
    source_locator=locator_for(text),
    content_hash=content_hash_for(text),
    author="Anne Durand",
    published_on="2026-06-28",
    content_type="research_note",
    canonical_quality="canonical-quality-m005-t008-unit-v1",
    chunk_level="CHILD",
    parent_chunk_id="KCHK-M005-T008-UNIT-PARENT",
    parent_text="Parent: volatilité convexe et risque de queue.",
    dense_score=0.92,
    sparse_score=7.0,
)
expanded = parent_policy().expand(document)
assert_equal(expanded.parent_chunk_id, "KCHK-M005-T008-UNIT-PARENT", "Le parent doit être nommé.")
assert_true("volatilité convexe" in expanded.parent_text, "Le contexte parent doit être présent.")
assert_raises(
    "parent_text depasse max_parent_characters",
    lambda: ParentContextExpansionPolicy(enabled=True, max_parent_characters=3).expand(document),
)

# Les candidats exposent SourceLocator, content_hash, scores et trace sans claim EG ni conclusion RA.
candidate = RetrievalCandidate.from_document(
    document=document,
    score_bundle=bundle,
    fusion_trace=first_fusion[0].fusion_trace,
    parent_context=expanded,
)
candidate_payload = candidate.to_payload()
assert_equal(candidate_payload["source_locator"]["content_hash"], content_hash_for(text), "Le locator doit porter le hash.")
assert_equal(candidate_payload["content_hash"], content_hash_for(text), "Le candidat doit porter le même hash.")
assert_false("verified_claim" in repr(candidate_payload).lower(), "KA ne doit pas retourner de claim vérifié.")
assert_false("business_conclusion" in repr(candidate_payload).lower(), "KA ne doit pas retourner de conclusion métier.")

# La trace de recherche persiste les paramètres, versions, modèles, profils, filtres et fusion.
trace_store = InMemorySearchTraceStore.empty()
trace = SearchTraceRecord.from_search(
    request=request,
    projection_id="PROJ-M005-T008-UNIT",
    projection_status="SEARCHABLE",
    projection_profile_id="projection-profile-m005-t008-unit",
    build_fingerprint="c" * 64,
    index_generation="IDX-M005-T008-UNIT",
    candidates=(candidate,),
    applied_filters=({"dimension": "author", "operator": "IN", "requested_value": ("Anne Durand",), "eligible_count": 1},),
    freshness_warnings=("PROJECTION_SEARCHABLE_VERIFIED",),
    fusion_trace=(first_fusion[0].fusion_trace,),
    diversification_trace={"mode": "PER_DOCUMENT", "max_per_document": 1, "input_count": 1, "output_count": 1},
)
persisted_trace = SearchTracePolicy(require_persisted_trace=True).persist(trace=trace, trace_store=trace_store)
loaded_trace = trace_store.trace_for_id(persisted_trace.search_trace_id)
trace_payload = loaded_trace.to_payload()
assert_equal(trace_payload["projection"]["status"], "SEARCHABLE", "La trace doit exposer le statut de projection.")
assert_equal(trace_payload["models"]["dense"]["model_version"], "dense-model-version-unit", "La version dense doit être tracée.")
assert_equal(trace_payload["models"]["sparse"]["model_version"], "sparse-model-version-unit", "La version sparse doit être tracée.")
assert_equal(trace_payload["models"]["rerank"]["model_version"], "rerank-model-version-unit", "La version rerank doit être tracée.")
assert_equal(trace_payload["fusion"]["algorithm"], "RRF", "La fusion RRF doit être tracée.")
assert_false("Volatilité convexe observée" in repr(trace_payload), "La trace ne doit pas stocker le texte documentaire complet.")
assert_raises(
    "SearchTraceStore obligatoire",
    lambda: SearchTracePolicy(require_persisted_trace=True).persist(trace=trace, trace_store=None),
)

response = SearchResponse(
    search_trace_id=persisted_trace.search_trace_id,
    projection_id="PROJ-M005-T008-UNIT",
    candidates=(candidate,),
    warnings=("PROJECTION_SEARCHABLE_VERIFIED",),
    applied_filters=({"dimension": "author", "operator": "IN", "requested_value": ("Anne Durand",), "eligible_count": 1},),
)
assert_equal(response.result_count, 1, "La réponse doit compter les preuves candidates.")
assert_equal(response.candidates[0].score_bundle.rerank_score, 0.81, "Le score rerank doit rester distinct.")

print("Tests unitaires T-008 recherche hybride traçable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_hybrid_search_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 recherche hybride traçable M-005: OK"
