$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.knowledge_access.adapters.in_memory_hybrid_search import (
    InMemoryHybridRetrievalIndex,
    InMemoryReranker,
    InMemorySearchTraceStore,
)
from app.knowledge_access.adapters.in_memory_projection_repository import InMemoryKnowledgeProjectionRepository
from app.knowledge_access.application.search_knowledge import SearchKnowledge, SearchProjectionStaleError
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint, KnowledgeProjection, ProjectionProfile, ProjectionStatus
from app.knowledge_access.domain.projection_metadata import EvidenceDiversificationPolicy, SearchFilter
from app.knowledge_access.domain.search import (
    HybridRetrievalPolicy,
    ParentContextExpansionPolicy,
    RetrievalDocument,
    SearchRequest,
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


def projection_profile():
    return ProjectionProfile(
        projection_profile_id="projection-profile-m005-t008",
        chunking_profile="chunking-profile-m005-t008",
        embedding_model="embedding-profile-m005-t008",
        sparse_profile="sparse-profile-m005-t008",
        index_schema="qdrant-index-schema-m005-t008-v1",
    )


def projection(status=ProjectionStatus.SEARCHABLE):
    return KnowledgeProjection(
        projection_id="PROJ-M005-T008-ACCEPTANCE",
        document_id="DOC-M005-T008-A",
        canonical_version_id="CVER-M005-T008-A-0001",
        projection_profile=projection_profile(),
        build_fingerprint=BuildFingerprint("c" * 64),
        status=status,
    )


def canonical_version_id_for(document_id):
    suffix = document_id.split("-")[-1]
    return f"CVER-M005-T008-{suffix}-0001"


def canonical_ref(document_id="DOC-M005-T008-A"):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M005-T008-{document_id.split('-')[-1]}",
            "document_id": document_id,
            "canonical_version_id": canonical_version_id_for(document_id),
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 3,
            "accepted_at": "2026-06-28T09:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t008-v1",
        }
    )


def validation_policy(item_hashes_by_document):
    sources = {}
    statuses = {}
    items = {}
    for document_id, item_hashes in item_hashes_by_document.items():
        ref = canonical_ref(document_id=document_id)
        sources[ref.canonical_version_id] = ref
        statuses[ref.canonical_version_id] = "ACCEPTED"
        items.setdefault(ref.canonical_version_id, {}).update(item_hashes)
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id=sources,
        version_statuses_by_version_id=statuses,
        resolvable_item_ids_by_version_id=items,
    )


def locator(document_id, item_id, text, policy):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id_for(document_id),
            "document_id": document_id,
            "page_pdf": 1,
            "item_id": item_id,
            "bbox": (0.1, 0.1, 0.8, 0.2),
            "content_hash": content_hash_for(text),
        },
        validation_policy=policy,
    )


def hybrid_policy():
    return HybridRetrievalPolicy(
        search_profile_id="hybrid-search-m005-t008",
        search_profile_version="hybrid-v1",
        dense_profile_id="dense-profile-m005-t008",
        dense_model_name="dense-model-m005-t008",
        dense_model_version="dense-model-version-m005-t008",
        sparse_profile_id="sparse-profile-m005-t008",
        sparse_model_name="bm25-m005-t008",
        sparse_model_version="sparse-model-version-m005-t008",
        rerank_profile_id="rerank-profile-m005-t008",
        rerank_model_name="cross-encoder-m005-t008",
        rerank_model_version="rerank-model-version-m005-t008",
        dense_limit=4,
        sparse_limit=4,
        result_limit=2,
        rrf_k=60,
        rerank_required=True,
        diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
        parent_context_policy=ParentContextExpansionPolicy(enabled=True, max_parent_characters=240),
    )


class RecordingSourceLocatorResolver:
    def __init__(self):
        self.resolved_item_ids = []

    def resolve(self, locator):
        self.resolved_item_ids.append(locator.item_id)
        return {"item_id": locator.item_id, "content_hash": locator.content_hash}


texts = {
    "DOC-M005-T008-A-P001-I001": "Convex risk budget protects the downside.",
    "DOC-M005-T008-A-P001-I002": "Convex payoff appears again in the appendix.",
    "DOC-M005-T008-B-P001-I001": "Tail hedge evidence improves crisis convexity.",
    "DOC-M005-T008-C-P001-I001": "Unrelated credit carry passage.",
}
policy = validation_policy(
    {
        "DOC-M005-T008-A": {
            "DOC-M005-T008-A-P001-I001": content_hash_for(texts["DOC-M005-T008-A-P001-I001"]),
            "DOC-M005-T008-A-P001-I002": content_hash_for(texts["DOC-M005-T008-A-P001-I002"]),
        },
        "DOC-M005-T008-B": {
            "DOC-M005-T008-B-P001-I001": content_hash_for(texts["DOC-M005-T008-B-P001-I001"]),
        },
        "DOC-M005-T008-C": {
            "DOC-M005-T008-C-P001-I001": content_hash_for(texts["DOC-M005-T008-C-P001-I001"]),
        },
    }
)

documents = (
    RetrievalDocument(
        projection_id="PROJ-M005-T008-ACCEPTANCE",
        projection_profile_id="projection-profile-m005-t008",
        build_fingerprint="c" * 64,
        index_generation="IDX-M005-T008-ACCEPTANCE",
        chunk_id="KCHK-M005-T008-A-001",
        canonical_version_id="CVER-M005-T008-A-0001",
        document_id="DOC-M005-T008-A",
        text=texts["DOC-M005-T008-A-P001-I001"],
        source_locator=locator("DOC-M005-T008-A", "DOC-M005-T008-A-P001-I001", texts["DOC-M005-T008-A-P001-I001"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T008-A-P001-I001"]),
        author="Anne Durand",
        published_on="2026-06-20",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t008-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T008-A-PARENT",
        parent_text="Parent A: convex risk budget and appendix evidence.",
        dense_score=0.91,
        sparse_score=8.0,
    ),
    RetrievalDocument(
        projection_id="PROJ-M005-T008-ACCEPTANCE",
        projection_profile_id="projection-profile-m005-t008",
        build_fingerprint="c" * 64,
        index_generation="IDX-M005-T008-ACCEPTANCE",
        chunk_id="KCHK-M005-T008-A-002",
        canonical_version_id="CVER-M005-T008-A-0001",
        document_id="DOC-M005-T008-A",
        text=texts["DOC-M005-T008-A-P001-I002"],
        source_locator=locator("DOC-M005-T008-A", "DOC-M005-T008-A-P001-I002", texts["DOC-M005-T008-A-P001-I002"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T008-A-P001-I002"]),
        author="Anne Durand",
        published_on="2026-06-20",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t008-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T008-A-PARENT",
        parent_text="Parent A: convex risk budget and appendix evidence.",
        dense_score=0.89,
        sparse_score=7.0,
    ),
    RetrievalDocument(
        projection_id="PROJ-M005-T008-ACCEPTANCE",
        projection_profile_id="projection-profile-m005-t008",
        build_fingerprint="c" * 64,
        index_generation="IDX-M005-T008-ACCEPTANCE",
        chunk_id="KCHK-M005-T008-B-001",
        canonical_version_id="CVER-M005-T008-B-0001",
        document_id="DOC-M005-T008-B",
        text=texts["DOC-M005-T008-B-P001-I001"],
        source_locator=locator("DOC-M005-T008-B", "DOC-M005-T008-B-P001-I001", texts["DOC-M005-T008-B-P001-I001"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T008-B-P001-I001"]),
        author="Anne Durand",
        published_on="2026-06-21",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t008-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T008-B-PARENT",
        parent_text="Parent B: tail hedges and crisis convexity.",
        dense_score=0.75,
        sparse_score=12.0,
    ),
    RetrievalDocument(
        projection_id="PROJ-M005-T008-ACCEPTANCE",
        projection_profile_id="projection-profile-m005-t008",
        build_fingerprint="c" * 64,
        index_generation="IDX-M005-T008-ACCEPTANCE",
        chunk_id="KCHK-M005-T008-C-001",
        canonical_version_id="CVER-M005-T008-C-0001",
        document_id="DOC-M005-T008-C",
        text=texts["DOC-M005-T008-C-P001-I001"],
        source_locator=locator("DOC-M005-T008-C", "DOC-M005-T008-C-P001-I001", texts["DOC-M005-T008-C-P001-I001"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T008-C-P001-I001"]),
        author="Bruno Martin",
        published_on="2026-06-22",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t008-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T008-C-PARENT",
        parent_text="Parent C: credit carry.",
        dense_score=0.99,
        sparse_score=9.0,
    ),
)

# Given une projection SEARCHABLE et des passages indexés avec scores dense et sparse.
repository = InMemoryKnowledgeProjectionRepository(projections=(projection(),))
retrieval_index = InMemoryHybridRetrievalIndex(documents=documents)
reranker = InMemoryReranker(scores_by_chunk_id={"KCHK-M005-T008-B-001": 0.98, "KCHK-M005-T008-A-001": 0.72, "KCHK-M005-T008-A-002": 0.70})
trace_store = InMemorySearchTraceStore.empty()
resolver = RecordingSourceLocatorResolver()
search = SearchKnowledge(
    projection_repository=repository,
    retrieval_index=retrieval_index,
    reranker=reranker,
    source_locator_resolver=resolver,
    trace_store=trace_store,
)
request = SearchRequest(
    projection_id="PROJ-M005-T008-ACCEPTANCE",
    query_text="convex risk",
    filters=SearchFilter.from_payload({"author": "Anne Durand", "content_type": "research_note"}),
    hybrid_policy=hybrid_policy(),
    occurred_at="2026-06-28T09:30:00Z",
    requested_by_context="RA",
)

# When SearchKnowledge exécute une recherche hybride.
response = search.search(request)

# Then KA retourne des preuves candidates ordonnées, citées, filtrées, diversifiées et auditées.
assert_equal(response.result_count, 2, "La diversification par document doit limiter les doublons.")
assert_equal(response.candidates[0].chunk_id, "KCHK-M005-T008-B-001", "Le reranker doit être appliqué derrière son port.")
assert_equal(response.candidates[1].chunk_id, "KCHK-M005-T008-A-001", "Le meilleur candidat restant du document A doit être conservé.")
assert_equal(tuple(candidate.document_id for candidate in response.candidates), ("DOC-M005-T008-B", "DOC-M005-T008-A"), "Les documents doivent être diversifiés.")
assert_false("DOC-M005-T008-C" in tuple(candidate.document_id for candidate in response.candidates), "Le filtre auteur doit exclure Bruno Martin.")
for candidate in response.candidates:
    assert_equal(candidate.content_hash, candidate.source_locator.content_hash, "Le content_hash doit rester cohérent avec SourceLocator.")
    assert_true(candidate.parent_context.parent_text.startswith("Parent"), "Le contexte parent doit être expansé.")
    assert_true(candidate.score_bundle.dense_score != candidate.score_bundle.sparse_score, "Dense et sparse doivent rester deux scores distincts.")
    assert_true(candidate.score_bundle.rerank_score is not None, "Le score rerank doit être présent quand le profil le demande.")
    assert_false("verified_claim" in repr(candidate.to_payload()).lower(), "KA ne doit pas produire de claim EG.")
    assert_false("truth" in repr(candidate.to_payload()).lower(), "KA ne doit pas produire de verdict de vérité.")

assert_equal(tuple(resolver.resolved_item_ids), tuple(candidate.source_locator.item_id for candidate in response.candidates), "Chaque SourceLocator retourné doit être résolu.")
assert_true(response.search_trace_id.startswith("STRC-"), "La réponse doit référencer une trace persistée.")
assert_equal(trace_store.trace_count(), 1, "Une recherche auditable doit persister exactement une trace.")
trace_payload = trace_store.trace_for_id(response.search_trace_id).to_payload()
assert_equal(trace_payload["projection"]["status"], "SEARCHABLE", "La trace doit enregistrer le statut SEARCHABLE.")
assert_equal(trace_payload["projection"]["build_fingerprint"], "c" * 64, "La version de projection doit être tracée.")
assert_equal(trace_payload["search_profile"]["profile_id"], "hybrid-search-m005-t008", "Le profil de recherche doit être tracé.")
assert_equal(trace_payload["models"]["dense"]["model_version"], "dense-model-version-m005-t008", "La version dense doit être tracée.")
assert_equal(trace_payload["models"]["sparse"]["model_version"], "sparse-model-version-m005-t008", "La version sparse doit être tracée.")
assert_equal(trace_payload["models"]["rerank"]["model_version"], "rerank-model-version-m005-t008", "La version rerank doit être tracée.")
assert_equal(trace_payload["fusion"]["algorithm"], "RRF", "La fusion doit nommer RRF.")
assert_equal(trace_payload["filters"]["author"], ("Anne Durand",), "Les filtres demandés doivent être persistés.")
assert_equal(trace_payload["applied_filters"][0]["dimension"], "author", "Le filtre appliqué doit être tracé.")
assert_equal(trace_payload["diversification"]["mode"], "PER_DOCUMENT", "La diversification doit être tracée.")
assert_equal(response.warnings, ("PROJECTION_SEARCHABLE_VERIFIED",), "L'avertissement de fraîcheur doit être explicite.")
assert_false("Convex risk budget protects" in repr(trace_payload), "La trace ne doit pas stocker le texte documentaire complet.")

# Une projection STALE est refusée explicitement, sans fallback vers l'ancienne génération.
stale_repository = InMemoryKnowledgeProjectionRepository(projections=(projection(status=ProjectionStatus.STALE),))
stale_search = SearchKnowledge(
    projection_repository=stale_repository,
    retrieval_index=retrieval_index,
    reranker=reranker,
    source_locator_resolver=resolver,
    trace_store=InMemorySearchTraceStore.empty(),
)
assert_raises(SearchProjectionStaleError, "PROJECTION_STALE", lambda: stale_search.search(request))

print("Test d'acceptation T-008 recherche hybride traçable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_hybrid_search_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 recherche hybride traçable M-005: OK"
