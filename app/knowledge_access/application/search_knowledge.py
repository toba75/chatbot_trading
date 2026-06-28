"""Cas d'usage KA de recherche de preuves candidates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.source_references import SourceLocator
from app.knowledge_access.domain.knowledge_projection import KnowledgeProjection, ProjectionStatus
from app.knowledge_access.domain.projection_metadata import (
    EvidenceDiversificationPolicy,
    ProjectionFreshnessPolicy,
    ProjectionMetadata,
    SearchFilter,
)
from app.knowledge_access.domain.search import (
    RetrievalCandidate,
    RetrievalDocument,
    SearchChannelHit,
    SearchRequest,
    SearchResponse,
    SearchTracePolicy,
    SearchTraceRecord,
)


class SearchKnowledgeError(ValueError):
    """Erreur metier stable de SearchKnowledge."""


class SearchProjectionStaleError(SearchKnowledgeError):
    """Erreur produite quand une projection STALE serait servie."""

    def __init__(self, projection_id: str) -> None:
        self.projection_id = _ensure_text(projection_id, "projection_id")
        super().__init__(f"PROJECTION_STALE: {self.projection_id}")


class SearchProjectionNotFoundError(SearchKnowledgeError):
    """Erreur produite quand la projection demandée est absente."""

    def __init__(self, projection_id: str) -> None:
        self.projection_id = _ensure_text(projection_id, "projection_id")
        super().__init__(f"PROJECTION_NOT_FOUND: {self.projection_id}")


class SearchProjectionUnavailableError(SearchKnowledgeError):
    """Erreur produite quand la projection n'est pas SEARCHABLE."""

    def __init__(self, *, projection_id: str, status: ProjectionStatus) -> None:
        self.projection_id = _ensure_text(projection_id, "projection_id")
        self.status = ProjectionStatus.from_value(status)
        super().__init__(f"PROJECTION_NOT_SEARCHABLE: {self.projection_id}; {self.status.value}")


class SearchProfileUnsupportedError(SearchKnowledgeError):
    """Erreur produite quand le profil demande un port absent."""

    def __init__(self, reason: str) -> None:
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"SEARCH_PROFILE_UNSUPPORTED: {self.reason}")


class SearchIndexUnavailableError(SearchKnowledgeError):
    """Erreur produite quand l'index de recherche ne peut pas repondre."""

    def __init__(self, reason: str) -> None:
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"SEARCH_INDEX_UNAVAILABLE: {self.reason}")


class SearchTracePersistenceError(SearchKnowledgeError):
    """Erreur produite quand la trace de recherche n'est pas persistée."""


class SearchProjectionRepository(Protocol):
    """Port de lecture de l'etat KnowledgeProjection."""

    def projection_for_id(self, projection_id: str) -> KnowledgeProjection:
        """Retourne une projection existante."""


class HybridRetrievalIndex(Protocol):
    """Port de recherche hybride masquant l'index technique."""

    def metadata_for_projection(self, projection_id: str) -> tuple[ProjectionMetadata, ...]:
        """Retourne les metadonnees filtrables d'une projection."""

    def search_dense(
        self,
        *,
        projection_id: str,
        query_text: str,
        eligible_chunk_ids: Sequence[str],
        limit: int,
    ) -> tuple[SearchChannelHit, ...]:
        """Recherche dense."""

    def search_sparse(
        self,
        *,
        projection_id: str,
        query_text: str,
        eligible_chunk_ids: Sequence[str],
        limit: int,
    ) -> tuple[SearchChannelHit, ...]:
        """Recherche sparse."""

    def document_for_chunk_id(self, chunk_id: str) -> RetrievalDocument:
        """Retourne le passage complet d'un chunk."""


class Reranker(Protocol):
    """Port de reranking."""

    def rerank(
        self,
        *,
        request: SearchRequest,
        candidates: Sequence[RetrievalCandidate],
    ) -> tuple[RetrievalCandidate, ...]:
        """Retourne les candidats rerankés."""


class SourceLocatorResolver(Protocol):
    """Port de resolution publique des SourceLocator."""

    def resolve(self, locator: SourceLocator) -> object:
        """Résout le SourceLocator ou échoue explicitement."""


class SearchTraceStore(Protocol):
    """Port de persistance des traces de recherche."""

    def save(self, trace: SearchTraceRecord) -> SearchTraceRecord:
        """Persiste une trace."""


@dataclass(frozen=True)
class SearchKnowledge:
    """Orchestre SearchKnowledge sans exposer Qdrant aux consommateurs."""

    projection_repository: SearchProjectionRepository
    retrieval_index: HybridRetrievalIndex
    reranker: Reranker | None
    source_locator_resolver: SourceLocatorResolver
    trace_store: SearchTraceStore

    def __post_init__(self) -> None:
        if not callable(getattr(self.projection_repository, "projection_for_id", None)):
            raise ValueError("projection_repository sans projection_for_id")
        for method_name in ("metadata_for_projection", "search_dense", "search_sparse", "document_for_chunk_id"):
            if not callable(getattr(self.retrieval_index, method_name, None)):
                raise ValueError(f"retrieval_index sans {method_name}")
        if self.reranker is not None and not callable(getattr(self.reranker, "rerank", None)):
            raise ValueError("reranker sans rerank")
        if not callable(getattr(self.source_locator_resolver, "resolve", None)):
            raise ValueError("source_locator_resolver sans resolve")
        if not callable(getattr(self.trace_store, "save", None)):
            raise ValueError("trace_store sans save")

    def search(self, request: SearchRequest) -> SearchResponse:
        parsed_request = _ensure_search_request(request)
        try:
            projection = self.projection_repository.projection_for_id(parsed_request.projection_id)
        except ValueError as exc:
            if str(exc).startswith("projection inconnue:"):
                raise SearchProjectionNotFoundError(parsed_request.projection_id) from exc
            raise
        _ensure_projection(projection)
        self._ensure_searchable(projection)

        all_metadata = self.retrieval_index.metadata_for_projection(parsed_request.projection_id)
        filtered_metadata, applied_filter_traces = parsed_request.filters.apply(all_metadata)
        eligible_chunk_ids = tuple(metadata.chunk_id for metadata in filtered_metadata)
        if len(eligible_chunk_ids) == 0:
            raise SearchIndexUnavailableError("aucun chunk eligible apres filtres")

        freshness = ProjectionFreshnessPolicy(require_current=True).evaluate(
            projection.status,
            contractual_warning="PROJECTION_SEARCHABLE_VERIFIED",
        )
        dense_hits = self.retrieval_index.search_dense(
            projection_id=parsed_request.projection_id,
            query_text=parsed_request.query_text,
            eligible_chunk_ids=eligible_chunk_ids,
            limit=parsed_request.hybrid_policy.dense_limit,
        )
        sparse_hits = self.retrieval_index.search_sparse(
            projection_id=parsed_request.projection_id,
            query_text=parsed_request.query_text,
            eligible_chunk_ids=eligible_chunk_ids,
            limit=parsed_request.hybrid_policy.sparse_limit,
        )
        fused_candidates = parsed_request.hybrid_policy.fuse(
            dense_hits=dense_hits,
            sparse_hits=sparse_hits,
        )

        candidates: list[RetrievalCandidate] = []
        for fused_candidate in fused_candidates:
            if fused_candidate.chunk_id not in eligible_chunk_ids:
                continue
            document = self.retrieval_index.document_for_chunk_id(fused_candidate.chunk_id)
            if document.projection_id != parsed_request.projection_id:
                raise SearchIndexUnavailableError("document hors projection")
            parent_context = parsed_request.hybrid_policy.parent_context_policy.expand(document)
            candidates.append(
                RetrievalCandidate.from_document(
                    document=document,
                    score_bundle=fused_candidate.score_bundle,
                    fusion_trace=fused_candidate.fusion_trace,
                    parent_context=parent_context,
                )
            )

        if len(candidates) == 0:
            raise SearchIndexUnavailableError("aucun candidat apres fusion")

        reranked_candidates = self._rerank_if_required(
            request=parsed_request,
            candidates=tuple(candidates),
        )
        diversified_candidates, diversification_trace = parsed_request.hybrid_policy.diversify(
            reranked_candidates
        )
        if len(diversified_candidates) == 0:
            raise SearchIndexUnavailableError("aucun candidat apres diversification")
        for candidate in diversified_candidates:
            self.source_locator_resolver.resolve(candidate.source_locator)

        trace = SearchTraceRecord.from_search(
            request=parsed_request,
            projection_id=projection.projection_id,
            projection_status=projection.status.value,
            projection_profile_id=projection.projection_profile.projection_profile_id,
            build_fingerprint=projection.build_fingerprint.value,
            index_generation=diversified_candidates[0].index_generation,
            candidates=diversified_candidates,
            applied_filters=tuple(trace.to_payload() for trace in applied_filter_traces),
            freshness_warnings=freshness.warnings,
            fusion_trace=tuple(candidate.fusion_trace for candidate in diversified_candidates),
            diversification_trace=diversification_trace,
        )
        persisted_trace = SearchTracePolicy(require_persisted_trace=True).persist(
            trace=trace,
            trace_store=self.trace_store,
        )
        return SearchResponse(
            search_trace_id=persisted_trace.search_trace_id,
            projection_id=projection.projection_id,
            candidates=diversified_candidates,
            warnings=freshness.warnings,
            applied_filters=tuple(trace.to_payload() for trace in applied_filter_traces),
        )

    def _ensure_searchable(self, projection: KnowledgeProjection) -> None:
        if projection.status is ProjectionStatus.STALE:
            raise SearchProjectionStaleError(projection.projection_id)
        if projection.status is not ProjectionStatus.SEARCHABLE:
            raise SearchProjectionUnavailableError(
                projection_id=projection.projection_id,
                status=projection.status,
            )

    def _rerank_if_required(
        self,
        *,
        request: SearchRequest,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> tuple[RetrievalCandidate, ...]:
        if not request.hybrid_policy.rerank_required:
            return candidates
        if self.reranker is None:
            raise SearchProfileUnsupportedError("RERANKER_REQUIRED")
        reranked = self.reranker.rerank(request=request, candidates=candidates)
        parsed_reranked = _ensure_candidates(reranked)
        if len(parsed_reranked) != len(candidates):
            raise SearchProfileUnsupportedError("RERANK_RESULT_INCOMPLETE")
        missing_rerank = tuple(
            candidate.chunk_id
            for candidate in parsed_reranked
            if candidate.score_bundle.rerank_score is None
        )
        if len(missing_rerank) > 0:
            raise SearchProfileUnsupportedError(f"RERANK_SCORE_MISSING:{missing_rerank[0]}")
        return parsed_reranked


def _ensure_search_request(value: SearchRequest) -> SearchRequest:
    if not isinstance(value, SearchRequest):
        raise ValueError("search_request invalide")
    return value


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("projection invalide")
    return value


def _ensure_candidates(value: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    if value is None:
        raise ValueError("candidates absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("candidates invalides")
    candidates = tuple(value)
    for candidate in candidates:
        if not isinstance(candidate, RetrievalCandidate):
            raise ValueError("candidate invalide")
    return candidates


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "HybridRetrievalIndex",
    "KnowledgeSearchPort",
    "Reranker",
    "SearchIndexUnavailableError",
    "SearchKnowledge",
    "SearchKnowledgeError",
    "SearchProfileUnsupportedError",
    "SearchProjectionNotFoundError",
    "SearchProjectionRepository",
    "SearchProjectionStaleError",
    "SearchProjectionUnavailableError",
    "SearchTracePersistenceError",
    "SearchTraceStore",
    "SourceLocatorResolver",
]


KnowledgeSearchPort = SearchKnowledge
