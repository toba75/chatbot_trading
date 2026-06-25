"""Contrats publies de reference documentaire."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.contracts.identity import ContractSchemaVersion, DomainIdentifier


SOURCE_REFERENCE_SCHEMA_VERSIONS = frozenset({"1.0"})
ACCEPTED_CANONICAL_VERSION_STATUS = "ACCEPTED"
UNAVAILABLE_CANONICAL_VERSION_STATUSES = frozenset({"QUARANTINED", "RETIRED"})
ALLOWED_CANONICAL_VERSION_STATUSES = UNAVAILABLE_CANONICAL_VERSION_STATUSES | {
    ACCEPTED_CANONICAL_VERSION_STATUS
}

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_UTC_INSTANT_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


@dataclass(frozen=True)
class CanonicalSourceRef:
    """Reference publiee d'une version documentaire canonique acceptee."""

    schema_version: str
    canonical_source_id: str
    document_id: str
    canonical_version_id: str
    source_sha256: str
    canonical_artifact_sha256: str
    page_count: int
    accepted_at: str
    quality_policy_version: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CanonicalSourceRef":
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=SOURCE_REFERENCE_SCHEMA_VERSIONS,
        )

        return cls(
            schema_version=str(schema_version),
            canonical_source_id=_required_domain_identifier(payload, "canonical_source_id", "CSRC"),
            document_id=_required_domain_identifier(payload, "document_id", "DOC"),
            canonical_version_id=_required_domain_identifier(
                payload,
                "canonical_version_id",
                "CVER",
            ),
            source_sha256=_required_hash(payload, "source_sha256"),
            canonical_artifact_sha256=_required_hash(payload, "canonical_artifact_sha256"),
            page_count=_required_positive_integer(payload, "page_count"),
            accepted_at=_required_utc_instant(payload, "accepted_at"),
            quality_policy_version=_required_text(payload, "quality_policy_version"),
        )

    @classmethod
    def from_json(cls, serialized_payload: str) -> "CanonicalSourceRef":
        return cls.from_payload(_loads_contract_json(serialized_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "canonical_source_id": self.canonical_source_id,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
            "source_sha256": self.source_sha256,
            "canonical_artifact_sha256": self.canonical_artifact_sha256,
            "page_count": self.page_count,
            "accepted_at": self.accepted_at,
            "quality_policy_version": self.quality_policy_version,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


@dataclass(frozen=True)
class SourceLocator:
    """Localisateur publie d'une preuve dans une version canonique."""

    schema_version: str
    canonical_version_id: str
    document_id: str
    page_pdf: int
    item_id: str
    bbox: tuple[float, float, float, float]
    content_hash: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        validation_policy: "SourceLocatorValidationPolicy",
    ) -> "SourceLocator":
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=SOURCE_REFERENCE_SCHEMA_VERSIONS,
        )

        locator = cls(
            schema_version=str(schema_version),
            canonical_version_id=_required_domain_identifier(
                payload,
                "canonical_version_id",
                "CVER",
            ),
            document_id=_required_domain_identifier(payload, "document_id", "DOC"),
            page_pdf=_required_positive_integer(payload, "page_pdf"),
            item_id=_required_text(payload, "item_id"),
            bbox=_required_bbox(payload, "bbox"),
            content_hash=_required_hash(payload, "content_hash"),
        )
        validation_policy.validate_locator(locator)
        return locator

    @classmethod
    def from_json(
        cls,
        serialized_payload: str,
        validation_policy: "SourceLocatorValidationPolicy",
    ) -> "SourceLocator":
        return cls.from_payload(
            _loads_contract_json(serialized_payload),
            validation_policy=validation_policy,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "canonical_version_id": self.canonical_version_id,
            "document_id": self.document_id,
            "page_pdf": self.page_pdf,
            "item_id": self.item_id,
            "bbox": list(self.bbox),
            "content_hash": self.content_hash,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


@dataclass(frozen=True)
class SourceLocatorValidationPolicy:
    """Contexte publie minimal pour verifier un SourceLocator."""

    canonical_sources_by_version_id: Mapping[str, CanonicalSourceRef]
    version_statuses_by_version_id: Mapping[str, str]
    resolvable_item_ids_by_version_id: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        _ensure_mapping(self.canonical_sources_by_version_id, "canonical_sources_by_version_id")
        _ensure_mapping(self.version_statuses_by_version_id, "version_statuses_by_version_id")
        _ensure_mapping(
            self.resolvable_item_ids_by_version_id,
            "resolvable_item_ids_by_version_id",
        )

        for version_id, canonical_source in self.canonical_sources_by_version_id.items():
            _ensure_domain_identifier_value(version_id, "canonical_version_id", "CVER")
            if not isinstance(canonical_source, CanonicalSourceRef):
                raise ValueError("CanonicalSourceRef invalide dans la politique SourceLocator")
            if version_id != canonical_source.canonical_version_id:
                raise ValueError("Cle de version incoherente avec CanonicalSourceRef")
            if version_id not in self.version_statuses_by_version_id:
                raise ValueError(f"Statut de version canonique absent: {version_id}")

        for version_id, status in self.version_statuses_by_version_id.items():
            _ensure_domain_identifier_value(version_id, "canonical_version_id", "CVER")
            _ensure_text_value(status, "canonical_version_status")
            if status not in ALLOWED_CANONICAL_VERSION_STATUSES:
                raise ValueError(f"Statut de version canonique inconnu: {status}")

        for version_id, item_ids in self.resolvable_item_ids_by_version_id.items():
            _ensure_domain_identifier_value(version_id, "canonical_version_id", "CVER")
            if isinstance(item_ids, str) or not hasattr(item_ids, "__iter__"):
                raise ValueError("item_ids resolvables non iterables")
            materialized_item_ids = frozenset(item_ids)
            if len(materialized_item_ids) == 0:
                raise ValueError(f"item_ids resolvables absents: {version_id}")
            for item_id in materialized_item_ids:
                _ensure_text_value(item_id, "item_id")

    def validate_locator(self, locator: SourceLocator) -> None:
        if not isinstance(locator, SourceLocator):
            raise ValueError("SourceLocator invalide")

        status = self.version_statuses_by_version_id.get(locator.canonical_version_id)
        if status is None:
            raise ValueError(f"Version canonique absente: {locator.canonical_version_id}")
        if status in UNAVAILABLE_CANONICAL_VERSION_STATUSES:
            raise ValueError(f"Version canonique indisponible: {status}")
        if status != ACCEPTED_CANONICAL_VERSION_STATUS:
            raise ValueError(f"Statut de version canonique inconnu: {status}")

        canonical_source = self.canonical_sources_by_version_id.get(locator.canonical_version_id)
        if canonical_source is None:
            raise ValueError(f"Version canonique absente: {locator.canonical_version_id}")
        if locator.document_id != canonical_source.document_id:
            raise ValueError("document_id incoherent avec CanonicalSourceRef")
        if locator.page_pdf > canonical_source.page_count:
            raise ValueError("page_pdf hors version canonique")

        resolvable_item_ids = self.resolvable_item_ids_by_version_id.get(locator.canonical_version_id)
        if resolvable_item_ids is None or locator.item_id not in resolvable_item_ids:
            raise ValueError("item_id non resolvable")


def _required_domain_identifier(
    payload: Mapping[str, Any],
    field_name: str,
    expected_prefix: str,
) -> str:
    value = _required_text(payload, field_name)
    return _ensure_domain_identifier_value(value, field_name, expected_prefix)


def _ensure_domain_identifier_value(value: str, field_name: str, expected_prefix: str) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text_value(payload[field_name], field_name)


def _ensure_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_hash(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_positive_integer(payload: Mapping[str, Any], field_name: str) -> int:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_bbox(payload: Mapping[str, Any], field_name: str) -> tuple[float, float, float, float]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise ValueError(f"{field_name} invalide")

    coordinates = tuple(value)
    if len(coordinates) != 4:
        raise ValueError(f"{field_name} invalide")

    for coordinate in coordinates:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise ValueError(f"{field_name} invalide")
        if coordinate < 0 or coordinate > 1:
            raise ValueError(f"{field_name} invalide")

    left, top, right, bottom = coordinates
    if left >= right or top >= bottom:
        raise ValueError(f"{field_name} invalide")

    return (float(left), float(top), float(right), float(bottom))


def _loads_contract_json(serialized_payload: str) -> Mapping[str, Any]:
    _ensure_text_value(serialized_payload, "contrat serialise")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("Contrat publie non objet.")
    return payload


def _dumps_contract_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
