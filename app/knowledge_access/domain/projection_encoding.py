"""Encodage dense et sparse versionne des chunks KA."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint


_DENSE_PROFILE_FIELDS = frozenset(
    {
        "profile_id",
        "model_name",
        "model_version",
        "dimensions",
        "parameters_hash",
    }
)
_SPARSE_PROFILE_FIELDS = frozenset(
    {
        "profile_id",
        "model_name",
        "model_version",
        "parameters_hash",
    }
)
_ENCODING_PROFILE_FIELDS = frozenset(
    {
        "profile_id",
        "profile_version",
        "dense",
        "sparse",
    }
)
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")


class ProjectionEncodingError(ValueError):
    """Erreur metier stable de l'encodage KA."""

    error_code: str


class EncodingModelVersionMissingError(ProjectionEncodingError):
    """Erreur produite quand une version de modele d'encodage est absente."""

    def __init__(self, field_name: str) -> None:
        self.error_code = "ENCODING_MODEL_VERSION_MISSING"
        self.field_name = _ensure_text(field_name, "field_name")
        super().__init__(f"{self.error_code}: {self.field_name} version manquante")


class DenseEncodingFailedError(ProjectionEncodingError):
    """Erreur produite quand le port dense ne produit pas un vecteur valide."""

    def __init__(self, *, chunk_id: str, reason: str) -> None:
        self.error_code = "DENSE_ENCODING_FAILED"
        self.chunk_id = _ensure_chunk_id(chunk_id)
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"{self.error_code}: {self.chunk_id}; {self.reason}")


class SparseEncodingFailedError(ProjectionEncodingError):
    """Erreur produite quand le port sparse ne produit pas une representation valide."""

    def __init__(self, *, chunk_id: str, reason: str) -> None:
        self.error_code = "SPARSE_ENCODING_FAILED"
        self.chunk_id = _ensure_chunk_id(chunk_id)
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"{self.error_code}: {self.chunk_id}; {self.reason}")


@dataclass(frozen=True)
class DenseEncodingProfile:
    """Profil dense explicite et versionne."""

    profile_id: str
    model_name: str
    model_version: str
    dimensions: int
    parameters_hash: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DenseEncodingProfile":
        parsed_payload = _ensure_mapping(payload, "dense_profile")
        _ensure_expected_fields(
            parsed_payload,
            expected_fields=_DENSE_PROFILE_FIELDS,
            missing_model_version_field="dense.model_version",
        )
        return cls(
            profile_id=parsed_payload["profile_id"],
            model_name=parsed_payload["model_name"],
            model_version=parsed_payload["model_version"],
            dimensions=parsed_payload["dimensions"],
            parameters_hash=parsed_payload["parameters_hash"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "dense.profile_id"))
        object.__setattr__(
            self,
            "model_name",
            _ensure_text(self.model_name, "dense.model_name"),
        )
        object.__setattr__(
            self,
            "model_version",
            _ensure_model_version(self.model_version, "dense.model_version"),
        )
        object.__setattr__(
            self,
            "dimensions",
            _ensure_positive_integer(self.dimensions, "dimensions invalide"),
        )
        object.__setattr__(
            self,
            "parameters_hash",
            _ensure_sha256(self.parameters_hash, "dense.parameters_hash"),
        )

    def to_fingerprint_payload(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "parameters_hash": self.parameters_hash,
            "profile_id": self.profile_id,
        }


@dataclass(frozen=True)
class SparseEncodingProfile:
    """Profil sparse explicite et versionne."""

    profile_id: str
    model_name: str
    model_version: str
    parameters_hash: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SparseEncodingProfile":
        parsed_payload = _ensure_mapping(payload, "sparse_profile")
        _ensure_expected_fields(
            parsed_payload,
            expected_fields=_SPARSE_PROFILE_FIELDS,
            missing_model_version_field="sparse.model_version",
        )
        return cls(
            profile_id=parsed_payload["profile_id"],
            model_name=parsed_payload["model_name"],
            model_version=parsed_payload["model_version"],
            parameters_hash=parsed_payload["parameters_hash"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "sparse.profile_id"))
        object.__setattr__(
            self,
            "model_name",
            _ensure_text(self.model_name, "sparse.model_name"),
        )
        object.__setattr__(
            self,
            "model_version",
            _ensure_model_version(self.model_version, "sparse.model_version"),
        )
        object.__setattr__(
            self,
            "parameters_hash",
            _ensure_sha256(self.parameters_hash, "sparse.parameters_hash"),
        )

    def to_fingerprint_payload(self) -> dict[str, str]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "parameters_hash": self.parameters_hash,
            "profile_id": self.profile_id,
        }


@dataclass(frozen=True)
class ProjectionEncodingProfile:
    """Profil complet d'encodage hybride dense et sparse."""

    profile_id: str
    profile_version: str
    dense: DenseEncodingProfile
    sparse: SparseEncodingProfile

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProjectionEncodingProfile":
        parsed_payload = _ensure_mapping(payload, "encoding_profile")
        _ensure_expected_fields(
            parsed_payload,
            expected_fields=_ENCODING_PROFILE_FIELDS,
            missing_model_version_field=None,
        )
        return cls(
            profile_id=parsed_payload["profile_id"],
            profile_version=parsed_payload["profile_version"],
            dense=DenseEncodingProfile.from_payload(parsed_payload["dense"]),
            sparse=SparseEncodingProfile.from_payload(parsed_payload["sparse"]),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "profile_id"))
        object.__setattr__(
            self,
            "profile_version",
            _ensure_text(self.profile_version, "profile_version"),
        )
        if not isinstance(self.dense, DenseEncodingProfile):
            raise ValueError("dense_profile invalide")
        if not isinstance(self.sparse, SparseEncodingProfile):
            raise ValueError("sparse_profile invalide")

    def to_fingerprint_payload(self) -> dict[str, Any]:
        return {
            "dense": self.dense.to_fingerprint_payload(),
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "sparse": self.sparse.to_fingerprint_payload(),
        }


@dataclass(frozen=True)
class DenseEncodingVector:
    """Vecteur dense produit par un port d'encodage."""

    values: Sequence[float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _ensure_float_tuple(self.values, "vecteur dense"))


@dataclass(frozen=True)
class SparseTokenWeight:
    """Poids sparse associe a un token explicite."""

    token: str
    weight: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "token", _ensure_text(self.token, "token sparse"))
        object.__setattr__(
            self,
            "weight",
            _ensure_positive_float(self.weight, "poids sparse invalide"),
        )


@dataclass(frozen=True)
class SparseEncodingVector:
    """Representation sparse produite par un port d'encodage."""

    weights: Sequence[SparseTokenWeight]

    def __post_init__(self) -> None:
        object.__setattr__(self, "weights", _ensure_sparse_weights(self.weights))

    @property
    def term_count(self) -> int:
        return len(self.weights)


@dataclass(frozen=True)
class DenseChunkEncoding:
    """Resultat dense versionne pour un chunk."""

    chunk_id: str
    content_hash: str
    profile_id: str
    model_name: str
    model_version: str
    parameters_hash: str
    dimensions: int
    values: tuple[float, ...]

    @classmethod
    def from_vector(
        cls,
        *,
        chunk: KnowledgeChunk,
        profile: DenseEncodingProfile,
        vector: DenseEncodingVector,
    ) -> "DenseChunkEncoding":
        parsed_chunk = _ensure_chunk(chunk)
        parsed_profile = _ensure_dense_profile(profile)
        parsed_vector = _ensure_dense_vector(vector)
        return cls(
            chunk_id=parsed_chunk.chunk_id,
            content_hash=parsed_chunk.content_hash,
            profile_id=parsed_profile.profile_id,
            model_name=parsed_profile.model_name,
            model_version=parsed_profile.model_version,
            parameters_hash=parsed_profile.parameters_hash,
            dimensions=parsed_profile.dimensions,
            values=parsed_vector.values,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "dense.profile_id"))
        object.__setattr__(self, "model_name", _ensure_text(self.model_name, "dense.model_name"))
        object.__setattr__(
            self,
            "model_version",
            _ensure_model_version(self.model_version, "dense.model_version"),
        )
        object.__setattr__(
            self,
            "parameters_hash",
            _ensure_sha256(self.parameters_hash, "dense.parameters_hash"),
        )
        object.__setattr__(
            self,
            "dimensions",
            _ensure_positive_integer(self.dimensions, "dimensions invalide"),
        )
        object.__setattr__(self, "values", _ensure_float_tuple(self.values, "vecteur dense"))
        if len(self.values) != self.dimensions:
            raise ValueError("dimension dense incoherente")


@dataclass(frozen=True)
class SparseChunkEncoding:
    """Resultat sparse versionne pour un chunk."""

    chunk_id: str
    content_hash: str
    profile_id: str
    model_name: str
    model_version: str
    parameters_hash: str
    weights: tuple[SparseTokenWeight, ...]

    @classmethod
    def from_vector(
        cls,
        *,
        chunk: KnowledgeChunk,
        profile: SparseEncodingProfile,
        vector: SparseEncodingVector,
    ) -> "SparseChunkEncoding":
        parsed_chunk = _ensure_chunk(chunk)
        parsed_profile = _ensure_sparse_profile(profile)
        parsed_vector = _ensure_sparse_vector(vector)
        return cls(
            chunk_id=parsed_chunk.chunk_id,
            content_hash=parsed_chunk.content_hash,
            profile_id=parsed_profile.profile_id,
            model_name=parsed_profile.model_name,
            model_version=parsed_profile.model_version,
            parameters_hash=parsed_profile.parameters_hash,
            weights=parsed_vector.weights,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "sparse.profile_id"))
        object.__setattr__(self, "model_name", _ensure_text(self.model_name, "sparse.model_name"))
        object.__setattr__(
            self,
            "model_version",
            _ensure_model_version(self.model_version, "sparse.model_version"),
        )
        object.__setattr__(
            self,
            "parameters_hash",
            _ensure_sha256(self.parameters_hash, "sparse.parameters_hash"),
        )
        object.__setattr__(self, "weights", _ensure_sparse_weights(self.weights))

    @property
    def term_count(self) -> int:
        return len(self.weights)


@dataclass(frozen=True)
class EncodedProjectionChunk:
    """Chunk encode complet, dense et sparse."""

    chunk_id: str
    content_hash: str
    dense: DenseChunkEncoding
    sparse: SparseChunkEncoding

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        if not isinstance(self.dense, DenseChunkEncoding):
            raise ValueError("encodage dense invalide")
        if not isinstance(self.sparse, SparseChunkEncoding):
            raise ValueError("encodage sparse invalide")
        if self.dense.chunk_id != self.chunk_id or self.sparse.chunk_id != self.chunk_id:
            raise ValueError("chunk_id encodage incoherent")
        if (
            self.dense.content_hash != self.content_hash
            or self.sparse.content_hash != self.content_hash
        ):
            raise ValueError("content_hash encodage incoherent")


@dataclass(frozen=True)
class ProjectionEncodingTrace:
    """Trace d'encodage sans payload documentaire complet."""

    projection_id: str
    build_fingerprint: BuildFingerprint
    encoding_profile_id: str
    encoding_profile_version: str
    dense_profile_id: str
    dense_model_name: str
    dense_model_version: str
    sparse_profile_id: str
    sparse_model_name: str
    sparse_model_version: str
    encoded_chunk_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint invalide")
        object.__setattr__(
            self,
            "encoding_profile_id",
            _ensure_text(self.encoding_profile_id, "encoding_profile_id"),
        )
        object.__setattr__(
            self,
            "encoding_profile_version",
            _ensure_text(self.encoding_profile_version, "encoding_profile_version"),
        )
        object.__setattr__(
            self,
            "dense_profile_id",
            _ensure_text(self.dense_profile_id, "dense_profile_id"),
        )
        object.__setattr__(
            self,
            "dense_model_name",
            _ensure_text(self.dense_model_name, "dense_model_name"),
        )
        object.__setattr__(
            self,
            "dense_model_version",
            _ensure_model_version(self.dense_model_version, "dense_model_version"),
        )
        object.__setattr__(
            self,
            "sparse_profile_id",
            _ensure_text(self.sparse_profile_id, "sparse_profile_id"),
        )
        object.__setattr__(
            self,
            "sparse_model_name",
            _ensure_text(self.sparse_model_name, "sparse_model_name"),
        )
        object.__setattr__(
            self,
            "sparse_model_version",
            _ensure_model_version(self.sparse_model_version, "sparse_model_version"),
        )
        object.__setattr__(
            self,
            "encoded_chunk_count",
            _ensure_positive_integer(self.encoded_chunk_count, "encoded_chunk_count invalide"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "build_fingerprint": self.build_fingerprint.value,
            "dense_model_name": self.dense_model_name,
            "dense_model_version": self.dense_model_version,
            "dense_profile_id": self.dense_profile_id,
            "encoded_chunk_count": self.encoded_chunk_count,
            "encoding_profile_id": self.encoding_profile_id,
            "encoding_profile_version": self.encoding_profile_version,
            "projection_id": self.projection_id,
            "sparse_model_name": self.sparse_model_name,
            "sparse_model_version": self.sparse_model_version,
            "sparse_profile_id": self.sparse_profile_id,
        }


@dataclass(frozen=True)
class ProjectionEncodingResult:
    """Resultat complet d'encodage de projection."""

    projection_id: str
    build_fingerprint: BuildFingerprint
    encoding_profile: ProjectionEncodingProfile
    encoded_chunks: Sequence[EncodedProjectionChunk]
    trace: ProjectionEncodingTrace

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint invalide")
        if not isinstance(self.encoding_profile, ProjectionEncodingProfile):
            raise ValueError("encoding_profile invalide")
        chunks = _ensure_encoded_chunks(self.encoded_chunks)
        object.__setattr__(self, "encoded_chunks", chunks)
        if not isinstance(self.trace, ProjectionEncodingTrace):
            raise ValueError("trace invalide")
        if self.trace.projection_id != self.projection_id:
            raise ValueError("projection_id trace incoherent")
        if self.trace.build_fingerprint != self.build_fingerprint:
            raise ValueError("build_fingerprint trace incoherent")
        if self.trace.encoded_chunk_count != len(chunks):
            raise ValueError("encoded_chunk_count incoherent")

    def to_trace_payload(self) -> dict[str, Any]:
        return self.trace.to_payload()


def _ensure_expected_fields(
    payload: Mapping[str, Any],
    *,
    expected_fields: frozenset[str],
    missing_model_version_field: str | None,
) -> None:
    actual_fields = frozenset(payload.keys())
    missing_fields = expected_fields - actual_fields
    if len(missing_fields) > 0:
        first_missing = sorted(missing_fields)[0]
        if first_missing == "model_version" and missing_model_version_field is not None:
            raise EncodingModelVersionMissingError(missing_model_version_field)
        raise ValueError(f"{first_missing} absent")
    unexpected_fields = actual_fields - expected_fields
    if len(unexpected_fields) > 0:
        raise ValueError(f"{sorted(unexpected_fields)[0]} interdit")


def _ensure_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_model_version(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise EncodingModelVersionMissingError(field_name)
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _ensure_float_tuple(value: Any, field_name: str) -> tuple[float, ...]:
    if value is None:
        raise ValueError(f"{field_name} absent")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed_values: list[float] = []
    for item in value:
        parsed_values.append(_ensure_float(item, f"{field_name} invalide"))
    if len(parsed_values) == 0:
        raise ValueError(f"{field_name} absent")
    return tuple(parsed_values)


def _ensure_float(value: Any, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(message)
    parsed_value = float(value)
    if not math.isfinite(parsed_value):
        raise ValueError(message)
    return parsed_value


def _ensure_positive_float(value: Any, message: str) -> float:
    parsed_value = _ensure_float(value, message)
    if parsed_value <= 0:
        raise ValueError(message)
    return parsed_value


def _ensure_sparse_weights(value: Any) -> tuple[SparseTokenWeight, ...]:
    if value is None:
        raise ValueError("poids sparse absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("poids sparse invalides")
    weights = tuple(value)
    if len(weights) == 0:
        raise ValueError("poids sparse absents")
    for weight in weights:
        if not isinstance(weight, SparseTokenWeight):
            raise ValueError("poids sparse invalides")
    tokens = tuple(weight.token for weight in weights)
    if len(tokens) != len(set(tokens)):
        raise ValueError("token sparse duplique")
    return weights


def _ensure_chunk(value: KnowledgeChunk) -> KnowledgeChunk:
    if not isinstance(value, KnowledgeChunk):
        raise ValueError("chunk invalide")
    return value


def _ensure_dense_profile(value: DenseEncodingProfile) -> DenseEncodingProfile:
    if not isinstance(value, DenseEncodingProfile):
        raise ValueError("dense_profile invalide")
    return value


def _ensure_sparse_profile(value: SparseEncodingProfile) -> SparseEncodingProfile:
    if not isinstance(value, SparseEncodingProfile):
        raise ValueError("sparse_profile invalide")
    return value


def _ensure_dense_vector(value: DenseEncodingVector) -> DenseEncodingVector:
    if not isinstance(value, DenseEncodingVector):
        raise ValueError("vecteur dense invalide")
    return value


def _ensure_sparse_vector(value: SparseEncodingVector) -> SparseEncodingVector:
    if not isinstance(value, SparseEncodingVector):
        raise ValueError("vecteur sparse invalide")
    return value


def _ensure_encoded_chunks(value: Any) -> tuple[EncodedProjectionChunk, ...]:
    if value is None:
        raise ValueError("encoded_chunks absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("encoded_chunks invalides")
    chunks = tuple(value)
    if len(chunks) == 0:
        raise ValueError("encoded_chunks absents")
    for chunk in chunks:
        if not isinstance(chunk, EncodedProjectionChunk):
            raise ValueError("encoded_chunk invalide")
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("chunk_id encode duplique")
    return chunks


def _ensure_projection_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("projection_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "PROJ"))
    except ValueError as exc:
        raise ValueError(f"projection_id invalide: {exc}") from exc


def _ensure_chunk_id(value: Any) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
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
    "DenseChunkEncoding",
    "DenseEncodingFailedError",
    "DenseEncodingProfile",
    "DenseEncodingVector",
    "EncodedProjectionChunk",
    "EncodingModelVersionMissingError",
    "ProjectionEncodingError",
    "ProjectionEncodingProfile",
    "ProjectionEncodingResult",
    "ProjectionEncodingTrace",
    "SparseChunkEncoding",
    "SparseEncodingFailedError",
    "SparseEncodingProfile",
    "SparseEncodingVector",
    "SparseTokenWeight",
]
