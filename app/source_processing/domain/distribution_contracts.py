"""Contrats SP versionnés pour la distribution locale des pages M-014."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.source_processing.domain.document_processing_run import (
    PageNumber,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import DocumentId


CONVERT_PAGE_JOB_NAME = "CONVERT_PAGE"
ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME = "ASSEMBLE_CANONICAL_DOCUMENT"
CONVERT_PAGE_CONTRACT_VERSION = "1.0"
PAGE_RESULT_CONTRACT_VERSION = "1.0"
ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION = "1.0"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_REF_PATTERN = re.compile(
    r"^artifact:source_processing\.local/(development|test|production)/"
    r"[A-Za-z0-9_.@/-]+$"
)
_ASSET_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_JOB_ID_PATTERN = re.compile(r"^JOB-M002-[0-9]{6}$")
_WORKER_INSTANCE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ENVIRONMENTS = frozenset(("development", "test", "production"))
_GRANITE_ROUTES = frozenset(
    {
        PageRouteName.SCAN_GRANITE,
        PageRouteName.PREPROCESS_GRANITE,
        PageRouteName.BAD_OCR_TO_GRANITE,
        PageRouteName.MIXED_PAGEWISE,
        PageRouteName.TARGETED_ENRICHMENT,
    }
)


class DistributionContractError(ValueError):
    """Erreur stable d'un contrat M-014 absent, divergent ou incohérent."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ArtifactContractError(DistributionContractError):
    """Erreur stable d'identité, de chemin ou de contenu d'artefact SP."""


class ExecutionCapability(str, Enum):
    DOCUMENT_STANDARD = "DOCUMENT_STANDARD"
    GRANITE_CUDA = "GRANITE_CUDA"


class PageResultStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIP_EMPTY = "SKIP_EMPTY"


class PageResultErrorCode(str, Enum):
    GRANITE_CAPACITY_CONFIGURATION_INVALID = "GRANITE_CAPACITY_CONFIGURATION_INVALID"
    GRANITE_CUDA_UNAVAILABLE = "GRANITE_CUDA_UNAVAILABLE"
    WORKER_MEMORY_LIMIT_EXCEEDED = "WORKER_MEMORY_LIMIT_EXCEEDED"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_OUTSIDE_PROFILE_ROOT = "ARTIFACT_OUTSIDE_PROFILE_ROOT"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"


@dataclass(frozen=True, slots=True)
class LocalArtifactIdentity:
    """Identité SP résoluble uniquement sous la racine locale d'un profil."""

    environment: str
    artifact_ref: str
    relative_path: str

    def __post_init__(self) -> None:
        environment = _environment(self.environment)
        relative_path = _relative_artifact_path(self.relative_path)
        artifact_ref = _text(self.artifact_ref, "ARTIFACT_IDENTITY_INVALID")
        expected_ref = f"artifact:source_processing.local/{environment}/{relative_path}"
        if (
            _ARTIFACT_REF_PATTERN.fullmatch(artifact_ref) is None
            or artifact_ref != expected_ref
        ):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "artifact_ref", artifact_ref)

    @classmethod
    def from_mapping(cls, value: Any) -> "LocalArtifactIdentity":
        payload = _mapping(
            value,
            {"environment", "artifact_ref", "relative_path"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            environment=payload["environment"],
            artifact_ref=payload["artifact_ref"],
            relative_path=payload["relative_path"],
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "environment": self.environment,
            "artifact_ref": self.artifact_ref,
            "relative_path": self.relative_path,
        }

    def resolve_under(self, profile_root: Path) -> Path:
        if not isinstance(profile_root, Path) or not profile_root.is_absolute():
            raise ArtifactContractError("ARTIFACT_ROOT_INVALID")
        environment_root = (profile_root / self.environment).resolve()
        candidate = (
            environment_root / Path(*PurePosixPath(self.relative_path).parts)
        ).resolve()
        if not candidate.is_relative_to(environment_root):
            raise ArtifactContractError("ARTIFACT_OUTSIDE_PROFILE_ROOT")
        return candidate


@dataclass(frozen=True, slots=True)
class LocalArtifactDescriptor:
    """Artefact local immutable identifié, borné et empreinté."""

    identity: LocalArtifactIdentity
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        object.__setattr__(
            self, "sha256", _sha256(self.sha256, "ARTIFACT_HASH_INVALID")
        )
        object.__setattr__(
            self,
            "size_bytes",
            _positive_integer(self.size_bytes, "ARTIFACT_SIZE_INVALID"),
        )

    @classmethod
    def from_mapping(cls, value: Any) -> "LocalArtifactDescriptor":
        payload = _mapping(
            value,
            {"identity", "sha256", "size_bytes"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            identity=LocalArtifactIdentity.from_mapping(payload["identity"]),
            sha256=payload["sha256"],
            size_bytes=payload["size_bytes"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_mapping(),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    def verify_content(self, content: bytes) -> None:
        if not isinstance(content, bytes):
            raise ArtifactContractError("ARTIFACT_CONTENT_INVALID")
        if hashlib.sha256(content).hexdigest() != self.sha256:
            raise ArtifactContractError("ARTIFACT_HASH_MISMATCH")


@dataclass(frozen=True, slots=True)
class LockedAssetVersion:
    """Actif ou modèle explicitement verrouillé par nom, version et empreinte."""

    name: str
    version: str
    sha256: str

    def __post_init__(self) -> None:
        name = _text(self.name, "LOCKED_ASSET_INVALID")
        if _ASSET_NAME_PATTERN.fullmatch(name) is None:
            raise DistributionContractError("LOCKED_ASSET_INVALID")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", _text(self.version, "LOCKED_ASSET_INVALID"))
        object.__setattr__(self, "sha256", _sha256(self.sha256, "LOCKED_ASSET_INVALID"))

    @classmethod
    def from_mapping(cls, value: Any) -> "LockedAssetVersion":
        payload = _mapping(
            value,
            {"name", "version", "sha256"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(payload["name"], payload["version"], payload["sha256"])

    def to_mapping(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ExecutionCapacityRequirement:
    """Capacité requise par la route sans sélectionner un worker particulier."""

    capability: ExecutionCapability | str
    slots: int
    device: str | None

    def __post_init__(self) -> None:
        try:
            capability = ExecutionCapability(self.capability)
        except (TypeError, ValueError) as exc:
            raise DistributionContractError("CAPACITY_CAPABILITY_INVALID") from exc
        if isinstance(self.slots, bool) or not isinstance(self.slots, int):
            raise DistributionContractError("CAPACITY_SLOTS_INVALID")
        if capability is ExecutionCapability.DOCUMENT_STANDARD:
            if self.slots != 0 or self.device is not None:
                raise DistributionContractError("CAPACITY_STANDARD_INVALID")
        elif self.slots != 1 or self.device != "cuda:0":
            raise DistributionContractError("CAPACITY_DEVICE_INVALID")
        object.__setattr__(self, "capability", capability)

    @classmethod
    def from_mapping(cls, value: Any) -> "ExecutionCapacityRequirement":
        if not isinstance(value, Mapping):
            raise DistributionContractError("CONTRACT_FIELDS_INVALID")
        capability = value.get("capability")
        expected = (
            {"capability", "slots"}
            if capability == ExecutionCapability.DOCUMENT_STANDARD.value
            else {"capability", "slots", "device"}
        )
        payload = _mapping(value, expected, "CONTRACT_FIELDS_INVALID")
        return cls(
            capability=payload["capability"],
            slots=payload["slots"],
            device=payload.get("device"),
        )

    def to_mapping(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "capability": self.capability.value,
            "slots": self.slots,
        }
        if self.capability is ExecutionCapability.GRANITE_CUDA:
            payload["device"] = self.device
        return payload


@dataclass(frozen=True, slots=True)
class PageExecutionIdentity:
    """Identité fenced de l'exécution qui a calculé un résultat de page."""

    job_id: str
    claim_generation: int
    claim_token: str
    worker_instance_id: str

    def __post_init__(self) -> None:
        job_id = _text(self.job_id, "PAGE_EXECUTION_IDENTITY_INVALID")
        if _JOB_ID_PATTERN.fullmatch(job_id) is None:
            raise DistributionContractError("PAGE_EXECUTION_IDENTITY_INVALID")
        generation = _positive_integer(
            self.claim_generation,
            "PAGE_EXECUTION_IDENTITY_INVALID",
        )
        token = _uuid4(self.claim_token, "PAGE_EXECUTION_IDENTITY_INVALID")
        worker = _text(self.worker_instance_id, "PAGE_EXECUTION_IDENTITY_INVALID")
        if _WORKER_INSTANCE_PATTERN.fullmatch(worker) is None:
            raise DistributionContractError("PAGE_EXECUTION_IDENTITY_INVALID")
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "claim_generation", generation)
        object.__setattr__(self, "claim_token", token)
        object.__setattr__(self, "worker_instance_id", worker)

    @classmethod
    def from_mapping(cls, value: Any) -> "PageExecutionIdentity":
        payload = _mapping(
            value,
            {"job_id", "claim_generation", "claim_token", "worker_instance_id"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            job_id=payload["job_id"],
            claim_generation=payload["claim_generation"],
            claim_token=payload["claim_token"],
            worker_instance_id=payload["worker_instance_id"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "claim_generation": self.claim_generation,
            "claim_token": self.claim_token,
            "worker_instance_id": self.worker_instance_id,
        }


@dataclass(frozen=True, slots=True)
class GraniteSlotExecutionIdentity:
    """Identité fenced du slot Granite lié au claim de page."""

    slot_ordinal: int
    slot_generation: int
    slot_token: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.slot_ordinal, bool)
            or not isinstance(self.slot_ordinal, int)
            or self.slot_ordinal not in {1, 2}
        ):
            raise DistributionContractError("GRANITE_SLOT_IDENTITY_INVALID")
        object.__setattr__(
            self,
            "slot_generation",
            _positive_integer(
                self.slot_generation,
                "GRANITE_SLOT_IDENTITY_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "slot_token",
            _uuid4(self.slot_token, "GRANITE_SLOT_IDENTITY_INVALID"),
        )

    @classmethod
    def from_mapping(cls, value: Any) -> "GraniteSlotExecutionIdentity":
        payload = _mapping(
            value,
            {"slot_ordinal", "slot_generation", "slot_token"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            slot_ordinal=payload["slot_ordinal"],
            slot_generation=payload["slot_generation"],
            slot_token=payload["slot_token"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "slot_ordinal": self.slot_ordinal,
            "slot_generation": self.slot_generation,
            "slot_token": self.slot_token,
        }


@dataclass(frozen=True, slots=True)
class PageGpuMetrics:
    """Pics GPU techniques mesurés pendant une conversion Granite."""

    peak_vram_bytes: int
    peak_utilization_percent: float
    peak_power_watts: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "peak_vram_bytes",
            _non_negative_integer(
                self.peak_vram_bytes,
                "PAGE_RESULT_GPU_METRICS_INVALID",
            ),
        )
        utilization = _finite_number(
            self.peak_utilization_percent,
            "PAGE_RESULT_GPU_METRICS_INVALID",
        )
        if not 0 <= utilization <= 100:
            raise DistributionContractError("PAGE_RESULT_GPU_METRICS_INVALID")
        power = _finite_number(
            self.peak_power_watts,
            "PAGE_RESULT_GPU_METRICS_INVALID",
        )
        if power < 0:
            raise DistributionContractError("PAGE_RESULT_GPU_METRICS_INVALID")
        object.__setattr__(self, "peak_utilization_percent", utilization)
        object.__setattr__(self, "peak_power_watts", power)

    @classmethod
    def from_mapping(cls, value: Any) -> "PageGpuMetrics":
        payload = _mapping(
            value,
            {
                "peak_vram_bytes",
                "peak_utilization_percent",
                "peak_power_watts",
            },
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            peak_vram_bytes=payload["peak_vram_bytes"],
            peak_utilization_percent=payload["peak_utilization_percent"],
            peak_power_watts=payload["peak_power_watts"],
        )

    def to_mapping(self) -> dict[str, int | float]:
        return {
            "peak_vram_bytes": self.peak_vram_bytes,
            "peak_utilization_percent": self.peak_utilization_percent,
            "peak_power_watts": self.peak_power_watts,
        }


@dataclass(frozen=True, slots=True)
class PageTechnicalMetrics:
    """Durée, pic RAM et mesures GPU d'une exécution de page."""

    duration_seconds: float
    peak_ram_bytes: int
    gpu: PageGpuMetrics | None

    def __post_init__(self) -> None:
        duration = _finite_number(
            self.duration_seconds,
            "PAGE_RESULT_METRICS_INVALID",
        )
        if duration <= 0:
            raise DistributionContractError("PAGE_RESULT_METRICS_INVALID")
        if self.gpu is not None and not isinstance(self.gpu, PageGpuMetrics):
            raise DistributionContractError("PAGE_RESULT_GPU_METRICS_INVALID")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(
            self,
            "peak_ram_bytes",
            _positive_integer(
                self.peak_ram_bytes,
                "PAGE_RESULT_METRICS_INVALID",
            ),
        )

    @classmethod
    def from_mapping(cls, value: Any) -> "PageTechnicalMetrics":
        payload = _mapping(
            value,
            {"duration_seconds", "peak_ram_bytes", "gpu"},
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            duration_seconds=payload["duration_seconds"],
            peak_ram_bytes=payload["peak_ram_bytes"],
            gpu=(
                None
                if payload["gpu"] is None
                else PageGpuMetrics.from_mapping(payload["gpu"])
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "peak_ram_bytes": self.peak_ram_bytes,
            "gpu": None if self.gpu is None else self.gpu.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class ConvertPageContract:
    """Payload SP fermé du job technique neutre ``CONVERT_PAGE``."""

    contract_version: str
    result_contract_version: str
    environment_identity: JobEnvironmentIdentity
    document_id: str
    processing_run_id: str
    page_number: int
    route_name: PageRouteName | str
    routing_policy_version: str
    source_artifact: LocalArtifactDescriptor
    expected_result_artifact: LocalArtifactIdentity
    required_capacity: ExecutionCapacityRequirement
    locked_assets: tuple[LockedAssetVersion, ...]
    idempotence_key: str

    def __post_init__(self) -> None:
        _contract_version(self.contract_version, CONVERT_PAGE_CONTRACT_VERSION)
        _contract_version(self.result_contract_version, PAGE_RESULT_CONTRACT_VERSION)
        identity = _environment_identity(self.environment_identity)
        document_id = _document_id(self.document_id)
        processing_run_id = _processing_run_id(self.processing_run_id)
        page_number = _page_number(self.page_number)
        route_name = _page_route(self.route_name)
        if route_name is PageRouteName.SKIP_EMPTY:
            raise DistributionContractError("CONVERT_PAGE_ROUTE_INVALID")
        routing_policy_version = _routing_policy_version(self.routing_policy_version)
        if not isinstance(self.source_artifact, LocalArtifactDescriptor):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(self.expected_result_artifact, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(self.required_capacity, ExecutionCapacityRequirement):
            raise DistributionContractError("CAPACITY_REQUIREMENT_INVALID")
        _validate_route_capacity(route_name, self.required_capacity)
        if (
            self.source_artifact.identity.environment != identity.environment
            or self.expected_result_artifact.environment != identity.environment
        ):
            raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        if self.source_artifact.identity == self.expected_result_artifact:
            raise ArtifactContractError("ARTIFACT_IDENTITIES_COLLIDE")
        locked_assets = _locked_assets(self.locked_assets)
        expected_key = convert_page_idempotence_key(
            processing_run_id=processing_run_id,
            page_number=page_number,
            route_name=route_name.value,
            routing_policy_version=routing_policy_version,
            contract_version=self.contract_version,
        )
        if self.idempotence_key != expected_key:
            raise DistributionContractError("IDEMPOTENCE_KEY_DIVERGENT")
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "processing_run_id", processing_run_id)
        object.__setattr__(self, "page_number", page_number)
        object.__setattr__(self, "route_name", route_name)
        object.__setattr__(self, "routing_policy_version", routing_policy_version)
        object.__setattr__(self, "locked_assets", locked_assets)

    @classmethod
    def from_mapping(cls, value: Any) -> "ConvertPageContract":
        payload = _mapping(
            value,
            {
                "contract_version",
                "result_contract_version",
                "environment_identity",
                "document_id",
                "processing_run_id",
                "page_number",
                "route_name",
                "routing_policy_version",
                "source_artifact",
                "expected_result_artifact",
                "required_capacity",
                "locked_assets",
                "idempotence_key",
            },
            "CONTRACT_FIELDS_INVALID",
        )
        environment_identity = _environment_identity_from_mapping(
            payload["environment_identity"]
        )
        source_payload = _mapping(
            payload["source_artifact"],
            {"identity", "sha256", "size_bytes"},
            "CONTRACT_FIELDS_INVALID",
        )
        source_identity_payload = _mapping(
            source_payload["identity"],
            {"environment", "artifact_ref", "relative_path"},
            "CONTRACT_FIELDS_INVALID",
        )
        result_identity_payload = _mapping(
            payload["expected_result_artifact"],
            {"environment", "artifact_ref", "relative_path"},
            "CONTRACT_FIELDS_INVALID",
        )
        if (
            source_identity_payload["environment"] != environment_identity.environment
            or result_identity_payload["environment"]
            != environment_identity.environment
        ):
            raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        return cls(
            contract_version=payload["contract_version"],
            result_contract_version=payload["result_contract_version"],
            environment_identity=environment_identity,
            document_id=payload["document_id"],
            processing_run_id=payload["processing_run_id"],
            page_number=payload["page_number"],
            route_name=payload["route_name"],
            routing_policy_version=payload["routing_policy_version"],
            source_artifact=LocalArtifactDescriptor.from_mapping(
                payload["source_artifact"]
            ),
            expected_result_artifact=LocalArtifactIdentity.from_mapping(
                payload["expected_result_artifact"]
            ),
            required_capacity=ExecutionCapacityRequirement.from_mapping(
                payload["required_capacity"]
            ),
            locked_assets=_sequence_of(
                payload["locked_assets"],
                LockedAssetVersion.from_mapping,
                "LOCKED_ASSET_INVALID",
            ),
            idempotence_key=payload["idempotence_key"],
        )

    @classmethod
    def from_json(cls, value: str) -> "ConvertPageContract":
        return cls.from_mapping(_loads_contract_json(value))

    @classmethod
    def from_job_request(cls, request: JobRequest) -> "ConvertPageContract":
        if (
            not isinstance(request, JobRequest)
            or request.job_name != CONVERT_PAGE_JOB_NAME
        ):
            raise DistributionContractError("JOB_ENVELOPE_NAME_INVALID")
        contract = cls.from_mapping(request.payload)
        if request.environment_identity != contract.environment_identity:
            raise DistributionContractError("JOB_ENVELOPE_IDENTITY_MISMATCH")
        if request.idempotence_key.input_hash != contract.idempotence_key:
            raise DistributionContractError("JOB_ENVELOPE_IDEMPOTENCE_MISMATCH")
        if request.execution_requirements != contract.execution_requirements():
            raise DistributionContractError("JOB_EXECUTION_REQUIREMENTS_MISMATCH")
        return contract

    def execution_requirements(self) -> JobExecutionRequirements:
        """Dérive les seuls discriminants techniques admis par platform."""

        return JobExecutionRequirements(
            contract_name=CONVERT_PAGE_JOB_NAME,
            contract_version=self.contract_version,
            capacity_capability=self.required_capacity.capability.value,
            capacity_slots=self.required_capacity.slots,
            capacity_device=self.required_capacity.device,
            storage_environment=self.environment_identity.environment,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "result_contract_version": self.result_contract_version,
            "environment_identity": self.environment_identity.to_mapping(),
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "page_number": self.page_number,
            "route_name": self.route_name.value,
            "routing_policy_version": self.routing_policy_version,
            "source_artifact": self.source_artifact.to_mapping(),
            "expected_result_artifact": self.expected_result_artifact.to_mapping(),
            "required_capacity": self.required_capacity.to_mapping(),
            "locked_assets": tuple(asset.to_mapping() for asset in self.locked_assets),
            "idempotence_key": self.idempotence_key,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_mapping())

    def to_job_request(
        self,
        *,
        priority: JobPriority,
        code_version: str,
        model_version: str,
    ) -> JobRequest:
        return JobRequest(
            environment=self.environment_identity.environment,
            deployment_id=self.environment_identity.deployment_id,
            job_name=CONVERT_PAGE_JOB_NAME,
            priority=priority,
            idempotence_key=JobIdempotenceKey(
                job_name=CONVERT_PAGE_JOB_NAME,
                input_hash=self.idempotence_key,
                configuration_hash=self.environment_identity.configuration_hash,
                code_version=code_version,
                model_version=model_version,
            ),
            execution_requirements=self.execution_requirements(),
            payload=self.to_mapping(),
        )


@dataclass(frozen=True, slots=True)
class PageResultContract:
    """Résultat SP terminal d'une page, sérialisable et rejouable strictement."""

    contract_version: str
    environment_identity: JobEnvironmentIdentity
    document_id: str
    processing_run_id: str
    page_number: int
    route_name: PageRouteName | str
    routing_policy_version: str
    request_idempotence_key: str
    execution: PageExecutionIdentity | None
    granite_slot_execution: GraniteSlotExecutionIdentity | None
    status: PageResultStatus | str
    result_artifact: LocalArtifactDescriptor | None
    tool_name: str | None
    tool_version: str | None
    error_code: PageResultErrorCode | str | None
    technical_metrics: PageTechnicalMetrics | None

    def __post_init__(self) -> None:
        _contract_version(self.contract_version, PAGE_RESULT_CONTRACT_VERSION)
        identity = _environment_identity(self.environment_identity)
        document_id = _document_id(self.document_id)
        processing_run_id = _processing_run_id(self.processing_run_id)
        page_number = _page_number(self.page_number)
        route_name = _page_route(self.route_name)
        routing_policy_version = _routing_policy_version(self.routing_policy_version)
        expected_key = convert_page_idempotence_key(
            processing_run_id=processing_run_id,
            page_number=page_number,
            route_name=route_name.value,
            routing_policy_version=routing_policy_version,
            contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        )
        if self.request_idempotence_key != expected_key:
            raise DistributionContractError("IDEMPOTENCE_KEY_DIVERGENT")
        try:
            status = PageResultStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise DistributionContractError("PAGE_RESULT_STATUS_INVALID") from exc
        error_code = self.error_code
        if error_code is not None:
            try:
                error_code = PageResultErrorCode(error_code)
            except (TypeError, ValueError) as exc:
                raise DistributionContractError("PAGE_RESULT_ERROR_INVALID") from exc
        if self.result_artifact is not None:
            if not isinstance(self.result_artifact, LocalArtifactDescriptor):
                raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
            if self.result_artifact.identity.environment != identity.environment:
                raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        _validate_page_result_variant(
            route_name=route_name,
            execution=self.execution,
            granite_slot_execution=self.granite_slot_execution,
            status=status,
            result_artifact=self.result_artifact,
            tool_name=self.tool_name,
            tool_version=self.tool_version,
            error_code=error_code,
            technical_metrics=self.technical_metrics,
        )
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "processing_run_id", processing_run_id)
        object.__setattr__(self, "page_number", page_number)
        object.__setattr__(self, "route_name", route_name)
        object.__setattr__(self, "routing_policy_version", routing_policy_version)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "error_code", error_code)

    @classmethod
    def from_mapping(cls, value: Any) -> "PageResultContract":
        payload = _mapping(
            value,
            {
                "contract_version",
                "environment_identity",
                "document_id",
                "processing_run_id",
                "page_number",
                "route_name",
                "routing_policy_version",
                "request_idempotence_key",
                "execution",
                "granite_slot_execution",
                "status",
                "result_artifact",
                "tool_name",
                "tool_version",
                "error_code",
                "technical_metrics",
            },
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            contract_version=payload["contract_version"],
            environment_identity=_environment_identity_from_mapping(
                payload["environment_identity"]
            ),
            document_id=payload["document_id"],
            processing_run_id=payload["processing_run_id"],
            page_number=payload["page_number"],
            route_name=payload["route_name"],
            routing_policy_version=payload["routing_policy_version"],
            request_idempotence_key=payload["request_idempotence_key"],
            execution=(
                None
                if payload["execution"] is None
                else PageExecutionIdentity.from_mapping(payload["execution"])
            ),
            granite_slot_execution=(
                None
                if payload["granite_slot_execution"] is None
                else GraniteSlotExecutionIdentity.from_mapping(
                    payload["granite_slot_execution"]
                )
            ),
            status=payload["status"],
            result_artifact=(
                None
                if payload["result_artifact"] is None
                else LocalArtifactDescriptor.from_mapping(payload["result_artifact"])
            ),
            tool_name=payload["tool_name"],
            tool_version=payload["tool_version"],
            error_code=payload["error_code"],
            technical_metrics=(
                None
                if payload["technical_metrics"] is None
                else PageTechnicalMetrics.from_mapping(payload["technical_metrics"])
            ),
        )

    @classmethod
    def from_json(cls, value: str) -> "PageResultContract":
        return cls.from_mapping(_loads_contract_json(value))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "environment_identity": self.environment_identity.to_mapping(),
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "page_number": self.page_number,
            "route_name": self.route_name.value,
            "routing_policy_version": self.routing_policy_version,
            "request_idempotence_key": self.request_idempotence_key,
            "execution": None
            if self.execution is None
            else self.execution.to_mapping(),
            "granite_slot_execution": (
                None
                if self.granite_slot_execution is None
                else self.granite_slot_execution.to_mapping()
            ),
            "status": self.status.value,
            "result_artifact": (
                None
                if self.result_artifact is None
                else self.result_artifact.to_mapping()
            ),
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "error_code": None if self.error_code is None else self.error_code.value,
            "technical_metrics": (
                None
                if self.technical_metrics is None
                else self.technical_metrics.to_mapping()
            ),
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_mapping())

    def assert_replay_compatible(self, replayed: "PageResultContract") -> None:
        if not isinstance(replayed, PageResultContract):
            raise DistributionContractError("PAGE_RESULT_REPLAY_INVALID")
        if self.request_idempotence_key != replayed.request_idempotence_key:
            raise DistributionContractError("PAGE_RESULT_IDEMPOTENCE_KEY_MISMATCH")
        if self.to_json() != replayed.to_json():
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")


@dataclass(frozen=True, slots=True)
class AssembleCanonicalDocumentContract:
    """Payload SP fermé d'assemblage d'un manifeste entièrement terminal."""

    contract_version: str
    environment_identity: JobEnvironmentIdentity
    document_id: str
    processing_run_id: str
    page_count: int
    page_manifest_sha256: str
    page_result_contract_version: str
    expected_canonical_artifact: LocalArtifactIdentity
    idempotence_key: str

    def __post_init__(self) -> None:
        _contract_version(
            self.contract_version,
            ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
        )
        identity = _environment_identity(self.environment_identity)
        document_id = _document_id(self.document_id)
        processing_run_id = _processing_run_id(self.processing_run_id)
        page_count = _positive_integer(self.page_count, "PAGE_COUNT_INVALID")
        manifest_hash = _sha256(self.page_manifest_sha256, "PAGE_MANIFEST_HASH_INVALID")
        _contract_version(
            self.page_result_contract_version,
            PAGE_RESULT_CONTRACT_VERSION,
        )
        if not isinstance(self.expected_canonical_artifact, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        if self.expected_canonical_artifact.environment != identity.environment:
            raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        expected_key = assemble_canonical_document_idempotence_key(
            processing_run_id=processing_run_id,
            page_manifest_sha256=manifest_hash,
            page_result_contract_version=self.page_result_contract_version,
            contract_version=self.contract_version,
        )
        if self.idempotence_key != expected_key:
            raise DistributionContractError("IDEMPOTENCE_KEY_DIVERGENT")
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "processing_run_id", processing_run_id)
        object.__setattr__(self, "page_count", page_count)
        object.__setattr__(self, "page_manifest_sha256", manifest_hash)

    @classmethod
    def from_mapping(cls, value: Any) -> "AssembleCanonicalDocumentContract":
        payload = _mapping(
            value,
            {
                "contract_version",
                "environment_identity",
                "document_id",
                "processing_run_id",
                "page_count",
                "page_manifest_sha256",
                "page_result_contract_version",
                "expected_canonical_artifact",
                "idempotence_key",
            },
            "CONTRACT_FIELDS_INVALID",
        )
        return cls(
            contract_version=payload["contract_version"],
            environment_identity=_environment_identity_from_mapping(
                payload["environment_identity"]
            ),
            document_id=payload["document_id"],
            processing_run_id=payload["processing_run_id"],
            page_count=payload["page_count"],
            page_manifest_sha256=payload["page_manifest_sha256"],
            page_result_contract_version=payload["page_result_contract_version"],
            expected_canonical_artifact=LocalArtifactIdentity.from_mapping(
                payload["expected_canonical_artifact"]
            ),
            idempotence_key=payload["idempotence_key"],
        )

    @classmethod
    def from_json(cls, value: str) -> "AssembleCanonicalDocumentContract":
        return cls.from_mapping(_loads_contract_json(value))

    @classmethod
    def from_job_request(
        cls,
        request: JobRequest,
    ) -> "AssembleCanonicalDocumentContract":
        if (
            not isinstance(request, JobRequest)
            or request.job_name != ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME
        ):
            raise DistributionContractError("JOB_ENVELOPE_NAME_INVALID")
        contract = cls.from_mapping(request.payload)
        if request.environment_identity != contract.environment_identity:
            raise DistributionContractError("JOB_ENVELOPE_IDENTITY_MISMATCH")
        if request.idempotence_key.input_hash != contract.idempotence_key:
            raise DistributionContractError("JOB_ENVELOPE_IDEMPOTENCE_MISMATCH")
        return contract

    def to_mapping(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "environment_identity": self.environment_identity.to_mapping(),
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "page_count": self.page_count,
            "page_manifest_sha256": self.page_manifest_sha256,
            "page_result_contract_version": self.page_result_contract_version,
            "expected_canonical_artifact": self.expected_canonical_artifact.to_mapping(),
            "idempotence_key": self.idempotence_key,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_mapping())

    def to_job_request(
        self,
        *,
        priority: JobPriority,
        code_version: str,
        model_version: str,
    ) -> JobRequest:
        return JobRequest(
            environment=self.environment_identity.environment,
            deployment_id=self.environment_identity.deployment_id,
            job_name=ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
            priority=priority,
            idempotence_key=JobIdempotenceKey(
                job_name=ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
                input_hash=self.idempotence_key,
                configuration_hash=self.environment_identity.configuration_hash,
                code_version=code_version,
                model_version=model_version,
            ),
            execution_requirements=None,
            payload=self.to_mapping(),
        )


def convert_page_idempotence_key(
    *,
    processing_run_id: str,
    page_number: int,
    route_name: PageRouteName | str,
    routing_policy_version: str,
    contract_version: str,
) -> str:
    """Calcule l'identité de page décidée par ADR-052, sans valeur implicite."""

    run = _processing_run_id(processing_run_id)
    page = _page_number(page_number)
    route = _page_route(route_name).value
    policy = _routing_policy_version(routing_policy_version)
    _contract_version(contract_version, CONVERT_PAGE_CONTRACT_VERSION)
    return _canonical_sha256(
        {
            "contract_name": CONVERT_PAGE_JOB_NAME,
            "contract_version": contract_version,
            "processing_run_id": run,
            "page_number": page,
            "route_name": route,
            "routing_policy_version": policy,
        }
    )


def assemble_canonical_document_idempotence_key(
    *,
    processing_run_id: str,
    page_manifest_sha256: str,
    page_result_contract_version: str,
    contract_version: str,
) -> str:
    """Calcule l'identité déterministe de l'assemblage canonique M-014."""

    run = _processing_run_id(processing_run_id)
    manifest_hash = _sha256(page_manifest_sha256, "PAGE_MANIFEST_HASH_INVALID")
    _contract_version(page_result_contract_version, PAGE_RESULT_CONTRACT_VERSION)
    _contract_version(
        contract_version,
        ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
    )
    return _canonical_sha256(
        {
            "contract_name": ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
            "contract_version": contract_version,
            "processing_run_id": run,
            "page_manifest_sha256": manifest_hash,
            "page_result_contract_version": page_result_contract_version,
        }
    )


def _validate_route_capacity(
    route_name: PageRouteName,
    capacity: ExecutionCapacityRequirement,
) -> None:
    if route_name in _GRANITE_ROUTES:
        if capacity.capability is not ExecutionCapability.GRANITE_CUDA:
            raise DistributionContractError("ROUTE_CAPACITY_MISMATCH")
    elif capacity.capability is not ExecutionCapability.DOCUMENT_STANDARD:
        raise DistributionContractError("ROUTE_CAPACITY_MISMATCH")


def _validate_page_result_variant(
    *,
    route_name: PageRouteName,
    execution: PageExecutionIdentity | None,
    granite_slot_execution: GraniteSlotExecutionIdentity | None,
    status: PageResultStatus,
    result_artifact: LocalArtifactDescriptor | None,
    tool_name: str | None,
    tool_version: str | None,
    error_code: PageResultErrorCode | None,
    technical_metrics: PageTechnicalMetrics | None,
) -> None:
    if status is PageResultStatus.SKIP_EMPTY:
        _validate_skipped_page_result(
            route_name=route_name,
            execution=execution,
            granite_slot_execution=granite_slot_execution,
            result_artifact=result_artifact,
            tool_name=tool_name,
            tool_version=tool_version,
            error_code=error_code,
            technical_metrics=technical_metrics,
        )
        return
    _validate_executed_page_result(
        route_name=route_name,
        execution=execution,
        granite_slot_execution=granite_slot_execution,
        status=status,
        result_artifact=result_artifact,
        tool_name=tool_name,
        tool_version=tool_version,
        error_code=error_code,
        technical_metrics=technical_metrics,
    )


def _validate_skipped_page_result(
    *,
    route_name: PageRouteName,
    execution: PageExecutionIdentity | None,
    granite_slot_execution: GraniteSlotExecutionIdentity | None,
    result_artifact: LocalArtifactDescriptor | None,
    tool_name: str | None,
    tool_version: str | None,
    error_code: PageResultErrorCode | None,
    technical_metrics: PageTechnicalMetrics | None,
) -> None:
    if route_name is not PageRouteName.SKIP_EMPTY:
        raise DistributionContractError("SKIP_EMPTY_ROUTE_REQUIRED")
    if technical_metrics is not None:
        raise DistributionContractError("SKIP_EMPTY_METRICS_FORBIDDEN")
    if any(
        value is not None
        for value in (
            execution,
            granite_slot_execution,
            result_artifact,
            tool_name,
            tool_version,
            error_code,
        )
    ):
        raise DistributionContractError("SKIP_EMPTY_CONVERTER_FORBIDDEN")


def _validate_executed_page_result(
    *,
    route_name: PageRouteName,
    execution: PageExecutionIdentity | None,
    granite_slot_execution: GraniteSlotExecutionIdentity | None,
    status: PageResultStatus,
    result_artifact: LocalArtifactDescriptor | None,
    tool_name: str | None,
    tool_version: str | None,
    error_code: PageResultErrorCode | None,
    technical_metrics: PageTechnicalMetrics | None,
) -> None:
    if route_name is PageRouteName.SKIP_EMPTY:
        raise DistributionContractError("SKIP_EMPTY_STATUS_REQUIRED")
    if not isinstance(execution, PageExecutionIdentity):
        raise DistributionContractError("PAGE_EXECUTION_IDENTITY_REQUIRED")
    _validate_page_result_route_resources(
        route_name=route_name,
        granite_slot_execution=granite_slot_execution,
        technical_metrics=technical_metrics,
    )
    _validate_page_result_outcome(
        status=status,
        result_artifact=result_artifact,
        tool_name=tool_name,
        tool_version=tool_version,
        error_code=error_code,
    )


def _validate_page_result_route_resources(
    *,
    route_name: PageRouteName,
    granite_slot_execution: GraniteSlotExecutionIdentity | None,
    technical_metrics: PageTechnicalMetrics | None,
) -> None:
    if not isinstance(technical_metrics, PageTechnicalMetrics):
        raise DistributionContractError("PAGE_RESULT_METRICS_REQUIRED")
    if route_name in _GRANITE_ROUTES:
        if not isinstance(granite_slot_execution, GraniteSlotExecutionIdentity):
            raise DistributionContractError("GRANITE_SLOT_IDENTITY_REQUIRED")
        if technical_metrics.gpu is None:
            raise DistributionContractError("PAGE_RESULT_GPU_METRICS_REQUIRED")
        return
    if granite_slot_execution is not None:
        raise DistributionContractError("GRANITE_SLOT_IDENTITY_FORBIDDEN")
    if technical_metrics.gpu is not None:
        raise DistributionContractError("PAGE_RESULT_GPU_METRICS_FORBIDDEN")


def _validate_page_result_outcome(
    *,
    status: PageResultStatus,
    result_artifact: LocalArtifactDescriptor | None,
    tool_name: str | None,
    tool_version: str | None,
    error_code: PageResultErrorCode | None,
) -> None:
    if status is PageResultStatus.SUCCEEDED:
        if (
            not isinstance(result_artifact, LocalArtifactDescriptor)
            or tool_name is None
            or tool_version is None
            or error_code is not None
        ):
            raise DistributionContractError("PAGE_RESULT_SUCCESS_INVALID")
        _text(tool_name, "PAGE_RESULT_SUCCESS_INVALID")
        _text(tool_version, "PAGE_RESULT_SUCCESS_INVALID")
        return
    if (
        result_artifact is not None
        or tool_name is not None
        or tool_version is not None
        or error_code is None
    ):
        raise DistributionContractError("PAGE_RESULT_FAILURE_INVALID")


def _locked_assets(value: Any) -> tuple[LockedAssetVersion, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise DistributionContractError("LOCKED_ASSET_INVALID")
    parsed = tuple(value)
    if len(parsed) == 0 or any(
        not isinstance(item, LockedAssetVersion) for item in parsed
    ):
        raise DistributionContractError("LOCKED_ASSET_INVALID")
    names = tuple(item.name for item in parsed)
    if len(set(names)) != len(names) or names != tuple(sorted(names)):
        raise DistributionContractError("LOCKED_ASSET_INVALID")
    return parsed


def _environment_identity(value: Any) -> JobEnvironmentIdentity:
    if not isinstance(value, JobEnvironmentIdentity):
        raise DistributionContractError("CONTRACT_ENVIRONMENT_IDENTITY_INVALID")
    return value


def _environment_identity_from_mapping(value: Any) -> JobEnvironmentIdentity:
    payload = _mapping(
        value,
        {"environment", "deployment_id", "configuration_hash"},
        "CONTRACT_FIELDS_INVALID",
    )
    try:
        return JobEnvironmentIdentity(
            environment=payload["environment"],
            deployment_id=payload["deployment_id"],
            configuration_hash=payload["configuration_hash"],
        )
    except ValueError as exc:
        raise DistributionContractError(
            "CONTRACT_ENVIRONMENT_IDENTITY_INVALID"
        ) from exc


def _page_route(value: PageRouteName | str) -> PageRouteName:
    try:
        return PageRouteName.from_value(value)
    except ValueError as exc:
        raise DistributionContractError("PAGE_ROUTE_INVALID") from exc


def _document_id(value: Any) -> str:
    try:
        return DocumentId.from_value(value).value
    except ValueError as exc:
        raise DistributionContractError("DOCUMENT_ID_INVALID") from exc


def _processing_run_id(value: Any) -> str:
    try:
        return ProcessingRunId.from_value(value).value
    except ValueError as exc:
        raise DistributionContractError("PROCESSING_RUN_ID_INVALID") from exc


def _page_number(value: Any) -> int:
    try:
        return PageNumber.from_value(value).value
    except ValueError as exc:
        raise DistributionContractError("PAGE_NUMBER_INVALID") from exc


def _routing_policy_version(value: Any) -> str:
    try:
        return RoutingPolicyVersion.from_value(value).value
    except ValueError as exc:
        raise DistributionContractError("ROUTING_POLICY_VERSION_INVALID") from exc


def _environment(value: Any) -> str:
    if value not in _ENVIRONMENTS:
        raise ArtifactContractError("ARTIFACT_ENVIRONMENT_INVALID")
    return value


def _relative_artifact_path(value: Any) -> str:
    path = _text(value, "ARTIFACT_PATH_INVALID", artifact=True)
    if "\\" in path or ":" in path or path.startswith("/") or "//" in path:
        raise ArtifactContractError("ARTIFACT_PATH_INVALID")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ArtifactContractError("ARTIFACT_PATH_INVALID")
    if parsed.as_posix() != path:
        raise ArtifactContractError("ARTIFACT_PATH_INVALID")
    return path


def _contract_version(value: Any, expected: str) -> str:
    if value != expected:
        raise DistributionContractError("CONTRACT_VERSION_UNSUPPORTED")
    return value


def _text(value: Any, code: str, *, artifact: bool = False) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        if artifact:
            raise ArtifactContractError(code)
        raise DistributionContractError(code)
    return value


def _sha256(value: Any, code: str) -> str:
    text = _text(value, code)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise DistributionContractError(code)
    return text


def _positive_integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DistributionContractError(code)
    return value


def _non_negative_integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DistributionContractError(code)
    return value


def _finite_number(value: Any, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DistributionContractError(code)
    parsed = float(value)
    if not math.isfinite(parsed):
        raise DistributionContractError(code)
    return parsed


def _uuid4(value: Any, code: str) -> str:
    text = _text(value, code)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise DistributionContractError(code) from exc
    if parsed.version != 4 or str(parsed) != text:
        raise DistributionContractError(code)
    return text


def _mapping(value: Any, fields: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise DistributionContractError(code)
    return value


def _sequence_of(
    value: Any,
    parser: Any,
    code: str,
) -> tuple[Any, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) == 0:
        raise DistributionContractError(code)
    return tuple(parser(item) for item in value)


def _dumps_contract_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads_contract_json(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, str) or value.strip() == "":
        raise DistributionContractError("CONTRACT_JSON_INVALID")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, item in pairs:
            if key in parsed:
                raise DistributionContractError("CONTRACT_JSON_INVALID")
            parsed[key] = item
        return parsed

    def reject_constant(_: str) -> None:
        raise DistributionContractError("CONTRACT_JSON_INVALID")

    try:
        payload = json.loads(
            value,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise DistributionContractError("CONTRACT_JSON_INVALID") from exc
    if not isinstance(payload, Mapping):
        raise DistributionContractError("CONTRACT_JSON_INVALID")
    return payload


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_dumps_contract_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION",
    "ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME",
    "CONVERT_PAGE_CONTRACT_VERSION",
    "CONVERT_PAGE_JOB_NAME",
    "PAGE_RESULT_CONTRACT_VERSION",
    "ArtifactContractError",
    "AssembleCanonicalDocumentContract",
    "ConvertPageContract",
    "DistributionContractError",
    "ExecutionCapacityRequirement",
    "ExecutionCapability",
    "GraniteSlotExecutionIdentity",
    "LocalArtifactDescriptor",
    "LocalArtifactIdentity",
    "LockedAssetVersion",
    "PageExecutionIdentity",
    "PageGpuMetrics",
    "PageResultContract",
    "PageResultErrorCode",
    "PageResultStatus",
    "PageTechnicalMetrics",
    "assemble_canonical_document_idempotence_key",
    "convert_page_idempotence_key",
]
