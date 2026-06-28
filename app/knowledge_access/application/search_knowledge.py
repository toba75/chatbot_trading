"""Cas d'usage KA de recherche de preuves candidates."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.knowledge_access.application.projection_events import (
    KnowledgeProjectionEventFactory,
    ProjectionOutbox,
    append_projection_events_to_outbox,
)
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


class KnowledgeAccessMetrics(Protocol):
    """Port minimal de métriques runtime KA."""

    def increment(self, metric_name: str, *, labels: dict[str, str]) -> None:
        """Incrémente un compteur nommé."""

    def observe(self, metric_name: str, value: float, *, labels: dict[str, str]) -> None:
        """Publie une observation numérique."""


@dataclass(frozen=True)
class SearchKnowledge:
    """Orchestre SearchKnowledge sans exposer Qdrant aux consommateurs."""

    projection_repository: SearchProjectionRepository
    retrieval_index: HybridRetrievalIndex
    reranker: Reranker | None
    source_locator_resolver: SourceLocatorResolver
    trace_store: SearchTraceStore
    outbox: ProjectionOutbox
    metrics: KnowledgeAccessMetrics

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
        if not callable(getattr(self.outbox, "has_event", None)):
            raise ValueError("outbox invalide")
        if not callable(getattr(self.outbox, "append_many_in_transaction", None)):
            raise ValueError("outbox invalide")
        if not callable(getattr(self.metrics, "increment", None)):
            raise ValueError("metrics sans increment")
        if not callable(getattr(self.metrics, "observe", None)):
            raise ValueError("metrics sans observe")

    def search(self, request: SearchRequest) -> SearchResponse:
        started_at = time.perf_counter()
        parsed_request = _ensure_search_request(request)
        projection = self._projection_for_id(parsed_request.projection_id)
        self._ensure_current_searchable(parsed_request, projection)

        try:
            all_metadata = self.retrieval_index.metadata_for_projection(parsed_request.projection_id)
        except ValueError as exc:
            raise SearchIndexUnavailableError(str(exc)) from exc
        filtered_metadata, applied_filter_traces = parsed_request.filters.apply(all_metadata)
        eligible_chunk_ids = tuple(metadata.chunk_id for metadata in filtered_metadata)
        if len(eligible_chunk_ids) == 0:
            return self._empty_response(
                request=parsed_request,
                projection=projection,
                applied_filter_traces=applied_filter_traces,
                started_at=started_at,
            )

        freshness = ProjectionFreshnessPolicy(require_current=True).evaluate(
            projection.status,
        )
        try:
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
        except ValueError as exc:
            raise SearchIndexUnavailableError(str(exc)) from exc

        candidates: list[RetrievalCandidate] = []
        for fused_candidate in fused_candidates:
            if fused_candidate.chunk_id not in eligible_chunk_ids:
                continue
            try:
                document = self.retrieval_index.document_for_chunk_id(fused_candidate.chunk_id)
            except ValueError as exc:
                raise SearchIndexUnavailableError(str(exc)) from exc
            if document.projection_id != parsed_request.projection_id:
                raise SearchIndexUnavailableError("document hors projection")
            try:
                parent_context = parsed_request.hybrid_policy.parent_context_policy.expand(document)
            except ValueError as exc:
                raise SearchIndexUnavailableError(str(exc)) from exc
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
            try:
                self.source_locator_resolver.resolve(candidate.source_locator)
            except ValueError as exc:
                raise SearchIndexUnavailableError(str(exc)) from exc

        projection = self._projection_for_id(parsed_request.projection_id)
        self._ensure_current_searchable(parsed_request, projection)
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
        try:
            persisted_trace = SearchTracePolicy(require_persisted_trace=True).persist(
                trace=trace,
                trace_store=self.trace_store,
            )
        except ValueError as exc:
            raise SearchTracePersistenceError(str(exc)) from exc
        response = SearchResponse(
            search_trace_id=persisted_trace.search_trace_id,
            projection_id=projection.projection_id,
            candidates=diversified_candidates,
            warnings=freshness.warnings,
            applied_filters=tuple(trace.to_payload() for trace in applied_filter_traces),
        )
        self._publish_search_performed(
            request=parsed_request,
            projection=projection,
            response=response,
        )
        self.metrics.observe(
            "knowledge_search_latency_seconds",
            time.perf_counter() - started_at,
            labels={"projection_id": projection.projection_id, "status": "SEARCH_COMPLETED"},
        )
        return response

    def _projection_for_id(self, projection_id: str) -> KnowledgeProjection:
        try:
            projection = self.projection_repository.projection_for_id(projection_id)
        except ValueError as exc:
            if str(exc).startswith("projection inconnue:"):
                raise SearchProjectionNotFoundError(projection_id) from exc
            raise
        return _ensure_projection(projection)

    def _ensure_current_searchable(
        self,
        request: SearchRequest,
        projection: KnowledgeProjection,
    ) -> None:
        try:
            self._ensure_searchable(projection)
        except SearchProjectionStaleError:
            self.metrics.increment(
                "knowledge_search_stale_projection_total",
                labels={"projection_id": request.projection_id},
            )
            raise

    def _empty_response(
        self,
        *,
        request: SearchRequest,
        projection: KnowledgeProjection,
        applied_filter_traces: Sequence[Any],
        started_at: float,
    ) -> SearchResponse:
        projection = self._projection_for_id(request.projection_id)
        self._ensure_current_searchable(request, projection)
        trace = SearchTraceRecord.from_search(
            request=request,
            projection_id=projection.projection_id,
            projection_status=projection.status.value,
            projection_profile_id=projection.projection_profile.projection_profile_id,
            build_fingerprint=projection.build_fingerprint.value,
            index_generation="NO_RESULT",
            candidates=(),
            applied_filters=tuple(trace.to_payload() for trace in applied_filter_traces),
            freshness_warnings=(),
            fusion_trace=(),
            diversification_trace={
                "mode": request.hybrid_policy.diversification_policy.mode,
                "input_count": 0,
                "output_count": 0,
            },
        )
        try:
            persisted_trace = SearchTracePolicy(require_persisted_trace=True).persist(
                trace=trace,
                trace_store=self.trace_store,
            )
        except ValueError as exc:
            raise SearchTracePersistenceError(str(exc)) from exc
        response = SearchResponse(
            search_trace_id=persisted_trace.search_trace_id,
            projection_id=projection.projection_id,
            candidates=(),
            warnings=(),
            applied_filters=tuple(trace.to_payload() for trace in applied_filter_traces),
        )
        self._publish_search_performed(
            request=request,
            projection=projection,
            response=response,
        )
        self.metrics.observe(
            "knowledge_search_latency_seconds",
            time.perf_counter() - started_at,
            labels={"projection_id": projection.projection_id, "status": "SEARCH_COMPLETED_EMPTY"},
        )
        return response

    def _publish_search_performed(
        self,
        *,
        request: SearchRequest,
        projection: KnowledgeProjection,
        response: SearchResponse,
    ) -> None:
        factory = KnowledgeProjectionEventFactory(
            occurred_at=request.occurred_at,
            correlation_id=_correlation_id_for_search(response.search_trace_id),
            causation_id=_causation_id_for_search(response.search_trace_id),
        )
        append_projection_events_to_outbox(
            outbox=self.outbox,
            events=(
                factory.search_performed(
                    projection=projection,
                    search_trace_id=response.search_trace_id,
                    query_hash=request.query_hash,
                    filters_hash=request.filters_hash,
                    result_count=response.result_count,
                ),
            ),
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


def _correlation_id_for_search(search_trace_id: str) -> str:
    return f"CORR-{_search_trace_suffix(search_trace_id)}"


def _causation_id_for_search(search_trace_id: str) -> str:
    return f"CMD-{_search_trace_suffix(search_trace_id)}"


def _search_trace_suffix(search_trace_id: str) -> str:
    return _ensure_text(search_trace_id, "search_trace_id").removeprefix("STRC-")
