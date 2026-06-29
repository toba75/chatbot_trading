"""Adaptateurs mémoire pour la recherche hybride KA."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.knowledge_access.domain.projection_metadata import ProjectionMetadata
from app.knowledge_access.domain.search import (
    RetrievalCandidate,
    RetrievalDocument,
    SearchChannelHit,
    SearchRequest,
    SearchTraceRecord,
)


class InMemoryHybridRetrievalIndex:
    """Double contractuel d'un index de recherche hybride."""

    def __init__(self, *, documents: Sequence[RetrievalDocument]) -> None:
        self._documents = _ensure_documents(documents)
        self._documents_by_chunk_id = {document.chunk_id: document for document in self._documents}

    def metadata_for_projection(self, projection_id: str) -> tuple[ProjectionMetadata, ...]:
        parsed_projection_id = _ensure_projection_id(projection_id)
        metadata = tuple(
            document.metadata
            for document in self._documents
            if document.projection_id == parsed_projection_id
        )
        if len(metadata) == 0:
            raise ValueError(f"projection sans metadata: {parsed_projection_id}")
        return metadata

    def search_dense(
        self,
        *,
        projection_id: str,
        query_text: str,
        eligible_chunk_ids: Sequence[str],
        limit: int,
    ) -> tuple[SearchChannelHit, ...]:
        return tuple(
            SearchChannelHit(chunk_id=document.chunk_id, score=document.dense_score)
            for document in self._ranked_documents(
                projection_id=projection_id,
                query_text=query_text,
                eligible_chunk_ids=eligible_chunk_ids,
                limit=limit,
                score_name="dense",
            )
        )

    def search_sparse(
        self,
        *,
        projection_id: str,
        query_text: str,
        eligible_chunk_ids: Sequence[str],
        limit: int,
    ) -> tuple[SearchChannelHit, ...]:
        return tuple(
            SearchChannelHit(chunk_id=document.chunk_id, score=document.sparse_score)
            for document in self._ranked_documents(
                projection_id=projection_id,
                query_text=query_text,
                eligible_chunk_ids=eligible_chunk_ids,
                limit=limit,
                score_name="sparse",
            )
        )

    def document_for_chunk_id(self, chunk_id: str) -> RetrievalDocument:
        parsed_chunk_id = _ensure_chunk_id(chunk_id)
        document = self._documents_by_chunk_id.get(parsed_chunk_id)
        if document is None:
            raise ValueError(f"chunk inconnu: {parsed_chunk_id}")
        return document

    def _ranked_documents(
        self,
        *,
        projection_id: str,
        query_text: str,
        eligible_chunk_ids: Sequence[str],
        limit: int,
        score_name: str,
    ) -> tuple[RetrievalDocument, ...]:
        parsed_projection_id = _ensure_projection_id(projection_id)
        _ensure_text(query_text, "query_text")
        parsed_limit = _ensure_positive_integer(limit, "limit")
        eligible_set = _ensure_chunk_id_set(eligible_chunk_ids)
        if score_name == "dense":
            score = lambda document: document.dense_score
        elif score_name == "sparse":
            score = lambda document: document.sparse_score
        else:
            raise ValueError("score_name inconnu")
        ranked = tuple(
            sorted(
                (
                    document
                    for document in self._documents
                    if document.projection_id == parsed_projection_id
                    and document.chunk_id in eligible_set
                    and score(document) > 0
                ),
                key=lambda document: (-score(document), document.chunk_id),
            )
        )
        return ranked[:parsed_limit]


class InMemoryReranker:
    """Double contractuel du port de reranking."""

    def __init__(self, *, scores_by_chunk_id: Mapping[str, float]) -> None:
        self._scores_by_chunk_id = _ensure_score_mapping(scores_by_chunk_id)
        self.calls: list[tuple[str, ...]] = []

    def rerank(
        self,
        *,
        request: SearchRequest,
        candidates: Sequence[RetrievalCandidate],
    ) -> tuple[RetrievalCandidate, ...]:
        if not isinstance(request, SearchRequest):
            raise ValueError("request invalide")
        parsed_candidates = _ensure_candidates(candidates)
        self.calls.append(tuple(candidate.chunk_id for candidate in parsed_candidates))
        reranked: list[RetrievalCandidate] = []
        for candidate in parsed_candidates:
            score = self._scores_by_chunk_id.get(candidate.chunk_id)
            if score is None:
                raise ValueError(f"rerank_score absent: {candidate.chunk_id}")
            reranked.append(candidate.with_rerank_score(score))
        return tuple(
            sorted(
                reranked,
                key=lambda candidate: (
                    -candidate.score_bundle.rerank_score,
                    -candidate.score_bundle.fusion_score,
                    candidate.chunk_id,
                ),
            )
        )


class InMemorySearchTraceStore:
    """Store mémoire strict des traces SearchKnowledge."""

    def __init__(self, *, traces: Sequence[SearchTraceRecord]) -> None:
        parsed_traces = _ensure_traces(traces)
        self._traces_by_id: dict[str, SearchTraceRecord] = {}
        for trace in parsed_traces:
            self.save(trace)

    @classmethod
    def empty(cls) -> "InMemorySearchTraceStore":
        return cls(traces=())

    def save(self, trace: SearchTraceRecord) -> SearchTraceRecord:
        parsed_trace = _ensure_trace(trace)
        existing_trace = self._traces_by_id.get(parsed_trace.search_trace_id)
        if existing_trace is not None:
            if existing_trace.to_payload() != parsed_trace.to_payload():
                raise ValueError(f"search_trace_id duplique incoherent: {parsed_trace.search_trace_id}")
            return existing_trace
        self._traces_by_id[parsed_trace.search_trace_id] = parsed_trace
        return parsed_trace

    def trace_for_id(self, search_trace_id: str) -> SearchTraceRecord:
        parsed_trace_id = _ensure_search_trace_id(search_trace_id)
        trace = self._traces_by_id.get(parsed_trace_id)
        if trace is None:
            raise ValueError(f"trace inconnue: {parsed_trace_id}")
        return trace

    def trace_count(self) -> int:
        return len(self._traces_by_id)


def _ensure_documents(value: Sequence[RetrievalDocument]) -> tuple[RetrievalDocument, ...]:
    if value is None:
        raise ValueError("documents absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("documents invalides")
    documents = tuple(value)
    if len(documents) == 0:
        raise ValueError("documents absents")
    for document in documents:
        if not isinstance(document, RetrievalDocument):
            raise ValueError("document invalide")
    chunk_ids = tuple(document.chunk_id for document in documents)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("chunk_id duplique")
    return documents


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


def _ensure_traces(value: Sequence[SearchTraceRecord]) -> tuple[SearchTraceRecord, ...]:
    if value is None:
        raise ValueError("traces absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("traces invalides")
    traces = tuple(value)
    for trace in traces:
        _ensure_trace(trace)
    return traces


def _ensure_trace(value: SearchTraceRecord) -> SearchTraceRecord:
    if not isinstance(value, SearchTraceRecord):
        raise ValueError("trace invalide")
    return value


def _ensure_score_mapping(value: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("scores_by_chunk_id non objet")
    scores: dict[str, float] = {}
    for chunk_id, score in value.items():
        scores[_ensure_chunk_id(chunk_id)] = _ensure_non_negative_float(score, "rerank_score")
    if len(scores) == 0:
        raise ValueError("scores_by_chunk_id absents")
    return scores


def _ensure_chunk_id_set(value: Sequence[str]) -> frozenset[str]:
    if value is None:
        raise ValueError("eligible_chunk_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("eligible_chunk_ids invalides")
    chunk_ids = tuple(_ensure_chunk_id(chunk_id) for chunk_id in value)
    if len(chunk_ids) == 0:
        raise ValueError("eligible_chunk_ids absents")
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("eligible_chunk_ids dupliques")
    return frozenset(chunk_ids)


def _ensure_projection_id(value: object) -> str:
    text = _ensure_text(value, "projection_id")
    if not text.startswith("PROJ-"):
        raise ValueError("projection_id invalide")
    return text


def _ensure_chunk_id(value: object) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
    return text


def _ensure_search_trace_id(value: object) -> str:
    text = _ensure_text(value, "search_trace_id")
    if not text.startswith("STRC-"):
        raise ValueError("search_trace_id invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{field_name} invalide")
    return parsed


__all__ = [
    "InMemoryHybridRetrievalIndex",
    "InMemoryReranker",
    "InMemorySearchTraceStore",
]
