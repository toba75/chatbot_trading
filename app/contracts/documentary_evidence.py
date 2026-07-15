"""Contrat partagé d'un extrait documentaire et de toutes ses sources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class DocumentaryEvidence:
    """Extrait KA remis à RA sans perdre une localisation canonique."""

    excerpt: str
    source_locators: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "excerpt", _text(self.excerpt, "excerpt"))
        if isinstance(self.source_locators, (str, bytes)) or not isinstance(
            self.source_locators,
            Sequence,
        ):
            raise ValueError("source_locators invalides")
        locators = tuple(_source_locator(locator) for locator in self.source_locators)
        if len(locators) == 0:
            raise ValueError("source_locators absents")
        identities = tuple(
            (locator["canonical_version_id"], locator["document_id"], locator["item_id"])
            for locator in locators
        )
        if len(identities) != len(set(identities)):
            raise ValueError("source_locators dupliqués")
        contexts = {
            (locator["canonical_version_id"], locator["document_id"])
            for locator in locators
        }
        if len(contexts) != 1:
            raise ValueError("source_locators incohérents")
        object.__setattr__(self, "source_locators", locators)


def _source_locator(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("source_locator non objet")
    locator = dict(value)
    if set(locator) != {
        "schema_version",
        "canonical_version_id",
        "document_id",
        "page_pdf",
        "item_id",
        "bbox",
        "content_hash",
    }:
        raise ValueError("source_locator invalide")
    _text(locator["schema_version"], "schema_version")
    _identifier(locator["canonical_version_id"], "CVER", "canonical_version_id")
    _identifier(locator["document_id"], "DOC", "document_id")
    if (
        isinstance(locator["page_pdf"], bool)
        or not isinstance(locator["page_pdf"], int)
        or locator["page_pdf"] < 1
    ):
        raise ValueError("page_pdf invalide")
    _text(locator["item_id"], "item_id")
    bbox = locator["bbox"]
    if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence) or len(bbox) != 4:
        raise ValueError("bbox invalide")
    if any(
        isinstance(coordinate, bool) or not isinstance(coordinate, (int, float))
        for coordinate in bbox
    ):
        raise ValueError("bbox invalide")
    locator["bbox"] = tuple(float(coordinate) for coordinate in bbox)
    _hash(locator["content_hash"], "content_hash")
    return MappingProxyType(locator)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{name} invalide")
    return value


def _identifier(value: object, prefix: str, name: str) -> str:
    text = _text(value, name)
    if not text.startswith(f"{prefix}-"):
        raise ValueError(f"{name} invalide")
    return text


def _hash(value: object, name: str) -> str:
    text = _text(value, name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} invalide")
    return text


__all__ = ["DocumentaryEvidence"]
