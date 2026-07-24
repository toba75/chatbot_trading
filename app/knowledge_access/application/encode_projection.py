"""Cas d'usage KA d'encodage dense et sparse d'une projection."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.domain.chunking import HierarchicalChunkProjection, KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint
from app.knowledge_access.domain.projection_encoding import (
    DenseChunkEncoding,
    DenseEncodingFailedError,
    DenseEncodingProfile,
    DenseEncodingVector,
    EncodedProjectionChunk,
    ProjectionEncodingProfile,
    ProjectionEncodingResult,
    ProjectionEncodingTrace,
    SparseChunkEncoding,
    SparseEncodingFailedError,
    SparseEncodingProfile,
    SparseEncodingVector,
)


class DenseEncoder(Protocol):
    """Port KA qui produit un vecteur dense pour un chunk."""

    def encode_dense(self, request: "DenseEncodingRequest") -> DenseEncodingVector:
        """Encode un chunk via le profil dense fourni."""


class SparseEncoder(Protocol):
    """Port KA qui produit une representation sparse pour un chunk."""

    def encode_sparse(self, request: "SparseEncodingRequest") -> SparseEncodingVector:
        """Encode un chunk via le profil sparse fourni."""


@dataclass(frozen=True)
class DenseEncodingRequest:
    """Requete transmise au port dense."""

    chunk_id: str
    content_hash: str
    text: str
    profile: DenseEncodingProfile

    @classmethod
    def from_chunk(
        cls,
        *,
        chunk: KnowledgeChunk,
        profile: DenseEncodingProfile,
    ) -> "DenseEncodingRequest":
        parsed_chunk = _ensure_chunk(chunk)
        if not isinstance(profile, DenseEncodingProfile):
            raise ValueError("dense_profile invalide")
        return cls(
            chunk_id=parsed_chunk.chunk_id,
            content_hash=parsed_chunk.content_hash,
            text=parsed_chunk.text,
            profile=profile,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        object.__setattr__(self, "text", _ensure_text(self.text, "chunk_text"))
        if not isinstance(self.profile, DenseEncodingProfile):
            raise ValueError("dense_profile invalide")


@dataclass(frozen=True)
class SparseEncodingRequest:
    """Requete transmise au port sparse."""

    chunk_id: str
    content_hash: str
    text: str
    profile: SparseEncodingProfile

    @classmethod
    def from_chunk(
        cls,
        *,
        chunk: KnowledgeChunk,
        profile: SparseEncodingProfile,
    ) -> "SparseEncodingRequest":
        parsed_chunk = _ensure_chunk(chunk)
        if not isinstance(profile, SparseEncodingProfile):
            raise ValueError("sparse_profile invalide")
        return cls(
            chunk_id=parsed_chunk.chunk_id,
            content_hash=parsed_chunk.content_hash,
            text=parsed_chunk.text,
            profile=profile,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        object.__setattr__(self, "text", _ensure_text(self.text, "chunk_text"))
        if not isinstance(self.profile, SparseEncodingProfile):
            raise ValueError("sparse_profile invalide")


@dataclass(frozen=True)
class EncodeProjectionCommand:
    """Commande KA d'encodage d'une projection de chunks."""

    projection_id: str
    build_fingerprint: BuildFingerprint
    chunk_projection: HierarchicalChunkProjection
    encoding_profile: ProjectionEncodingProfile

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint invalide")
        if not isinstance(self.chunk_projection, HierarchicalChunkProjection):
            raise ValueError("chunk_projection invalide")
        if not isinstance(self.encoding_profile, ProjectionEncodingProfile):
            raise ValueError("encoding_profile invalide")


class ProjectionEncodingHandler:
    """Orchestre l'encodage complet des chunks eligibles."""

    def __init__(
        self,
        *,
        dense_encoder: DenseEncoder,
        sparse_encoder: SparseEncoder,
        max_parallel_chunks: int = 1,
    ) -> None:
        if not callable(getattr(dense_encoder, "encode_dense", None)):
            raise ValueError("dense_encoder sans encode_dense")
        if not callable(getattr(sparse_encoder, "encode_sparse", None)):
            raise ValueError("sparse_encoder sans encode_sparse")
        self._dense_encoder = dense_encoder
        self._sparse_encoder = sparse_encoder
        self._max_parallel_chunks = _ensure_positive_int(max_parallel_chunks, "max_parallel_chunks")

    def encode_projection(self, command: EncodeProjectionCommand) -> ProjectionEncodingResult:
        parsed_command = _ensure_command(command)
        encoding_fingerprint = parsed_command.build_fingerprint.extend_with_payload(
            scope="projection_encoding",
            payload=parsed_command.encoding_profile.to_fingerprint_payload(),
        )
        encoded_chunks = self._encode_chunks(
            chunks=parsed_command.chunk_projection.chunks,
            encoding_profile=parsed_command.encoding_profile,
        )
        trace = ProjectionEncodingTrace(
            projection_id=parsed_command.projection_id,
            build_fingerprint=encoding_fingerprint,
            encoding_profile_id=parsed_command.encoding_profile.profile_id,
            encoding_profile_version=parsed_command.encoding_profile.profile_version,
            dense_profile_id=parsed_command.encoding_profile.dense.profile_id,
            dense_model_name=parsed_command.encoding_profile.dense.model_name,
            dense_model_version=parsed_command.encoding_profile.dense.model_version,
            sparse_profile_id=parsed_command.encoding_profile.sparse.profile_id,
            sparse_model_name=parsed_command.encoding_profile.sparse.model_name,
            sparse_model_version=parsed_command.encoding_profile.sparse.model_version,
            encoded_chunk_count=len(encoded_chunks),
        )
        return ProjectionEncodingResult(
            projection_id=parsed_command.projection_id,
            build_fingerprint=encoding_fingerprint,
            encoding_profile=parsed_command.encoding_profile,
            encoded_chunks=encoded_chunks,
            trace=trace,
        )

    def _encode_chunks(
        self,
        *,
        chunks: Sequence[KnowledgeChunk],
        encoding_profile: ProjectionEncodingProfile,
    ) -> tuple[EncodedProjectionChunk, ...]:
        chunk_count = len(chunks)
        if chunk_count == 0:
            raise ValueError("chunks de projection absents")
        if self._max_parallel_chunks == 1 or chunk_count == 1:
            return tuple(
                self._encode_chunk(
                    chunk=_ensure_chunk(chunk),
                    encoding_profile=encoding_profile,
                )
                for chunk in chunks
            )
        results: list[EncodedProjectionChunk | None] = [None] * chunk_count
        with ThreadPoolExecutor(
            max_workers=min(self._max_parallel_chunks, chunk_count),
            thread_name_prefix="ka-projection-encoding",
        ) as executor:
            futures: dict[Future[EncodedProjectionChunk], int] = {}
            next_index = 0

            def submit_next() -> bool:
                nonlocal next_index
                if next_index >= chunk_count:
                    return False
                index = next_index
                next_index += 1
                future = executor.submit(
                    self._encode_chunk,
                    chunk=_ensure_chunk(chunks[index]),
                    encoding_profile=encoding_profile,
                )
                futures[future] = index
                return True

            for _ in range(min(self._max_parallel_chunks, chunk_count)):
                submit_next()
            while futures:
                completed, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
                for future in completed:
                    results[futures.pop(future)] = future.result()
                    submit_next()
        return tuple(_ensure_encoded_chunk(value) for value in results)

    def _encode_chunk(
        self,
        *,
        chunk: KnowledgeChunk,
        encoding_profile: ProjectionEncodingProfile,
    ) -> EncodedProjectionChunk:
        parsed_chunk = _ensure_chunk(chunk)
        try:
            dense_vector = self._dense_encoder.encode_dense(
                DenseEncodingRequest.from_chunk(
                    chunk=parsed_chunk,
                    profile=encoding_profile.dense,
                )
            )
        except Exception as exc:
            raise DenseEncodingFailedError(chunk_id=parsed_chunk.chunk_id, reason=str(exc)) from exc
        dense = DenseChunkEncoding.from_vector(
            chunk=parsed_chunk,
            profile=encoding_profile.dense,
            vector=dense_vector,
        )

        try:
            sparse_vector = self._sparse_encoder.encode_sparse(
                SparseEncodingRequest.from_chunk(
                    chunk=parsed_chunk,
                    profile=encoding_profile.sparse,
                )
            )
        except Exception as exc:
            raise SparseEncodingFailedError(chunk_id=parsed_chunk.chunk_id, reason=str(exc)) from exc
        sparse = SparseChunkEncoding.from_vector(
            chunk=parsed_chunk,
            profile=encoding_profile.sparse,
            vector=sparse_vector,
        )

        return EncodedProjectionChunk(
            chunk_id=parsed_chunk.chunk_id,
            content_hash=parsed_chunk.content_hash,
            dense=dense,
            sparse=sparse,
        )


def _ensure_command(value: EncodeProjectionCommand) -> EncodeProjectionCommand:
    if not isinstance(value, EncodeProjectionCommand):
        raise ValueError("commande EncodeProjection invalide")
    return value


def _ensure_chunk(value: KnowledgeChunk) -> KnowledgeChunk:
    if not isinstance(value, KnowledgeChunk):
        raise ValueError("chunk invalide")
    return value


def _ensure_encoded_chunk(value: EncodedProjectionChunk | None) -> EncodedProjectionChunk:
    if not isinstance(value, EncodedProjectionChunk):
        raise ValueError("chunk encodé absent")
    return value


def _ensure_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


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


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in "0123456789abcdef":
            raise ValueError(f"{field_name} invalide")
    return text_value


__all__ = [
    "DenseEncoder",
    "DenseEncodingRequest",
    "EncodeProjectionCommand",
    "ProjectionEncodingHandler",
    "SparseEncoder",
    "SparseEncodingRequest",
]
