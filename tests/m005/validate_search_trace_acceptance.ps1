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
from app.knowledge_access.adapters.in_memory_metrics import InMemoryKnowledgeAccessMetrics
from app.knowledge_access.adapters.in_memory_projection_repository import InMemoryKnowledgeProjectionRepository
from app.knowledge_access.application.search_knowledge import SearchKnowledge, SearchTracePersistenceError
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint, KnowledgeProjection, ProjectionProfile, ProjectionStatus
from app.knowledge_access.domain.projection_metadata import EvidenceDiversificationPolicy, SearchFilter
from app.knowledge_access.domain.search import HybridRetrievalPolicy, ParentContextExpansionPolicy, RetrievalDocument, SearchRequest
from app.platform.event_bus import InMemoryTransactionalOutbox


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
        projection_profile_id="projection-profile-m005-t008-trace",
        chunking_profile="chunking-profile-m005-t008-trace",
        embedding_model="embedding-profile-m005-t008-trace",
        sparse_profile="sparse-profile-m005-t008-trace",
        index_schema="qdrant-index-schema-m005-t008-trace-v1",
    )


def projection():
    return KnowledgeProjection(
        projection_id="PROJ-M005-T008-TRACE",
        document_id="DOC-M005-T008-TRACE",
        canonical_version_id="CVER-M005-T008-TRACE-0001",
        projection_profile=projection_profile(),
        build_fingerprint=BuildFingerprint("d" * 64),
        status=ProjectionStatus.SEARCHABLE,
    )


def policy_for(text):
    ref = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M005-T008-TRACE",
            "document_id": "DOC-M005-T008-TRACE",
            "canonical_version_id": "CVER-M005-T008-TRACE-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 1,
            "accepted_at": "2026-06-28T10:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t008-trace-v1",
        }
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                "DOC-M005-T008-TRACE-P001-I001": content_hash_for(text),
            }
        },
    )


def locator_for(text):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M005-T008-TRACE-0001",
            "document_id": "DOC-M005-T008-TRACE",
            "page_pdf": 1,
            "item_id": "DOC-M005-T008-TRACE-P001-I001",
            "bbox": (0.1, 0.1, 0.8, 0.2),
            "content_hash": content_hash_for(text),
        },
        validation_policy=policy_for(text),
    )


def hybrid_policy():
    return HybridRetrievalPolicy(
        search_profile_id="hybrid-search-m005-t008-trace",
        search_profile_version="hybrid-trace-v1",
        dense_profile_id="dense-profile-m005-t008-trace",
        dense_model_name="dense-model-m005-t008-trace",
        dense_model_version="dense-model-version-m005-t008-trace",
        sparse_profile_id="sparse-profile-m005-t008-trace",
        sparse_model_name="bm25-m005-t008-trace",
        sparse_model_version="sparse-model-version-m005-t008-trace",
        rerank_profile_id="rerank-profile-m005-t008-trace",
        rerank_model_name="cross-encoder-m005-t008-trace",
        rerank_model_version="rerank-model-version-m005-t008-trace",
        dense_limit=2,
        sparse_limit=2,
        result_limit=1,
        rrf_k=42,
        rerank_required=True,
        diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
        parent_context_policy=ParentContextExpansionPolicy(enabled=True, max_parent_characters=180),
    )


class Resolver:
    def resolve(self, locator):
        return {"item_id": locator.item_id}


class FailingTraceStore:
    def save(self, trace):
        raise SearchTracePersistenceError("SEARCH_TRACE_NOT_PERSISTED")


text = "Traceable candidate passage."
document = RetrievalDocument(
    projection_id="PROJ-M005-T008-TRACE",
    projection_profile_id="projection-profile-m005-t008-trace",
    build_fingerprint="d" * 64,
    index_generation="IDX-M005-T008-TRACE",
    chunk_id="KCHK-M005-T008-TRACE-001",
    canonical_version_id="CVER-M005-T008-TRACE-0001",
    document_id="DOC-M005-T008-TRACE",
    text=text,
    source_locator=locator_for(text),
    content_hash=content_hash_for(text),
    author="Anne Durand",
    published_on="2026-06-28",
    content_type="research_note",
    canonical_quality="canonical-quality-m005-t008-trace-v1",
    chunk_level="CHILD",
    parent_chunk_id="KCHK-M005-T008-TRACE-PARENT",
    parent_text="Parent trace context.",
    dense_score=0.88,
    sparse_score=6.5,
)
request = SearchRequest(
    projection_id="PROJ-M005-T008-TRACE",
    query_text="trace candidate",
    filters=SearchFilter.from_payload({"published_on_or_after": "2026-06-01", "content_type": "research_note"}),
    hybrid_policy=hybrid_policy(),
    occurred_at="2026-06-28T10:15:00Z",
    requested_by_context="EG",
)

# Given une recherche auditable avec trace store disponible.
trace_store = InMemorySearchTraceStore.empty()
outbox = InMemoryTransactionalOutbox.empty()
metrics = InMemoryKnowledgeAccessMetrics()
search = SearchKnowledge(
    projection_repository=InMemoryKnowledgeProjectionRepository(projections=(projection(),)),
    retrieval_index=InMemoryHybridRetrievalIndex(documents=(document,)),
    reranker=InMemoryReranker(scores_by_chunk_id={"KCHK-M005-T008-TRACE-001": 0.77}),
    source_locator_resolver=Resolver(),
    trace_store=trace_store,
    outbox=outbox,
    metrics=metrics,
)

# When SearchKnowledge retourne une preuve candidate.
response = search.search(request)

# Then la trace persistée contient paramètres, versions, modèles, profils, filtres et fusion.
assert_equal(trace_store.trace_count(), 1, "La trace doit être persistée.")
trace = trace_store.trace_for_id(response.search_trace_id)
payload = trace.to_payload()
assert_equal(payload["search_trace_id"], response.search_trace_id, "La trace doit être retrouvable par id.")
assert_equal(payload["request"]["requested_by_context"], "EG", "Le contexte consommateur doit être tracé.")
assert_equal(payload["request"]["query_hash"], content_hash_for("trace candidate"), "La requête doit être tracée par hash.")
assert_false("trace candidate" in repr(payload), "La trace ne doit pas stocker la requête brute.")
assert_equal(payload["projection"]["projection_id"], "PROJ-M005-T008-TRACE", "La projection doit être tracée.")
assert_equal(payload["projection"]["index_generation"], "IDX-M005-T008-TRACE", "La génération d'index doit être tracée.")
assert_equal(payload["search_profile"]["profile_version"], "hybrid-trace-v1", "La version du profil doit être tracée.")
assert_equal(payload["fusion"]["rrf_k"], 42, "Le paramètre RRF doit être tracé.")
assert_equal(payload["filters"]["published_on_or_after"], "2026-06-01", "Le filtre de date demandé doit être tracé.")
assert_equal(payload["applied_filters"][0]["dimension"], "published_on", "Le filtre appliqué doit être tracé.")
assert_equal(payload["result_count"], 1, "Le nombre de preuves candidates doit être tracé.")
assert_equal(payload["candidate_refs"][0]["content_hash"], content_hash_for(text), "Le hash de contenu doit être tracé.")
assert_equal(payload["candidate_refs"][0]["source_locator"]["item_id"], "DOC-M005-T008-TRACE-P001-I001", "Le SourceLocator doit être tracé.")
assert_false(text in repr(payload), "La trace ne doit pas stocker le passage complet.")
assert_false("business_conclusion" in repr(payload).lower(), "La trace ne doit pas contenir de conclusion métier.")
assert_false("verified_claim" in repr(payload).lower(), "La trace ne doit pas contenir de claim vérifié.")
assert_equal(
    tuple(entry.event.event_type for entry in outbox.pending_events()),
    ("SearchKnowledgePerformed",),
    "La recherche tracée doit publier son événement KA.",
)
assert_equal(
    len(metrics.values_for("knowledge_search_latency_seconds")),
    1,
    "La latence doit être observée quand la trace est persistée.",
)

# Sans trace persistée, la recherche auditable est refusée explicitement.
failing_search = SearchKnowledge(
    projection_repository=InMemoryKnowledgeProjectionRepository(projections=(projection(),)),
    retrieval_index=InMemoryHybridRetrievalIndex(documents=(document,)),
    reranker=InMemoryReranker(scores_by_chunk_id={"KCHK-M005-T008-TRACE-001": 0.77}),
    source_locator_resolver=Resolver(),
    trace_store=FailingTraceStore(),
    outbox=InMemoryTransactionalOutbox.empty(),
    metrics=InMemoryKnowledgeAccessMetrics(),
)
assert_raises(SearchTracePersistenceError, "SEARCH_TRACE_NOT_PERSISTED", lambda: failing_search.search(request))

print("Test d'acceptation T-008 trace de recherche M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_search_trace_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 trace de recherche M-005: OK"
