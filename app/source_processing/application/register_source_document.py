"""Cas d'usage d'enregistrement immuable d'une source documentaire."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Protocol

from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class OriginalSourceStore(Protocol):
    """Port de stockage de l'original immuable."""

    def put_original_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        original_content: bytes,
    ) -> str:
        """Stocke l'original bit-à-bit si absent et retourne sa référence immuable."""


    def put_original_path_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        source_path: Path,
    ) -> str: ...


class SourceDocumentRepository(Protocol):
    """Port de dépôt de SourceDocument."""

    def find_by_fingerprint(self, fingerprint: SourceFingerprint) -> SourceDocument | None:
        """Retourne la source qui possède déjà l'empreinte, si elle existe."""

    def find_by_work_key(self, work_key: tuple[str, tuple[str, ...]]) -> SourceDocument | None:
        """Retourne une source du même ouvrage, si elle existe."""

    def save_if_absent(self, source_document: SourceDocument) -> SourceDocument | None:
        """Persiste la source si aucune source de même identité n'existe."""


@dataclass(frozen=True)
class RegisterSourceDocumentCommand:
    """Commande applicative d'enregistrement d'un PDF original."""

    original_content: bytes
    bibliographic_metadata: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        if not isinstance(self.original_content, bytes):
            raise ValueError("original_content non binaire")
        if self.bibliographic_metadata is not None and not isinstance(
            self.bibliographic_metadata, Mapping
        ):
            raise ValueError("bibliographic_metadata non objet")


@dataclass(frozen=True)
class RegisterSourceDocumentResult:
    """Résultat observable de l'enregistrement documentaire."""

    decision: str
    source_document: SourceDocument | None
    duplicate_document_id: DocumentId | None
    review_reason: str | None

    def __post_init__(self) -> None:
        if self.decision not in {
            "REGISTERED",
            "BINARY_DUPLICATE",
            "DISTINCT_EDITION_REGISTERED",
            "REVIEW_REQUIRED",
        }:
            raise ValueError(f"décision d'enregistrement inconnue: {self.decision}")
        if self.decision in {"REGISTERED", "DISTINCT_EDITION_REGISTERED"}:
            if not isinstance(self.source_document, SourceDocument):
                raise ValueError("source_document absent pour enregistrement")
            if self.duplicate_document_id is not None:
                raise ValueError("duplicate_document_id interdit pour enregistrement")
            if self.review_reason is not None:
                raise ValueError("review_reason interdit pour enregistrement")
        if self.decision == "BINARY_DUPLICATE":
            if self.source_document is not None:
                raise ValueError("source_document interdit pour doublon binaire")
            if not isinstance(self.duplicate_document_id, DocumentId):
                raise ValueError("duplicate_document_id absent pour doublon binaire")
            if self.review_reason is not None:
                raise ValueError("review_reason interdit pour doublon binaire")
        if self.decision == "REVIEW_REQUIRED":
            if self.source_document is not None:
                raise ValueError("source_document interdit pour revue explicite")
            if self.duplicate_document_id is not None:
                raise ValueError("duplicate_document_id interdit pour revue explicite")
            _ensure_text(self.review_reason, "review_reason")


class RegisterSourceDocumentHandler:
    """Handler applicatif de la commande RegisterSourceDocument."""

    def __init__(
        self,
        original_source_store: OriginalSourceStore,
        source_document_repository: SourceDocumentRepository,
    ) -> None:
        if not callable(getattr(original_source_store, "put_original_if_absent", None)):
            raise ValueError("original_source_store invalide")
        if not callable(getattr(source_document_repository, "find_by_fingerprint", None)):
            raise ValueError("source_document_repository invalide")
        if not callable(getattr(source_document_repository, "find_by_work_key", None)):
            raise ValueError("source_document_repository invalide")
        if not callable(getattr(source_document_repository, "save_if_absent", None)):
            raise ValueError("source_document_repository invalide")
        self._original_source_store = original_source_store
        self._source_document_repository = source_document_repository

    def handle(self, command: RegisterSourceDocumentCommand) -> RegisterSourceDocumentResult:
        if not isinstance(command, RegisterSourceDocumentCommand):
            raise ValueError("commande RegisterSourceDocument invalide")

        metadata = (
            None
            if command.bibliographic_metadata is None
            else BibliographicMetadata.from_payload(command.bibliographic_metadata)
        )
        review_reason = _review_reason_for_unreadable_pdf(command.original_content)
        if review_reason is not None:
            return RegisterSourceDocumentResult(
                decision="REVIEW_REQUIRED",
                source_document=None,
                duplicate_document_id=None,
                review_reason=review_reason,
            )

        fingerprint = SourceFingerprint.from_content(command.original_content)
        binary_duplicate = self._source_document_repository.find_by_fingerprint(
            fingerprint
        )
        if binary_duplicate is not None:
            return RegisterSourceDocumentResult(
                decision="BINARY_DUPLICATE",
                source_document=None,
                duplicate_document_id=binary_duplicate.document_id,
                review_reason=None,
            )

        work_duplicate = (
            None
            if metadata is None
            else self._source_document_repository.find_by_work_key(metadata.work_key)
        )
        duplicate_decision = "NEW_SOURCE" if work_duplicate is None else "DISTINCT_EDITION"

        document_id = DocumentId.from_fingerprint(fingerprint)
        storage_ref = OriginalStorageRef.from_value(
            self._original_source_store.put_original_if_absent(
                document_id=document_id,
                fingerprint=fingerprint,
                original_content=command.original_content,
            )
        )
        source_document = SourceDocument.register_original(
            document_id=document_id,
            fingerprint=fingerprint,
            original_storage_ref=storage_ref,
            metadata=metadata,
        )
        concurrent_duplicate = self._source_document_repository.save_if_absent(
            source_document
        )
        if concurrent_duplicate is not None:
            if concurrent_duplicate.fingerprint != fingerprint:
                raise ValueError("document_id concurrent incohérent")
            return RegisterSourceDocumentResult(
                decision="BINARY_DUPLICATE",
                source_document=None,
                duplicate_document_id=concurrent_duplicate.document_id,
                review_reason=None,
            )

        if duplicate_decision == "DISTINCT_EDITION":
            registration_decision = "DISTINCT_EDITION_REGISTERED"
        else:
            registration_decision = "REGISTERED"

        return RegisterSourceDocumentResult(
            decision=registration_decision,
            source_document=source_document,
            duplicate_document_id=None,
            review_reason=None,
        )


    def handle_path(
        self,
        *,
        original_path: Path,
        bibliographic_metadata: Mapping[str, Any] | None,
    ) -> RegisterSourceDocumentResult:
        if not isinstance(original_path, Path) or not original_path.is_file():
            raise ValueError("original_path invalide")
        metadata = (
            None
            if bibliographic_metadata is None
            else BibliographicMetadata.from_payload(bibliographic_metadata)
        )
        review_reason = _review_reason_for_unreadable_pdf_path(original_path)
        if review_reason is not None:
            return RegisterSourceDocumentResult("REVIEW_REQUIRED", None, None, review_reason)
        digest = hashlib.sha256()
        with original_path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        fingerprint = SourceFingerprint.from_value(digest.hexdigest())
        binary_duplicate = self._source_document_repository.find_by_fingerprint(fingerprint)
        if binary_duplicate is not None:
            return RegisterSourceDocumentResult(
                "BINARY_DUPLICATE", None, binary_duplicate.document_id, None
            )
        work_duplicate = (
            None
            if metadata is None
            else self._source_document_repository.find_by_work_key(metadata.work_key)
        )
        document_id = DocumentId.from_fingerprint(fingerprint)
        storage_ref = OriginalStorageRef.from_value(
            self._original_source_store.put_original_path_if_absent(
                document_id=document_id,
                fingerprint=fingerprint,
                source_path=original_path,
            )
        )
        source_document = SourceDocument.register_original(
            document_id=document_id,
            fingerprint=fingerprint,
            original_storage_ref=storage_ref,
            metadata=metadata,
        )
        concurrent_duplicate = self._source_document_repository.save_if_absent(source_document)
        if concurrent_duplicate is not None:
            if concurrent_duplicate.fingerprint != fingerprint:
                raise ValueError("document_id concurrent incohérent")
            return RegisterSourceDocumentResult(
                "BINARY_DUPLICATE", None, concurrent_duplicate.document_id, None
            )
        decision = "DISTINCT_EDITION_REGISTERED" if work_duplicate is not None else "REGISTERED"
        return RegisterSourceDocumentResult(decision, source_document, None, None)


def _review_reason_for_unreadable_pdf(original_content: bytes) -> str | None:
    if not isinstance(original_content, bytes):
        raise ValueError("original_content non binaire")
    if not original_content.startswith(b"%PDF-"):
        return "PDF_CORRUPTED"
    if b"%%EOF" not in original_content[-2048:]:
        return "PDF_CORRUPTED"
    if b"/Encrypt" in original_content:
        return "PDF_ENCRYPTED"
    return None


def _review_reason_for_unreadable_pdf_path(path: Path) -> str | None:
    content_length = path.stat().st_size
    if content_length < 1:
        return "PDF_CORRUPTED"
    encrypted = False
    with path.open("rb") as stream:
        prefix = stream.read(5)
        while chunk := stream.read(64 * 1024):
            if b"/Encrypt" in chunk:
                encrypted = True
        stream.seek(max(0, content_length - 2048))
        suffix = stream.read(2048)
    if prefix != b"%PDF-" or b"%%EOF" not in suffix:
        return "PDF_CORRUPTED"
    if encrypted:
        return "PDF_ENCRYPTED"
    return None


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


__all__ = [
    "OriginalSourceStore",
    "RegisterSourceDocumentCommand",
    "RegisterSourceDocumentHandler",
    "RegisterSourceDocumentResult",
    "SourceDocumentRepository",
]
