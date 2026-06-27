"""Résolution des SourceLocator depuis les versions canoniques publiées."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.contracts.source_references import (
    ALLOWED_CANONICAL_VERSION_STATUSES,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.source_processing.domain.canonical_source import (
    CanonicalSource,
    CanonicalSourceVersion,
)
from app.source_processing.domain.page_conversion import (
    CanonicalDocumentItem,
    CanonicalDocumentPage,
    PagewiseDoclingDocument,
)


@dataclass(frozen=True)
class SourceLocatorResolution:
    """Résolution publique minimale d'un item canonique cité."""

    canonical_version_id: str
    document_id: str
    page_pdf: int
    item_id: str
    bbox: tuple[float, float, float, float]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_text(self.canonical_version_id, "canonical_version_id invalide"),
        )
        object.__setattr__(self, "document_id", _ensure_text(self.document_id, "document_id invalide"))
        object.__setattr__(self, "page_pdf", _ensure_positive_integer(self.page_pdf, "page_pdf invalide"))
        object.__setattr__(self, "item_id", _ensure_text(self.item_id, "item_id invalide"))
        object.__setattr__(self, "bbox", _ensure_bbox(self.bbox))
        object.__setattr__(self, "content_hash", _ensure_text(self.content_hash, "content_hash invalide"))

    def to_public_payload(self) -> dict[str, Any]:
        return {
            "page_pdf": self.page_pdf,
            "item_id": self.item_id,
            "bbox": list(self.bbox),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class CanonicalVersionResolutionIndex:
    """Index de résolvabilité d'une version canonique."""

    canonical_ref: CanonicalSourceRef
    status: str
    items_by_item_id: Mapping[str, SourceLocatorResolution]

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_ref, CanonicalSourceRef):
            raise ValueError("CanonicalSourceRef de résolution invalide")
        object.__setattr__(self, "status", _ensure_version_status(self.status))
        item_mapping = _ensure_resolution_items(
            self.items_by_item_id,
            canonical_version_id=self.canonical_ref.canonical_version_id,
            document_id=self.canonical_ref.document_id,
        )
        object.__setattr__(self, "items_by_item_id", MappingProxyType(item_mapping))

    @property
    def canonical_version_id(self) -> str:
        return self.canonical_ref.canonical_version_id

    def item_hashes(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                item_id: item.content_hash
                for item_id, item in self.items_by_item_id.items()
            }
        )

    def resolve(self, locator: SourceLocator) -> SourceLocatorResolution:
        if not isinstance(locator, SourceLocator):
            raise ValueError("SourceLocator invalide")
        item = self.items_by_item_id.get(locator.item_id)
        if item is None:
            raise ValueError("item_id non resolvable")
        if item.page_pdf != locator.page_pdf:
            raise ValueError("page_pdf incoherent avec item_id")
        if item.bbox != locator.bbox:
            raise ValueError("bbox incoherente avec item_id")
        if item.content_hash != locator.content_hash:
            raise ValueError("content_hash incoherent")
        return item

    def to_public_payload(self) -> dict[str, Any]:
        return {
            "canonical_version_id": self.canonical_ref.canonical_version_id,
            "document_id": self.canonical_ref.document_id,
            "status": self.status,
            "page_count": self.canonical_ref.page_count,
            "items": tuple(
                item.to_public_payload()
                for item in self.items_by_item_id.values()
            ),
        }


@dataclass(frozen=True)
class SourceLocatorResolutionRegistry:
    """Registre SP publiant la résolvabilité sans exposer le stockage interne."""

    indexes_by_version_id: Mapping[str, CanonicalVersionResolutionIndex]

    @classmethod
    def from_canonical_source(
        cls,
        *,
        canonical_source: CanonicalSource,
        docling_documents_by_version_id: Mapping[str, PagewiseDoclingDocument],
        version_statuses_by_version_id: Mapping[str, str],
    ) -> "SourceLocatorResolutionRegistry":
        parsed_canonical_source = _ensure_canonical_source(canonical_source)
        _ensure_mapping(docling_documents_by_version_id, "docling_documents_by_version_id")
        _ensure_mapping(version_statuses_by_version_id, "version_statuses_by_version_id")

        version_ids = tuple(
            version.canonical_version_id
            for version in parsed_canonical_source.versions
        )
        version_id_set = set(version_ids)

        for version_id in docling_documents_by_version_id:
            if version_id not in version_id_set:
                raise ValueError("DoclingDocument de version inconnu")
        for version_id in version_statuses_by_version_id:
            if version_id not in version_id_set:
                raise ValueError("Statut de version canonique inconnu")

        indexes_by_version_id: dict[str, CanonicalVersionResolutionIndex] = {}
        for version in parsed_canonical_source.versions:
            if version.canonical_version_id not in docling_documents_by_version_id:
                raise ValueError("DoclingDocument de version absent")
            if version.canonical_version_id not in version_statuses_by_version_id:
                raise ValueError("Statut de version canonique absent")

            indexes_by_version_id[version.canonical_version_id] = _build_version_index(
                version=version,
                docling_document=docling_documents_by_version_id[version.canonical_version_id],
                status=version_statuses_by_version_id[version.canonical_version_id],
            )

        return cls(indexes_by_version_id=indexes_by_version_id)

    def __post_init__(self) -> None:
        _ensure_mapping(self.indexes_by_version_id, "indexes_by_version_id")
        indexes: dict[str, CanonicalVersionResolutionIndex] = {}
        for version_id, index in self.indexes_by_version_id.items():
            parsed_version_id = _ensure_text(version_id, "canonical_version_id invalide")
            if not isinstance(index, CanonicalVersionResolutionIndex):
                raise ValueError("index de résolution invalide")
            if parsed_version_id != index.canonical_version_id:
                raise ValueError("cle de version incoherente avec index de résolution")
            indexes[parsed_version_id] = index
        if len(indexes) == 0:
            raise ValueError("registre de résolvabilité vide")
        object.__setattr__(self, "indexes_by_version_id", MappingProxyType(indexes))
        object.__setattr__(
            self,
            "_validation_policy",
            _validation_policy_for_indexes(indexes),
        )

    def to_validation_policy(self) -> SourceLocatorValidationPolicy:
        return self._validation_policy

    def resolve(self, locator: SourceLocator) -> SourceLocatorResolution:
        if not isinstance(locator, SourceLocator):
            raise ValueError("SourceLocator invalide")
        self.to_validation_policy().validate_locator(locator)
        index = self.indexes_by_version_id.get(locator.canonical_version_id)
        if index is None:
            raise ValueError("Version canonique absente")
        return index.resolve(locator)

    def to_public_payload(self) -> dict[str, Any]:
        return {
            "versions": tuple(
                index.to_public_payload()
                for index in self.indexes_by_version_id.values()
            )
        }


def _validation_policy_for_indexes(
    indexes_by_version_id: Mapping[str, CanonicalVersionResolutionIndex],
) -> SourceLocatorValidationPolicy:
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={
            version_id: index.canonical_ref
            for version_id, index in indexes_by_version_id.items()
        },
        version_statuses_by_version_id={
            version_id: index.status
            for version_id, index in indexes_by_version_id.items()
        },
        resolvable_item_ids_by_version_id={
            version_id: index.item_hashes()
            for version_id, index in indexes_by_version_id.items()
        },
    )


def _build_version_index(
    *,
    version: CanonicalSourceVersion,
    docling_document: PagewiseDoclingDocument,
    status: str,
) -> CanonicalVersionResolutionIndex:
    if not isinstance(version, CanonicalSourceVersion):
        raise ValueError("version canonique invalide")
    if not isinstance(docling_document, PagewiseDoclingDocument):
        raise ValueError("DoclingDocument de version invalide")
    if docling_document.canonical_version_id != version.canonical_version_id:
        raise ValueError("DoclingDocument hors version canonique")
    if docling_document.document_id != version.document_id:
        raise ValueError("document_id de résolution incoherent")
    if docling_document.source_sha256 != version.source_sha256:
        raise ValueError("source_sha256 de résolution incoherent")
    if len(docling_document.pages) != version.page_count:
        raise ValueError("page_count de résolution incoherent")

    items_by_item_id: dict[str, SourceLocatorResolution] = {}
    for page in docling_document.pages:
        for item in page.items:
            resolution = _resolution_from_item(
                version=version,
                page=page,
                item=item,
            )
            if resolution.item_id in items_by_item_id:
                raise ValueError("item_id de résolution dupliqué")
            items_by_item_id[resolution.item_id] = resolution

    if len(items_by_item_id) == 0:
        raise ValueError("items de résolution absents")

    return CanonicalVersionResolutionIndex(
        canonical_ref=version.canonical_ref,
        status=status,
        items_by_item_id=items_by_item_id,
    )


def _resolution_from_item(
    *,
    version: CanonicalSourceVersion,
    page: CanonicalDocumentPage,
    item: CanonicalDocumentItem,
) -> SourceLocatorResolution:
    if not isinstance(page, CanonicalDocumentPage):
        raise ValueError("page canonique invalide")
    if not isinstance(item, CanonicalDocumentItem):
        raise ValueError("item canonique invalide")
    provenance = item.provenance
    if provenance.canonical_version_id != version.canonical_version_id:
        raise ValueError("provenance hors version canonique")
    if provenance.document_id != version.document_id.value:
        raise ValueError("document_id de provenance incoherent")
    if provenance.page_pdf != page.page_number.value:
        raise ValueError("page_pdf de provenance incoherent")
    if provenance.item_id != item.item_id:
        raise ValueError("item_id de provenance incoherent")
    if provenance.bbox != item.bbox:
        raise ValueError("bbox de provenance incoherente")
    if provenance.content_hash != item.content_hash:
        raise ValueError("content_hash de provenance incoherent")

    return SourceLocatorResolution(
        canonical_version_id=version.canonical_version_id,
        document_id=version.document_id.value,
        page_pdf=page.page_number.value,
        item_id=item.item_id,
        bbox=item.bbox,
        content_hash=item.content_hash,
    )


def _ensure_resolution_items(
    value: Mapping[str, SourceLocatorResolution],
    *,
    canonical_version_id: str,
    document_id: str,
) -> dict[str, SourceLocatorResolution]:
    _ensure_mapping(value, "items_by_item_id")
    items: dict[str, SourceLocatorResolution] = {}
    for item_id, item in value.items():
        parsed_item_id = _ensure_text(item_id, "item_id invalide")
        if not isinstance(item, SourceLocatorResolution):
            raise ValueError("item de résolution invalide")
        if item.item_id != parsed_item_id:
            raise ValueError("cle d'item incoherente avec item de résolution")
        if item.canonical_version_id != canonical_version_id:
            raise ValueError("item de résolution hors version canonique")
        if item.document_id != document_id:
            raise ValueError("item de résolution hors document")
        items[parsed_item_id] = item
    if len(items) == 0:
        raise ValueError("items de résolution absents")
    return items


def _ensure_canonical_source(value: Any) -> CanonicalSource:
    if not isinstance(value, CanonicalSource):
        raise ValueError("CanonicalSource invalide")
    return value


def _ensure_version_status(value: Any) -> str:
    text = _ensure_text(value, "statut de version canonique invalide")
    if text not in ALLOWED_CANONICAL_VERSION_STATUSES:
        raise ValueError(f"Statut de version canonique inconnu: {text}")
    return text


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")


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
    "CanonicalVersionResolutionIndex",
    "SourceLocatorResolution",
    "SourceLocatorResolutionRegistry",
]
