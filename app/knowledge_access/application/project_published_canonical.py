"""Contrat KA du fait canonique publié vers le job local de projection."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.contracts.event_envelope import EventEnvelope
from app.contracts.source_references import CanonicalSourceRef
from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionProfile,
)


PROJECT_DOCUMENT_JOB_NAME = "PROJECT_DOCUMENT"
PROJECT_DOCUMENT_CONTRACT_VERSION = "1.0"
_CANONICAL_ARTIFACT_PREFIX = "artifact:source_processing.canonical_sources/"


class ProjectionPublicationError(RuntimeError):
    """Erreur stable du relais de publication canonique vers KA."""

    def __init__(self, code: str) -> None:
        self.code = _text(code, "PROJECTION_PUBLICATION_ERROR_CODE_INVALID")
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class CanonicalPublicationMessage:
    """Vue publique immutable transportée depuis l'outbox SP."""

    event: EventEnvelope
    canonical_artifact_ref: str
    environment_identity: JobEnvironmentIdentity
    event_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.event, EventEnvelope):
            raise ProjectionPublicationError("PROJECTION_EVENT_INVALID")
        if (
            self.event.event_type != "CanonicalSourcePublished"
            or self.event.producer_context != "SP"
        ):
            raise ProjectionPublicationError("PROJECTION_EVENT_TYPE_INVALID")
        canonical_ref = CanonicalSourceRef.from_payload(dict(self.event.payload))
        artifact_ref = _canonical_artifact_ref(
            self.canonical_artifact_ref,
            canonical_version_id=canonical_ref.canonical_version_id,
        )
        if not isinstance(self.environment_identity, JobEnvironmentIdentity):
            raise ProjectionPublicationError("PROJECTION_ENVIRONMENT_IDENTITY_INVALID")
        fingerprint = _sha256(
            self.event_fingerprint,
            "PROJECTION_EVENT_FINGERPRINT_INVALID",
        )
        expected = canonical_publication_fingerprint(
            event=self.event,
            canonical_artifact_ref=artifact_ref,
            environment_identity=self.environment_identity,
        )
        if fingerprint != expected:
            raise ProjectionPublicationError("PROJECTION_EVENT_FINGERPRINT_MISMATCH")
        object.__setattr__(self, "canonical_artifact_ref", artifact_ref)

    @property
    def canonical_ref(self) -> CanonicalSourceRef:
        return CanonicalSourceRef.from_payload(dict(self.event.payload))


@dataclass(frozen=True, slots=True)
class PublishedCanonicalProjectionRequest:
    """Décision déterministe KA : projection REQUESTED et commande technique."""

    message: CanonicalPublicationMessage
    projection: KnowledgeProjection
    job_request: JobRequest

    @classmethod
    def from_message(
        cls,
        *,
        message: CanonicalPublicationMessage,
        projection_profile: ProjectionProfile,
        configured_identity: JobEnvironmentIdentity,
        configured_collection_name: str,
        code_version: str,
    ) -> "PublishedCanonicalProjectionRequest":
        if not isinstance(message, CanonicalPublicationMessage):
            raise ProjectionPublicationError("PROJECTION_EVENT_INVALID")
        if not isinstance(projection_profile, ProjectionProfile):
            raise ProjectionPublicationError("PROJECTION_PROFILE_INVALID")
        if not isinstance(configured_identity, JobEnvironmentIdentity):
            raise ProjectionPublicationError("PROJECTION_ENVIRONMENT_IDENTITY_INVALID")
        if message.environment_identity != configured_identity:
            raise ProjectionPublicationError("PROJECTION_ENVIRONMENT_MISMATCH")
        collection_name = _text(
            configured_collection_name,
            "PROJECTION_COLLECTION_INVALID",
        )
        parsed_code_version = _text(code_version, "PROJECTION_CODE_VERSION_INVALID")
        projection = KnowledgeProjection.request(
            canonical_ref=message.canonical_ref,
            projection_profile=projection_profile,
        )
        payload = {
            "contract_version": PROJECT_DOCUMENT_CONTRACT_VERSION,
            "projection_id": projection.projection_id,
            "document_id": projection.document_id,
            "canonical_version_id": projection.canonical_version_id,
            "canonical_artifact_ref": message.canonical_artifact_ref,
            "canonical_artifact_sha256": message.canonical_ref.canonical_artifact_sha256,
            "build_fingerprint": projection.build_fingerprint.value,
            "projection_profile": projection_profile.to_fingerprint_payload(),
            "qdrant_collection_name": collection_name,
            "environment_identity": configured_identity.to_mapping(),
            "causation_event_id": message.event.event_id,
        }
        request = JobRequest(
            environment=configured_identity.environment,
            deployment_id=configured_identity.deployment_id,
            job_name=PROJECT_DOCUMENT_JOB_NAME,
            priority=JobPriority.P1,
            idempotence_key=JobIdempotenceKey(
                job_name=PROJECT_DOCUMENT_JOB_NAME,
                input_hash=projection.build_fingerprint.value,
                configuration_hash=configured_identity.configuration_hash,
                code_version=parsed_code_version,
                model_version=projection_profile.embedding_model,
            ),
            execution_requirements=JobExecutionRequirements(
                contract_name="project-canonical-document",
                contract_version=PROJECT_DOCUMENT_CONTRACT_VERSION,
                capacity_capability="knowledge-projection",
                capacity_slots=0,
                capacity_device=None,
                storage_environment=configured_identity.environment,
            ),
            payload=payload,
        )
        return cls(message=message, projection=projection, job_request=request)

    def __post_init__(self) -> None:
        if not isinstance(self.message, CanonicalPublicationMessage):
            raise ProjectionPublicationError("PROJECTION_EVENT_INVALID")
        if not isinstance(self.projection, KnowledgeProjection):
            raise ProjectionPublicationError("PROJECTION_INVALID")
        if not isinstance(self.job_request, JobRequest):
            raise ProjectionPublicationError("PROJECTION_JOB_INVALID")


def canonical_publication_fingerprint(
    *,
    event: EventEnvelope,
    canonical_artifact_ref: str,
    environment_identity: JobEnvironmentIdentity,
) -> str:
    if not isinstance(event, EventEnvelope):
        raise ProjectionPublicationError("PROJECTION_EVENT_INVALID")
    canonical_ref = CanonicalSourceRef.from_payload(dict(event.payload))
    artifact_ref = _canonical_artifact_ref(
        canonical_artifact_ref,
        canonical_version_id=canonical_ref.canonical_version_id,
    )
    if not isinstance(environment_identity, JobEnvironmentIdentity):
        raise ProjectionPublicationError("PROJECTION_ENVIRONMENT_IDENTITY_INVALID")
    serialized = json.dumps(
        {
            "canonical_artifact_ref": artifact_ref,
            "environment_identity": environment_identity.to_mapping(),
            "event": json.loads(event.to_json()),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def job_request_payload(request: JobRequest) -> dict[str, Any]:
    """Retourne un payload JSON strict sans modifier le DTO immutable."""

    if not isinstance(request, JobRequest):
        raise ProjectionPublicationError("PROJECTION_JOB_INVALID")
    return _json_value(request.payload)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _canonical_artifact_ref(value: Any, *, canonical_version_id: str) -> str:
    artifact_ref = _text(value, "PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    if not artifact_ref.startswith(_CANONICAL_ARTIFACT_PREFIX):
        raise ProjectionPublicationError("PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    relative = artifact_ref.removeprefix(_CANONICAL_ARTIFACT_PREFIX)
    parts = relative.split("/")
    if (
        len(parts) < 2
        or parts[-1] != "docling.json"
        or canonical_version_id not in parts
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ProjectionPublicationError("PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    return artifact_ref


def _sha256(value: Any, code: str) -> str:
    text = _text(value, code)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ProjectionPublicationError(code)
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ProjectionPublicationError(code)
    return value


__all__ = [
    "CanonicalPublicationMessage",
    "PROJECT_DOCUMENT_CONTRACT_VERSION",
    "PROJECT_DOCUMENT_JOB_NAME",
    "ProjectionPublicationError",
    "PublishedCanonicalProjectionRequest",
    "canonical_publication_fingerprint",
    "job_request_payload",
]
