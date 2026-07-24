"""Fan-out SP transactionnel des pages routées d'un ``CONVERT_DOCUMENT``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.technical_jobs import JobRequest
from app.source_processing.domain.distribution_contracts import (
    CONVERT_PAGE_CONTRACT_VERSION,
    PAGE_RESULT_CONTRACT_VERSION,
    ConvertPageContract,
    DistributionContractError,
    ExecutionCapacityRequirement,
    ExecutionCapability,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    LockedAssetVersion,
    PageResultContract,
    PageResultStatus,
    convert_page_idempotence_key,
    page_manifest_sha256,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    PageRouteName,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import DocumentId


DISTRIBUTED_PAGE_FAN_OUT_VERSION = "m014-page-fanout-v1"
LEGACY_INLINE_ORCHESTRATION_VERSION = "m004-inline-v1"

_PARENT_FIELDS = frozenset(
    {
        "document_id",
        "processing_run_id",
        "source_sha256",
        "routing_policy_version",
        "route_count",
        "orchestration_version",
    }
)
_GRANITE_ROUTES = frozenset(
    {
        PageRouteName.SCAN_GRANITE,
        PageRouteName.PREPROCESS_GRANITE,
        PageRouteName.BAD_OCR_TO_GRANITE,
        PageRouteName.MIXED_PAGEWISE,
        PageRouteName.TARGETED_ENRICHMENT,
    }
)


class ProcessingRunForFanOutRepository(Protocol):
    def find_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None: ...


class PageFanOutRepository(Protocol):
    def persist_page_fan_out(
        self,
        plan: "PageFanOutPlan",
        *,
        trace_id: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class SkippedPageFanOutResult:
    """Résultat vide SP doté d'une identité de persistance déterministe."""

    completion_id: str
    result: PageResultContract

    def __post_init__(self) -> None:
        if (
            not isinstance(self.completion_id, str)
            or not self.completion_id.startswith("SKIP-M014-")
        ):
            raise DistributionContractError("SKIP_EMPTY_COMPLETION_ID_INVALID")
        if (
            not isinstance(self.result, PageResultContract)
            or self.result.status is not PageResultStatus.SKIP_EMPTY
        ):
            raise DistributionContractError("SKIP_EMPTY_RESULT_INVALID")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "completion_id": self.completion_id,
            "result": self.result.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class PageFanOutPlan:
    """Plan SP immutable écrit en une transaction avant tout relais."""

    orchestration_version: str
    document_id: DocumentId
    processing_run_id: ProcessingRunId
    page_manifest_sha256: str
    total_units: int
    source_artifact: LocalArtifactDescriptor
    locked_assets: tuple[LockedAssetVersion, ...]
    page_jobs: tuple[JobRequest, ...]
    skipped_results: tuple[SkippedPageFanOutResult, ...]

    def __post_init__(self) -> None:
        if self.orchestration_version != DISTRIBUTED_PAGE_FAN_OUT_VERSION:
            raise DistributionContractError(
                "PAGE_FAN_OUT_ORCHESTRATION_VERSION_UNSUPPORTED"
            )
        if not isinstance(self.document_id, DocumentId):
            raise DistributionContractError("DOCUMENT_ID_INVALID")
        if not isinstance(self.processing_run_id, ProcessingRunId):
            raise DistributionContractError("PROCESSING_RUN_ID_INVALID")
        if (
            not isinstance(self.page_manifest_sha256, str)
            or len(self.page_manifest_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.page_manifest_sha256)
        ):
            raise DistributionContractError("PAGE_MANIFEST_HASH_INVALID")
        if isinstance(self.total_units, bool) or not isinstance(self.total_units, int) or self.total_units < 1:
            raise DistributionContractError("PAGE_FAN_OUT_TOTAL_INVALID")
        if not isinstance(self.source_artifact, LocalArtifactDescriptor):
            raise DistributionContractError("PAGE_FAN_OUT_SOURCE_ARTIFACT_INVALID")
        assets = tuple(self.locked_assets)
        if len(assets) == 0 or any(not isinstance(asset, LockedAssetVersion) for asset in assets):
            raise DistributionContractError("LOCKED_ASSET_INVALID")
        jobs = tuple(self.page_jobs)
        skipped = tuple(self.skipped_results)
        if any(not isinstance(request, JobRequest) for request in jobs):
            raise DistributionContractError("PAGE_FAN_OUT_JOB_INVALID")
        if any(not isinstance(result, SkippedPageFanOutResult) for result in skipped):
            raise DistributionContractError("SKIP_EMPTY_RESULT_INVALID")
        job_pages = tuple(ConvertPageContract.from_job_request(request).page_number for request in jobs)
        skipped_pages = tuple(result.result.page_number for result in skipped)
        all_pages = tuple(sorted((*job_pages, *skipped_pages)))
        if all_pages != tuple(range(1, self.total_units + 1)):
            raise DistributionContractError("PAGE_FAN_OUT_PAGE_COVERAGE_INVALID")
        object.__setattr__(self, "locked_assets", assets)
        object.__setattr__(self, "page_jobs", jobs)
        object.__setattr__(self, "skipped_results", skipped)

    @property
    def fingerprint(self) -> str:
        serialized = json.dumps(
            self.to_mapping(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "orchestration_version": self.orchestration_version,
            "document_id": self.document_id.value,
            "processing_run_id": self.processing_run_id.value,
            "page_manifest_sha256": self.page_manifest_sha256,
            "total_units": self.total_units,
            "source_artifact": self.source_artifact.to_mapping(),
            "locked_assets": tuple(asset.to_mapping() for asset in self.locked_assets),
            "page_jobs": tuple(_job_request_mapping(request) for request in self.page_jobs),
            "skipped_results": tuple(result.to_mapping() for result in self.skipped_results),
        }

    def assert_replay_compatible(self, replayed: "PageFanOutPlan") -> None:
        if not isinstance(replayed, PageFanOutPlan) or self.fingerprint != replayed.fingerprint:
            raise DistributionContractError("PAGE_FAN_OUT_REPLAY_DIVERGENCE")


@dataclass(frozen=True, slots=True)
class FanOutDocumentPagesResult:
    created: bool
    total_units: int
    completed_units: int
    page_job_count: int
    page_manifest_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.created, bool):
            raise ValueError("created invalide")


class FanOutDocumentPagesHandler:
    """Transforme le job parent en effets SP durables, sans convertir de page."""

    def __init__(
        self,
        *,
        processing_run_repository: ProcessingRunForFanOutRepository,
        page_fan_out_repository: PageFanOutRepository,
        locked_assets: Sequence[LockedAssetVersion],
    ) -> None:
        if not callable(getattr(processing_run_repository, "find_by_document_id", None)):
            raise ValueError("processing_run_repository fan-out invalide")
        if not callable(getattr(page_fan_out_repository, "persist_page_fan_out", None)):
            raise ValueError("page_fan_out_repository invalide")
        parsed_assets = tuple(locked_assets)
        if len(parsed_assets) == 0 or any(
            not isinstance(asset, LockedAssetVersion) for asset in parsed_assets
        ):
            raise ValueError("locked_assets fan-out invalides")
        self._processing_run_repository = processing_run_repository
        self._page_fan_out_repository = page_fan_out_repository
        self._locked_assets = parsed_assets

    def handle(
        self,
        *,
        parent_job: JobRequest,
        source_artifact: LocalArtifactDescriptor,
        trace_id: str,
    ) -> FanOutDocumentPagesResult:
        if not isinstance(parent_job, JobRequest) or parent_job.job_name != "CONVERT_DOCUMENT":
            raise DistributionContractError("PAGE_FAN_OUT_PARENT_JOB_INVALID")
        payload = _mapping(parent_job.payload, _PARENT_FIELDS)
        if payload["orchestration_version"] != DISTRIBUTED_PAGE_FAN_OUT_VERSION:
            raise DistributionContractError(
                "PAGE_FAN_OUT_ORCHESTRATION_VERSION_UNSUPPORTED"
            )
        document_id = _document_id(payload["document_id"])
        processing_run_id = _processing_run_id(payload["processing_run_id"])
        if not isinstance(source_artifact, LocalArtifactDescriptor):
            raise DistributionContractError("PAGE_FAN_OUT_SOURCE_ARTIFACT_INVALID")
        if source_artifact.identity.environment != parent_job.environment:
            raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        if source_artifact.sha256 != payload["source_sha256"]:
            raise DistributionContractError("PAGE_FAN_OUT_SOURCE_HASH_DIVERGENT")
        if parent_job.idempotence_key.input_hash != payload["source_sha256"]:
            raise DistributionContractError("PAGE_FAN_OUT_SOURCE_HASH_DIVERGENT")
        run = self._processing_run_repository.find_by_document_id(document_id)
        if not isinstance(run, DocumentProcessingRun):
            raise DistributionContractError("PAGE_FAN_OUT_PROCESSING_RUN_NOT_FOUND")
        run.ensure_documentary_publication_allowed()
        if run.processing_run_id != processing_run_id:
            raise DistributionContractError("PAGE_FAN_OUT_PROCESSING_RUN_DIVERGENT")
        route_plan = run.route_plan
        if route_plan is None:
            raise DistributionContractError("PAGE_FAN_OUT_ROUTE_PLAN_MISSING")
        if route_plan.routing_policy_version.value != payload["routing_policy_version"]:
            raise DistributionContractError("PAGE_FAN_OUT_ROUTING_POLICY_DIVERGENT")
        if len(route_plan.page_routes) != payload["route_count"]:
            raise DistributionContractError("PAGE_FAN_OUT_ROUTE_COUNT_DIVERGENT")
        manifest_hash = page_manifest_sha256(
            document_id=run.document_id,
            processing_run_id=run.processing_run_id,
            page_manifest=run.page_manifest,
            page_routes=route_plan.page_routes,
            routing_policy_version=route_plan.routing_policy_version,
        )
        page_jobs: list[JobRequest] = []
        skipped_results: list[SkippedPageFanOutResult] = []
        for route in route_plan.page_routes:
            idempotence_key = convert_page_idempotence_key(
                processing_run_id=run.processing_run_id.value,
                page_number=route.page_number.value,
                route_name=route.route_name,
                routing_policy_version=route.routing_policy_version.value,
                contract_version=CONVERT_PAGE_CONTRACT_VERSION,
            )
            if route.route_name is PageRouteName.SKIP_EMPTY:
                skipped_results.append(
                    SkippedPageFanOutResult(
                        completion_id=_skip_completion_id(
                            processing_run_id=run.processing_run_id,
                            page_number=route.page_number.value,
                            manifest_hash=manifest_hash,
                        ),
                        result=PageResultContract(
                            contract_version=PAGE_RESULT_CONTRACT_VERSION,
                            environment_identity=parent_job.environment_identity,
                            document_id=run.document_id.value,
                            processing_run_id=run.processing_run_id.value,
                            page_number=route.page_number.value,
                            route_name=route.route_name,
                            routing_policy_version=route.routing_policy_version.value,
                            request_idempotence_key=idempotence_key,
                            execution=None,
                            granite_slot_execution=None,
                            status=PageResultStatus.SKIP_EMPTY,
                            result_artifact=None,
                            tool_name=None,
                            tool_version=None,
                            error_code=None,
                            technical_metrics=None,
                        ),
                    )
                )
                continue
            contract = ConvertPageContract(
                contract_version=CONVERT_PAGE_CONTRACT_VERSION,
                result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
                environment_identity=parent_job.environment_identity,
                document_id=run.document_id.value,
                processing_run_id=run.processing_run_id.value,
                page_number=route.page_number.value,
                route_name=route.route_name,
                routing_policy_version=route.routing_policy_version.value,
                source_artifact=source_artifact,
                expected_result_artifact=_result_artifact_identity(
                    environment=parent_job.environment,
                    processing_run_id=run.processing_run_id,
                    page_number=route.page_number.value,
                ),
                required_capacity=_capacity_for_route(route.route_name),
                locked_assets=self._locked_assets,
                idempotence_key=idempotence_key,
            )
            page_jobs.append(
                contract.to_job_request(
                    priority=parent_job.priority,
                    code_version=parent_job.idempotence_key.code_version,
                    model_version=parent_job.idempotence_key.model_version,
                )
            )
        plan = PageFanOutPlan(
            orchestration_version=DISTRIBUTED_PAGE_FAN_OUT_VERSION,
            document_id=run.document_id,
            processing_run_id=run.processing_run_id,
            page_manifest_sha256=manifest_hash,
            total_units=run.page_manifest.source_page_count,
            source_artifact=source_artifact,
            locked_assets=self._locked_assets,
            page_jobs=tuple(page_jobs),
            skipped_results=tuple(skipped_results),
        )
        created = self._page_fan_out_repository.persist_page_fan_out(
            plan,
            trace_id=_text(trace_id, "PAGE_FAN_OUT_TRACE_ID_INVALID"),
        )
        return FanOutDocumentPagesResult(
            created=created,
            total_units=plan.total_units,
            completed_units=len(plan.skipped_results),
            page_job_count=len(plan.page_jobs),
            page_manifest_sha256=plan.page_manifest_sha256,
        )


def _capacity_for_route(route_name: PageRouteName) -> ExecutionCapacityRequirement:
    if route_name in _GRANITE_ROUTES:
        return ExecutionCapacityRequirement(
            capability=ExecutionCapability.GRANITE_CUDA,
            slots=1,
            device="cuda:0",
        )
    return ExecutionCapacityRequirement(
        capability=ExecutionCapability.DOCUMENT_STANDARD,
        slots=0,
        device=None,
    )


def _result_artifact_identity(
    *,
    environment: str,
    processing_run_id: ProcessingRunId,
    page_number: int,
) -> LocalArtifactIdentity:
    relative_path = (
        f"processing-runs/{processing_run_id.value}/pages/{page_number:06d}.json"
    )
    return LocalArtifactIdentity(
        environment=environment,
        artifact_ref=f"artifact:source_processing.local/{environment}/{relative_path}",
        relative_path=relative_path,
    )


def _skip_completion_id(
    *,
    processing_run_id: ProcessingRunId,
    page_number: int,
    manifest_hash: str,
) -> str:
    digest = hashlib.sha256(
        f"{processing_run_id.value}|{page_number}|{manifest_hash}".encode("utf-8")
    ).hexdigest()
    return f"SKIP-M014-{digest[:32].upper()}"


def _job_request_mapping(request: JobRequest) -> dict[str, Any]:
    requirements = request.execution_requirements
    return {
        "environment": request.environment,
        "deployment_id": request.deployment_id,
        "job_name": request.job_name,
        "priority": request.priority.value,
        "idempotence": {
            "job_name": request.idempotence_key.job_name,
            "input_hash": request.idempotence_key.input_hash,
            "configuration_hash": request.idempotence_key.configuration_hash,
            "code_version": request.idempotence_key.code_version,
            "model_version": request.idempotence_key.model_version,
        },
        "execution_requirements": None
        if requirements is None
        else {
            "contract_name": requirements.contract_name,
            "contract_version": requirements.contract_version,
            "capacity_capability": requirements.capacity_capability,
            "capacity_slots": requirements.capacity_slots,
            "capacity_device": requirements.capacity_device,
            "storage_environment": requirements.storage_environment,
        },
        "payload": _json_value(request.payload),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_json_value(item) for item in value]
    return value


def _mapping(value: Any, fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        raise DistributionContractError("PAGE_FAN_OUT_PARENT_PAYLOAD_INVALID")
    return value


def _document_id(value: Any) -> DocumentId:
    try:
        return DocumentId.from_value(value)
    except ValueError as error:
        raise DistributionContractError("DOCUMENT_ID_INVALID") from error


def _processing_run_id(value: Any) -> ProcessingRunId:
    try:
        return ProcessingRunId.from_value(value)
    except ValueError as error:
        raise DistributionContractError("PROCESSING_RUN_ID_INVALID") from error


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise DistributionContractError(code)
    return value


__all__ = [
    "DISTRIBUTED_PAGE_FAN_OUT_VERSION",
    "LEGACY_INLINE_ORCHESTRATION_VERSION",
    "FanOutDocumentPagesHandler",
    "FanOutDocumentPagesResult",
    "PageFanOutPlan",
    "PageFanOutRepository",
    "ProcessingRunForFanOutRepository",
    "SkippedPageFanOutResult",
]
