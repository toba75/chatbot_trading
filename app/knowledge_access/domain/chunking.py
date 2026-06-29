"""Chunking hiérarchique KA depuis le contrat canonique publié."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.contracts.identity import ContractSchemaVersion, DomainIdentifier
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)


_CHUNKING_SCHEMA_VERSIONS = frozenset({"1.0"})
_CANONICAL_CHUNK_DOCUMENT_FIELDS = frozenset(
    {
        "schema_version",
        "canonical_ref",
        "version_status",
        "items",
    }
)
_CANONICAL_CHUNK_ITEM_FIELDS = frozenset({"text", "source_locator"})
_FORBIDDEN_CHUNK_KEYS = frozenset({"claim", "claims", "verified_claim_id"})
_CHUNK_LEVELS = frozenset({"PARENT", "CHILD"})
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class ChunkingProfile:
    """Profil versionné et borné de chunking hiérarchique."""

    profile_id: str
    profile_version: str
    max_parent_items: int
    max_child_items: int
    max_child_characters: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "profile_id invalide"))
        object.__setattr__(
            self,
            "profile_version",
            _ensure_text(self.profile_version, "profile_version invalide"),
        )
        object.__setattr__(
            self,
            "max_parent_items",
            _ensure_positive_integer(self.max_parent_items, "max_parent_items invalide"),
        )
        object.__setattr__(
            self,
            "max_child_items",
            _ensure_positive_integer(self.max_child_items, "max_child_items invalide"),
        )
        object.__setattr__(
            self,
            "max_child_characters",
            _ensure_positive_integer(
                self.max_child_characters,
                "max_child_characters invalide",
            ),
        )
        if self.max_child_items > self.max_parent_items:
            raise ValueError("limites de profil incoherentes")

    def to_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "max_parent_items": self.max_parent_items,
            "max_child_items": self.max_child_items,
            "max_child_characters": self.max_child_characters,
        }


@dataclass(frozen=True)
class CanonicalChunkItem:
    """Item canonique minimal publié pour le chunking KA."""

    text: str
    source_locator: SourceLocator

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        validation_policy: SourceLocatorValidationPolicy,
    ) -> "CanonicalChunkItem":
        if not isinstance(validation_policy, SourceLocatorValidationPolicy):
            raise ValueError("validation_policy invalide")
        parsed_payload = _ensure_mapping(payload, "item canonique invalide")
        _reject_forbidden_keys(parsed_payload)
        actual_fields = frozenset(parsed_payload.keys())
        missing_fields = _CANONICAL_CHUNK_ITEM_FIELDS - actual_fields
        if len(missing_fields) > 0:
            raise ValueError(f"{sorted(missing_fields)[0]} absent")
        unexpected_fields = actual_fields - _CANONICAL_CHUNK_ITEM_FIELDS
        if len(unexpected_fields) > 0:
            raise ValueError(f"{sorted(unexpected_fields)[0]} interdit")
        return cls(
            text=parsed_payload["text"],
            source_locator=SourceLocator.from_payload(
                parsed_payload["source_locator"],
                validation_policy=validation_policy,
            ),
        )

    def __post_init__(self) -> None:
        text = _ensure_text(self.text, "texte canonique invalide")
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        if _content_hash_for_text(text) != self.source_locator.content_hash:
            raise ValueError("content_hash incoherent avec le texte")
        object.__setattr__(self, "text", text)

    @property
    def item_id(self) -> str:
        return self.source_locator.item_id

    @property
    def page_pdf(self) -> int:
        return self.source_locator.page_pdf

    def to_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_locator": self.source_locator.to_payload(),
        }


@dataclass(frozen=True)
class CanonicalChunkDocument:
    """Vue KA du contenu canonique publié et résolvable."""

    canonical_ref: CanonicalSourceRef
    version_status: str
    items: tuple[CanonicalChunkItem, ...]
    schema_version: str = "1.0"

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        validation_policy: SourceLocatorValidationPolicy,
    ) -> "CanonicalChunkDocument":
        if not isinstance(validation_policy, SourceLocatorValidationPolicy):
            raise ValueError("validation_policy invalide")
        parsed_payload = _ensure_mapping(payload, "document canonique invalide")
        _reject_forbidden_keys(parsed_payload)
        if "raw_text" in parsed_payload:
            raise ValueError("raw_text interdit")
        actual_fields = frozenset(parsed_payload.keys())
        missing_fields = _CANONICAL_CHUNK_DOCUMENT_FIELDS - actual_fields
        if len(missing_fields) > 0:
            raise ValueError(f"{sorted(missing_fields)[0]} absent")
        unexpected_fields = actual_fields - _CANONICAL_CHUNK_DOCUMENT_FIELDS
        if len(unexpected_fields) > 0:
            raise ValueError(f"{sorted(unexpected_fields)[0]} interdit")
        schema_version = str(
            ContractSchemaVersion.require_in_payload(
                parsed_payload,
                supported_schema_versions=_CHUNKING_SCHEMA_VERSIONS,
            )
        )
        canonical_ref = CanonicalSourceRef.from_payload(parsed_payload["canonical_ref"])
        version_status = _ensure_text(parsed_payload["version_status"], "version_status invalide")
        if version_status != ACCEPTED_CANONICAL_VERSION_STATUS:
            raise ValueError("version canonique non publiee")
        items = _canonical_items_from_payload(
            parsed_payload["items"],
            validation_policy=validation_policy,
        )
        return cls(
            schema_version=schema_version,
            canonical_ref=canonical_ref,
            version_status=version_status,
            items=items,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_ref, CanonicalSourceRef):
            raise ValueError("CanonicalSourceRef invalide")
        object.__setattr__(
            self,
            "version_status",
            _ensure_text(self.version_status, "version_status invalide"),
        )
        if self.version_status != ACCEPTED_CANONICAL_VERSION_STATUS:
            raise ValueError("version canonique non publiee")
        object.__setattr__(
            self,
            "schema_version",
            str(
                ContractSchemaVersion.parse(
                    self.schema_version,
                    supported_schema_versions=_CHUNKING_SCHEMA_VERSIONS,
                )
            ),
        )
        items = _ensure_canonical_items(self.items)
        _ensure_document_item_consistency(self.canonical_ref, items)
        object.__setattr__(self, "items", items)

    @property
    def canonical_version_id(self) -> str:
        return self.canonical_ref.canonical_version_id

    @property
    def document_id(self) -> str:
        return self.canonical_ref.document_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "canonical_ref": self.canonical_ref.to_payload(),
            "version_status": self.version_status,
            "items": tuple(item.to_payload() for item in self.items),
        }


@dataclass(frozen=True)
class KnowledgeChunk:
    """Chunk documentaire KA traçable, non autonome et sans claim."""

    chunk_id: str
    chunk_level: str
    parent_chunk_id: str | None
    canonical_version_id: str
    document_id: str
    profile_id: str
    profile_version: str
    text: str
    pages: tuple[int, ...]
    item_ids: tuple[str, ...]
    source_locators: tuple[SourceLocator, ...]
    content_hash: str

    @classmethod
    def parent(
        cls,
        *,
        chunk_id: str,
        canonical_version_id: str,
        document_id: str,
        profile_id: str,
        profile_version: str,
        text: str,
        source_locators: Sequence[SourceLocator],
    ) -> "KnowledgeChunk":
        locators = _ensure_source_locators(source_locators)
        parsed_text = _ensure_text(text, "texte de chunk invalide")
        return cls(
            chunk_id=chunk_id,
            chunk_level="PARENT",
            parent_chunk_id=None,
            canonical_version_id=canonical_version_id,
            document_id=document_id,
            profile_id=profile_id,
            profile_version=profile_version,
            text=parsed_text,
            pages=_pages_from_locators(locators),
            item_ids=tuple(locator.item_id for locator in locators),
            source_locators=locators,
            content_hash=_content_hash_for_text(parsed_text),
        )

    @classmethod
    def child(
        cls,
        *,
        chunk_id: str,
        parent_chunk_id: str | None,
        canonical_version_id: str,
        document_id: str,
        profile_id: str,
        profile_version: str,
        text: str,
        source_locators: Sequence[SourceLocator],
    ) -> "KnowledgeChunk":
        if parent_chunk_id is None:
            raise ValueError("parent_chunk_id obligatoire")
        locators = _ensure_source_locators(source_locators)
        parsed_text = _ensure_text(text, "texte de chunk invalide")
        return cls(
            chunk_id=chunk_id,
            chunk_level="CHILD",
            parent_chunk_id=parent_chunk_id,
            canonical_version_id=canonical_version_id,
            document_id=document_id,
            profile_id=profile_id,
            profile_version=profile_version,
            text=parsed_text,
            pages=_pages_from_locators(locators),
            item_ids=tuple(locator.item_id for locator in locators),
            source_locators=locators,
            content_hash=_content_hash_for_text(parsed_text),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        chunk_level = _ensure_text(self.chunk_level, "chunk_level invalide")
        if chunk_level not in _CHUNK_LEVELS:
            raise ValueError("chunk_level inconnu")
        object.__setattr__(self, "chunk_level", chunk_level)
        if chunk_level == "PARENT":
            if self.parent_chunk_id is not None:
                raise ValueError("parent_chunk_id interdit pour parent")
        else:
            object.__setattr__(
                self,
                "parent_chunk_id",
                _ensure_chunk_id(self.parent_chunk_id, field_name="parent_chunk_id"),
            )
            if self.parent_chunk_id == self.chunk_id:
                raise ValueError("parent_chunk_id incoherent")
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "profile_id invalide"))
        object.__setattr__(
            self,
            "profile_version",
            _ensure_text(self.profile_version, "profile_version invalide"),
        )
        text = _ensure_text(self.text, "texte de chunk invalide")
        object.__setattr__(self, "text", text)
        locators = _ensure_source_locators(self.source_locators)
        _ensure_chunk_locators_match_context(
            locators,
            canonical_version_id=self.canonical_version_id,
            document_id=self.document_id,
        )
        expected_pages = _pages_from_locators(locators)
        expected_item_ids = tuple(locator.item_id for locator in locators)
        if tuple(self.pages) != expected_pages:
            raise ValueError("pages incoherentes avec SourceLocator")
        if tuple(self.item_ids) != expected_item_ids:
            raise ValueError("item_ids incoherents avec SourceLocator")
        object.__setattr__(self, "pages", expected_pages)
        object.__setattr__(self, "item_ids", expected_item_ids)
        object.__setattr__(self, "source_locators", locators)
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))
        if self.content_hash != _content_hash_for_text(text):
            raise ValueError("content_hash incoherent")

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_level": self.chunk_level,
            "parent_chunk_id": self.parent_chunk_id,
            "canonical_version_id": self.canonical_version_id,
            "document_id": self.document_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "text": self.text,
            "pages": self.pages,
            "item_ids": self.item_ids,
            "source_locators": tuple(locator.to_payload() for locator in self.source_locators),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class HierarchicalChunkProjection:
    """Projection de chunks traçables pour une version canonique."""

    canonical_version_id: str
    document_id: str
    profile_id: str
    profile_version: str
    chunks: tuple[KnowledgeChunk, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(self, "profile_id", _ensure_text(self.profile_id, "profile_id invalide"))
        object.__setattr__(
            self,
            "profile_version",
            _ensure_text(self.profile_version, "profile_version invalide"),
        )
        chunks = _ensure_chunks(self.chunks)
        _ensure_projection_chunk_consistency(
            chunks,
            canonical_version_id=self.canonical_version_id,
            document_id=self.document_id,
            profile_id=self.profile_id,
            profile_version=self.profile_version,
        )
        object.__setattr__(self, "chunks", chunks)

    def chunks_by_id(self) -> Mapping[str, KnowledgeChunk]:
        return MappingProxyType({chunk.chunk_id: chunk for chunk in self.chunks})

    def to_payload(self) -> dict[str, Any]:
        return {
            "canonical_version_id": self.canonical_version_id,
            "document_id": self.document_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "chunks": tuple(chunk.to_payload() for chunk in self.chunks),
        }


class HierarchicalChunkProjector:
    """Construit des chunks parents/enfants depuis les items canoniques publiés."""

    def project(
        self,
        *,
        canonical_document: CanonicalChunkDocument,
        chunking_profile: ChunkingProfile,
    ) -> HierarchicalChunkProjection:
        parsed_document = _ensure_canonical_document(canonical_document)
        parsed_profile = _ensure_chunking_profile(chunking_profile)
        chunks: list[KnowledgeChunk] = []
        for parent_index, parent_items in enumerate(
            _groups(parsed_document.items, parsed_profile.max_parent_items),
            start=1,
        ):
            parent_chunk = KnowledgeChunk.parent(
                chunk_id=_chunk_id_for(
                    canonical_document=parsed_document,
                    chunking_profile=parsed_profile,
                    chunk_level="PARENT",
                    group_index=parent_index,
                    item_ids=tuple(item.item_id for item in parent_items),
                ),
                canonical_version_id=parsed_document.canonical_version_id,
                document_id=parsed_document.document_id,
                profile_id=parsed_profile.profile_id,
                profile_version=parsed_profile.profile_version,
                text=_chunk_text_for_items(parent_items),
                source_locators=tuple(item.source_locator for item in parent_items),
            )
            chunks.append(parent_chunk)
            for child_index, child_items in enumerate(
                _child_groups(parent_items, parsed_profile),
                start=1,
            ):
                chunks.append(
                    KnowledgeChunk.child(
                        chunk_id=_chunk_id_for(
                            canonical_document=parsed_document,
                            chunking_profile=parsed_profile,
                            chunk_level="CHILD",
                            group_index=(parent_index * 1000) + child_index,
                            item_ids=tuple(item.item_id for item in child_items),
                        ),
                        parent_chunk_id=parent_chunk.chunk_id,
                        canonical_version_id=parsed_document.canonical_version_id,
                        document_id=parsed_document.document_id,
                        profile_id=parsed_profile.profile_id,
                        profile_version=parsed_profile.profile_version,
                        text=_chunk_text_for_items(child_items),
                        source_locators=tuple(item.source_locator for item in child_items),
                    )
                )
        return HierarchicalChunkProjection(
            canonical_version_id=parsed_document.canonical_version_id,
            document_id=parsed_document.document_id,
            profile_id=parsed_profile.profile_id,
            profile_version=parsed_profile.profile_version,
            chunks=tuple(chunks),
        )


def _canonical_items_from_payload(
    value: Any,
    *,
    validation_policy: SourceLocatorValidationPolicy,
) -> tuple[CanonicalChunkItem, ...]:
    if value is None:
        raise ValueError("items canoniques absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("items canoniques invalides")
    return tuple(
        CanonicalChunkItem.from_payload(item, validation_policy=validation_policy)
        for item in value
    )


def _ensure_canonical_items(value: Sequence[CanonicalChunkItem]) -> tuple[CanonicalChunkItem, ...]:
    if value is None:
        raise ValueError("items canoniques absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("items canoniques invalides")
    items = tuple(value)
    if len(items) == 0:
        raise ValueError("items canoniques absents")
    for item in items:
        if not isinstance(item, CanonicalChunkItem):
            raise ValueError("item canonique invalide")
    item_ids = tuple(item.item_id for item in items)
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("item_id canonique duplique")
    return items


def _ensure_document_item_consistency(
    canonical_ref: CanonicalSourceRef,
    items: tuple[CanonicalChunkItem, ...],
) -> None:
    for item in items:
        locator = item.source_locator
        if locator.canonical_version_id != canonical_ref.canonical_version_id:
            raise ValueError("item hors version canonique")
        if locator.document_id != canonical_ref.document_id:
            raise ValueError("item hors document canonique")
        if locator.page_pdf > canonical_ref.page_count:
            raise ValueError("page_pdf hors version canonique")


def _ensure_source_locators(value: Sequence[SourceLocator]) -> tuple[SourceLocator, ...]:
    if value is None:
        raise ValueError("source_locators absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("source_locators invalides")
    locators = tuple(value)
    if len(locators) == 0:
        raise ValueError("source_locators absents")
    for locator in locators:
        if not isinstance(locator, SourceLocator):
            raise ValueError("source_locator invalide")
    item_ids = tuple(locator.item_id for locator in locators)
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("source_locator duplique")
    return locators


def _ensure_chunk_locators_match_context(
    locators: tuple[SourceLocator, ...],
    *,
    canonical_version_id: str,
    document_id: str,
) -> None:
    for locator in locators:
        if locator.canonical_version_id != canonical_version_id:
            raise ValueError("SourceLocator hors version canonique")
        if locator.document_id != document_id:
            raise ValueError("SourceLocator hors document")


def _pages_from_locators(locators: tuple[SourceLocator, ...]) -> tuple[int, ...]:
    pages: list[int] = []
    for locator in locators:
        if locator.page_pdf not in pages:
            pages.append(locator.page_pdf)
    return tuple(pages)


def _ensure_chunks(value: Sequence[KnowledgeChunk]) -> tuple[KnowledgeChunk, ...]:
    if value is None:
        raise ValueError("chunks absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("chunks invalides")
    chunks = tuple(value)
    if len(chunks) == 0:
        raise ValueError("chunks absents")
    for chunk in chunks:
        if not isinstance(chunk, KnowledgeChunk):
            raise ValueError("chunk invalide")
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("chunk_id duplique")
    return chunks


def _ensure_projection_chunk_consistency(
    chunks: tuple[KnowledgeChunk, ...],
    *,
    canonical_version_id: str,
    document_id: str,
    profile_id: str,
    profile_version: str,
) -> None:
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    for chunk in chunks:
        if chunk.canonical_version_id != canonical_version_id:
            raise ValueError("chunk hors version canonique")
        if chunk.document_id != document_id:
            raise ValueError("chunk hors document")
        if chunk.profile_id != profile_id or chunk.profile_version != profile_version:
            raise ValueError("chunk hors profil")
        if chunk.chunk_level == "CHILD" and chunk.parent_chunk_id not in chunk_ids:
            raise ValueError("parent_chunk_id inconnu")


def _groups(
    items: tuple[CanonicalChunkItem, ...],
    group_size: int,
) -> tuple[tuple[CanonicalChunkItem, ...], ...]:
    parsed_group_size = _ensure_positive_integer(group_size, "group_size invalide")
    return tuple(
        tuple(items[index : index + parsed_group_size])
        for index in range(0, len(items), parsed_group_size)
    )


def _child_groups(
    items: tuple[CanonicalChunkItem, ...],
    chunking_profile: ChunkingProfile,
) -> tuple[tuple[CanonicalChunkItem, ...], ...]:
    parsed_profile = _ensure_chunking_profile(chunking_profile)
    groups: list[tuple[CanonicalChunkItem, ...]] = []
    current: list[CanonicalChunkItem] = []
    for item in items:
        if len(item.text) > parsed_profile.max_child_characters:
            raise ValueError("item canonique depasse max_child_characters")
        if len(current) == 0:
            current.append(item)
            continue
        candidate = tuple(current + [item])
        if (
            len(candidate) > parsed_profile.max_child_items
            or len(_chunk_text_for_items(candidate)) > parsed_profile.max_child_characters
        ):
            groups.append(tuple(current))
            current = [item]
        else:
            current.append(item)
    if len(current) > 0:
        groups.append(tuple(current))
    return tuple(groups)


def _chunk_text_for_items(items: Sequence[CanonicalChunkItem]) -> str:
    parsed_items = tuple(items)
    if len(parsed_items) == 0:
        raise ValueError("items de chunk absents")
    return "\n".join(item.text for item in parsed_items)


def _chunk_id_for(
    *,
    canonical_document: CanonicalChunkDocument,
    chunking_profile: ChunkingProfile,
    chunk_level: str,
    group_index: int,
    item_ids: tuple[str, ...],
) -> str:
    payload = {
        "canonical_version_id": canonical_document.canonical_version_id,
        "document_id": canonical_document.document_id,
        "profile_id": chunking_profile.profile_id,
        "profile_version": chunking_profile.profile_version,
        "chunk_level": chunk_level,
        "group_index": group_index,
        "item_ids": item_ids,
    }
    serialized_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"KCHK-{hashlib.sha256(serialized_payload.encode('utf-8')).hexdigest()[:32].upper()}"


def _reject_forbidden_keys(payload: Mapping[str, Any]) -> None:
    for key in _FORBIDDEN_CHUNK_KEYS:
        if key in payload:
            raise ValueError(f"{key} interdit")


def _ensure_canonical_document(value: CanonicalChunkDocument) -> CanonicalChunkDocument:
    if not isinstance(value, CanonicalChunkDocument):
        raise ValueError("document canonique invalide")
    return value


def _ensure_chunking_profile(value: ChunkingProfile) -> ChunkingProfile:
    if not isinstance(value, ChunkingProfile):
        raise ValueError("chunking_profile invalide")
    return value


def _ensure_mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(message)
    return dict(value)


def _ensure_text(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    if value.strip() == "":
        raise ValueError(message)
    if value != value.strip():
        raise ValueError(message)
    return value


def _ensure_positive_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identifiant de domaine invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"identifiant {expected_prefix} invalide: {exc}") from exc


def _ensure_chunk_id(value: Any, field_name: str = "chunk_id") -> str:
    text = _ensure_text(value, f"{field_name} invalide")
    if not text.startswith("KCHK-"):
        raise ValueError(f"{field_name} invalide")
    return text


def _content_hash_for_text(value: str) -> str:
    text = _ensure_text(value, "texte canonique invalide")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, f"{field_name} invalide")
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text_value


def _ensure_bbox(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("bbox invalide")
    coordinates = tuple(value)
    if len(coordinates) != 4:
        raise ValueError("bbox invalide")
    normalized_coordinates: list[float] = []
    for coordinate in coordinates:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise ValueError("bbox invalide")
        normalized_coordinate = float(coordinate)
        if not math.isfinite(normalized_coordinate):
            raise ValueError("bbox invalide")
        if normalized_coordinate < 0 or normalized_coordinate > 1:
            raise ValueError("bbox invalide")
        normalized_coordinates.append(normalized_coordinate)
    left, top, right, bottom = tuple(normalized_coordinates)
    if left >= right or top >= bottom:
        raise ValueError("bbox invalide")
    return (left, top, right, bottom)


__all__ = [
    "CanonicalChunkDocument",
    "CanonicalChunkItem",
    "ChunkingProfile",
    "HierarchicalChunkProjection",
    "HierarchicalChunkProjector",
    "KnowledgeChunk",
]
