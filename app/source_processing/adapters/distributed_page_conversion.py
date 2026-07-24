"""Adaptateur T-006 vers les convertisseurs réels déjà qualifiés par M-004."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import psutil

from app.contracts.technical_jobs import ClaimedJob
from app.platform.job_runtime.granite_capacity import (
    GraniteExecution,
    GraniteSlotLease,
)
from app.source_processing.adapters.docling_granite_conversion import (
    GraniteDoclingAssetManifest,
    IsolatedGraniteDoclingConverter,
)
from app.source_processing.adapters.docling_native_conversion import (
    DoclingAssetManifest,
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
    GranitePageConverter,
    NativePageConverter,
)
from app.source_processing.application.targeted_enrichment import (
    TargetedEnrichmentPageConverter,
)
from app.source_processing.domain.distribution_contracts import (
    ConvertPageContract,
    ExecutionCapability,
    LockedAssetVersion,
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


class _ResourcePeakSampler:
    """Échantillonne les pics du processus de conversion et de ses enfants."""

    def __init__(
        self,
        *,
        ram_sampler: Callable[[], int],
        gpu_sampler: Callable[[], PageGpuMetrics] | None,
        sample_interval_seconds: float,
    ) -> None:
        if not callable(ram_sampler):
            raise ValueError("PAGE_RAM_SAMPLER_INVALID")
        if gpu_sampler is not None and not callable(gpu_sampler):
            raise ValueError("PAGE_GPU_SAMPLER_INVALID")
        if (
            isinstance(sample_interval_seconds, bool)
            or not isinstance(sample_interval_seconds, int | float)
            or sample_interval_seconds <= 0
        ):
            raise ValueError("PAGE_RESOURCE_SAMPLE_INTERVAL_INVALID")
        self._ram_sampler = ram_sampler
        self._gpu_sampler = gpu_sampler
        self._sample_interval_seconds = float(sample_interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None
        self._peak_ram_bytes = 0
        self._peak_vram_bytes = 0
        self._peak_gpu_utilization_percent = 0.0
        self._peak_gpu_power_watts = 0.0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("PAGE_RESOURCE_SAMPLER_ALREADY_STARTED")
        self._sample()
        self._thread = threading.Thread(
            target=self._run,
            name="sp-page-resource-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, started: float) -> PageTechnicalMetrics:
        thread = self._thread
        if thread is None:
            raise RuntimeError("PAGE_RESOURCE_SAMPLER_NOT_STARTED")
        self._stop.set()
        thread.join(timeout=max(12.0, self._sample_interval_seconds * 4))
        if thread.is_alive():
            raise RuntimeError("PAGE_RESOURCE_SAMPLER_STOP_TIMEOUT")
        if self._error is None:
            self._sample()
        if self._error is not None:
            raise self._error
        return self._metrics(started=started, include_gpu=True)

    def metrics_without_gpu(self, *, started: float) -> PageTechnicalMetrics:
        return self._metrics(started=started, include_gpu=False)

    def _run(self) -> None:
        while not self._stop.wait(self._sample_interval_seconds):
            try:
                self._sample()
            except Exception as error:
                self._error = error
                self._stop.set()
                return

    def _sample(self) -> None:
        ram_bytes = self._ram_sampler()
        if isinstance(ram_bytes, bool) or not isinstance(ram_bytes, int) or ram_bytes < 1:
            raise RuntimeError("PAGE_RAM_SAMPLE_INVALID")
        self._peak_ram_bytes = max(self._peak_ram_bytes, ram_bytes)
        if self._gpu_sampler is None:
            return
        gpu = self._gpu_sampler()
        self._peak_vram_bytes = max(self._peak_vram_bytes, gpu.peak_vram_bytes)
        self._peak_gpu_utilization_percent = max(
            self._peak_gpu_utilization_percent,
            gpu.peak_utilization_percent,
        )
        self._peak_gpu_power_watts = max(
            self._peak_gpu_power_watts,
            gpu.peak_power_watts,
        )

    def _metrics(self, *, started: float, include_gpu: bool) -> PageTechnicalMetrics:
        gpu = None
        if include_gpu and self._gpu_sampler is not None:
            gpu = PageGpuMetrics(
                peak_vram_bytes=self._peak_vram_bytes,
                peak_utilization_percent=self._peak_gpu_utilization_percent,
                peak_power_watts=self._peak_gpu_power_watts,
            )
        return PageTechnicalMetrics(
            duration_seconds=time.perf_counter() - started,
            peak_ram_bytes=self._peak_ram_bytes,
            gpu=gpu,
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
        source_path: Path,
        granite_lease: GraniteSlotLease | None,
    ) -> PageConversionOutput:
        if not isinstance(contract, ConvertPageContract):
            raise ValueError("CONVERT_PAGE_CONTRACT_INVALID")
        if not isinstance(source_path, Path) or not source_path.is_file():
            raise ValueError("PAGE_SOURCE_PATH_INVALID")
        requires_granite = (
            contract.required_capacity.capability is ExecutionCapability.GRANITE_CUDA
        )
        if requires_granite != isinstance(granite_lease, GraniteSlotLease):
            raise ValueError("GRANITE_SLOT_EXECUTION_VARIANT_INVALID")
        started = time.perf_counter()
        sampler = _ResourcePeakSampler(
            ram_sampler=_process_tree_rss,
            gpu_sampler=_gpu_metrics if requires_granite else None,
            sample_interval_seconds=0.1,
        )
        try:
            sampler.start()
        except Exception as error:
            code = _known_error_code(error)
            if code is None:
                raise
            raise PageConversionFailure(
                error_code=code,
                technical_metrics=sampler.metrics_without_gpu(started=started),
            ) from error
        conversion_error: BaseException | None = None
        page_output = None
        try:
            page_output = self._convert(
                contract=contract,
                source_path=source_path,
                granite_lease=granite_lease,
            )
        except BaseException as error:
            conversion_error = error
        sampling_error: Exception | None = None
        try:
            metrics = sampler.stop(started=started)
        except Exception as error:
            sampling_error = error
            metrics = sampler.metrics_without_gpu(started=started)
        terminal_error = sampling_error or conversion_error
        if terminal_error is not None:
            if not isinstance(terminal_error, Exception):
                raise terminal_error
            code = _known_error_code(terminal_error)
            if code is None:
                raise terminal_error
            raise PageConversionFailure(
                error_code=code,
                technical_metrics=metrics,
            ) from terminal_error
        if page_output is None:
            raise RuntimeError("PAGE_CONVERSION_OUTPUT_ABSENT")
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
        source_path: Path,
        granite_lease: GraniteSlotLease | None,
    ) -> Any:
        def resolve_original(artifact_ref: str) -> Path:
            if artifact_ref != contract.source_artifact.identity.artifact_ref:
                raise ValueError("PAGE_SOURCE_ARTIFACT_REF_DIVERGENT")
            return source_path

        native = NativePageConverter(
            converter=self._native_converter,
            resolve_source_path=resolve_original,
        )
        request = _conversion_request(
            contract=contract,
            source_artifact_ref=contract.source_artifact.identity.artifact_ref,
            source_sha256=contract.source_artifact.sha256,
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
                source_sha256=preprocessed.artifact_hash,
            )

        def resolve_granite_source(artifact_ref: str) -> Path:
            if artifact_ref == contract.source_artifact.identity.artifact_ref:
                return source_path
            if preprocessor is not None:
                return preprocessor.path_for_artifact_ref(artifact_ref)
            raise ValueError("PAGE_SOURCE_ARTIFACT_REF_DIVERGENT")

        granite = GranitePageConverter(
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
    source_sha256: str,
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
        source_sha256=source_sha256,
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


def _process_tree_rss() -> int:
    process = psutil.Process()
    rss = process.memory_info().rss
    for child in process.children(recursive=True):
        try:
            rss += child.memory_info().rss
        except psutil.NoSuchProcess:
            continue
    return rss


def _gpu_metrics() -> PageGpuMetrics:
    try:
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
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("GRANITE_CUDA_UNAVAILABLE") from error
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


def _known_error_code(error: Exception) -> PageResultErrorCode | None:
    if isinstance(error, ExceptionGroup):
        for nested in error.exceptions:
            if isinstance(nested, Exception):
                code = _known_error_code(nested)
                if code is not None:
                    return code
        return None
    candidate = getattr(error, "code", None)
    if not isinstance(candidate, str):
        candidate = str(error)
    try:
        return PageResultErrorCode(candidate)
    except ValueError:
        return None


def load_runtime_locked_assets(
    *,
    native_manifest_path: Path,
    native_assets_root: Path,
    granite_manifest_path: Path,
    granite_assets_root: Path,
    ocrmypdf_manifest_path: Path,
) -> tuple[LockedAssetVersion, ...]:
    native = DoclingAssetManifest.load(
        manifest_path=native_manifest_path,
        assets_root=native_assets_root,
    )
    granite = GraniteDoclingAssetManifest.load(
        manifest_path=granite_manifest_path,
        assets_root=granite_assets_root,
    )
    try:
        ocr_payload = json.loads(ocrmypdf_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("CONVERSION_ASSET_MANIFEST_INVALID") from error
    if not isinstance(ocr_payload, dict) or set(ocr_payload) != {
        "schema_version",
        "tool",
        "tool_version",
        "image_reference",
    }:
        raise ValueError("CONVERSION_ASSET_MANIFEST_INVALID")
    return (
        LockedAssetVersion(
            name="docling-native",
            version=native.tool_version,
            sha256=hashlib.sha256(native_manifest_path.read_bytes()).hexdigest(),
        ),
        LockedAssetVersion(
            name="docling-granite",
            version=f"{granite.tool_version}@{granite.model_revision}",
            sha256=hashlib.sha256(granite_manifest_path.read_bytes()).hexdigest(),
        ),
        LockedAssetVersion(
            name="ocrmypdf-image",
            version=str(ocr_payload["image_reference"]),
            sha256=hashlib.sha256(ocrmypdf_manifest_path.read_bytes()).hexdigest(),
        ),
    )


__all__ = ["M004RoutedPageConverter", "load_runtime_locked_assets"]
