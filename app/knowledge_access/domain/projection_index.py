"""Contrats KA de publication d'index vectoriel régénérable."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
)
from app.knowledge_access.domain.projection_encoding import (
    EncodedProjectionChunk,
    ProjectionEncodingResult,
)


_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "claim",
        "claims",
        "claim_id",
        "verified_claim",
        "verified_claim_id",
        "verified_claim_ref",
        "qdrant_id",
        "dense_vector",
        "sparse_weights",
        "text",
    }
)


class VectorIndexError(ValueError):
    """Erreur métier stable du port VectorIndex."""

    error_code: str


class PartialVectorIndexError(VectorIndexError):
    """Erreur produite quand tous les points attendus ne sont pas publiés."""

    def __init__(self, *, expected_point_count: int, published_point_count: int) -> None:
        self.error_code = "INDEX_PARTIAL"
        self.expected_point_count = _ensure_positive_integer(
            expected_point_count,
            "expected_point_count",
        )
        if isinstance(published_point_count, bool) or not isinstance(published_point_count, int):
            raise ValueError("published_point_count invalide")
        if published_point_count < 0:
            raise ValueError("published_point_count invalide")
        self.published_point_count = published_point_count
        super().__init__(
            f"{self.error_code}: {self.published_point_count}/{self.expected_point_count}"
        )


class VectorIndexUnavailableError(VectorIndexError):
    """Erreur produite quand l'adaptateur d'index refuse explicitement la publication."""

    def __init__(self, reason: str) -> None:
        self.error_code = "INDEX_UNAVAILABLE"
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"{self.error_code}: {self.reason}")


@dataclass(frozen=True)
class VectorIndexSchema:
    """Schéma explicite de collection vectorielle KA."""

    schema_version: str
    collection_name: str
    dense_dimensions: int
    distance: str
    payload_schema_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _ensure_text(self.schema_version, "schema_version"))
        object.__setattr__(self, "collection_name", _ensure_text(self.collection_name, "collection_name"))
        object.__setattr__(
            self,
            "dense_dimensions",
            _ensure_positive_integer(self.dense_dimensions, "dense_dimensions"),
        )
        object.__setattr__(self, "distance", _ensure_text(self.distance, "distance"))
        object.__setattr__(
            self,
            "payload_schema_version",
            _ensure_text(self.payload_schema_version, "payload_schema_version"),
        )

    def to_fingerprint_payload(self) -> dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "dense_dimensions": self.dense_dimensions,
            "distance": self.distance,
            "payload_schema_version": self.payload_schema_version,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class VectorIndexPoint:
    """Point documentaire publié dans la projection vectorielle."""

    point_id: str
    chunk_id: str
    content_hash: str
    dense_vector: Sequence[float]
    sparse_weights: Sequence[tuple[str, float]]
    payload: Mapping[str, Any]

    @classmethod
    def from_encoded_chunk(
        cls,
        *,
        projection: KnowledgeProjection,
        encoded_chunk: EncodedProjectionChunk,
        index_schema: VectorIndexSchema,
    ) -> "VectorIndexPoint":
        parsed_projection = _ensure_projection(projection)
        chunk = _ensure_encoded_chunk(encoded_chunk)
        schema = _ensure_schema(index_schema)
        return cls(
            point_id=chunk.chunk_id,
            chunk_id=chunk.chunk_id,
            content_hash=chunk.content_hash,
            dense_vector=chunk.dense.values,
            sparse_weights=tuple((weight.token, weight.weight) for weight in chunk.sparse.weights),
            payload={
                "build_fingerprint": parsed_projection.build_fingerprint.value,
                "canonical_version_id": parsed_projection.canonical_version_id,
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "dense_profile_id": chunk.dense.profile_id,
                "document_id": parsed_projection.document_id,
                "index_schema_version": schema.schema_version,
                "payload_schema_version": schema.payload_schema_version,
                "projection_id": parsed_projection.projection_id,
                "projection_profile_id": parsed_projection.projection_profile.projection_profile_id,
                "sparse_profile_id": chunk.sparse.profile_id,
            },
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "point_id", _ensure_chunk_id(self.point_id, "point_id"))
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id, "chunk_id"))
        if self.point_id != self.chunk_id:
            raise ValueError("point_id incoherent avec chunk_id")
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        object.__setattr__(self, "dense_vector", _ensure_float_tuple(self.dense_vector, "dense_vector"))
        object.__setattr__(self, "sparse_weights", _ensure_sparse_weights(self.sparse_weights))
        payload = _ensure_payload(self.payload)
        if payload.get("chunk_id") != self.chunk_id:
            raise ValueError("payload chunk_id incoherent")
        if payload.get("content_hash") != self.content_hash:
            raise ValueError("payload content_hash incoherent")
        object.__setattr__(self, "payload", payload)

    def require_dense_dimensions(self, expected_dimensions: int) -> None:
        parsed_dimensions = _ensure_positive_integer(expected_dimensions, "dense_dimensions")
        if len(self.dense_vector) != parsed_dimensions:
            raise ValueError("dimension dense incoherente")


@dataclass(frozen=True)
class VectorIndexPublishRequest:
    """Commande transmise au port VectorIndex pour publier une génération."""

    collection_name: str
    index_generation: str
    schema: VectorIndexSchema
    build_fingerprint: BuildFingerprint
    points: Sequence[VectorIndexPoint]
    expected_point_count: int

    def __post_init__(self) -> None:
        schema = _ensure_schema(self.schema)
        object.__setattr__(self, "collection_name", _ensure_text(self.collection_name, "collection_name"))
        if self.collection_name != schema.collection_name:
            raise ValueError("collection_name incoherent avec schema")
        object.__setattr__(
            self,
            "index_generation",
            _ensure_index_generation(self.index_generation),
        )
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint invalide")
        points = _ensure_points(self.points, schema=schema)
        expected_point_count = _ensure_positive_integer(
            self.expected_point_count,
            "expected_point_count",
        )
        if expected_point_count != len(points):
            raise PartialVectorIndexError(
                expected_point_count=expected_point_count,
                published_point_count=len(points),
            )
        object.__setattr__(self, "points", points)


@dataclass(frozen=True)
class VectorIndexPublication:
    """Résultat observable de publication d'une génération d'index."""

    collection_name: str
    index_generation: str
    published_point_ids: Sequence[str]
    expected_point_count: int
    idempotent: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "collection_name", _ensure_text(self.collection_name, "collection_name"))
        object.__setattr__(
            self,
            "index_generation",
            _ensure_index_generation(self.index_generation),
        )
        point_ids = _ensure_point_ids(self.published_point_ids)
        object.__setattr__(self, "published_point_ids", point_ids)
        object.__setattr__(
            self,
            "expected_point_count",
            _ensure_positive_integer(self.expected_point_count, "expected_point_count"),
        )
        if len(point_ids) != self.expected_point_count:
            raise PartialVectorIndexError(
                expected_point_count=self.expected_point_count,
                published_point_count=len(point_ids),
            )
        if not isinstance(self.idempotent, bool):
            raise ValueError("idempotent non booleen")

    @property
    def published_point_count(self) -> int:
        return len(self.published_point_ids)


@dataclass(frozen=True)
class VectorIndexDeletion:
    """Résultat observable de suppression d'une génération technique."""

    collection_name: str
    index_generation: str
    deleted: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "collection_name", _ensure_text(self.collection_name, "collection_name"))
        object.__setattr__(
            self,
            "index_generation",
            _ensure_index_generation(self.index_generation),
        )
        if not isinstance(self.deleted, bool):
            raise ValueError("deleted non booleen")


def index_generation_for(
    *,
    projection: KnowledgeProjection,
    encoded_projection: ProjectionEncodingResult,
    index_schema: VectorIndexSchema,
) -> str:
    parsed_projection = _ensure_projection(projection)
    parsed_encoded_projection = _ensure_encoded_projection(encoded_projection)
    schema = _ensure_schema(index_schema)
    if parsed_projection.projection_id != parsed_encoded_projection.projection_id:
        raise ValueError("projection_id encodage incoherent")
    chunks_payload = tuple(
        {
            "chunk_id": chunk.chunk_id,
            "content_hash": chunk.content_hash,
            "dense_profile_id": chunk.dense.profile_id,
            "dense_model_version": chunk.dense.model_version,
            "sparse_profile_id": chunk.sparse.profile_id,
            "sparse_model_version": chunk.sparse.model_version,
        }
        for chunk in parsed_encoded_projection.encoded_chunks
    )
    payload = {
        "encoded_build_fingerprint": parsed_encoded_projection.build_fingerprint.value,
        "index_schema": schema.to_fingerprint_payload(),
        "projection_build_fingerprint": parsed_projection.build_fingerprint.value,
        "projection_id": parsed_projection.projection_id,
        "chunks": chunks_payload,
    }
    serialized_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"IDX-{hashlib.sha256(serialized_payload.encode('utf-8')).hexdigest()[:32].upper()}"


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("projection invalide")
    return value


def _ensure_encoded_projection(value: ProjectionEncodingResult) -> ProjectionEncodingResult:
    if not isinstance(value, ProjectionEncodingResult):
        raise ValueError("encoded_projection invalide")
    return value


def _ensure_encoded_chunk(value: EncodedProjectionChunk) -> EncodedProjectionChunk:
    if not isinstance(value, EncodedProjectionChunk):
        raise ValueError("encoded_chunk invalide")
    return value


def _ensure_schema(value: VectorIndexSchema) -> VectorIndexSchema:
    if not isinstance(value, VectorIndexSchema):
        raise ValueError("index_schema invalide")
    return value


def _ensure_points(value: Any, *, schema: VectorIndexSchema) -> tuple[VectorIndexPoint, ...]:
    if value is None:
        raise ValueError("points absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("points invalides")
    points = tuple(value)
    if len(points) == 0:
        raise ValueError("points absents")
    point_ids: list[str] = []
    for point in points:
        if not isinstance(point, VectorIndexPoint):
            raise ValueError("point invalide")
        point.require_dense_dimensions(schema.dense_dimensions)
        point_ids.append(point.point_id)
    if len(point_ids) != len(set(point_ids)):
        raise ValueError("point_id duplique")
    return points


def _ensure_point_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        raise ValueError("published_point_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("published_point_ids invalides")
    point_ids = tuple(_ensure_chunk_id(item, "published_point_id") for item in value)
    if len(point_ids) == 0:
        raise ValueError("published_point_ids absents")
    if len(point_ids) != len(set(point_ids)):
        raise ValueError("published_point_id duplique")
    return point_ids


def _ensure_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("payload non objet")
    payload = dict(value)
    if len(payload) == 0:
        raise ValueError("payload vide")
    _reject_forbidden_payload(payload)
    return payload


def _reject_forbidden_payload(payload: Mapping[str, Any]) -> None:
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError("payload key non textuelle")
        normalized_key = key.lower()
        if normalized_key in _FORBIDDEN_PAYLOAD_KEYS:
            raise ValueError(f"{normalized_key} interdit dans payload index")
        if isinstance(value, Mapping):
            _reject_forbidden_payload(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                if isinstance(item, Mapping):
                    _reject_forbidden_payload(item)


def _ensure_sparse_weights(value: Any) -> tuple[tuple[str, float], ...]:
    if value is None:
        raise ValueError("sparse_weights absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("sparse_weights invalides")
    parsed_weights: list[tuple[str, float]] = []
    for item in value:
        if isinstance(item, str) or not isinstance(item, Sequence):
            raise ValueError("sparse_weight invalide")
        pair = tuple(item)
        if len(pair) != 2:
            raise ValueError("sparse_weight invalide")
        token = _ensure_text(pair[0], "sparse_token")
        weight = _ensure_positive_float(pair[1], "sparse_weight")
        parsed_weights.append((token, weight))
    if len(parsed_weights) == 0:
        raise ValueError("sparse_weights absents")
    tokens = tuple(token for token, _ in parsed_weights)
    if len(tokens) != len(set(tokens)):
        raise ValueError("sparse_token duplique")
    return tuple(parsed_weights)


def _ensure_float_tuple(value: Any, field_name: str) -> tuple[float, ...]:
    if value is None:
        raise ValueError(f"{field_name} absent")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed_values = tuple(_ensure_float(item, f"{field_name} invalide") for item in value)
    if len(parsed_values) == 0:
        raise ValueError(f"{field_name} absent")
    return parsed_values


def _ensure_float(value: Any, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(message)
    parsed_value = float(value)
    if not math.isfinite(parsed_value):
        raise ValueError(message)
    return parsed_value


def _ensure_positive_float(value: Any, field_name: str) -> float:
    parsed_value = _ensure_float(value, f"{field_name} invalide")
    if parsed_value <= 0:
        raise ValueError(f"{field_name} invalide")
    return parsed_value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_chunk_id(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith("KCHK-"):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_index_generation(value: Any) -> str:
    text = _ensure_text(value, "index_generation")
    if not text.startswith("IDX-"):
        raise ValueError("index_generation invalide")
    return text


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text_value


__all__ = [
    "PartialVectorIndexError",
    "VectorIndexDeletion",
    "VectorIndexError",
    "VectorIndexPoint",
    "VectorIndexPublication",
    "VectorIndexPublishRequest",
    "VectorIndexSchema",
    "VectorIndexUnavailableError",
    "index_generation_for",
]
