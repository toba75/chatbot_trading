"""Cas d'usage d'enregistrement immuable d'une source documentaire."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    DuplicateEditionPolicy,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class OriginalSourceStore(Protocol):
    """Port de stockage de l'original immuable."""

    def store_original(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        original_content: bytes,
    ) -> str:
        """Stocke l'original bit-à-bit et retourne sa référence immuable."""


class SourceDocumentRepository(Protocol):
    """Port de dépôt de SourceDocument."""

    def list_registered(self) -> list[SourceDocument]:
        """Retourne les sources documentaires déjà enregistrées."""

    def save(self, source_document: SourceDocument) -> None:
        """Persiste un SourceDocument nouvellement enregistré."""


@dataclass(frozen=True)
class RegisterSourceDocumentCommand:
    """Commande applicative d'enregistrement d'un PDF original."""

    original_content: bytes
    bibliographic_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.original_content, bytes):
            raise ValueError("original_content non binaire")
        if not isinstance(self.bibliographic_metadata, Mapping):
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
        if not hasattr(original_source_store, "store_original"):
            raise ValueError("original_source_store invalide")
        if not hasattr(source_document_repository, "list_registered"):
            raise ValueError("source_document_repository invalide")
        if not hasattr(source_document_repository, "save"):
            raise ValueError("source_document_repository invalide")
        self._original_source_store = original_source_store
        self._source_document_repository = source_document_repository
        self._duplicate_policy = DuplicateEditionPolicy()

    def handle(self, command: RegisterSourceDocumentCommand) -> RegisterSourceDocumentResult:
        if not isinstance(command, RegisterSourceDocumentCommand):
            raise ValueError("commande RegisterSourceDocument invalide")

        metadata = BibliographicMetadata.from_payload(command.bibliographic_metadata)
        review_reason = _review_reason_for_unreadable_pdf(command.original_content)
        if review_reason is not None:
            return RegisterSourceDocumentResult(
                decision="REVIEW_REQUIRED",
                source_document=None,
                duplicate_document_id=None,
                review_reason=review_reason,
            )

        fingerprint = SourceFingerprint.from_content(command.original_content)
        existing_documents = self._source_document_repository.list_registered()
        duplicate_decision = self._duplicate_policy.classify(
            candidate_fingerprint=fingerprint,
            candidate_metadata=metadata,
            existing_documents=existing_documents,
        )

        if duplicate_decision.decision == "BINARY_DUPLICATE":
            return RegisterSourceDocumentResult(
                decision="BINARY_DUPLICATE",
                source_document=None,
                duplicate_document_id=duplicate_decision.matching_document_id,
                review_reason=None,
            )

        document_id = DocumentId.from_fingerprint(fingerprint)
        storage_ref = OriginalStorageRef.from_value(
            self._original_source_store.store_original(
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
        self._source_document_repository.save(source_document)

        if duplicate_decision.decision == "DISTINCT_EDITION":
            registration_decision = "DISTINCT_EDITION_REGISTERED"
        else:
            registration_decision = "REGISTERED"

        return RegisterSourceDocumentResult(
            decision=registration_decision,
            source_document=source_document,
            duplicate_document_id=None,
            review_reason=None,
        )


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


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "OriginalSourceStore",
    "RegisterSourceDocumentCommand",
    "RegisterSourceDocumentHandler",
    "RegisterSourceDocumentResult",
    "SourceDocumentRepository",
]
