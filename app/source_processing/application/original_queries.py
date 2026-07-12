"""Lecture contrôlée du PDF original propriétaire du bounded context SP."""

from __future__ import annotations

import hashlib
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

    def read_original(self, source_document: SourceDocument) -> bytes:
        """Retourne les octets immuables après contrôle du stockage."""


class OriginalHashMismatchError(ValueError):
    """Signale une substitution ou une corruption de l'original."""

    def __init__(self) -> None:
        super().__init__("ORIGINAL_HASH_MISMATCH")


@dataclass(frozen=True, slots=True)
class OriginalPdfContent:
    """Contenu PDF vérifié prêt à franchir la frontière HTTP publique."""

    document_id: str
    source_sha256: str
    content: bytes

    @property
    def content_length(self) -> int:
        return len(self.content)

    @property
    def public_filename(self) -> str:
        return f"{self.document_id}.pdf"

    def __post_init__(self) -> None:
        DocumentId.from_value(self.document_id)
        SourceFingerprint.from_value(self.source_sha256)
        if not isinstance(self.content, bytes) or len(self.content) == 0:
            raise ValueError("contenu PDF original invalide")
        if hashlib.sha256(self.content).hexdigest() != self.source_sha256:
            raise OriginalHashMismatchError()


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
        if not callable(getattr(original_source_reader, "read_original", None)):
            raise ValueError("original_source_reader sans lecture originale")
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
        content = self._original_source_reader.read_original(parsed_source_document)
        if not isinstance(content, bytes) or len(content) == 0:
            raise ValueError("contenu PDF original invalide")
        return OriginalPdfContent(
            document_id=parsed_source_document.document_id.value,
            source_sha256=parsed_source_document.fingerprint.value,
            content=content,
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
    "SourceDocumentOriginalRepository",
]
