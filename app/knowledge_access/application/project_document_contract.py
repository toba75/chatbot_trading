"""Contrat unique et versionné du job technique PROJECT_DOCUMENT."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.knowledge_access.domain.knowledge_projection import ProjectionProfile


PROJECT_DOCUMENT_JOB_NAME = "PROJECT_DOCUMENT"
PROJECT_DOCUMENT_CONTRACT_VERSION = "1.0"
PROJECT_DOCUMENT_EXECUTION_CONTRACT = "project-canonical-document"
PROJECT_DOCUMENT_CAPABILITY = "knowledge-projection"
_CANONICAL_ARTIFACT_PREFIX = "artifact:source_processing.canonical_sources/"
_FIELDS = frozenset(
    {
        "contract_version",
        "projection_id",
        "document_id",
        "canonical_version_id",
        "canonical_artifact_ref",
        "canonical_artifact_sha256",
        "build_fingerprint",
        "projection_profile",
        "qdrant_collection_name",
        "environment_identity",
        "causation_event_id",
    }
)


class ProjectDocumentContractError(RuntimeError):
    """Erreur stable de sérialisation ou de rejeu du contrat PROJECT_DOCUMENT."""

    def __init__(self, code: str) -> None:
        self.code = _error_code(code)
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ProjectDocumentContract:
    """DTO partagé par commande manuelle, relais, plateforme et worker KA."""

    projection_id: str
    document_id: str
    canonical_version_id: str
    canonical_artifact_ref: str
    canonical_artifact_sha256: str
    build_fingerprint: str
    projection_profile: ProjectionProfile
    qdrant_collection_name: str
    environment_identity: JobEnvironmentIdentity
    causation_event_id: str
    contract_version: str = PROJECT_DOCUMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PROJECT_DOCUMENT_CONTRACT_VERSION:
            raise ProjectDocumentContractError("PROJECTION_JOB_VERSION_UNSUPPORTED")
        _domain_id(self.projection_id, "PROJ", "PROJECTION_JOB_PAYLOAD_INVALID")
        _domain_id(self.document_id, "DOC", "PROJECTION_JOB_PAYLOAD_INVALID")
        _domain_id(
            self.canonical_version_id,
            "CVER",
            "PROJECTION_JOB_PAYLOAD_INVALID",
        )
        if not isinstance(self.projection_profile, ProjectionProfile):
            raise ProjectDocumentContractError("PROJECTION_JOB_PAYLOAD_INVALID")
        if not isinstance(self.environment_identity, JobEnvironmentIdentity):
            raise ProjectDocumentContractError("PROJECTION_ENVIRONMENT_IDENTITY_INVALID")
        _sha256(self.canonical_artifact_sha256, "PROJECTION_JOB_PAYLOAD_INVALID")
        _sha256(self.build_fingerprint, "PROJECTION_JOB_PAYLOAD_INVALID")
        _resource_name(
            self.qdrant_collection_name,
            "PROJECTION_COLLECTION_MISMATCH",
        )
        _text(self.causation_event_id, "PROJECTION_JOB_PAYLOAD_INVALID")
        _artifact_ref(
            self.canonical_artifact_ref,
            canonical_version_id=self.canonical_version_id,
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProjectDocumentContract":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise ProjectDocumentContractError("PROJECTION_JOB_PAYLOAD_INVALID")
        try:
            profile_payload = payload["projection_profile"]
            identity_payload = payload["environment_identity"]
            if not isinstance(profile_payload, Mapping) or not isinstance(
                identity_payload,
                Mapping,
            ):
                raise ValueError
            profile = ProjectionProfile.from_payload(profile_payload)
            identity = JobEnvironmentIdentity(
                environment=identity_payload["environment"],
                deployment_id=identity_payload["deployment_id"],
                configuration_hash=identity_payload["configuration_hash"],
            )
            if set(identity_payload) != {
                "environment",
                "deployment_id",
                "configuration_hash",
            }:
                raise ValueError
            return cls(
                contract_version=payload["contract_version"],
                projection_id=payload["projection_id"],
                document_id=payload["document_id"],
                canonical_version_id=payload["canonical_version_id"],
                canonical_artifact_ref=payload["canonical_artifact_ref"],
                canonical_artifact_sha256=payload["canonical_artifact_sha256"],
                build_fingerprint=payload["build_fingerprint"],
                projection_profile=profile,
                qdrant_collection_name=payload["qdrant_collection_name"],
                environment_identity=identity,
                causation_event_id=payload["causation_event_id"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProjectDocumentContractError(
                "PROJECTION_JOB_PAYLOAD_INVALID"
            ) from error

    @classmethod
    def from_job_request(cls, request: JobRequest) -> "ProjectDocumentContract":
        if not isinstance(request, JobRequest) or request.job_name != PROJECT_DOCUMENT_JOB_NAME:
            raise ProjectDocumentContractError("PROJECTION_JOB_PAYLOAD_INVALID")
        contract = cls.from_mapping(request.payload)
        if request.environment_identity != contract.environment_identity:
            raise ProjectDocumentContractError("PROJECTION_ENVIRONMENT_MISMATCH")
        if request.priority is not JobPriority.P1:
            raise ProjectDocumentContractError("PROJECTION_JOB_PAYLOAD_INVALID")
        if request.idempotence_key.input_hash != contract.build_fingerprint:
            raise ProjectDocumentContractError("PROJECTION_JOB_REPLAY_DIVERGENCE")
        if request.idempotence_key.model_version != contract.projection_profile.embedding_model:
            raise ProjectDocumentContractError("PROJECTION_JOB_REPLAY_DIVERGENCE")
        if request.execution_requirements is None:
            raise ProjectDocumentContractError(
                "PROJECTION_EXECUTION_REQUIREMENTS_REQUIRED"
            )
        if request.execution_requirements != contract.execution_requirements():
            raise ProjectDocumentContractError(
                "PROJECTION_EXECUTION_REQUIREMENTS_MISMATCH"
            )
        return contract

    def execution_requirements(self) -> JobExecutionRequirements:
        return JobExecutionRequirements(
            contract_name=PROJECT_DOCUMENT_EXECUTION_CONTRACT,
            contract_version=self.contract_version,
            capacity_capability=PROJECT_DOCUMENT_CAPABILITY,
            capacity_slots=0,
            capacity_device=None,
            storage_environment=self.environment_identity.environment,
        )

    def to_job_request(self, *, code_version: str) -> JobRequest:
        parsed_code_version = _text(
            code_version,
            "PROJECTION_CODE_VERSION_INVALID",
        )
        return JobRequest(
            environment=self.environment_identity.environment,
            deployment_id=self.environment_identity.deployment_id,
            job_name=PROJECT_DOCUMENT_JOB_NAME,
            priority=JobPriority.P1,
            idempotence_key=JobIdempotenceKey(
                job_name=PROJECT_DOCUMENT_JOB_NAME,
                input_hash=self.build_fingerprint,
                configuration_hash=self.environment_identity.configuration_hash,
                code_version=parsed_code_version,
                model_version=self.projection_profile.embedding_model,
            ),
            execution_requirements=self.execution_requirements(),
            payload=self.to_mapping(),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "projection_id": self.projection_id,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
            "canonical_artifact_ref": self.canonical_artifact_ref,
            "canonical_artifact_sha256": self.canonical_artifact_sha256,
            "build_fingerprint": self.build_fingerprint,
            "projection_profile": self.projection_profile.to_fingerprint_payload(),
            "qdrant_collection_name": self.qdrant_collection_name,
            "environment_identity": self.environment_identity.to_mapping(),
            "causation_event_id": self.causation_event_id,
        }


def _artifact_ref(value: Any, *, canonical_version_id: str) -> str:
    artifact_ref = _text(value, "PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    if not artifact_ref.startswith(_CANONICAL_ARTIFACT_PREFIX):
        raise ProjectDocumentContractError("PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    relative = artifact_ref.removeprefix(_CANONICAL_ARTIFACT_PREFIX)
    parts = relative.split("/")
    if (
        len(parts) < 2
        or parts[-1] != "docling.json"
        or canonical_version_id not in parts
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ProjectDocumentContractError("PROJECTION_CANONICAL_ARTIFACT_REF_INVALID")
    return artifact_ref


def _domain_id(value: Any, prefix: str, code: str) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(value, prefix))
    except (TypeError, ValueError) as error:
        raise ProjectDocumentContractError(code) from error


def _sha256(value: Any, code: str) -> str:
    text = _text(value, code)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ProjectDocumentContractError(code)
    return text


def _resource_name(value: Any, code: str) -> str:
    text = _text(value, code)
    if re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text) is None:
        raise ProjectDocumentContractError(code)
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ProjectDocumentContractError(code)
    return value


def _error_code(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", value) is None:
        raise ValueError("error_code PROJECT_DOCUMENT invalide")
    return value


__all__ = [
    "PROJECT_DOCUMENT_CAPABILITY",
    "PROJECT_DOCUMENT_CONTRACT_VERSION",
    "PROJECT_DOCUMENT_EXECUTION_CONTRACT",
    "PROJECT_DOCUMENT_JOB_NAME",
    "ProjectDocumentContract",
    "ProjectDocumentContractError",
]
