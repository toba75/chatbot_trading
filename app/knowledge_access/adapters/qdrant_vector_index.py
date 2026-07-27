"""Adaptateur Qdrant explicite du port VectorIndex KA."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from app.knowledge_access.domain.projection_index import (
    PartialVectorIndexError,
    VectorIndexDeletion,
    VectorIndexPoint,
    VectorIndexPublication,
    VectorIndexPublishRequest,
)


class QdrantClientPort(Protocol):
    """Sous-ensemble Qdrant requis par l'adaptateur KA."""

    def upsert(self, *, collection_name: str, points: Sequence[Mapping[str, Any]]) -> object:
        """Publie des points dans une collection."""

    def delete(self, *, collection_name: str, points_selector: Mapping[str, Any]) -> object:
        """Supprime des points dans une collection."""

    def count(self, *, collection_name: str, count_filter: Mapping[str, Any], exact: bool) -> object:
        """Compte les points d'une génération."""


class QdrantVectorIndex:
    """Adaptateur Qdrant derrière le port VectorIndex, sans fallback mémoire."""

    def __init__(self, *, client: QdrantClientPort) -> None:
        if not callable(getattr(client, "upsert", None)):
            raise ValueError("client Qdrant sans upsert")
        if not callable(getattr(client, "delete", None)):
            raise ValueError("client Qdrant sans delete")
        if not callable(getattr(client, "count", None)):
            raise ValueError("client Qdrant sans count")
        self._client = client

    def publish_generation(
        self,
        request: VectorIndexPublishRequest,
        *,
        max_parallel_batches: int = 1,
        batch_size: int | None = None,
        on_batch_published: Callable[[int], None] | None = None,
    ) -> VectorIndexPublication:
        parsed_request = _ensure_publish_request(request)
        parsed_max_parallel_batches = _ensure_positive_int(
            max_parallel_batches,
            "max_parallel_batches",
        )
        parsed_batch_size = _ensure_batch_size(
            batch_size,
            point_count=len(parsed_request.points),
        )
        if on_batch_published is not None and not callable(on_batch_published):
            raise ValueError("rapporteur Qdrant invalide")
        existing_count = self._generation_count(
            collection_name=parsed_request.collection_name,
            index_generation=parsed_request.index_generation,
        )
        if existing_count > 0:
            if existing_count != parsed_request.expected_point_count:
                raise PartialVectorIndexError(
                    expected_point_count=parsed_request.expected_point_count,
                    published_point_count=existing_count,
                )
            return VectorIndexPublication(
                collection_name=parsed_request.collection_name,
                index_generation=parsed_request.index_generation,
                published_point_ids=tuple(point.point_id for point in parsed_request.points),
                expected_point_count=parsed_request.expected_point_count,
                idempotent=True,
            )

        qdrant_points = tuple(
            _qdrant_point_for(parsed_request.index_generation, point)
            for point in parsed_request.points
        )
        self._upsert_batches(
            collection_name=parsed_request.collection_name,
            qdrant_points=qdrant_points,
            batch_size=parsed_batch_size,
            max_parallel_batches=parsed_max_parallel_batches,
            on_batch_published=on_batch_published,
        )
        published_count = self._generation_count(
            collection_name=parsed_request.collection_name,
            index_generation=parsed_request.index_generation,
        )
        if published_count != parsed_request.expected_point_count:
            raise PartialVectorIndexError(
                expected_point_count=parsed_request.expected_point_count,
                published_point_count=published_count,
            )
        return VectorIndexPublication(
            collection_name=parsed_request.collection_name,
            index_generation=parsed_request.index_generation,
            published_point_ids=tuple(point.point_id for point in parsed_request.points),
            expected_point_count=parsed_request.expected_point_count,
            idempotent=False,
        )

    def _upsert_batches(
        self,
        *,
        collection_name: str,
        qdrant_points: Sequence[Mapping[str, Any]],
        batch_size: int,
        max_parallel_batches: int,
        on_batch_published: Callable[[int], None] | None,
    ) -> None:
        batches = _point_batches(qdrant_points, batch_size=batch_size)
        completed_points = 0
        if max_parallel_batches == 1 or len(batches) == 1:
            for batch in batches:
                self._client.upsert(collection_name=collection_name, points=batch)
                completed_points += len(batch)
                if on_batch_published is not None:
                    on_batch_published(completed_points)
            return

        with ThreadPoolExecutor(
            max_workers=min(max_parallel_batches, len(batches)),
            thread_name_prefix="ka-qdrant-upsert",
        ) as executor:
            futures = {
                executor.submit(
                    self._client.upsert,
                    collection_name=collection_name,
                    points=batch,
                ): len(batch)
                for batch in batches
            }
            for future in as_completed(futures):
                future.result()
                completed_points += futures[future]
                if on_batch_published is not None:
                    on_batch_published(completed_points)

    def generation_exists(self, *, collection_name: str, index_generation: str) -> bool:
        parsed_collection_name = _ensure_text(collection_name, "collection_name")
        parsed_index_generation = _ensure_text(index_generation, "index_generation")
        return self._generation_count(
            collection_name=parsed_collection_name,
            index_generation=parsed_index_generation,
        ) > 0

    def delete_generation(self, *, collection_name: str, index_generation: str) -> VectorIndexDeletion:
        parsed_collection_name = _ensure_text(collection_name, "collection_name")
        parsed_index_generation = _ensure_text(index_generation, "index_generation")
        existed = self.generation_exists(
            collection_name=parsed_collection_name,
            index_generation=parsed_index_generation,
        )
        if existed:
            self._client.delete(
                collection_name=parsed_collection_name,
                points_selector={
                    "filter": _generation_filter(parsed_index_generation),
                },
            )
        return VectorIndexDeletion(
            collection_name=parsed_collection_name,
            index_generation=parsed_index_generation,
            deleted=existed,
        )

    def _generation_count(self, *, collection_name: str, index_generation: str) -> int:
        result = self._client.count(
            collection_name=collection_name,
            count_filter=_generation_filter(index_generation),
            exact=True,
        )
        if isinstance(result, int):
            count = result
        else:
            count = getattr(result, "count", None)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("compte Qdrant invalide")
        return count


def _qdrant_point_for(index_generation: str, point: VectorIndexPoint) -> dict[str, Any]:
    parsed_point = _ensure_point(point)
    payload = dict(parsed_point.payload)
    payload["index_generation"] = _ensure_text(index_generation, "index_generation")
    sparse_weights_by_index: dict[int, float] = {}
    for token, weight in parsed_point.sparse_weights:
        index = int.from_bytes(
            hashlib.sha256(token.encode("utf-8")).digest()[:4],
            "big",
        )
        sparse_weights_by_index[index] = sparse_weights_by_index.get(index, 0.0) + weight
    return {
        "id": str(UUID(bytes=hashlib.sha256(parsed_point.point_id.encode("utf-8")).digest()[:16])),
        "vector": {
            "dense": parsed_point.dense_vector,
            "sparse": {
                "indices": tuple(sorted(sparse_weights_by_index)),
                "values": tuple(
                    sparse_weights_by_index[index]
                    for index in sorted(sparse_weights_by_index)
                ),
            },
        },
        "payload": payload,
    }


def _generation_filter(index_generation: str) -> dict[str, Any]:
    return {
        "must": (
            {
                "key": "index_generation",
                "match": {"value": _ensure_text(index_generation, "index_generation")},
            },
        )
    }


def _ensure_publish_request(value: VectorIndexPublishRequest) -> VectorIndexPublishRequest:
    if not isinstance(value, VectorIndexPublishRequest):
        raise ValueError("requete VectorIndex invalide")
    return value


def _ensure_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_batch_size(value: int | None, *, point_count: int) -> int:
    if value is None:
        return _ensure_positive_int(point_count, "batch_size")
    return _ensure_positive_int(value, "batch_size")


def _point_batches(
    points: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    return tuple(
        tuple(points[index : index + batch_size])
        for index in range(0, len(points), batch_size)
    )


def _ensure_point(value: VectorIndexPoint) -> VectorIndexPoint:
    if not isinstance(value, VectorIndexPoint):
        raise ValueError("point invalide")
    return value


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["QdrantClientPort", "QdrantVectorIndex"]
