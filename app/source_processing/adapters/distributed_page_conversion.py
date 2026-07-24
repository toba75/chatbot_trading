"""Adaptateur T-006 vers les convertisseurs réels déjà qualifiés par M-004."""

from __future__ import annotations

import dataclasses
import json
import subprocess
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any

import psutil

from app.contracts.technical_jobs import ClaimedJob
from app.platform.job_runtime.granite_capacity import (
    GraniteExecution,
    GraniteSlotLease,
)
from app.source_processing.adapters.docling_granite_conversion import (
    IsolatedGraniteDoclingConverter,
)
from app.source_processing.adapters.docling_native_conversion import (
    IsolatedNativeDoclingConverter,
)
from app.source_processing.adapters.gemma_vision_conversion import (
    IsolatedGemmaVisionPageConverter,
)
from app.source_processing.adapters.ocrmypdf_container import (
    OcrmyPdfPagePreprocessor,
)
from app.source_processing.application.convert_routed_pages import (
    PageConversionRequest,
    PagePreprocessingRequest,
)
from app.source_processing.application.execute_document_page import (
    PageConversionFailure,
    PageConversionOutput,
)
from app.source_processing.application.routed_document_conversion_worker import (
    _GranitePageConverter,
    _NativePageConverter,
)
from app.source_processing.application.targeted_enrichment import (
    TargetedEnrichmentPageConverter,
)
from app.source_processing.domain.distribution_contracts import (
    ConvertPageContract,
    ExecutionCapability,
    PageGpuMetrics,
    PageResultErrorCode,
    PageTechnicalMetrics,
)
from app.source_processing.domain.document_processing_run import (
    PageNumber,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import DocumentId


class _NoopHeartbeatControl:
    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None


class _PreAcquiredCapacityController:
    """Adapte le contrôleur M14 à un claim-slot déjà acquis atomiquement."""

    def __init__(
        self,
        *,
        capacity_controller: Any,
        lease: GraniteSlotLease,
    ) -> None:
        if not callable(
            getattr(capacity_controller, "execute_acquired_page_job", None)
        ):
            raise ValueError("GRANITE_PAGE_CAPACITY_CONTROLLER_INVALID")
        self._capacity_controller = capacity_controller
        self._lease = lease

    def execute_claimed_job(
        self,
        *,
        worker: Any,
        claimed_job: ClaimedJob,
        lease_seconds: int,
        heartbeat_seconds: float,
        start_model: Any,
    ) -> GraniteExecution[Any]:
        del worker
        if claimed_job != self._lease.claimed_job:
            raise ValueError("GRANITE_SLOT_CLAIM_DIVERGENT")
        return self._capacity_controller.execute_acquired_page_job(
            lease=self._lease,
            lease_seconds=lease_seconds,
            heartbeat_seconds=heartbeat_seconds,
            start_model=start_model,
        )


class M004RoutedPageConverter:
    """Exécute exactement la route M-003 sans modifier son choix."""

    def __init__(
        self,
        *,
        native_converter: IsolatedNativeDoclingConverter,
        granite_converter: IsolatedGraniteDoclingConverter,
        gemma_converter: IsolatedGemmaVisionPageConverter,
        capacity_controller: Any,
        granite_worker: Any,
        granite_lease_seconds: int,
        granite_heartbeat_seconds: float,
        ocrmypdf_manifest_path: Path,
        audit_root: Path,
        ocrmypdf_timeout_seconds: float,
        gateway_endpoint_url: str,
        gateway_timeout_seconds: int,
        gateway_max_output_tokens: int,
        expected_model_id: str,
    ) -> None:
        for dependency, method in (
            (native_converter, "convert"),
            (granite_converter, "start"),
            (gemma_converter, "start"),
            (capacity_controller, "execute_acquired_page_job"),
        ):
            if not callable(getattr(dependency, method, None)):
                raise ValueError("PAGE_CONVERTER_DEPENDENCY_INVALID")
        if not isinstance(ocrmypdf_manifest_path, Path) or not isinstance(
            audit_root, Path
        ):
            raise ValueError("PAGE_CONVERTER_PATH_INVALID")
        self._native_converter = native_converter
        self._granite_converter = granite_converter
        self._gemma_converter = gemma_converter
        self._capacity_controller = capacity_controller
        self._granite_worker = granite_worker
        self._granite_lease_seconds = granite_lease_seconds
        self._granite_heartbeat_seconds = granite_heartbeat_seconds
        self._ocrmypdf_manifest_path = ocrmypdf_manifest_path
        self._audit_root = audit_root
        self._ocrmypdf_timeout_seconds = ocrmypdf_timeout_seconds
        self._gateway_endpoint_url = gateway_endpoint_url
        self._gateway_timeout_seconds = gateway_timeout_seconds
        self._gateway_max_output_tokens = gateway_max_output_tokens
        self._expected_model_id = expected_model_id

    def convert_page(
        self,
        *,
        contract: ConvertPageContract,
        source_content: bytes,
        granite_lease: GraniteSlotLease | None,
    ) -> PageConversionOutput:
        if not isinstance(contract, ConvertPageContract):
            raise ValueError("CONVERT_PAGE_CONTRACT_INVALID")
        if not isinstance(source_content, bytes) or len(source_content) == 0:
            raise ValueError("PAGE_SOURCE_CONTENT_INVALID")
        requires_granite = (
            contract.required_capacity.capability is ExecutionCapability.GRANITE_CUDA
        )
        if requires_granite != isinstance(granite_lease, GraniteSlotLease):
            raise ValueError("GRANITE_SLOT_EXECUTION_VARIANT_INVALID")
        started = time.perf_counter()
        try:
            page_output = self._convert(
                contract=contract,
                source_content=source_content,
                granite_lease=granite_lease,
            )
            metrics = _technical_metrics(
                started=started,
                requires_granite=requires_granite,
            )
        except Exception as error:
            code = _known_error_code(error)
            if code is None:
                raise
            try:
                failure_metrics = _technical_metrics(
                    started=started,
                    requires_granite=requires_granite,
                )
            except RuntimeError as metrics_error:
                metrics_code = _known_error_code(metrics_error)
                if metrics_code is not PageResultErrorCode.GRANITE_CUDA_UNAVAILABLE:
                    raise
                code = metrics_code
                failure_metrics = _technical_metrics_without_gpu(started=started)
            raise PageConversionFailure(
                error_code=code,
                technical_metrics=failure_metrics,
            ) from error
        return PageConversionOutput(
            content=_serialize_page_output(page_output),
            tool_name=page_output.tool_name.value,
            tool_version=page_output.tool_version,
            technical_metrics=metrics,
        )

    def _convert(
        self,
        *,
        contract: ConvertPageContract,
        source_content: bytes,
        granite_lease: GraniteSlotLease | None,
    ) -> Any:
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-page-") as temporary:
            root = Path(temporary)
            source_path = root / "source.pdf"
            source_path.write_bytes(source_content)

            def resolve_original(artifact_ref: str) -> Path:
                if artifact_ref != contract.source_artifact.identity.artifact_ref:
                    raise ValueError("PAGE_SOURCE_ARTIFACT_REF_DIVERGENT")
                return source_path

            native = _NativePageConverter(
                converter=self._native_converter,
                resolve_source_path=resolve_original,
            )
            request = _conversion_request(
                contract=contract,
                source_artifact_ref=contract.source_artifact.identity.artifact_ref,
            )
            if contract.route_name is PageRouteName.NATIVE_STANDARD:
                return native.convert_page(request)
            if granite_lease is None:
                raise ValueError("GRANITE_SLOT_IDENTITY_REQUIRED")
            preprocessor = None
            if contract.route_name is PageRouteName.PREPROCESS_GRANITE:
                preprocessor = OcrmyPdfPagePreprocessor(
                    image_manifest_path=self._ocrmypdf_manifest_path,
                    audit_root=self._audit_root,
                    source_path_resolver=resolve_original,
                    timeout_seconds=self._ocrmypdf_timeout_seconds,
                )
                preprocessed = preprocessor.preprocess_page(
                    PagePreprocessingRequest(
                        processing_run_id=ProcessingRunId.from_value(
                            contract.processing_run_id
                        ),
                        document_id=DocumentId.from_value(contract.document_id),
                        page_number=PageNumber.from_value(contract.page_number),
                        route_name=contract.route_name,
                        routing_policy_version=RoutingPolicyVersion.from_value(
                            contract.routing_policy_version
                        ),
                        source_artifact_ref=contract.source_artifact.identity.artifact_ref,
                        expected_output_artifact_ref=(
                            "artifact:source_processing.page_conversion/"
                            f"{contract.processing_run_id}/"
                            f"page-{contract.page_number:03d}-preprocessed.pdf"
                        ),
                    )
                )
                request = _conversion_request(
                    contract=contract,
                    source_artifact_ref=preprocessed.artifact_ref,
                )

            def resolve_granite_source(artifact_ref: str) -> Path:
                if artifact_ref == contract.source_artifact.identity.artifact_ref:
                    return source_path
                if preprocessor is not None:
                    return preprocessor.path_for_artifact_ref(artifact_ref)
                raise ValueError("PAGE_SOURCE_ARTIFACT_REF_DIVERGENT")

            granite = _GranitePageConverter(
                granite_converter=self._granite_converter,
                gemma_converter=self._gemma_converter,
                capacity_controller=_PreAcquiredCapacityController(
                    capacity_controller=self._capacity_controller,
                    lease=granite_lease,
                ),
                granite_worker=self._granite_worker,
                claimed_job=granite_lease.claimed_job,
                lease_seconds=self._granite_lease_seconds,
                heartbeat_seconds=self._granite_heartbeat_seconds,
                job_heartbeat_control=_NoopHeartbeatControl(),
                resolve_source_path=resolve_granite_source,
                gateway_endpoint_url=self._gateway_endpoint_url,
                gateway_timeout_seconds=self._gateway_timeout_seconds,
                gateway_max_output_tokens=self._gateway_max_output_tokens,
                expected_model_id=self._expected_model_id,
            )
            if contract.route_name is PageRouteName.TARGETED_ENRICHMENT:
                return TargetedEnrichmentPageConverter(
                    native_converter=native,
                    granite_converter=granite,
                    policy_version="targeted-enrichment-v1",
                ).convert_page(request)
            return granite.convert_page(request)


def _conversion_request(
    *,
    contract: ConvertPageContract,
    source_artifact_ref: str,
) -> PageConversionRequest:
    return PageConversionRequest(
        processing_run_id=ProcessingRunId.from_value(contract.processing_run_id),
        document_id=DocumentId.from_value(contract.document_id),
        page_number=PageNumber.from_value(contract.page_number),
        route_name=contract.route_name,
        routing_policy_version=RoutingPolicyVersion.from_value(
            contract.routing_policy_version
        ),
        source_artifact_ref=source_artifact_ref,
        expected_output_artifact_ref=contract.expected_result_artifact.artifact_ref,
    )


def _serialize_page_output(value: Any) -> bytes:
    if not dataclasses.is_dataclass(value):
        raise ValueError("PAGE_CONVERSION_OUTPUT_INVALID")
    return json.dumps(
        _json_value(dataclasses.asdict(value)),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _technical_metrics(
    *,
    started: float,
    requires_granite: bool,
) -> PageTechnicalMetrics:
    duration = time.perf_counter() - started
    gpu = _gpu_metrics() if requires_granite else None
    return PageTechnicalMetrics(
        duration_seconds=duration,
        peak_ram_bytes=psutil.Process().memory_info().rss,
        gpu=gpu,
    )


def _gpu_metrics() -> PageGpuMetrics:
    completed = subprocess.run(
        (
            "nvidia-smi",
            "--id=0",
            "--query-gpu=memory.used,utilization.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("GRANITE_CUDA_UNAVAILABLE")
    fields = tuple(field.strip() for field in completed.stdout.strip().split(","))
    if len(fields) != 3:
        raise RuntimeError("GRANITE_CUDA_UNAVAILABLE")
    try:
        memory_mib, utilization, power = (float(field) for field in fields)
    except ValueError as error:
        raise RuntimeError("GRANITE_CUDA_UNAVAILABLE") from error
    return PageGpuMetrics(
        peak_vram_bytes=int(memory_mib * 1024**2),
        peak_utilization_percent=utilization,
        peak_power_watts=power,
    )


def _technical_metrics_without_gpu(*, started: float) -> PageTechnicalMetrics:
    return PageTechnicalMetrics(
        duration_seconds=time.perf_counter() - started,
        peak_ram_bytes=psutil.Process().memory_info().rss,
        gpu=None,
    )


def _known_error_code(error: Exception) -> PageResultErrorCode | None:
    candidate = getattr(error, "code", None)
    if not isinstance(candidate, str):
        candidate = str(error)
    try:
        return PageResultErrorCode(candidate)
    except ValueError:
        return None


__all__ = ["M004RoutedPageConverter"]
