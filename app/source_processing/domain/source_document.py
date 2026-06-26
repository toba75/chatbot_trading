"""Enregistrement immuable des sources documentaires SP."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contracts.identity import DomainIdentifier


_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_ORIGINAL_STORAGE_REF_PATTERN = re.compile(
    r"^artifact:source_processing\.original_sources/DOC-[A-Z0-9-]+/[0-9a-f]{64}\.pdf$"
)
_ORIGINAL_STORAGE_PREFIX = "artifact:source_processing.original_sources/"


class SourceDocumentStatus(str, Enum):
    """État métier explicite d'un SourceDocument M-003."""

    REGISTERED = "REGISTERED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class SourceFingerprint:
    """Empreinte stable calculée sur le PDF original."""

    value: str

    @classmethod
    def from_content(cls, original_content: bytes) -> "SourceFingerprint":
        if not isinstance(original_content, bytes):
            raise ValueError("contenu original non binaire")
        if len(original_content) == 0:
            raise ValueError("contenu original vide")
        return cls(value=hashlib.sha256(original_content).hexdigest())

    @classmethod
    def from_value(cls, value: str) -> "SourceFingerprint":
        return cls(value=_ensure_hash_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_hash_value(self.value))


@dataclass(frozen=True)
class DocumentId:
    """Identifiant métier stable d'une source documentaire."""

    value: str

    @classmethod
    def from_fingerprint(cls, fingerprint: SourceFingerprint) -> "DocumentId":
        parsed_fingerprint = _ensure_fingerprint(fingerprint)
        return cls.from_value(f"DOC-{parsed_fingerprint.value[:16].upper()}")

    @classmethod
    def from_value(cls, value: str) -> "DocumentId":
        return cls(value=_ensure_document_id_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_document_id_value(self.value))


@dataclass(frozen=True)
class OriginalStorageRef:
    """Référence de stockage de l'artefact original immuable."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "OriginalStorageRef":
        return cls(value=_ensure_original_storage_ref_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _ensure_original_storage_ref_value(self.value),
        )


@dataclass(frozen=True)
class BibliographicMetadata:
    """Métadonnées bibliographiques minimales requises avant enregistrement."""

    title: str
    authors: tuple[str, ...]
    publication_year: int
    edition: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "BibliographicMetadata":
        if not isinstance(payload, Mapping):
            raise ValueError("métadonnées bibliographiques non objet")
        return cls(
            title=_required_text(payload, "title"),
            authors=_required_authors(payload),
            publication_year=_required_publication_year(payload),
            edition=_required_text(payload, "edition"),
        )

    @property
    def work_key(self) -> tuple[str, tuple[str, ...]]:
        normalized_authors = tuple(author.casefold() for author in self.authors)
        return (self.title.casefold(), normalized_authors)

    def __post_init__(self) -> None:
        _ensure_text(self.title, "title")
        _ensure_authors_value(self.authors)
        _ensure_publication_year_value(self.publication_year)
        _ensure_text(self.edition, "edition")


@dataclass(frozen=True)
class SourceDocumentRegistered:
    """Événement produit par l'enregistrement d'une source originale."""

    document_id: DocumentId
    fingerprint: SourceFingerprint
    original_storage_ref: OriginalStorageRef

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        _ensure_fingerprint(self.fingerprint)
        _ensure_storage_ref(self.original_storage_ref)


@dataclass(frozen=True)
class SourceDocumentQuarantined:
    """Événement produit quand une source documentaire devient non publiable."""

    document_id: DocumentId
    reason: str

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        object.__setattr__(self, "reason", _ensure_text(self.reason, "reason"))


@dataclass(frozen=True)
class SourceDocument:
    """Agrégat SP qui porte l'original immuable et son état d'enregistrement."""

    document_id: DocumentId
    fingerprint: SourceFingerprint
    original_storage_ref: OriginalStorageRef
    metadata: BibliographicMetadata
    status: SourceDocumentStatus
    events: tuple[SourceDocumentRegistered | SourceDocumentQuarantined, ...]

    @classmethod
    def register_original(
        cls,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        original_storage_ref: OriginalStorageRef,
        metadata: BibliographicMetadata,
    ) -> "SourceDocument":
        parsed_document_id = _ensure_document_id(document_id)
        parsed_fingerprint = _ensure_fingerprint(fingerprint)
        parsed_storage_ref = _ensure_storage_ref(original_storage_ref)
        _ensure_storage_ref_matches(
            storage_ref=parsed_storage_ref,
            document_id=parsed_document_id,
            fingerprint=parsed_fingerprint,
        )
        parsed_metadata = _ensure_metadata(metadata)
        registered_event = SourceDocumentRegistered(
            document_id=parsed_document_id,
            fingerprint=parsed_fingerprint,
            original_storage_ref=parsed_storage_ref,
        )
        return cls(
            document_id=parsed_document_id,
            fingerprint=parsed_fingerprint,
            original_storage_ref=parsed_storage_ref,
            metadata=parsed_metadata,
            status=SourceDocumentStatus.REGISTERED,
            events=(registered_event,),
        )

    def quarantine(self, reason: str) -> "SourceDocument":
        if self.status is not SourceDocumentStatus.REGISTERED:
            raise ValueError("transition de source interdite")
        quarantined_event = SourceDocumentQuarantined(
            document_id=self.document_id,
            reason=reason,
        )
        return SourceDocument(
            document_id=self.document_id,
            fingerprint=self.fingerprint,
            original_storage_ref=self.original_storage_ref,
            metadata=self.metadata,
            status=SourceDocumentStatus.QUARANTINED,
            events=self.events + (quarantined_event,),
        )

    def ensure_documentary_publication_allowed(self) -> None:
        if self.status is SourceDocumentStatus.REGISTERED:
            return
        raise ValueError(f"source documentaire non publiable: {self.status.value}")

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        _ensure_fingerprint(self.fingerprint)
        _ensure_storage_ref(self.original_storage_ref)
        _ensure_metadata(self.metadata)
        if not isinstance(self.status, SourceDocumentStatus):
            raise ValueError("source_document_status invalide")
        if not isinstance(self.events, tuple):
            raise ValueError("events SourceDocument non tuple")
        if len(self.events) == 0:
            raise ValueError("events SourceDocument vide")
        for event in self.events:
            if not isinstance(event, (SourceDocumentRegistered, SourceDocumentQuarantined)):
                raise ValueError("event SourceDocument invalide")
        if not isinstance(self.events[0], SourceDocumentRegistered):
            raise ValueError("premier event SourceDocument invalide")
        if self.status is SourceDocumentStatus.REGISTERED:
            if any(isinstance(event, SourceDocumentQuarantined) for event in self.events):
                raise ValueError("event de quarantaine interdit sur source enregistrée")
        if self.status is SourceDocumentStatus.QUARANTINED:
            if not isinstance(self.events[-1], SourceDocumentQuarantined):
                raise ValueError("event de quarantaine absent")


@dataclass(frozen=True)
class DuplicateEditionDecision:
    """Décision explicite de la politique doublon binaire/nouvelle édition."""

    decision: str
    matching_document_id: DocumentId | None

    def __post_init__(self) -> None:
        if self.decision not in {"BINARY_DUPLICATE", "DISTINCT_EDITION", "NEW_SOURCE"}:
            raise ValueError(f"décision de doublon inconnue: {self.decision}")
        if self.decision == "NEW_SOURCE":
            if self.matching_document_id is not None:
                raise ValueError("matching_document_id interdit pour NEW_SOURCE")
        else:
            _ensure_document_id(self.matching_document_id)


class DuplicateEditionPolicy:
    """Politique de distinction entre copie binaire et édition distincte."""

    def classify(
        self,
        candidate_fingerprint: SourceFingerprint,
        candidate_metadata: BibliographicMetadata,
        existing_documents: Iterable[SourceDocument],
    ) -> DuplicateEditionDecision:
        parsed_fingerprint = _ensure_fingerprint(candidate_fingerprint)
        parsed_metadata = _ensure_metadata(candidate_metadata)
        documents = _ensure_source_documents(existing_documents)

        for document in documents:
            if document.fingerprint == parsed_fingerprint:
                return DuplicateEditionDecision(
                    decision="BINARY_DUPLICATE",
                    matching_document_id=document.document_id,
                )

        for document in documents:
            if document.metadata.work_key == parsed_metadata.work_key:
                return DuplicateEditionDecision(
                    decision="DISTINCT_EDITION",
                    matching_document_id=document.document_id,
                )

        return DuplicateEditionDecision(decision="NEW_SOURCE", matching_document_id=None)


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text(payload[field_name], field_name)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_hash_value(value: Any) -> str:
    text_value = _ensure_text(value, "source_sha256")
    if _HASH_PATTERN.fullmatch(text_value) is None:
        raise ValueError("source_sha256 invalide")
    return text_value.lower()


def _ensure_document_id_value(value: str) -> str:
    try:
        parsed = DomainIdentifier.parse_with_prefix(value, "DOC")
    except ValueError as exc:
        raise ValueError(f"document_id invalide: {exc}") from exc
    return str(parsed)


def _ensure_original_storage_ref_value(value: Any) -> str:
    text_value = _ensure_text(value, "original_storage_ref")
    if not text_value.startswith(_ORIGINAL_STORAGE_PREFIX):
        raise ValueError("original_storage_ref invalide")
    if _ORIGINAL_STORAGE_REF_PATTERN.fullmatch(text_value) is None:
        raise ValueError("original_storage_ref invalide")
    return text_value


def _required_authors(payload: Mapping[str, Any]) -> tuple[str, ...]:
    if "authors" not in payload:
        raise ValueError("authors absent")
    return _ensure_authors_value(payload["authors"])


def _ensure_authors_value(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("authors invalide")
    if len(value) == 0:
        raise ValueError("authors vide")
    return tuple(_ensure_text(author, "author") for author in value)


def _required_publication_year(payload: Mapping[str, Any]) -> int:
    if "publication_year" not in payload:
        raise ValueError("publication_year absent")
    return _ensure_publication_year_value(payload["publication_year"])


def _ensure_publication_year_value(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("publication_year invalide")
    return value


def _ensure_document_id(value: DocumentId | None) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_fingerprint(value: SourceFingerprint) -> SourceFingerprint:
    if not isinstance(value, SourceFingerprint):
        raise ValueError("source_fingerprint invalide")
    return value


def _ensure_storage_ref(value: OriginalStorageRef) -> OriginalStorageRef:
    if not isinstance(value, OriginalStorageRef):
        raise ValueError("original_storage_ref invalide")
    return value


def _ensure_storage_ref_matches(
    *,
    storage_ref: OriginalStorageRef,
    document_id: DocumentId,
    fingerprint: SourceFingerprint,
) -> None:
    expected_value = (
        f"{_ORIGINAL_STORAGE_PREFIX}"
        f"{document_id.value}/{fingerprint.value}.pdf"
    )
    if storage_ref.value != expected_value:
        raise ValueError("original_storage_ref incohérent")


def _ensure_metadata(value: BibliographicMetadata) -> BibliographicMetadata:
    if not isinstance(value, BibliographicMetadata):
        raise ValueError("métadonnées bibliographiques invalides")
    return value


def _ensure_source_documents(value: Iterable[SourceDocument]) -> tuple[SourceDocument, ...]:
    if value is None:
        raise ValueError("sources existantes absentes")
    documents = tuple(value)
    for document in documents:
        if not isinstance(document, SourceDocument):
            raise ValueError("SourceDocument existant invalide")
    return documents


__all__ = [
    "BibliographicMetadata",
    "DocumentId",
    "DuplicateEditionDecision",
    "DuplicateEditionPolicy",
    "OriginalStorageRef",
    "SourceDocument",
    "SourceDocumentQuarantined",
    "SourceDocumentRegistered",
    "SourceDocumentStatus",
    "SourceFingerprint",
]
