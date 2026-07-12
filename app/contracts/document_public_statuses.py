"""Statuts documentaires publics partagés entre SP, l'API et ses clients."""

from __future__ import annotations

from enum import Enum
from typing import Any


class _StrictPublicStatus(str, Enum):
    @classmethod
    def from_value(cls, value: Any):
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"{cls.__name__} invalide")
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"{cls.__name__} inconnu") from exc


class PublicSourceStatus(_StrictPublicStatus):
    REGISTERED = "REGISTERED"
    QUARANTINED = "QUARANTINED"


class PublicDiagnosticStatus(_StrictPublicStatus):
    DIAGNOSTIC_NOT_REQUESTED = "DIAGNOSTIC_NOT_REQUESTED"
    MANIFEST_CREATED = "MANIFEST_CREATED"
    DIAGNOSED = "DIAGNOSED"
    ROUTE_PLANNED = "ROUTE_PLANNED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class PublicConversionStatus(_StrictPublicStatus):
    CONVERSION_NOT_REQUESTED = "CONVERSION_NOT_REQUESTED"
    CONVERSION_REQUESTED = "CONVERSION_REQUESTED"
    QA_REJECTED = "QA_REJECTED"
    CANONICAL_ACCEPTED = "CANONICAL_ACCEPTED"


class PublicProjectionStatus(_StrictPublicStatus):
    PROJECTION_NOT_REQUESTED = "PROJECTION_NOT_REQUESTED"
    REQUESTED = "REQUESTED"
    BUILDING = "BUILDING"
    BUILT = "BUILT"
    INDEXING = "INDEXING"
    SEARCHABLE = "SEARCHABLE"
    STALE = "STALE"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


__all__ = [
    "PublicConversionStatus",
    "PublicDiagnosticStatus",
    "PublicProjectionStatus",
    "PublicSourceStatus",
]
