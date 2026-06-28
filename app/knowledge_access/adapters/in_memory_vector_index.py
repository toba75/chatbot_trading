"""Adaptateur mémoire contractuel du port VectorIndex KA."""

from __future__ import annotations

from collections.abc import Iterable

from app.knowledge_access.domain.projection_index import (
    PartialVectorIndexError,
    VectorIndexDeletion,
    VectorIndexPoint,
    VectorIndexPublication,
    VectorIndexPublishRequest,
    VectorIndexUnavailableError,
)


class InMemoryVectorIndex:
    """Double contractuel d'une collection vectorielle Qdrant régénérable."""

    def __init__(
        self,
        *,
        generations: Iterable[VectorIndexPublishRequest],
        omit_receipt_for_chunk_ids: Iterable[str],
        fail_publication_for_chunk_ids: Iterable[str],
    ) -> None:
        if generations is None:
            raise ValueError("generations absentes")
        self._generations: dict[tuple[str, str], dict[str, VectorIndexPoint]] = {}
        self._omit_receipt_for_chunk_ids = _ensure_chunk_id_set(
            omit_receipt_for_chunk_ids,
            "omit_receipt_for_chunk_ids",
        )
        self._fail_publication_for_chunk_ids = _ensure_chunk_id_set(
            fail_publication_for_chunk_ids,
            "fail_publication_for_chunk_ids",
        )
        for generation in generations:
            request = _ensure_publish_request(generation)
            self._store_generation(request=request)

    @classmethod
    def empty(
        cls,
        *,
        omit_receipt_for_chunk_ids: Iterable[str] = (),
        fail_publication_for_chunk_ids: Iterable[str] = (),
    ) -> "InMemoryVectorIndex":
        return cls(
            generations=(),
            omit_receipt_for_chunk_ids=omit_receipt_for_chunk_ids,
            fail_publication_for_chunk_ids=fail_publication_for_chunk_ids,
        )

    def publish_generation(self, request: VectorIndexPublishRequest) -> VectorIndexPublication:
        parsed_request = _ensure_publish_request(request)
        key = (parsed_request.collection_name, parsed_request.index_generation)
        requested_point_ids = tuple(point.point_id for point in parsed_request.points)

        existing_generation = self._generations.get(key)
        if existing_generation is not None:
            existing_point_ids = tuple(existing_generation.keys())
            if existing_point_ids != requested_point_ids:
                raise VectorIndexUnavailableError("generation existante incoherente")
            return VectorIndexPublication(
                collection_name=parsed_request.collection_name,
                index_generation=parsed_request.index_generation,
                published_point_ids=existing_point_ids,
                expected_point_count=parsed_request.expected_point_count,
                idempotent=True,
            )

        failed_chunk_ids = tuple(
            point.chunk_id
            for point in parsed_request.points
            if point.chunk_id in self._fail_publication_for_chunk_ids
        )
        if len(failed_chunk_ids) > 0:
            raise VectorIndexUnavailableError(f"publication refusee: {failed_chunk_ids[0]}")

        published_point_ids = tuple(
            point.point_id
            for point in parsed_request.points
            if point.chunk_id not in self._omit_receipt_for_chunk_ids
        )
        if len(published_point_ids) != parsed_request.expected_point_count:
            raise PartialVectorIndexError(
                expected_point_count=parsed_request.expected_point_count,
                published_point_count=len(published_point_ids),
            )

        self._store_generation(request=parsed_request)
        return VectorIndexPublication(
            collection_name=parsed_request.collection_name,
            index_generation=parsed_request.index_generation,
            published_point_ids=published_point_ids,
            expected_point_count=parsed_request.expected_point_count,
            idempotent=False,
        )

    def generation_exists(self, *, collection_name: str, index_generation: str) -> bool:
        return (_ensure_text(collection_name, "collection_name"), _ensure_text(index_generation, "index_generation")) in self._generations

    def collection_point_count(self, *, collection_name: str, index_generation: str) -> int:
        key = (_ensure_text(collection_name, "collection_name"), _ensure_text(index_generation, "index_generation"))
        generation = self._generations.get(key)
        if generation is None:
            return 0
        return len(generation)

    def delete_generation(self, *, collection_name: str, index_generation: str) -> VectorIndexDeletion:
        parsed_collection_name = _ensure_text(collection_name, "collection_name")
        parsed_index_generation = _ensure_text(index_generation, "index_generation")
        key = (parsed_collection_name, parsed_index_generation)
        deleted = key in self._generations
        if deleted:
            del self._generations[key]
        return VectorIndexDeletion(
            collection_name=parsed_collection_name,
            index_generation=parsed_index_generation,
            deleted=deleted,
        )

    def _store_generation(self, *, request: VectorIndexPublishRequest) -> None:
        key = (request.collection_name, request.index_generation)
        self._generations[key] = {point.point_id: point for point in request.points}


def _ensure_publish_request(value: VectorIndexPublishRequest) -> VectorIndexPublishRequest:
    if not isinstance(value, VectorIndexPublishRequest):
        raise ValueError("requete VectorIndex invalide")
    return value


def _ensure_chunk_id_set(value: Iterable[str], field_name: str) -> frozenset[str]:
    if value is None:
        raise ValueError(f"{field_name} absent")
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise ValueError(f"{field_name} invalide")
    chunk_ids = []
    for chunk_id in value:
        chunk_ids.append(_ensure_text(chunk_id, "chunk_id"))
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(f"{field_name} duplique")
    return frozenset(chunk_ids)


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["InMemoryVectorIndex"]
