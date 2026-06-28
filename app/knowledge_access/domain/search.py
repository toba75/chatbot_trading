"""Objets de recherche hybride traçable KA."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.contracts.source_references import SourceLocator
from app.knowledge_access.domain.projection_metadata import (
    EvidenceDiversificationPolicy,
    ProjectionMetadata,
    SearchFilter,
)


_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_ALLOWED_REQUESTING_CONTEXTS = frozenset({"RA", "EG"})


@dataclass(frozen=True)
class SearchChannelHit:
    """Résultat brut d'un canal dense ou sparse avant fusion."""

    chunk_id: str
    score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "score", _ensure_non_negative_float(self.score, "score"))


@dataclass(frozen=True)
class SearchScoreBundle:
    """Scores de recherche, sans verdict métier."""

    dense_score: float
    sparse_score: float
    fusion_score: float
    rerank_score: float | None
    diversification_rank: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dense_score",
            _ensure_non_negative_float(self.dense_score, "dense_score"),
        )
        object.__setattr__(
            self,
            "sparse_score",
            _ensure_non_negative_float(self.sparse_score, "sparse_score"),
        )
        object.__setattr__(
            self,
            "fusion_score",
            _ensure_positive_float(self.fusion_score, "fusion_score"),
        )
        if self.rerank_score is not None:
            object.__setattr__(
                self,
                "rerank_score",
                _ensure_non_negative_float(self.rerank_score, "rerank_score"),
            )
        if self.diversification_rank is not None:
            object.__setattr__(
                self,
                "diversification_rank",
                _ensure_positive_integer(self.diversification_rank, "diversification_rank"),
            )

    def with_rerank_score(self, rerank_score: float) -> "SearchScoreBundle":
        return replace(self, rerank_score=rerank_score)

    def with_diversification_rank(self, diversification_rank: int) -> "SearchScoreBundle":
        return replace(self, diversification_rank=diversification_rank)

    def to_payload(self) -> dict[str, Any]:
        return {
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "fusion_score": self.fusion_score,
            "rerank_score": self.rerank_score,
            "diversification_rank": self.diversification_rank,
        }


@dataclass(frozen=True)
class FusionCandidate:
    """Candidat après fusion RRF, avant expansion/reranking."""

    chunk_id: str
    score_bundle: SearchScoreBundle
    fusion_trace: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        if not isinstance(self.score_bundle, SearchScoreBundle):
            raise ValueError("score_bundle invalide")
        object.__setattr__(self, "fusion_trace", _ensure_mapping(self.fusion_trace, "fusion_trace"))


@dataclass(frozen=True)
class ParentContext:
    """Contexte parent explicitement expansé autour d'un passage."""

    parent_chunk_id: str | None
    parent_text: str

    def __post_init__(self) -> None:
        if self.parent_chunk_id is None:
            if self.parent_text != "":
                raise ValueError("parent_text interdit sans parent_chunk_id")
            return
        object.__setattr__(self, "parent_chunk_id", _ensure_chunk_id(self.parent_chunk_id))
        object.__setattr__(self, "parent_text", _ensure_text(self.parent_text, "parent_text"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "parent_chunk_id": self.parent_chunk_id,
            "parent_text": self.parent_text,
        }


@dataclass(frozen=True)
class ParentContextExpansionPolicy:
    """Politique d'expansion vers le chunk parent."""

    enabled: bool
    max_parent_characters: int

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("parent_context_enabled non booleen")
        object.__setattr__(
            self,
            "max_parent_characters",
            _ensure_positive_integer(self.max_parent_characters, "max_parent_characters"),
        )

    def expand(self, document: "RetrievalDocument") -> ParentContext:
        parsed_document = _ensure_retrieval_document(document)
        if not self.enabled:
            return ParentContext(parent_chunk_id=None, parent_text="")
        if parsed_document.parent_chunk_id is None:
            raise ValueError("parent_chunk_id obligatoire")
        if parsed_document.parent_text is None:
            raise ValueError("parent_text obligatoire")
        if len(parsed_document.parent_text) > self.max_parent_characters:
            raise ValueError("parent_text depasse max_parent_characters")
        return ParentContext(
            parent_chunk_id=parsed_document.parent_chunk_id,
            parent_text=parsed_document.parent_text,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_parent_characters": self.max_parent_characters,
        }


@dataclass(frozen=True)
class HybridRetrievalPolicy:
    """Profil explicite de recherche dense, sparse, RRF, rerank et diversité."""

    search_profile_id: str
    search_profile_version: str
    dense_profile_id: str
    dense_model_name: str
    dense_model_version: str
    sparse_profile_id: str
    sparse_model_name: str
    sparse_model_version: str
    rerank_profile_id: str
    rerank_model_name: str
    rerank_model_version: str
    dense_limit: int
    sparse_limit: int
    result_limit: int
    rrf_k: int
    rerank_required: bool
    diversification_policy: EvidenceDiversificationPolicy
    parent_context_policy: ParentContextExpansionPolicy

    def __post_init__(self) -> None:
        for field_name in (
            "search_profile_id",
            "search_profile_version",
            "dense_profile_id",
            "dense_model_name",
            "dense_model_version",
            "sparse_profile_id",
            "sparse_model_name",
            "sparse_model_version",
            "rerank_profile_id",
            "rerank_model_name",
            "rerank_model_version",
        ):
            object.__setattr__(self, field_name, _ensure_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "dense_limit",
            _ensure_positive_integer(self.dense_limit, "dense_limit"),
        )
        object.__setattr__(
            self,
            "sparse_limit",
            _ensure_positive_integer(self.sparse_limit, "sparse_limit"),
        )
        object.__setattr__(
            self,
            "result_limit",
            _ensure_positive_integer(self.result_limit, "result_limit"),
        )
        object.__setattr__(self, "rrf_k", _ensure_positive_integer(self.rrf_k, "rrf_k"))
        if not isinstance(self.rerank_required, bool):
            raise ValueError("rerank_required non booleen")
        if not isinstance(self.diversification_policy, EvidenceDiversificationPolicy):
            raise ValueError("diversification_policy invalide")
        if not isinstance(self.parent_context_policy, ParentContextExpansionPolicy):
            raise ValueError("parent_context_policy invalide")

    def fuse(
        self,
        *,
        dense_hits: Sequence[SearchChannelHit],
        sparse_hits: Sequence[SearchChannelHit],
    ) -> tuple[FusionCandidate, ...]:
        parsed_dense_hits = _ensure_channel_hits(dense_hits, "dense_hits")
        parsed_sparse_hits = _ensure_channel_hits(sparse_hits, "sparse_hits")
        dense_ranks = _rank_by_chunk_id(parsed_dense_hits, "dense")
        sparse_ranks = _rank_by_chunk_id(parsed_sparse_hits, "sparse")
        dense_scores = {hit.chunk_id: hit.score for hit in parsed_dense_hits}
        sparse_scores = {hit.chunk_id: hit.score for hit in parsed_sparse_hits}
        chunk_ids = sorted(set(dense_scores) | set(sparse_scores))
        fused: list[FusionCandidate] = []

        for chunk_id in chunk_ids:
            dense_rank = dense_ranks.get(chunk_id)
            sparse_rank = sparse_ranks.get(chunk_id)
            fusion_score = 0.0
            if dense_rank is not None:
                fusion_score += 1.0 / (self.rrf_k + dense_rank)
            if sparse_rank is not None:
                fusion_score += 1.0 / (self.rrf_k + sparse_rank)
            fused.append(
                FusionCandidate(
                    chunk_id=chunk_id,
                    score_bundle=SearchScoreBundle(
                        dense_score=dense_scores.get(chunk_id, 0.0),
                        sparse_score=sparse_scores.get(chunk_id, 0.0),
                        fusion_score=fusion_score,
                        rerank_score=None,
                        diversification_rank=None,
                    ),
                    fusion_trace={
                        "chunk_id": chunk_id,
                        "dense_rank": dense_rank,
                        "sparse_rank": sparse_rank,
                        "rrf_k": self.rrf_k,
                        "fusion_score": fusion_score,
                    },
                )
            )

        return tuple(
            sorted(
                fused,
                key=lambda candidate: (
                    -candidate.score_bundle.fusion_score,
                    _best_rank(candidate.fusion_trace),
                    candidate.chunk_id,
                ),
            )
        )

    def diversify(
        self,
        candidates: Sequence["RetrievalCandidate"],
    ) -> tuple[tuple["RetrievalCandidate", ...], dict[str, Any]]:
        parsed_candidates = _ensure_candidates(candidates)
        if self.diversification_policy.mode == "NONE":
            ranked = tuple(
                candidate.with_diversification_rank(index)
                for index, candidate in enumerate(parsed_candidates, start=1)
            )
            return ranked, {
                "mode": "NONE",
                "max_per_document": None,
                "input_count": len(parsed_candidates),
                "output_count": len(ranked),
            }

        selected: list[RetrievalCandidate] = []
        counts_by_document: dict[str, int] = {}
        assert self.diversification_policy.max_per_document is not None
        for candidate in parsed_candidates:
            current_count = counts_by_document.get(candidate.document_id, 0)
            if current_count >= self.diversification_policy.max_per_document:
                continue
            selected.append(candidate)
            counts_by_document[candidate.document_id] = current_count + 1

        limited = tuple(selected[: self.result_limit])
        ranked = tuple(
            candidate.with_diversification_rank(index)
            for index, candidate in enumerate(limited, start=1)
        )
        return ranked, {
            "mode": "PER_DOCUMENT",
            "max_per_document": self.diversification_policy.max_per_document,
            "input_count": len(parsed_candidates),
            "output_count": len(ranked),
        }

    def to_profile_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.search_profile_id,
            "profile_version": self.search_profile_version,
            "dense_limit": self.dense_limit,
            "sparse_limit": self.sparse_limit,
            "result_limit": self.result_limit,
            "rerank_required": self.rerank_required,
            "parent_context": self.parent_context_policy.to_payload(),
        }

    def to_models_payload(self) -> dict[str, Any]:
        return {
            "dense": {
                "profile_id": self.dense_profile_id,
                "model_name": self.dense_model_name,
                "model_version": self.dense_model_version,
            },
            "sparse": {
                "profile_id": self.sparse_profile_id,
                "model_name": self.sparse_model_name,
                "model_version": self.sparse_model_version,
            },
            "rerank": {
                "profile_id": self.rerank_profile_id,
                "model_name": self.rerank_model_name,
                "model_version": self.rerank_model_version,
            },
        }


@dataclass(frozen=True)
class RetrievalDocument:
    """Passage indexé, cité et projeté par KA."""

    projection_id: str
    projection_profile_id: str
    build_fingerprint: str
    index_generation: str
    chunk_id: str
    canonical_version_id: str
    document_id: str
    text: str
    source_locator: SourceLocator
    content_hash: str
    author: str
    published_on: str
    content_type: str
    canonical_quality: str
    chunk_level: str
    parent_chunk_id: str | None
    parent_text: str | None
    dense_score: float
    sparse_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(
            self,
            "projection_profile_id",
            _ensure_text(self.projection_profile_id, "projection_profile_id"),
        )
        object.__setattr__(
            self,
            "build_fingerprint",
            _ensure_sha256(self.build_fingerprint, "build_fingerprint"),
        )
        object.__setattr__(
            self,
            "index_generation",
            _ensure_text(self.index_generation, "index_generation"),
        )
        if not self.index_generation.startswith("IDX-"):
            raise ValueError("index_generation invalide")
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(self, "text", _ensure_text(self.text, "text"))
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        if self.source_locator.content_hash != self.content_hash:
            raise ValueError("content_hash incoherent avec SourceLocator")
        if self.source_locator.document_id != self.document_id:
            raise ValueError("document_id incoherent avec SourceLocator")
        if self.source_locator.canonical_version_id != self.canonical_version_id:
            raise ValueError("canonical_version_id incoherent avec SourceLocator")
        for field_name in ("author", "published_on", "content_type", "canonical_quality", "chunk_level"):
            object.__setattr__(self, field_name, _ensure_text(getattr(self, field_name), field_name))
        if self.parent_chunk_id is not None:
            object.__setattr__(self, "parent_chunk_id", _ensure_chunk_id(self.parent_chunk_id))
        if self.parent_text is not None:
            object.__setattr__(self, "parent_text", _ensure_text(self.parent_text, "parent_text"))
        object.__setattr__(
            self,
            "dense_score",
            _ensure_non_negative_float(self.dense_score, "dense_score"),
        )
        object.__setattr__(
            self,
            "sparse_score",
            _ensure_non_negative_float(self.sparse_score, "sparse_score"),
        )

    @property
    def metadata(self) -> ProjectionMetadata:
        return ProjectionMetadata(
            projection_id=self.projection_id,
            chunk_id=self.chunk_id,
            canonical_version_id=self.canonical_version_id,
            document_id=self.document_id,
            author=self.author,
            published_on=self.published_on,
            content_type=self.content_type,
            canonical_quality=self.canonical_quality,
            chunk_level=self.chunk_level,
            content_hash=self.content_hash,
        )


@dataclass(frozen=True)
class RetrievalCandidate:
    """Preuve candidate retournée par KA."""

    projection_id: str
    projection_profile_id: str
    build_fingerprint: str
    index_generation: str
    chunk_id: str
    canonical_version_id: str
    document_id: str
    text: str
    source_locator: SourceLocator
    content_hash: str
    score_bundle: SearchScoreBundle
    fusion_trace: Mapping[str, Any]
    parent_context: ParentContext

    @classmethod
    def from_document(
        cls,
        *,
        document: RetrievalDocument,
        score_bundle: SearchScoreBundle,
        fusion_trace: Mapping[str, Any],
        parent_context: ParentContext,
    ) -> "RetrievalCandidate":
        parsed_document = _ensure_retrieval_document(document)
        if not isinstance(score_bundle, SearchScoreBundle):
            raise ValueError("score_bundle invalide")
        if not isinstance(parent_context, ParentContext):
            raise ValueError("parent_context invalide")
        return cls(
            projection_id=parsed_document.projection_id,
            projection_profile_id=parsed_document.projection_profile_id,
            build_fingerprint=parsed_document.build_fingerprint,
            index_generation=parsed_document.index_generation,
            chunk_id=parsed_document.chunk_id,
            canonical_version_id=parsed_document.canonical_version_id,
            document_id=parsed_document.document_id,
            text=parsed_document.text,
            source_locator=parsed_document.source_locator,
            content_hash=parsed_document.content_hash,
            score_bundle=score_bundle,
            fusion_trace=fusion_trace,
            parent_context=parent_context,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(
            self,
            "projection_profile_id",
            _ensure_text(self.projection_profile_id, "projection_profile_id"),
        )
        object.__setattr__(
            self,
            "build_fingerprint",
            _ensure_sha256(self.build_fingerprint, "build_fingerprint"),
        )
        object.__setattr__(self, "index_generation", _ensure_text(self.index_generation, "index_generation"))
        if not self.index_generation.startswith("IDX-"):
            raise ValueError("index_generation invalide")
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(self, "text", _ensure_text(self.text, "text"))
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        if self.source_locator.content_hash != self.content_hash:
            raise ValueError("content_hash incoherent avec SourceLocator")
        if not isinstance(self.score_bundle, SearchScoreBundle):
            raise ValueError("score_bundle invalide")
        object.__setattr__(self, "fusion_trace", _ensure_mapping(self.fusion_trace, "fusion_trace"))
        if not isinstance(self.parent_context, ParentContext):
            raise ValueError("parent_context invalide")

    def with_rerank_score(self, rerank_score: float) -> "RetrievalCandidate":
        return replace(self, score_bundle=self.score_bundle.with_rerank_score(rerank_score))

    def with_diversification_rank(self, diversification_rank: int) -> "RetrievalCandidate":
        return replace(
            self,
            score_bundle=self.score_bundle.with_diversification_rank(diversification_rank),
        )

    def to_reference_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
            "content_hash": self.content_hash,
            "source_locator": self.source_locator.to_payload(),
            "scores": self.score_bundle.to_payload(),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            **self.to_reference_payload(),
            "projection_id": self.projection_id,
            "projection_profile_id": self.projection_profile_id,
            "build_fingerprint": self.build_fingerprint,
            "index_generation": self.index_generation,
            "text": self.text,
            "parent_context": self.parent_context.to_payload(),
            "fusion_trace": dict(self.fusion_trace),
        }


@dataclass(frozen=True)
class SearchRequest:
    """Commande SearchKnowledge interne KA."""

    projection_id: str
    query_text: str
    filters: SearchFilter
    hybrid_policy: HybridRetrievalPolicy
    occurred_at: str
    requested_by_context: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(self, "query_text", _ensure_text(self.query_text, "query_text"))
        if not isinstance(self.filters, SearchFilter):
            raise ValueError("filters invalides")
        if not isinstance(self.hybrid_policy, HybridRetrievalPolicy):
            raise ValueError("hybrid_policy invalide")
        object.__setattr__(self, "occurred_at", _ensure_text(self.occurred_at, "occurred_at"))
        context = _ensure_text(self.requested_by_context, "requested_by_context")
        if context not in _ALLOWED_REQUESTING_CONTEXTS:
            raise ValueError("requested_by_context inconnu")
        object.__setattr__(self, "requested_by_context", context)

    @property
    def query_hash(self) -> str:
        return _sha256_text(self.query_text)

    def filters_payload(self) -> dict[str, Any]:
        return _filter_payload(self.filters)


@dataclass(frozen=True)
class SearchTraceRecord:
    """Trace persistée d'une recherche hybride."""

    search_trace_id: str
    request_payload: Mapping[str, Any]
    projection_payload: Mapping[str, Any]
    search_profile_payload: Mapping[str, Any]
    models_payload: Mapping[str, Any]
    filters_payload: Mapping[str, Any]
    applied_filters: Sequence[Mapping[str, Any]]
    freshness_warnings: Sequence[str]
    fusion_payload: Mapping[str, Any]
    diversification_trace: Mapping[str, Any]
    candidate_refs: Sequence[Mapping[str, Any]]
    result_count: int

    @classmethod
    def from_search(
        cls,
        *,
        request: SearchRequest,
        projection_id: str,
        projection_status: str,
        projection_profile_id: str,
        build_fingerprint: str,
        index_generation: str,
        candidates: Sequence[RetrievalCandidate],
        applied_filters: Sequence[Mapping[str, Any]],
        freshness_warnings: Sequence[str],
        fusion_trace: Sequence[Mapping[str, Any]],
        diversification_trace: Mapping[str, Any],
    ) -> "SearchTraceRecord":
        parsed_request = _ensure_search_request(request)
        parsed_candidates = _ensure_candidates(candidates)
        projection_payload = {
            "projection_id": _ensure_domain_id(projection_id, "PROJ"),
            "status": _ensure_text(projection_status, "projection_status"),
            "projection_profile_id": _ensure_text(projection_profile_id, "projection_profile_id"),
            "build_fingerprint": _ensure_sha256(build_fingerprint, "build_fingerprint"),
            "index_generation": _ensure_text(index_generation, "index_generation"),
        }
        request_payload = {
            "query_hash": parsed_request.query_hash,
            "occurred_at": parsed_request.occurred_at,
            "requested_by_context": parsed_request.requested_by_context,
        }
        candidate_refs = tuple(candidate.to_reference_payload() for candidate in parsed_candidates)
        fusion_payload = {
            "algorithm": "RRF",
            "rrf_k": parsed_request.hybrid_policy.rrf_k,
            "rankings": _ensure_mapping_tuple(fusion_trace, "fusion_trace"),
        }
        base_payload = {
            "request": request_payload,
            "projection": projection_payload,
            "search_profile": parsed_request.hybrid_policy.to_profile_payload(),
            "models": parsed_request.hybrid_policy.to_models_payload(),
            "filters": parsed_request.filters_payload(),
            "applied_filters": _ensure_mapping_tuple(applied_filters, "applied_filters"),
            "freshness_warnings": _ensure_text_tuple(freshness_warnings, "freshness_warnings"),
            "fusion": fusion_payload,
            "diversification": _ensure_mapping(diversification_trace, "diversification_trace"),
            "candidate_refs": candidate_refs,
            "result_count": len(parsed_candidates),
        }
        return cls(
            search_trace_id=_trace_id_for(base_payload),
            request_payload=request_payload,
            projection_payload=projection_payload,
            search_profile_payload=parsed_request.hybrid_policy.to_profile_payload(),
            models_payload=parsed_request.hybrid_policy.to_models_payload(),
            filters_payload=parsed_request.filters_payload(),
            applied_filters=base_payload["applied_filters"],
            freshness_warnings=base_payload["freshness_warnings"],
            fusion_payload=fusion_payload,
            diversification_trace=base_payload["diversification"],
            candidate_refs=candidate_refs,
            result_count=len(parsed_candidates),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "search_trace_id", _ensure_search_trace_id(self.search_trace_id))
        for field_name in (
            "request_payload",
            "projection_payload",
            "search_profile_payload",
            "models_payload",
            "filters_payload",
            "fusion_payload",
            "diversification_trace",
        ):
            object.__setattr__(self, field_name, _ensure_mapping(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "applied_filters",
            _ensure_mapping_tuple(self.applied_filters, "applied_filters"),
        )
        object.__setattr__(
            self,
            "freshness_warnings",
            _ensure_text_tuple(self.freshness_warnings, "freshness_warnings"),
        )
        object.__setattr__(
            self,
            "candidate_refs",
            _ensure_mapping_tuple(self.candidate_refs, "candidate_refs"),
        )
        object.__setattr__(self, "result_count", _ensure_non_negative_integer(self.result_count, "result_count"))
        if self.result_count != len(self.candidate_refs):
            raise ValueError("result_count incoherent")

    def to_payload(self) -> dict[str, Any]:
        return {
            "search_trace_id": self.search_trace_id,
            "request": dict(self.request_payload),
            "projection": dict(self.projection_payload),
            "search_profile": dict(self.search_profile_payload),
            "models": dict(self.models_payload),
            "filters": dict(self.filters_payload),
            "applied_filters": tuple(dict(item) for item in self.applied_filters),
            "freshness_warnings": self.freshness_warnings,
            "fusion": dict(self.fusion_payload),
            "diversification": dict(self.diversification_trace),
            "candidate_refs": tuple(dict(item) for item in self.candidate_refs),
            "result_count": self.result_count,
        }


@dataclass(frozen=True)
class SearchTracePolicy:
    """Politique de persistance obligatoire des traces de recherche."""

    require_persisted_trace: bool

    def __post_init__(self) -> None:
        if not isinstance(self.require_persisted_trace, bool):
            raise ValueError("require_persisted_trace non booleen")

    def persist(self, *, trace: SearchTraceRecord, trace_store: Any) -> SearchTraceRecord:
        if not isinstance(trace, SearchTraceRecord):
            raise ValueError("trace invalide")
        if self.require_persisted_trace:
            if trace_store is None or not callable(getattr(trace_store, "save", None)):
                raise ValueError("SearchTraceStore obligatoire")
            persisted_trace = trace_store.save(trace)
            if not isinstance(persisted_trace, SearchTraceRecord):
                raise ValueError("trace persistée invalide")
            return persisted_trace
        return trace


@dataclass(frozen=True)
class SearchResponse:
    """Réponse KA contenant des preuves candidates."""

    search_trace_id: str
    projection_id: str
    candidates: Sequence[RetrievalCandidate]
    warnings: Sequence[str]
    applied_filters: Sequence[Mapping[str, Any]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "search_trace_id", _ensure_search_trace_id(self.search_trace_id))
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(self, "candidates", _ensure_candidates(self.candidates))
        object.__setattr__(self, "warnings", _ensure_text_tuple(self.warnings, "warnings"))
        object.__setattr__(
            self,
            "applied_filters",
            _ensure_mapping_tuple(self.applied_filters, "applied_filters"),
        )

    @property
    def result_count(self) -> int:
        return len(self.candidates)

    def to_payload(self) -> dict[str, Any]:
        return {
            "search_trace_id": self.search_trace_id,
            "projection_id": self.projection_id,
            "results": tuple(candidate.to_payload() for candidate in self.candidates),
            "warnings": self.warnings,
            "applied_filters": self.applied_filters,
        }


def _ensure_search_request(value: SearchRequest) -> SearchRequest:
    if not isinstance(value, SearchRequest):
        raise ValueError("search_request invalide")
    return value


def _ensure_retrieval_document(value: RetrievalDocument) -> RetrievalDocument:
    if not isinstance(value, RetrievalDocument):
        raise ValueError("retrieval_document invalide")
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
    chunk_ids = tuple(candidate.chunk_id for candidate in candidates)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("candidate chunk_id duplique")
    return candidates


def _ensure_channel_hits(value: Sequence[SearchChannelHit], field_name: str) -> tuple[SearchChannelHit, ...]:
    if value is None:
        raise ValueError(f"{field_name} absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    hits = tuple(value)
    if len(hits) == 0:
        raise ValueError(f"{field_name} absents")
    for hit in hits:
        if not isinstance(hit, SearchChannelHit):
            raise ValueError(f"{field_name} invalides")
    chunk_ids = tuple(hit.chunk_id for hit in hits)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(f"{field_name} dupliques")
    return hits


def _rank_by_chunk_id(hits: tuple[SearchChannelHit, ...], channel: str) -> dict[str, int]:
    _ensure_text(channel, "channel")
    return {hit.chunk_id: index for index, hit in enumerate(hits, start=1)}


def _best_rank(fusion_trace: Mapping[str, Any]) -> int:
    ranks = tuple(
        rank for rank in (fusion_trace.get("dense_rank"), fusion_trace.get("sparse_rank")) if rank is not None
    )
    if len(ranks) == 0:
        return 999999
    return min(ranks)


def _filter_payload(search_filter: SearchFilter) -> dict[str, Any]:
    if not isinstance(search_filter, SearchFilter):
        raise ValueError("search_filter invalide")
    return {
        "author": search_filter.author,
        "published_on_or_after": (
            search_filter.published_on_or_after.isoformat()
            if search_filter.published_on_or_after is not None
            else None
        ),
        "published_on_or_before": (
            search_filter.published_on_or_before.isoformat()
            if search_filter.published_on_or_before is not None
            else None
        ),
        "content_type": search_filter.content_type,
        "canonical_quality": search_filter.canonical_quality,
        "chunk_level": search_filter.chunk_level,
    }


def _trace_id_for(payload: Mapping[str, Any]) -> str:
    serialized_payload = json.dumps(
        _json_ready(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"STRC-{hashlib.sha256(serialized_payload.encode('utf-8')).hexdigest()[:32].upper()}"


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple) or isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "text").encode("utf-8")).hexdigest()


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_mapping_tuple(value: Any, field_name: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        raise ValueError(f"{field_name} absent")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(_ensure_mapping(item, field_name) for item in value)


def _ensure_text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        raise ValueError(f"{field_name} absent")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} duplique")
    return parsed


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    text = _ensure_text(value, "identifiant")
    if not text.startswith(f"{expected_prefix}-"):
        raise ValueError(f"identifiant {expected_prefix} invalide")
    return text


def _ensure_chunk_id(value: Any) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
    return text


def _ensure_search_trace_id(value: Any) -> str:
    text = _ensure_text(value, "search_trace_id")
    if not text.startswith("STRC-"):
        raise ValueError("search_trace_id invalide")
    return text


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_float(value: Any, field_name: str) -> float:
    parsed = _ensure_float(value, field_name)
    if parsed < 0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _ensure_positive_float(value: Any, field_name: str) -> float:
    parsed = _ensure_float(value, field_name)
    if parsed <= 0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _ensure_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} invalide")
    return parsed


__all__ = [
    "FusionCandidate",
    "HybridRetrievalPolicy",
    "ParentContext",
    "ParentContextExpansionPolicy",
    "RetrievalCandidate",
    "RetrievalDocument",
    "SearchChannelHit",
    "SearchRequest",
    "SearchResponse",
    "SearchScoreBundle",
    "SearchTracePolicy",
    "SearchTraceRecord",
]
