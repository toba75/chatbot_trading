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
from app.knowledge_access.adapters.search_http import (
    HttpRequest,
    KnowledgeSearchHttpAdapter,
)
from app.knowledge_access.application.search_knowledge import SearchKnowledge
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint, KnowledgeProjection, ProjectionProfile, ProjectionStatus
from app.knowledge_access.domain.projection_metadata import EvidenceDiversificationPolicy
from app.knowledge_access.domain.search import HybridRetrievalPolicy, ParentContextExpansionPolicy, RetrievalDocument


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_not_contains(container, forbidden, message):
    rendered = repr(container).lower()
    if forbidden.lower() in rendered:
        raise AssertionError(f"{message} Élément interdit: {forbidden}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def projection_profile():
    return ProjectionProfile(
        projection_profile_id="projection-profile-m005-t009",
        chunking_profile="chunking-profile-m005-t009",
        embedding_model="embedding-profile-m005-t009",
        sparse_profile="sparse-profile-m005-t009",
        index_schema="qdrant-index-schema-m005-t009-v1",
    )


def projection(status=ProjectionStatus.SEARCHABLE, projection_id="PROJ-M005-T009-SEARCH"):
    return KnowledgeProjection(
        projection_id=projection_id,
        document_id="DOC-M005-T009-A",
        canonical_version_id="CVER-M005-T009-A-0001",
        projection_profile=projection_profile(),
        build_fingerprint=BuildFingerprint("d" * 64),
        status=status,
    )


def canonical_version_id_for(document_id):
    suffix = document_id.split("-")[-1]
    return f"CVER-M005-T009-{suffix}-0001"


def canonical_ref(document_id):
    suffix = document_id.split("-")[-1]
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M005-T009-{suffix}",
            "document_id": document_id,
            "canonical_version_id": canonical_version_id_for(document_id),
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-28T10:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t009-v1",
        }
    )


def validation_policy(item_hashes_by_document):
    sources = {}
    statuses = {}
    items = {}
    for document_id, item_hashes in item_hashes_by_document.items():
        ref = canonical_ref(document_id)
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
        search_profile_id="hybrid-search-public-m005-t009",
        search_profile_version="hybrid-v1",
        dense_profile_id="dense-profile-m005-t009",
        dense_model_name="dense-model-m005-t009",
        dense_model_version="dense-model-version-m005-t009",
        sparse_profile_id="sparse-profile-m005-t009",
        sparse_model_name="bm25-m005-t009",
        sparse_model_version="sparse-model-version-m005-t009",
        rerank_profile_id="rerank-profile-m005-t009",
        rerank_model_name="cross-encoder-m005-t009",
        rerank_model_version="rerank-model-version-m005-t009",
        dense_limit=4,
        sparse_limit=4,
        result_limit=2,
        rrf_k=60,
        rerank_required=True,
        diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
        parent_context_policy=ParentContextExpansionPolicy(enabled=True, max_parent_characters=240),
    )


class InMemorySearchProfileCatalog:
    def __init__(self, profiles):
        self._profiles = dict(profiles)

    def profile_for_id(self, search_profile_id):
        profile = self._profiles.get(search_profile_id)
        if profile is None:
            raise ValueError(f"profil de recherche inconnu: {search_profile_id}")
        return profile


class RecordingSourceLocatorResolver:
    def __init__(self):
        self.resolved_item_ids = []

    def resolve(self, locator):
        self.resolved_item_ids.append(locator.item_id)
        return {"item_id": locator.item_id, "content_hash": locator.content_hash}


def search_request_body(**overrides):
    body = {
        "projection_id": "PROJ-M005-T009-SEARCH",
        "query_text": "convex risk",
        "filters": {"author": "Anne Durand", "content_type": "research_note"},
        "search_profile_id": "hybrid-search-public-m005-t009",
        "occurred_at": "2026-06-28T10:30:00Z",
        "requested_by_context": "RA",
    }
    body.update(overrides)
    return body


texts = {
    "DOC-M005-T009-A-P001-I001": "Convex risk budget protects the downside.",
    "DOC-M005-T009-A-P001-I002": "Convex payoff appears again in the appendix.",
    "DOC-M005-T009-B-P001-I001": "Tail hedge evidence improves crisis convexity.",
}
policy = validation_policy(
    {
        "DOC-M005-T009-A": {
            "DOC-M005-T009-A-P001-I001": content_hash_for(texts["DOC-M005-T009-A-P001-I001"]),
            "DOC-M005-T009-A-P001-I002": content_hash_for(texts["DOC-M005-T009-A-P001-I002"]),
        },
        "DOC-M005-T009-B": {
            "DOC-M005-T009-B-P001-I001": content_hash_for(texts["DOC-M005-T009-B-P001-I001"]),
        },
    }
)

documents = (
    RetrievalDocument(
        projection_id="PROJ-M005-T009-SEARCH",
        projection_profile_id="projection-profile-m005-t009",
        build_fingerprint="d" * 64,
        index_generation="IDX-M005-T009-SEARCH",
        chunk_id="KCHK-M005-T009-A-001",
        canonical_version_id="CVER-M005-T009-A-0001",
        document_id="DOC-M005-T009-A",
        text=texts["DOC-M005-T009-A-P001-I001"],
        source_locator=locator("DOC-M005-T009-A", "DOC-M005-T009-A-P001-I001", texts["DOC-M005-T009-A-P001-I001"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T009-A-P001-I001"]),
        author="Anne Durand",
        published_on="2026-06-20",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t009-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T009-A-PARENT",
        parent_text="Parent A: convex risk budget and appendix evidence.",
        dense_score=0.91,
        sparse_score=8.0,
    ),
    RetrievalDocument(
        projection_id="PROJ-M005-T009-SEARCH",
        projection_profile_id="projection-profile-m005-t009",
        build_fingerprint="d" * 64,
        index_generation="IDX-M005-T009-SEARCH",
        chunk_id="KCHK-M005-T009-A-002",
        canonical_version_id="CVER-M005-T009-A-0001",
        document_id="DOC-M005-T009-A",
        text=texts["DOC-M005-T009-A-P001-I002"],
        source_locator=locator("DOC-M005-T009-A", "DOC-M005-T009-A-P001-I002", texts["DOC-M005-T009-A-P001-I002"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T009-A-P001-I002"]),
        author="Anne Durand",
        published_on="2026-06-20",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t009-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T009-A-PARENT",
        parent_text="Parent A: convex risk budget and appendix evidence.",
        dense_score=0.89,
        sparse_score=7.0,
    ),
    RetrievalDocument(
        projection_id="PROJ-M005-T009-SEARCH",
        projection_profile_id="projection-profile-m005-t009",
        build_fingerprint="d" * 64,
        index_generation="IDX-M005-T009-SEARCH",
        chunk_id="KCHK-M005-T009-B-001",
        canonical_version_id="CVER-M005-T009-B-0001",
        document_id="DOC-M005-T009-B",
        text=texts["DOC-M005-T009-B-P001-I001"],
        source_locator=locator("DOC-M005-T009-B", "DOC-M005-T009-B-P001-I001", texts["DOC-M005-T009-B-P001-I001"], policy),
        content_hash=content_hash_for(texts["DOC-M005-T009-B-P001-I001"]),
        author="Anne Durand",
        published_on="2026-06-21",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t009-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T009-B-PARENT",
        parent_text="Parent B: tail hedges and crisis convexity.",
        dense_score=0.75,
        sparse_score=12.0,
    ),
)


def build_adapter(*, projection_status=ProjectionStatus.SEARCHABLE, projections=None):
    repository = InMemoryKnowledgeProjectionRepository(
        projections=projections
        if projections is not None
        else (projection(status=projection_status),)
    )
    retrieval_index = InMemoryHybridRetrievalIndex(documents=documents)
    reranker = InMemoryReranker(
        scores_by_chunk_id={
            "KCHK-M005-T009-B-001": 0.98,
            "KCHK-M005-T009-A-001": 0.72,
            "KCHK-M005-T009-A-002": 0.70,
        }
    )
    trace_store = InMemorySearchTraceStore.empty()
    resolver = RecordingSourceLocatorResolver()
    search = SearchKnowledge(
        projection_repository=repository,
        retrieval_index=retrieval_index,
        reranker=reranker,
        source_locator_resolver=resolver,
        trace_store=trace_store,
    )
    adapter = KnowledgeSearchHttpAdapter(
        search_commands=search,
        search_profile_catalog=InMemorySearchProfileCatalog(
            {"hybrid-search-public-m005-t009": hybrid_policy()}
        ),
    )
    return adapter, trace_store, resolver


def post_search(adapter, body, path="/v1/search"):
    return adapter.handle(HttpRequest(method="POST", path=path, body=body))


# Given une projection actuelle est SEARCHABLE.
# When un client appelle POST /v1/search avec une requête valide.
# Then KA retourne des preuves candidates citées, scorées et traçables sans exposer Qdrant.
adapter, trace_store, resolver = build_adapter()
accepted = post_search(adapter, search_request_body())

assert_equal(accepted.status_code, 200, "POST /v1/search doit retourner 200 sur recherche valide.")
assert_equal(
    set(accepted.body.keys()),
    {"search_trace_id", "projection_id", "results", "warnings", "applied_filters"},
    "La réponse doit rester limitée au contrat public KA.",
)
assert_equal(accepted.body["projection_id"], "PROJ-M005-T009-SEARCH", "La réponse doit nommer la projection publique.")
assert_true(accepted.body["search_trace_id"].startswith("STRC-"), "La réponse doit référencer une trace de recherche.")
assert_equal(len(accepted.body["results"]), 2, "La recherche doit retourner les preuves candidates diversifiées.")
assert_equal(trace_store.trace_count(), 1, "La commande publique doit persister une trace via SearchKnowledge.")
assert_equal(
    tuple(resolver.resolved_item_ids),
    tuple(result["source_locator"]["item_id"] for result in accepted.body["results"]),
    "Chaque SourceLocator retourné doit être résolu.",
)
for result in accepted.body["results"]:
    assert_equal(
        set(result.keys()),
        {"chunk_id", "document_id", "canonical_version_id", "content_hash", "source_locator", "scores", "excerpt"},
        "Chaque preuve candidate doit exposer seulement le contrat public.",
    )
    assert_equal(result["content_hash"], result["source_locator"]["content_hash"], "La citation doit être cohérente avec le hash.")
    assert_true(result["scores"]["dense_score"] >= 0, "Le score dense doit être public.")
    assert_true(result["scores"]["sparse_score"] >= 0, "Le score sparse doit être public.")
    assert_true(result["scores"]["fusion_score"] > 0, "Le score de fusion doit être public sans trace interne.")
    assert_true(result["scores"]["rerank_score"] is not None, "Le score rerank doit être public.")

for forbidden in (
    "qdrant",
    "embedding_model",
    "projection_profile_id",
    "build_fingerprint",
    "index_generation",
    "fusion_trace",
    "dense_model",
    "sparse_model",
    "rerank_model",
    "parent_text",
    "verified_claim",
    "business_conclusion",
):
    assert_not_contains(accepted.body, forbidden, "La réponse publique ne doit pas exposer de détail interne.")

trace_payload = trace_store.trace_for_id(accepted.body["search_trace_id"]).to_payload()
assert_false(
    "Convex risk budget protects" in repr(trace_payload),
    "La trace ne doit pas stocker le texte documentaire complet.",
)

# Given un corps ambigu ou invalide.
# Then le transport refuse sans valeur par défaut et sans appeler une recherche vide.
ambiguous = post_search(adapter, {**search_request_body(), "query": "alias non supporté"})
assert_equal(ambiguous.status_code, 400, "Un corps ambigu doit retourner 400.")
assert_equal(ambiguous.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le refus du corps ambigu doit être stable.")

missing_query = dict(search_request_body())
del missing_query["query_text"]
invalid_query = post_search(adapter, missing_query)
assert_equal(invalid_query.status_code, 400, "Une requête incomplète doit retourner 400.")
assert_equal(invalid_query.body["error_code"], "HTTP_REQUEST_INVALID", "Le code de requête invalide doit être stable.")

wrong_endpoint = post_search(
    adapter,
    search_request_body(),
    path="/v1/documents/DOC-M005-T009-A/index",
)
assert_equal(wrong_endpoint.status_code, 404, "L'adaptateur de recherche ne doit pas router l'indexation KA.")
assert_equal(wrong_endpoint.body["error_code"], "ENDPOINT_NOT_FOUND", "Le mauvais endpoint doit être explicite.")

# Given une projection absente.
# Then KA retourne 404 sans fallback vers une recherche vide.
missing_adapter, missing_trace_store, _ = build_adapter(projections=())
missing_projection = post_search(
    missing_adapter,
    search_request_body(projection_id="PROJ-M005-T009-MISSING"),
)
assert_equal(missing_projection.status_code, 404, "Une projection absente doit retourner 404.")
assert_equal(
    missing_projection.body,
    {"error_code": "PROJECTION_NOT_FOUND", "projection_id": "PROJ-M005-T009-MISSING"},
    "PROJECTION_NOT_FOUND doit rester public et stable.",
)
assert_equal(missing_trace_store.trace_count(), 0, "Une projection absente ne doit pas créer de trace.")

# Given une projection STALE.
# Then KA retourne 409 sans servir l'ancienne génération.
stale_adapter, stale_trace_store, _ = build_adapter(projection_status=ProjectionStatus.STALE)
stale = post_search(stale_adapter, search_request_body())
assert_equal(stale.status_code, 409, "Une projection STALE doit retourner 409.")
assert_equal(stale.body, {"error_code": "PROJECTION_STALE", "projection_id": "PROJ-M005-T009-SEARCH"}, "PROJECTION_STALE doit être explicite.")
assert_equal(stale_trace_store.trace_count(), 0, "Une projection STALE ne doit pas créer de trace.")

# Given un filtre inconnu.
# Then KA retourne FILTER_NOT_SUPPORTED et ne le convertit pas silencieusement.
unsupported_filter = post_search(
    adapter,
    search_request_body(filters={"desk": "macro"}),
)
assert_equal(unsupported_filter.status_code, 422, "Un filtre non supporté doit retourner 422.")
assert_equal(
    unsupported_filter.body,
    {"error_code": "FILTER_NOT_SUPPORTED", "dimension": "desk"},
    "Le filtre refusé doit être nommé.",
)

# Given un filtre valide mais sans résultat utile.
# Then KA ne retourne pas 200 avec une liste vide.
empty_result = post_search(
    adapter,
    search_request_body(filters={"author": "Auteur absent"}),
)
assert_equal(empty_result.status_code, 503, "Une recherche sans chunk éligible ne doit pas retourner 200.")
assert_equal(empty_result.body["error_code"], "SEARCH_INDEX_UNAVAILABLE", "L'indisponibilité de recherche doit être explicite.")

# Given un profil public inconnu.
# Then KA refuse le profil sans fallback vers un profil par défaut.
unsupported_profile = post_search(
    adapter,
    search_request_body(search_profile_id="hybrid-search-public-m005-inconnu"),
)
assert_equal(unsupported_profile.status_code, 422, "Un profil inconnu doit retourner 422.")
assert_equal(unsupported_profile.body["error_code"], "SEARCH_PROFILE_UNSUPPORTED", "Le profil inconnu doit être public.")

print("Test d'acceptation T-009 commande de recherche publique KA M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_search_command_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 commande de recherche publique KA M-005: OK"
