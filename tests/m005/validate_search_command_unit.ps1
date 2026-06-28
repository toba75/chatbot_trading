$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import ast
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef, SourceLocator, SourceLocatorValidationPolicy
from app.knowledge_access.adapters.search_http import (
    HttpRequest,
    KnowledgeSearchHttpAdapter,
    SearchRequestDto,
    SearchResponseDto,
)
from app.knowledge_access.application.search_knowledge import (
    SearchIndexUnavailableError,
    SearchProfileUnsupportedError,
    SearchProjectionNotFoundError,
    SearchProjectionStaleError,
)
from app.knowledge_access.domain.projection_metadata import EvidenceDiversificationPolicy
from app.knowledge_access.domain.search import (
    HybridRetrievalPolicy,
    ParentContextExpansionPolicy,
    RetrievalCandidate,
    RetrievalDocument,
    SearchRequest,
    SearchResponse,
    SearchScoreBundle,
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


def assert_raises(expected_type, expected_fragment, action):
    try:
        action()
    except expected_type as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
        return exc
    except Exception as exc:
        raise AssertionError(f"Type d'erreur inattendu: {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M005-T009-UNIT",
            "document_id": "DOC-M005-T009-UNIT",
            "canonical_version_id": "CVER-M005-T009-UNIT-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 1,
            "accepted_at": "2026-06-28T10:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t009-unit-v1",
        }
    )


def locator_for(text):
    ref = canonical_ref()
    policy = SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                "DOC-M005-T009-UNIT-P001-I001": content_hash_for(text),
            }
        },
    )
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M005-T009-UNIT-0001",
            "document_id": "DOC-M005-T009-UNIT",
            "page_pdf": 1,
            "item_id": "DOC-M005-T009-UNIT-P001-I001",
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
        dense_limit=3,
        sparse_limit=3,
        result_limit=2,
        rrf_k=60,
        rerank_required=True,
        diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
        parent_context_policy=ParentContextExpansionPolicy(enabled=True, max_parent_characters=160),
    )


def valid_body(**overrides):
    body = {
        "projection_id": "PROJ-M005-T009-UNIT",
        "query_text": "convex risk",
        "filters": {"author": "Anne Durand"},
        "search_profile_id": "hybrid-search-public-m005-t009",
        "occurred_at": "2026-06-28T10:45:00Z",
        "requested_by_context": "RA",
    }
    body.update(overrides)
    return body


def retrieval_candidate():
    text = "Volatilité convexe observée."
    document = RetrievalDocument(
        projection_id="PROJ-M005-T009-UNIT",
        projection_profile_id="projection-profile-m005-t009-unit",
        build_fingerprint="d" * 64,
        index_generation="IDX-M005-T009-UNIT",
        chunk_id="KCHK-M005-T009-UNIT-A",
        canonical_version_id="CVER-M005-T009-UNIT-0001",
        document_id="DOC-M005-T009-UNIT",
        text=text,
        source_locator=locator_for(text),
        content_hash=content_hash_for(text),
        author="Anne Durand",
        published_on="2026-06-28",
        content_type="research_note",
        canonical_quality="canonical-quality-m005-t009-unit-v1",
        chunk_level="CHILD",
        parent_chunk_id="KCHK-M005-T009-UNIT-PARENT",
        parent_text="Parent: volatilité convexe et risque de queue.",
        dense_score=0.92,
        sparse_score=7.0,
    )
    parent_context = hybrid_policy().parent_context_policy.expand(document)
    return RetrievalCandidate.from_document(
        document=document,
        score_bundle=SearchScoreBundle(
            dense_score=0.92,
            sparse_score=7.0,
            fusion_score=0.032,
            rerank_score=0.81,
            diversification_rank=1,
        ),
        fusion_trace={"chunk_id": "KCHK-M005-T009-UNIT-A", "dense_rank": 1, "sparse_rank": 1},
        parent_context=parent_context,
    )


class InMemorySearchProfileCatalog:
    def __init__(self, profiles):
        self._profiles = dict(profiles)

    def profile_for_id(self, search_profile_id):
        profile = self._profiles.get(search_profile_id)
        if profile is None:
            raise ValueError(f"profil de recherche inconnu: {search_profile_id}")
        return profile


class ScriptedSearchCommands:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def adapter_for(scripted_commands):
    return KnowledgeSearchHttpAdapter(
        search_commands=scripted_commands,
        search_profile_catalog=InMemorySearchProfileCatalog(
            {"hybrid-search-public-m005-t009": hybrid_policy()}
        ),
    )


# SearchRequestDto valide strictement le corps public sans profil par défaut.
dto = SearchRequestDto.from_payload(valid_body())
domain_request = dto.to_domain_request(hybrid_policy())
assert_true(isinstance(domain_request, SearchRequest), "Le DTO doit produire une SearchRequest applicative.")
assert_equal(domain_request.projection_id, "PROJ-M005-T009-UNIT", "La projection doit être conservée.")
assert_equal(domain_request.query_text, "convex risk", "La requête doit être conservée.")
assert_equal(domain_request.requested_by_context, "RA", "Le contexte demandeur doit être conservé.")
assert_equal(domain_request.filters.author, ("Anne Durand",), "Les filtres publics doivent être convertis.")

for field_name in ("projection_id", "query_text", "filters", "search_profile_id", "occurred_at", "requested_by_context"):
    incomplete = valid_body()
    del incomplete[field_name]
    assert_raises(ValueError, f"{field_name} absent", lambda body=incomplete: SearchRequestDto.from_payload(body))

assert_raises(ValueError, "body ambigu", lambda: SearchRequestDto.from_payload({**valid_body(), "query": "alias"}))
assert_raises(ValueError, "body champ interdit", lambda: SearchRequestDto.from_payload({**valid_body(), "qdrant_collection": "private"}))
assert_raises(ValueError, "body champ interdit", lambda: SearchRequestDto.from_payload({**valid_body(), "embedding_model": "private"}))
assert_raises(ValueError, "filters non objet", lambda: SearchRequestDto.from_payload(valid_body(filters=[])))
assert_raises(ValueError, "query_text vide", lambda: SearchRequestDto.from_payload(valid_body(query_text="")))
assert_raises(ValueError, "requested_by_context inconnu", lambda: SearchRequestDto.from_payload(valid_body(requested_by_context="SP")))

# SearchResponseDto sérialise seulement le contrat public.
candidate = retrieval_candidate()
domain_response = SearchResponse(
    search_trace_id="STRC-11111111111111111111111111111111",
    projection_id="PROJ-M005-T009-UNIT",
    candidates=(candidate,),
    warnings=("PROJECTION_SEARCHABLE_VERIFIED",),
    applied_filters=({"dimension": "author", "operator": "IN", "requested_value": ("Anne Durand",), "eligible_count": 1},),
)
payload = SearchResponseDto.from_domain(domain_response).to_payload()
assert_equal(
    set(payload.keys()),
    {"search_trace_id", "projection_id", "results", "warnings", "applied_filters"},
    "La réponse DTO doit rester le contrat public.",
)
assert_equal(len(payload["results"]), 1, "La réponse doit porter une preuve candidate.")
result = payload["results"][0]
assert_equal(
    set(result.keys()),
    {"chunk_id", "document_id", "canonical_version_id", "content_hash", "source_locator", "scores", "excerpt"},
    "Le résultat DTO ne doit pas exposer de champ interne.",
)
assert_equal(result["source_locator"]["content_hash"], result["content_hash"], "Le hash doit rester traçable.")
assert_equal(result["scores"]["rerank_score"], 0.81, "Le score rerank doit être sérialisé.")
for forbidden in (
    "qdrant",
    "projection_profile_id",
    "build_fingerprint",
    "index_generation",
    "fusion_trace",
    "parent_text",
    "embedding_model",
    "dense_model",
    "sparse_model",
    "rerank_model",
):
    assert_false(forbidden in repr(payload).lower(), f"Champ interne interdit dans le DTO: {forbidden}.")

# L'adaptateur mappe les erreurs publiques et ne retourne jamais 200 sur erreur métier.
success_commands = ScriptedSearchCommands(response=domain_response)
success = adapter_for(success_commands).handle(
    HttpRequest(method="POST", path="/v1/search", body=valid_body())
)
assert_equal(success.status_code, 200, "Le succès HTTP doit retourner 200.")
assert_equal(len(success_commands.requests), 1, "Le transport doit appeler une seule recherche.")

invalid_body_commands = ScriptedSearchCommands(response=domain_response)
invalid_body = adapter_for(invalid_body_commands).handle(
    HttpRequest(method="POST", path="/v1/search", body={**valid_body(), "query": "alias"})
)
assert_equal(invalid_body.status_code, 400, "Le corps ambigu doit retourner 400.")
assert_equal(len(invalid_body_commands.requests), 0, "Un corps invalide ne doit pas appeler SearchKnowledge.")

error_cases = (
    (
        SearchProjectionNotFoundError("PROJ-M005-T009-MISSING"),
        404,
        {"error_code": "PROJECTION_NOT_FOUND", "projection_id": "PROJ-M005-T009-MISSING"},
    ),
    (
        SearchProjectionStaleError("PROJ-M005-T009-UNIT"),
        409,
        {"error_code": "PROJECTION_STALE", "projection_id": "PROJ-M005-T009-UNIT"},
    ),
    (
        SearchProfileUnsupportedError("RERANKER_REQUIRED"),
        422,
        {"error_code": "SEARCH_PROFILE_UNSUPPORTED", "reason": "RERANKER_REQUIRED"},
    ),
    (
        SearchIndexUnavailableError("aucun chunk eligible apres filtres"),
        503,
        {"error_code": "SEARCH_INDEX_UNAVAILABLE", "reason": "aucun chunk eligible apres filtres"},
    ),
)
for error, status_code, expected_body in error_cases:
    response = adapter_for(ScriptedSearchCommands(error=error)).handle(
        HttpRequest(method="POST", path="/v1/search", body=valid_body())
    )
    assert_equal(response.status_code, status_code, f"{expected_body['error_code']} doit mapper le statut HTTP.")
    assert_equal(response.body, expected_body, f"{expected_body['error_code']} doit mapper le corps public.")

unsupported_filter = adapter_for(ScriptedSearchCommands(response=domain_response)).handle(
    HttpRequest(method="POST", path="/v1/search", body=valid_body(filters={"desk": "macro"}))
)
assert_equal(unsupported_filter.status_code, 422, "Un filtre non supporté doit retourner 422.")
assert_equal(unsupported_filter.body, {"error_code": "FILTER_NOT_SUPPORTED", "dimension": "desk"}, "La dimension refusée doit être nommée.")

unsupported_profile = adapter_for(ScriptedSearchCommands(response=domain_response)).handle(
    HttpRequest(method="POST", path="/v1/search", body=valid_body(search_profile_id="profil-absent"))
)
assert_equal(unsupported_profile.status_code, 422, "Un profil absent doit retourner 422.")
assert_equal(unsupported_profile.body["error_code"], "SEARCH_PROFILE_UNSUPPORTED", "Le profil absent ne doit pas recevoir de fallback.")

wrong_endpoint = adapter_for(ScriptedSearchCommands(response=domain_response)).handle(
    HttpRequest(method="POST", path="/v1/research/deep", body=valid_body())
)
assert_equal(wrong_endpoint.status_code, 404, "T-009 ne doit pas ajouter d'endpoint RA.")
index_endpoint = adapter_for(ScriptedSearchCommands(response=domain_response)).handle(
    HttpRequest(method="POST", path="/v1/documents/DOC-M005-T009-UNIT/index", body=valid_body())
)
assert_equal(index_endpoint.status_code, 404, "L'adaptateur de recherche ne doit pas router l'indexation KA.")

# L'adaptateur ne journalise pas de texte documentaire complet.
adapter_path = Path(sys.argv[1]) / "app" / "knowledge_access" / "adapters" / "search_http.py"
tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        called_name = getattr(node.func, "id", None)
        called_attr = getattr(node.func, "attr", None)
        if called_name == "print" or called_attr in {"debug", "info", "warning", "error", "exception"}:
            raise AssertionError("L'adaptateur HTTP de recherche ne doit pas écrire de log documentaire.")
    if isinstance(node, ast.Import):
        imported_roots = {alias.name.split(".")[0] for alias in node.names}
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        imported_roots = {node.module.split(".")[0]}
    else:
        imported_roots = set()
    forbidden_imports = imported_roots & {"qdrant_client", "logging", "fastapi", "starlette", "flask", "django"}
    if forbidden_imports:
        raise AssertionError(f"Import interdit dans search_http.py: {sorted(forbidden_imports)}")

print("Tests unitaires T-009 commande de recherche publique KA M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_search_command_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 commande de recherche publique KA M-005: OK"
