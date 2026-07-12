"""Agrégat KA de projection de connaissance reconstruisible."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import CanonicalSourceRef


_PROJECTION_PROFILE_FIELDS = frozenset(
    {
        "projection_profile_id",
        "chunking_profile",
        "embedding_model",
        "sparse_profile",
        "index_schema",
    }
)
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")


class ProjectionStatus(str, Enum):
    """État observable de KnowledgeProjection."""

    REQUESTED = "REQUESTED"
    BUILDING = "BUILDING"
    BUILT = "BUILT"
    INDEXING = "INDEXING"
    SEARCHABLE = "SEARCHABLE"
    STALE = "STALE"
    FAILED = "FAILED"
    RETIRED = "RETIRED"

    @classmethod
    def from_value(cls, value: "ProjectionStatus | str") -> "ProjectionStatus":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("projection_status invalide")
        for status in cls:
            if status.value == value:
                return status
        raise ValueError("projection_status inconnu")


@dataclass(frozen=True)
class ProjectionProfile:
    """Profil explicite d'indexation KA."""

    projection_profile_id: str
    chunking_profile: str
    embedding_model: str
    sparse_profile: str
    index_schema: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProjectionProfile":
        if not isinstance(payload, Mapping):
            raise ValueError("projection_profile non objet")
        actual_fields = frozenset(payload.keys())
        missing_fields = _PROJECTION_PROFILE_FIELDS - actual_fields
        if len(missing_fields) > 0:
            first_missing = sorted(missing_fields)[0]
            raise ValueError(f"{first_missing} absent")
        unexpected_fields = actual_fields - _PROJECTION_PROFILE_FIELDS
        if len(unexpected_fields) > 0:
            first_unexpected = sorted(unexpected_fields)[0]
            raise ValueError(f"{first_unexpected} interdit")
        return cls(
            projection_profile_id=payload["projection_profile_id"],
            chunking_profile=payload["chunking_profile"],
            embedding_model=payload["embedding_model"],
            sparse_profile=payload["sparse_profile"],
            index_schema=payload["index_schema"],
        )

    def __post_init__(self) -> None:
        _ensure_text(self.projection_profile_id, "projection_profile_id")
        _ensure_text(self.chunking_profile, "chunking_profile")
        _ensure_text(self.embedding_model, "embedding_model")
        _ensure_text(self.sparse_profile, "sparse_profile")
        _ensure_text(self.index_schema, "index_schema")

    def to_fingerprint_payload(self) -> dict[str, str]:
        return {
            "projection_profile_id": self.projection_profile_id,
            "chunking_profile": self.chunking_profile,
            "embedding_model": self.embedding_model,
            "sparse_profile": self.sparse_profile,
            "index_schema": self.index_schema,
        }


@dataclass(frozen=True)
class BuildFingerprint:
    """Empreinte déterministe des entrées de build KA."""

    value: str

    @classmethod
    def from_inputs(
        cls,
        *,
        canonical_ref: CanonicalSourceRef,
        projection_profile: ProjectionProfile,
    ) -> "BuildFingerprint":
        parsed_ref = _ensure_canonical_ref(canonical_ref)
        parsed_profile = _ensure_projection_profile(projection_profile)
        payload = {
            "canonical_source_id": parsed_ref.canonical_source_id,
            "document_id": parsed_ref.document_id,
            "canonical_version_id": parsed_ref.canonical_version_id,
            "source_sha256": parsed_ref.source_sha256,
            "canonical_artifact_sha256": parsed_ref.canonical_artifact_sha256,
            "page_count": parsed_ref.page_count,
            "quality_policy_version": parsed_ref.quality_policy_version,
            "projection_profile": parsed_profile.to_fingerprint_payload(),
        }
        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest())

    def extend_with_payload(self, *, scope: str, payload: Mapping[str, Any]) -> "BuildFingerprint":
        parsed_scope = _ensure_text(scope, "fingerprint_scope")
        parsed_payload = _ensure_mapping(payload, "fingerprint_payload")
        serialized_payload = json.dumps(
            {
                "base_build_fingerprint": self.value,
                "payload": parsed_payload,
                "scope": parsed_scope,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return BuildFingerprint(hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest())

    def __post_init__(self) -> None:
        _ensure_sha256(self.value, "build_fingerprint")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class KnowledgeProjection:
    """Projection KA dérivée d'une version canonique publiée."""

    projection_id: str
    document_id: str
    canonical_version_id: str
    projection_profile: ProjectionProfile
    build_fingerprint: BuildFingerprint
    status: ProjectionStatus
    aggregate_version: int = 0

    @classmethod
    def request(
        cls,
        *,
        canonical_ref: CanonicalSourceRef,
        projection_profile: ProjectionProfile,
    ) -> "KnowledgeProjection":
        parsed_ref = _ensure_canonical_ref(canonical_ref)
        parsed_profile = _ensure_projection_profile(projection_profile)
        build_fingerprint = BuildFingerprint.from_inputs(
            canonical_ref=parsed_ref,
            projection_profile=parsed_profile,
        )
        return cls(
            projection_id=_projection_id_for(build_fingerprint),
            document_id=parsed_ref.document_id,
            canonical_version_id=parsed_ref.canonical_version_id,
            projection_profile=parsed_profile,
            build_fingerprint=build_fingerprint,
            status=ProjectionStatus.REQUESTED,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        _ensure_projection_profile(self.projection_profile)
        _ensure_build_fingerprint(self.build_fingerprint)
        object.__setattr__(self, "status", ProjectionStatus.from_value(self.status))
        if (
            isinstance(self.aggregate_version, bool)
            or not isinstance(self.aggregate_version, int)
            or self.aggregate_version < 0
        ):
            raise ValueError("aggregate_version KA invalide")

    def start_build(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={ProjectionStatus.REQUESTED, ProjectionStatus.STALE},
            next_status=ProjectionStatus.BUILDING,
        )

    def mark_built(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={ProjectionStatus.BUILDING},
            next_status=ProjectionStatus.BUILT,
        )

    def start_indexing(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={ProjectionStatus.BUILT},
            next_status=ProjectionStatus.INDEXING,
        )

    def mark_searchable(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={ProjectionStatus.INDEXING},
            next_status=ProjectionStatus.SEARCHABLE,
        )

    def mark_stale(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={
                ProjectionStatus.BUILDING,
                ProjectionStatus.BUILT,
                ProjectionStatus.INDEXING,
                ProjectionStatus.SEARCHABLE,
            },
            next_status=ProjectionStatus.STALE,
        )

    def mark_failed(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={
                ProjectionStatus.REQUESTED,
                ProjectionStatus.BUILDING,
                ProjectionStatus.INDEXING,
            },
            next_status=ProjectionStatus.FAILED,
        )

    def retry_request(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={ProjectionStatus.FAILED},
            next_status=ProjectionStatus.REQUESTED,
        )

    def retire(self) -> "KnowledgeProjection":
        return self._transition(
            allowed_statuses={
                ProjectionStatus.BUILDING,
                ProjectionStatus.BUILT,
                ProjectionStatus.SEARCHABLE,
                ProjectionStatus.STALE,
            },
            next_status=ProjectionStatus.RETIRED,
        )

    def _transition(
        self,
        *,
        allowed_statuses: set[ProjectionStatus],
        next_status: ProjectionStatus,
    ) -> "KnowledgeProjection":
        if self.status not in allowed_statuses:
            raise ValueError(
                f"transition interdite vers {next_status.value} depuis {self.status.value}"
            )
        return replace(
            self,
            status=next_status,
            aggregate_version=self.aggregate_version + 1,
        )


def _projection_id_for(build_fingerprint: BuildFingerprint) -> str:
    parsed_fingerprint = _ensure_build_fingerprint(build_fingerprint)
    return f"PROJ-{parsed_fingerprint.value.upper()}"


def _ensure_canonical_ref(value: CanonicalSourceRef) -> CanonicalSourceRef:
    if not isinstance(value, CanonicalSourceRef):
        raise ValueError("CanonicalSourceRef obligatoire")
    return value


def _ensure_projection_profile(value: ProjectionProfile) -> ProjectionProfile:
    if not isinstance(value, ProjectionProfile):
        raise ValueError("projection_profile invalide")
    return value


def _ensure_build_fingerprint(value: BuildFingerprint) -> BuildFingerprint:
    if not isinstance(value, BuildFingerprint):
        raise ValueError("build_fingerprint invalide")
    return value


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identifiant de domaine invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"identifiant {expected_prefix} invalide: {exc}") from exc


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text_value


def _ensure_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


__all__ = [
    "BuildFingerprint",
    "KnowledgeProjection",
    "ProjectionProfile",
    "ProjectionStatus",
]
