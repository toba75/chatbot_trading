"""Lecture contrôlée du PDF original propriétaire du bounded context SP."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from app.source_processing.application.document_commands import SourceNotFoundError
from app.source_processing.domain.source_document import (
    DocumentId,
    SourceDocument,
    SourceFingerprint,
)


class SourceDocumentOriginalRepository(Protocol):
    """Résout une source uniquement depuis son identité publique."""

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        """Retourne le SourceDocument propriétaire de l'original."""


class OriginalSourceReader(Protocol):
    """Port binaire qui lit la référence interne portée par le SourceDocument."""

    def open_verified_original(
        self,
        source_document: SourceDocument,
        *,
        chunk_size: int,
    ) -> "VerifiedOriginalBinary":
        """Ouvre un original vérifié et un itérateur binaire borné."""


class OriginalHashMismatchError(ValueError):
    """Signale une substitution ou une corruption de l'original."""

    def __init__(self) -> None:
        super().__init__("ORIGINAL_HASH_MISMATCH")


ORIGINAL_STREAM_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class VerifiedOriginalBinary:
    """Descripteur binaire vérifié dont la fermeture est explicite."""

    content_length: int
    content_chunks: Iterator[bytes]
    close: Callable[[], None]

    def __post_init__(self) -> None:
        if (
            isinstance(self.content_length, bool)
            or not isinstance(self.content_length, int)
            or self.content_length < 1
        ):
            raise ValueError("content_length original invalide")
        if not callable(getattr(self.content_chunks, "__next__", None)):
            raise ValueError("content_chunks original invalide")
        if not callable(self.close):
            raise ValueError("fermeture original invalide")


@dataclass(frozen=True, slots=True)
class OriginalPdfContent:
    """Flux PDF vérifié prêt à franchir la frontière HTTP publique."""

    document_id: str
    source_sha256: str
    content_length: int
    content_chunks: Iterator[bytes]
    close: Callable[[], None]

    @property
    def public_filename(self) -> str:
        return f"{self.document_id}.pdf"

    def __post_init__(self) -> None:
        DocumentId.from_value(self.document_id)
        SourceFingerprint.from_value(self.source_sha256)
        if (
            isinstance(self.content_length, bool)
            or not isinstance(self.content_length, int)
            or self.content_length < 1
        ):
            raise ValueError("content_length PDF original invalide")
        if not callable(getattr(self.content_chunks, "__next__", None)):
            raise ValueError("chunks PDF original invalides")
        if not callable(self.close):
            raise ValueError("fermeture PDF original invalide")


class OriginalPdfQueryService:
    """Résout l'original par DocumentId sans accepter de référence de stockage."""

    def __init__(
        self,
        *,
        source_document_repository: SourceDocumentOriginalRepository,
        original_source_reader: OriginalSourceReader,
    ) -> None:
        if not callable(getattr(source_document_repository, "find_by_document_id", None)):
            raise ValueError("source_document_repository sans lecture par document_id")
        if not callable(getattr(original_source_reader, "open_verified_original", None)):
            raise ValueError("original_source_reader sans ouverture vérifiée")
        self._source_document_repository = source_document_repository
        self._original_source_reader = original_source_reader

    def read_original(self, document_id: str) -> OriginalPdfContent:
        parsed_document_id = DocumentId.from_value(document_id)
        source_document = self._source_document_repository.find_by_document_id(
            parsed_document_id
        )
        if source_document is None:
            raise SourceNotFoundError(parsed_document_id.value)
        parsed_source_document = _ensure_source_document(source_document)
        binary = self._original_source_reader.open_verified_original(
            parsed_source_document,
            chunk_size=ORIGINAL_STREAM_CHUNK_BYTES,
        )
        if not isinstance(binary, VerifiedOriginalBinary):
            raise ValueError("flux PDF original invalide")
        return OriginalPdfContent(
            document_id=parsed_source_document.document_id.value,
            source_sha256=parsed_source_document.fingerprint.value,
            content_length=binary.content_length,
            content_chunks=binary.content_chunks,
            close=binary.close,
        )


def _ensure_source_document(value: Any) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


__all__ = [
    "OriginalHashMismatchError",
    "OriginalPdfContent",
    "OriginalPdfQueryService",
    "OriginalSourceReader",
    "ORIGINAL_STREAM_CHUNK_BYTES",
    "SourceDocumentOriginalRepository",
    "VerifiedOriginalBinary",
]
