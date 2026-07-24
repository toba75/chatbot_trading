"""Worker M-004 de toutes les routes M-003, sans conversion de remplacement."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.contracts.technical_jobs import ClaimedJob, GraniteModelStillRunning, JobStatus
from app.source_processing.adapters.docling_granite_conversion import (
    GraniteDoclingConversionError,
    GraniteDoclingConversionRequest,
    IsolatedGraniteDoclingConverter,
)
from app.source_processing.adapters.gemma_vision_conversion import (
    GEMMA_DENSE_RENDER_SEGMENT_COUNT,
    GemmaVisionConversionError,
    GemmaVisionConversionRequest,
    GemmaVisionConversionResponse,
    GemmaVisionPageItem,
    IsolatedGemmaVisionPageConverter,
)
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactStoreError,
    DoclingAssetManifestError,
    DoclingNativeConversionError,
    IsolatedNativeDoclingConverter,
    NativeDoclingConversionRequest,
    NativeDoclingConversionResponse,
)
from app.source_processing.adapters.ocrmypdf_container import (
    OcrmyPdfContainerError,
    OcrmyPdfImageManifestError,
    OcrmyPdfPagePreprocessor,
)
from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesCommand,
    ConvertRoutedPagesHandler,
    PageConversionRequest,
)
from app.source_processing.application.concurrency_limited_page_converter import (
    ConcurrencyLimitedPageConverter,
    SharedPageConversionCapacity,
)
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_worker import WorkerProcessingError
from app.source_processing.application.granite_gemma_recovery import (
    GEMMA_RECOVERY_GRANITE_ERROR_CODES,
    GraniteConversionFailure,
)
from app.source_processing.application.targeted_enrichment import (
    TargetedEnrichmentPageConverter,
)
from app.source_processing.application.native_document_conversion_worker import (
    NativeCanonicalPublication,
)
from app.source_processing.application.publish_canonical_source import (
    CanonicalArtifactStore,
    PublishCanonicalSourceCommand,
    PublishCanonicalSourceHandler,
)
from app.source_processing.domain.document_processing_run import (
    ManualReviewDecisionType,
    PageDecisionState,
    PageNumber,
    PageRouteName,
)
from app.source_processing.domain.page_conversion import (
    CanonicalAcceptancePolicy,
    ConversionToolName,
    CriticalPageSamplingPolicy,
    PageConversionArtifact,
    PageConversionFallbackTrace,
    PageConversionCandidate,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PreConversionQualityReport,
    PreConversionRouteComparison,
    QualityDecisionStatus,
    SkippedEmptyPage,
    SkippedEmptyPageSource,
    TextAuthorityManifest,
    TextAuthoritySelectionPolicy,
)
from app.source_processing.domain.source_document import DocumentId


NON_NATIVE_TERMINAL_ERROR_CODES = frozenset(
    {
        "GRANITE_DOCLING_UNAVAILABLE",
        "OCRMYPDF_UNAVAILABLE",
        "CONVERSION_ASSET_MANIFEST_INVALID",
        "DOCLING_PAGE_MANIFEST_MISMATCH",
        "DOCLING_PROVENANCE_MISSING",
        "GEMMA_VISION_UNAVAILABLE",
        "GEMMA_VISION_OUTPUT_INVALID",
        "GEMMA_VISION_OUTPUT_TRUNCATED",
        "GEMMA_VISION_MODEL_MISMATCH",
        "GEMMA_VISION_RENDERING_FAILED",
        "GEMMA_VISION_IMAGE_TOO_LARGE",
    }
)


class OriginalPathResolver(Protocol):
    def resolve_internal_path(self, storage_ref: Any) -> Path:
        """Résout l'original privé depuis le seul bounded context SP."""


class GraniteSlotLease(Protocol):
    """Lease opaque fournie par l'adaptateur de capacité au cas d'usage SP."""

    claimed_job: ClaimedJob


class GraniteWorker(Protocol):
    """Identité opaque du worker enregistré par la composition technique."""

    worker_instance_id: str


class GraniteExecution(Protocol):
    """Résultat d'un appel modèle supervisé par la capacité technique."""

    model_result: Any


class GraniteCapacityController(Protocol):
    """Port applicatif vers la capacité Granite durable de la plateforme."""

    def execute_claimed_job(
        self,
        *,
        worker: GraniteWorker,
        claimed_job: ClaimedJob,
        lease_seconds: int,
        heartbeat_seconds: float,
        start_model: Callable[[GraniteSlotLease], Any],
    ) -> GraniteExecution:
        """Exécute un modèle seulement sous le double fencing actif."""


class JobHeartbeatControl(Protocol):
    """Transfère temporairement l'autorité au heartbeat du double fencing."""

    def pause(self) -> None: ...

    def resume(self) -> None: ...


class RoutedConversionRepository(Protocol):
    def find_conversion_by_document_id(
        self, document_id: DocumentId
    ) -> DocumentConversionState | None:
        """Lit l'état durable de conversion."""

    def complete_native_conversion(
        self, publication: NativeCanonicalPublication
    ) -> None:
        """Persiste une unique publication canonique, quelle que soit sa route."""

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        """Persiste RUNNING avant tout processus d'outil."""

    def record_conversion_progress(
        self, *, document_id: DocumentId, completed_units: int
    ) -> None:
        """Persiste chaque page réellement convertie avant la lecture publique."""

    def reject_native_conversion(
        self, *, document_id: DocumentId, error_code: str
    ) -> None:
        """Persiste un échec terminal sans route de secours."""


class _ConversionProgressRecorder:
    """Rejoue une reprise sans faire régresser le compteur public persistant."""

    def __init__(
        self,
        *,
        conversion_repository: RoutedConversionRepository,
        document_id: DocumentId,
        persisted_completed_units: int,
        skipped_empty_page_count: int,
    ) -> None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        for value, error_message in (
            (persisted_completed_units, "progression persistée invalide"),
            (skipped_empty_page_count, "pages vides ignorées invalides"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(error_message)
        if (
            persisted_completed_units != 0
            and persisted_completed_units < skipped_empty_page_count
        ):
            raise ValueError("progression persistée antérieure aux pages vides")
        self._conversion_repository = conversion_repository
        self._document_id = document_id
        self._lock = threading.Lock()
        self._completed_units = persisted_completed_units
        self._replayed_page_count = max(
            0,
            persisted_completed_units - skipped_empty_page_count,
        )
        if persisted_completed_units == 0 and skipped_empty_page_count > 0:
            self._completed_units = skipped_empty_page_count
            self._conversion_repository.record_conversion_progress(
                document_id=self._document_id,
                completed_units=skipped_empty_page_count,
            )

    def record_page(self, page_output: object) -> None:
        del page_output
        with self._lock:
            if self._replayed_page_count > 0:
                self._replayed_page_count -= 1
                return
            self._completed_units += 1
            self._conversion_repository.record_conversion_progress(
                document_id=self._document_id,
                completed_units=self._completed_units,
            )


class _NativePageConverter:
    def __init__(
        self,
        *,
        converter: IsolatedNativeDoclingConverter,
        resolve_source_path: Callable[[str], Path],
    ) -> None:
        self._converter = converter
        self._resolve_source_path = resolve_source_path

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        source_path = self._resolve_source_path(request.source_artifact_ref)
        response = self._converter.convert(
            NativeDoclingConversionRequest(
                document_id=request.document_id.value,
                processing_run_id=request.processing_run_id.value,
                source_sha256=_sha256_file(source_path),
                source_pdf_path=source_path,
                expected_page_numbers=(request.page_number.value,),
                routing_policy_version=request.routing_policy_version.value,
            )
        )
        return _page_output(
            response=response,
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.DOCLING_STANDARD,
            expected_artifact_ref=request.expected_output_artifact_ref,
        )


class _GranitePageConverter:
    """Route Granite/Gemma dont chaque processus exige une lease PostgreSQL active."""

    def __init__(
        self,
        *,
        granite_converter: IsolatedGraniteDoclingConverter,
        gemma_converter: IsolatedGemmaVisionPageConverter,
        capacity_controller: GraniteCapacityController,
        granite_worker: GraniteWorker,
        claimed_job: ClaimedJob,
        lease_seconds: int,
        heartbeat_seconds: float,
        job_heartbeat_control: JobHeartbeatControl,
        resolve_source_path: Callable[[str], Path],
        gateway_endpoint_url: str,
        gateway_timeout_seconds: int,
        gateway_max_output_tokens: int,
        expected_model_id: str,
    ) -> None:
        self._granite_converter = granite_converter
        self._gemma_converter = gemma_converter
        self._capacity_controller = capacity_controller
        self._granite_worker = granite_worker
        self._claimed_job = claimed_job
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._job_heartbeat_control = job_heartbeat_control
        self._resolve_source_path = resolve_source_path
        self._gateway_endpoint_url = gateway_endpoint_url
        self._gateway_timeout_seconds = gateway_timeout_seconds
        self._gateway_max_output_tokens = gateway_max_output_tokens
        self._expected_model_id = expected_model_id

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        source_path = self._resolve_source_path(request.source_artifact_ref)
        self._job_heartbeat_control.pause()
        try:
            execution = self._capacity_controller.execute_claimed_job(
                worker=self._granite_worker,
                claimed_job=self._claimed_job,
                lease_seconds=self._lease_seconds,
                heartbeat_seconds=self._heartbeat_seconds,
                start_model=lambda lease: _RunningGraniteRouteConversion(
                    lease=lease,
                    request=request,
                    source_path=source_path,
                    granite_converter=self._granite_converter,
                    gemma_converter=self._gemma_converter,
                    gateway_endpoint_url=self._gateway_endpoint_url,
                    gateway_timeout_seconds=self._gateway_timeout_seconds,
                    gateway_max_output_tokens=self._gateway_max_output_tokens,
                    expected_model_id=self._expected_model_id,
                ),
            )
        finally:
            self._job_heartbeat_control.resume()
        return execution.model_result


class _RunningGraniteRouteConversion:
    """Séquence Granite puis Gemma, conservée sous la même double fencing."""

    def __init__(
        self,
        *,
        lease: GraniteSlotLease,
        request: PageConversionRequest,
        source_path: Path,
        granite_converter: IsolatedGraniteDoclingConverter,
        gemma_converter: IsolatedGemmaVisionPageConverter,
        gateway_endpoint_url: str,
        gateway_timeout_seconds: int,
        gateway_max_output_tokens: int,
        expected_model_id: str,
    ) -> None:
        self._lease = lease
        self._request = request
        self._source_path = source_path
        self._gemma_converter = gemma_converter
        self._gateway_endpoint_url = gateway_endpoint_url
        self._gateway_timeout_seconds = gateway_timeout_seconds
        self._gateway_max_output_tokens = gateway_max_output_tokens
        self._expected_model_id = expected_model_id
        self._state = "granite"
        self._granite_error_code: str | None = None
        self._segment_responses: list[GemmaVisionConversionResponse] = []
        self._active_process = granite_converter.start(
            GraniteDoclingConversionRequest(
                document_id=request.document_id.value,
                processing_run_id=request.processing_run_id.value,
                source_sha256=_sha256_file(source_path),
                source_pdf_path=source_path,
                page_number=request.page_number.value,
                source_page_number=_source_page_number(request),
                route_name=request.route_name.value,
                routing_policy_version=request.routing_policy_version.value,
            ),
            lease=lease,
        )

    def wait(self, *, timeout_seconds: float) -> PageConversionArtifact:
        if self._state == "granite":
            try:
                response = self._active_process.wait(timeout_seconds=timeout_seconds)
            except GraniteDoclingConversionError as error:
                if error.code not in GEMMA_RECOVERY_GRANITE_ERROR_CODES:
                    raise GraniteConversionFailure(error.code) from error
                self._granite_error_code = error.code
                self._start_gemma(rotation=0)
                raise GraniteModelStillRunning() from error
            return _page_output(
                response=response,
                page_number=self._request.page_number,
                route_name=self._request.route_name,
                tool_name=ConversionToolName.GRANITE_DOCLING,
                expected_artifact_ref=self._request.expected_output_artifact_ref,
            )
        try:
            gemma_response = self._active_process.wait(timeout_seconds=timeout_seconds)
        except GemmaVisionConversionError as error:
            if (
                self._state == "gemma-initial"
                and error.code == "GEMMA_VISION_OUTPUT_INVALID"
            ):
                self._start_gemma(rotation=90)
                raise GraniteModelStillRunning() from error
            if (
                self._state == "gemma-rotated"
                and error.code == "GEMMA_VISION_OUTPUT_TRUNCATED"
            ):
                self._start_segment(1)
                raise GraniteModelStillRunning() from error
            raise
        if self._state == "gemma-segment":
            self._segment_responses.append(gemma_response)
            next_segment = len(self._segment_responses) + 1
            if next_segment <= GEMMA_DENSE_RENDER_SEGMENT_COUNT:
                self._start_segment(next_segment)
                raise GraniteModelStillRunning()
            gemma_response = _merge_gemma_segment_responses(
                tuple(self._segment_responses)
            )
        if self._granite_error_code is None:
            raise RuntimeError("GRANITE_PRIMARY_ERROR_ABSENT")
        return _gemma_page_output(
            response=gemma_response,
            page_number=self._request.page_number,
            route_name=self._request.route_name,
            expected_artifact_ref=self._request.expected_output_artifact_ref,
            granite_error_code=self._granite_error_code,
        )

    def terminate(self) -> None:
        self._active_process.terminate()

    def _start_gemma(self, *, rotation: int) -> None:
        self._state = "gemma-initial" if rotation == 0 else "gemma-rotated"
        self._active_process = self._gemma_converter.start(
            self._gemma_request(render_rotation_degrees=rotation),
            lease=self._lease,
        )

    def _start_segment(self, segment_index: int) -> None:
        self._state = "gemma-segment"
        self._active_process = self._gemma_converter.start(
            self._gemma_request(
                render_rotation_degrees=90,
                render_segment_index=segment_index,
                render_segment_count=GEMMA_DENSE_RENDER_SEGMENT_COUNT,
            ),
            lease=self._lease,
        )

    def _gemma_request(
        self,
        *,
        render_rotation_degrees: int,
        render_segment_index: int | None = None,
        render_segment_count: int | None = None,
    ) -> GemmaVisionConversionRequest:
        return GemmaVisionConversionRequest(
            document_id=self._request.document_id.value,
            processing_run_id=self._request.processing_run_id.value,
            source_sha256=_sha256_file(self._source_path),
            source_pdf_path=self._source_path,
            page_number=self._request.page_number.value,
            source_page_number=_source_page_number(self._request),
            route_name=self._request.route_name.value,
            routing_policy_version=self._request.routing_policy_version.value,
            gateway_endpoint_url=self._gateway_endpoint_url,
            gateway_timeout_seconds=self._gateway_timeout_seconds,
            max_output_tokens=self._gateway_max_output_tokens,
            expected_model_id=self._expected_model_id,
            render_rotation_degrees=render_rotation_degrees,
            render_segment_index=render_segment_index,
            render_segment_count=render_segment_count,
        )


def _source_page_number(request: PageConversionRequest) -> int:
    return (
        1
        if request.source_artifact_ref.startswith(
            "artifact:source_processing.page_conversion/"
        )
        else request.page_number.value
    )


def _merge_gemma_segment_responses(
    responses: tuple[GemmaVisionConversionResponse, ...],
) -> GemmaVisionConversionResponse:
    if len(responses) != GEMMA_DENSE_RENDER_SEGMENT_COUNT:
        raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
    base_version: str | None = None
    items: list[GemmaVisionPageItem] = []
    for segment_index, response in enumerate(responses, start=1):
        suffix = (
            f";render-segment-{segment_index:02d}-"
            f"of-{GEMMA_DENSE_RENDER_SEGMENT_COUNT:02d}"
        )
        if not response.tool_version.endswith(suffix):
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        response_base_version = response.tool_version.removesuffix(suffix)
        if base_version is None:
            base_version = response_base_version
        elif response_base_version != base_version:
            raise GemmaVisionConversionError("GEMMA_VISION_MODEL_MISMATCH")
        items.extend(response.items)
    if base_version is None:
        raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
    return GemmaVisionConversionResponse(
        tool_version=(
            f"{base_version};render-segments-{GEMMA_DENSE_RENDER_SEGMENT_COUNT:02d}"
        ),
        items=tuple(items),
    )


class _NoOcrPreprocessor:
    """Port présent pour le handler, mais impossible à appeler hors PREPROCESS_GRANITE."""

    def preprocess_page(self, request: Any) -> Any:
        raise ValueError("OCRmyPDF hors route PREPROCESS_GRANITE")


class RoutedDocumentConversionWorker:
    """Exécute l'outil imposé par chaque PageRoute de M-003 et publie seulement à la fin."""

    def __init__(
        self,
        *,
        source_document_repository: Any,
        processing_run_repository: Any,
        conversion_repository: RoutedConversionRepository,
        original_source_store: OriginalPathResolver,
        native_converter: IsolatedNativeDoclingConverter,
        granite_converter: IsolatedGraniteDoclingConverter,
        gemma_converter: IsolatedGemmaVisionPageConverter,
        granite_capacity_controller: GraniteCapacityController,
        granite_worker: GraniteWorker,
        granite_lease_seconds: int,
        granite_heartbeat_seconds: float,
        job_heartbeat_control: JobHeartbeatControl,
        llm_gateway_url: str,
        llm_gateway_timeout_seconds: int,
        llm_gateway_max_output_tokens: int,
        expected_gemma_model_id: str,
        ocrmypdf_manifest_path: Path,
        audit_root: Path,
        ocrmypdf_timeout_seconds: float,
        artifact_store: CanonicalArtifactStore,
        max_parallel_pages: int,
        docling_max_concurrency: int,
        granite_max_concurrency: int,
    ) -> None:
        for dependency, method in (
            (source_document_repository, "find_by_document_id"),
            (processing_run_repository, "find_by_document_id"),
            (conversion_repository, "find_conversion_by_document_id"),
            (conversion_repository, "begin_native_conversion"),
            (conversion_repository, "record_conversion_progress"),
            (conversion_repository, "complete_native_conversion"),
            (conversion_repository, "reject_native_conversion"),
            (original_source_store, "resolve_internal_path"),
            (native_converter, "convert"),
            (granite_converter, "start"),
            (gemma_converter, "start"),
            (granite_capacity_controller, "execute_claimed_job"),
            (job_heartbeat_control, "pause"),
            (job_heartbeat_control, "resume"),
            (artifact_store, "store_docling_json"),
        ):
            if not callable(getattr(dependency, method, None)):
                raise ValueError(f"dépendance conversion routée invalide: {method}")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._conversion_repository = conversion_repository
        self._original_source_store = original_source_store
        self._native_converter = native_converter
        self._granite_converter = granite_converter
        self._gemma_converter = gemma_converter
        self._granite_capacity_controller = granite_capacity_controller
        self._granite_worker = granite_worker
        self._granite_lease_seconds = _required_positive_int(
            granite_lease_seconds,
            "durée de lease Granite invalide",
        )
        if (
            isinstance(granite_heartbeat_seconds, bool)
            or not isinstance(granite_heartbeat_seconds, int | float)
            or granite_heartbeat_seconds <= 0
            or granite_heartbeat_seconds >= granite_lease_seconds
        ):
            raise ValueError("heartbeat Granite invalide")
        self._granite_heartbeat_seconds = float(granite_heartbeat_seconds)
        self._job_heartbeat_control = job_heartbeat_control
        self._llm_gateway_url = _required_gateway_url(llm_gateway_url)
        self._llm_gateway_timeout_seconds = _required_positive_int(
            llm_gateway_timeout_seconds,
            "timeout gateway LLM invalide",
        )
        self._llm_gateway_max_output_tokens = _required_positive_int(
            llm_gateway_max_output_tokens,
            "maximum de sortie gateway LLM invalide",
        )
        self._expected_gemma_model_id = _required_text_value(
            expected_gemma_model_id,
            "modèle Gemma attendu invalide",
        )
        self._ocrmypdf_manifest_path = ocrmypdf_manifest_path
        self._audit_root = audit_root
        self._ocrmypdf_timeout_seconds = ocrmypdf_timeout_seconds
        self._artifact_store = artifact_store
        self._max_parallel_pages = _required_positive_int(
            max_parallel_pages,
            "parallélisme conversion invalide",
        )
        self._docling_max_concurrency = _required_positive_int(
            docling_max_concurrency,
            "parallélisme Docling invalide",
        )
        self._granite_max_concurrency = _required_positive_int(
            granite_max_concurrency,
            "parallélisme Granite invalide",
        )
        if self._docling_max_concurrency > self._max_parallel_pages:
            raise ValueError("parallélisme Docling supérieur au parallélisme des pages")
        if self._granite_max_concurrency > self._max_parallel_pages:
            raise ValueError("parallélisme Granite supérieur au parallélisme des pages")
        if self._granite_max_concurrency > self._docling_max_concurrency:
            raise ValueError("parallélisme Granite supérieur à la capacité Docling")

    def execute(self, claimed_job: ClaimedJob) -> Mapping[str, Any]:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        job = claimed_job.job
        if (
            job.status is not JobStatus.RUNNING
            or job.request.job_name != "CONVERT_DOCUMENT"
        ):
            raise ValueError("job CONVERT_DOCUMENT running requis")
        payload = dict(job.request.payload)
        document_id = DocumentId.from_value(_required_text(payload, "document_id"))
        processing_run_id = _required_text(payload, "processing_run_id")
        source_sha256 = _required_text(payload, "source_sha256")
        routing_policy_version = _required_text(payload, "routing_policy_version")
        source_document, processing_run, conversion = self._load_executable_state(
            document_id=document_id,
            processing_run_id=processing_run_id,
            source_sha256=source_sha256,
            routing_policy_version=routing_policy_version,
        )
        if conversion.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED:
            return {
                "document_id": document_id.value,
                "conversion_status": conversion.conversion_status.value,
                "canonical_version_id": conversion.canonical_version_id,
            }
        self._conversion_repository.begin_native_conversion(document_id=document_id)
        original_path = self._original_source_store.resolve_internal_path(
            source_document.original_storage_ref
        )

        def resolve_original_path(artifact_ref: str) -> Path:
            if artifact_ref != source_document.original_storage_ref.value:
                raise ValueError("référence originale OCRmyPDF incohérente")
            return original_path

        has_preprocess_route = any(
            route.route_name is PageRouteName.PREPROCESS_GRANITE
            for route in processing_run.route_plan.page_routes
        )
        if has_preprocess_route:
            try:
                preprocessor = OcrmyPdfPagePreprocessor(
                    image_manifest_path=self._ocrmypdf_manifest_path,
                    audit_root=self._audit_root,
                    source_path_resolver=resolve_original_path,
                    timeout_seconds=self._ocrmypdf_timeout_seconds,
                )
            except (OcrmyPdfImageManifestError, OcrmyPdfContainerError) as error:
                raise WorkerProcessingError(str(error), retryable=False) from error

            def resolve_source_path(artifact_ref: str) -> Path:
                if artifact_ref == source_document.original_storage_ref.value:
                    return original_path
                return preprocessor.path_for_artifact_ref(artifact_ref)
        else:
            preprocessor = _NoOcrPreprocessor()

            def resolve_source_path(artifact_ref: str) -> Path:
                if artifact_ref != source_document.original_storage_ref.value:
                    raise ValueError("référence source de conversion incohérente")
                return original_path

        try:
            docling_capacity = SharedPageConversionCapacity(
                max_concurrency=self._docling_max_concurrency,
            )
            raw_native_page_converter = _NativePageConverter(
                converter=self._native_converter,
                resolve_source_path=resolve_source_path,
            )
            native_page_converter = docling_capacity.limit(
                page_converter=raw_native_page_converter,
            )
            raw_granite_page_converter = _GranitePageConverter(
                granite_converter=self._granite_converter,
                gemma_converter=self._gemma_converter,
                capacity_controller=self._granite_capacity_controller,
                granite_worker=self._granite_worker,
                claimed_job=claimed_job,
                lease_seconds=self._granite_lease_seconds,
                heartbeat_seconds=self._granite_heartbeat_seconds,
                job_heartbeat_control=self._job_heartbeat_control,
                resolve_source_path=resolve_source_path,
                gateway_endpoint_url=self._llm_gateway_url,
                gateway_timeout_seconds=self._llm_gateway_timeout_seconds,
                gateway_max_output_tokens=self._llm_gateway_max_output_tokens,
                expected_model_id=self._expected_gemma_model_id,
            )
            granite_page_converter = ConcurrencyLimitedPageConverter(
                page_converter=docling_capacity.limit(
                    page_converter=raw_granite_page_converter,
                ),
                max_concurrency=self._granite_max_concurrency,
            )
            handler = ConvertRoutedPagesHandler(
                native_converter=native_page_converter,
                granite_converter=granite_page_converter,
                targeted_enrichment_converter=TargetedEnrichmentPageConverter(
                    native_converter=native_page_converter,
                    granite_converter=granite_page_converter,
                    policy_version="targeted-enrichment-v1",
                ),
                ocrmypdf_preprocessor=preprocessor,
                max_parallel_pages=self._max_parallel_pages,
            )
            skipped_empty_page_count = sum(
                1
                for route in processing_run.route_plan.page_routes
                if route.route_name is PageRouteName.SKIP_EMPTY
            )
            progress_recorder = _ConversionProgressRecorder(
                conversion_repository=self._conversion_repository,
                document_id=document_id,
                persisted_completed_units=conversion.completed_units,
                skipped_empty_page_count=skipped_empty_page_count,
            )

            result = handler.handle(
                ConvertRoutedPagesCommand(
                    source_document=source_document,
                    processing_run=processing_run,
                    canonical_version_id=_canonical_version_id(source_sha256),
                ),
                on_page_converted=progress_recorder.record_page,
            )
        except (DoclingAssetManifestError, OcrmyPdfImageManifestError) as error:
            raise WorkerProcessingError(
                "CONVERSION_ASSET_MANIFEST_INVALID", retryable=False
            ) from error
        except (
            DoclingNativeConversionError,
            GraniteDoclingConversionError,
            GraniteConversionFailure,
            GemmaVisionConversionError,
            OcrmyPdfContainerError,
        ) as error:
            raise WorkerProcessingError(
                getattr(error, "code", str(error)), retryable=False
            ) from error
        except ValueError as error:
            raise WorkerProcessingError(
                "DOCLING_PAGE_MANIFEST_MISMATCH", retryable=False
            ) from error

        authority_manifest = _authority_manifest(
            processing_run=processing_run,
            page_outputs=result.page_outputs,
        )
        docling_document = result.docling_document
        quality_policy = CanonicalAcceptancePolicy(
            policy_version="m004-routed-docling-v1"
        )
        pre_report = _pre_conversion_report(
            processing_run=processing_run, policy_version=quality_policy.policy_version
        )
        post_report = quality_policy.evaluate_post_conversion(
            page_manifest=processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
            docling_document=docling_document,
            findings=(),
        )
        quality_decision = quality_policy.decide(
            source_document=source_document,
            page_manifest=processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
            pre_conversion_report=pre_report,
            post_conversion_report=post_report,
        )
        try:
            publication = PublishCanonicalSourceHandler(
                artifact_store=self._artifact_store
            ).handle(
                PublishCanonicalSourceCommand(
                    source_document=source_document,
                    docling_document=docling_document,
                    text_authority_manifest=authority_manifest,
                    quality_decision=quality_decision,
                    accepted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    expected_current_version_id=None,
                    existing_canonical_source=None,
                )
            )
            self._conversion_repository.complete_native_conversion(
                NativeCanonicalPublication(
                    document_id=document_id,
                    canonical_source_id=publication.canonical_source.canonical_source_id,
                    canonical_version_id=publication.published_version.canonical_version_id,
                    canonical_artifact_ref=publication.stored_artifact_ref,
                    canonical_artifact_sha256=publication.published_version.canonical_artifact.artifact_sha256,
                    route_name=processing_run.route_plan.dominant_route_name.value,
                    tool_version=";".join(
                        sorted({output.tool_version for output in result.page_outputs})
                    ),
                )
            )
        except CanonicalArtifactStoreError as error:
            raise WorkerProcessingError(str(error), retryable=False) from error
        return {
            "document_id": document_id.value,
            "conversion_status": DocumentConversionStatus.CANONICAL_ACCEPTED.value,
            "canonical_version_id": publication.published_version.canonical_version_id,
            "canonical_artifact_sha256": publication.published_version.canonical_artifact.artifact_sha256,
        }

    def mark_failed(self, claimed_job: ClaimedJob, error_code: str) -> None:
        payload = dict(claimed_job.job.request.payload)
        document_id = DocumentId.from_value(_required_text(payload, "document_id"))
        self._conversion_repository.reject_native_conversion(
            document_id=document_id, error_code=error_code
        )

    def _load_executable_state(
        self,
        *,
        document_id: DocumentId,
        processing_run_id: str,
        source_sha256: str,
        routing_policy_version: str,
    ):
        source_document = self._source_document_repository.find_by_document_id(
            document_id
        )
        if source_document is None:
            raise WorkerProcessingError("SOURCE_NOT_FOUND", retryable=False)
        if source_document.fingerprint.value != source_sha256:
            raise WorkerProcessingError("SOURCE_FINGERPRINT_MISMATCH", retryable=False)
        processing_run = self._processing_run_repository.find_by_document_id(
            document_id
        )
        if processing_run is None:
            raise WorkerProcessingError("PROCESSING_RUN_NOT_FOUND", retryable=False)
        if processing_run.processing_run_id.value != processing_run_id:
            raise WorkerProcessingError("PROCESSING_RUN_ID_MISMATCH", retryable=False)
        if (
            processing_run.route_plan is None
            or processing_run.route_plan.routing_policy_version.value
            != routing_policy_version
        ):
            raise WorkerProcessingError("SOURCE_NOT_ROUTED", retryable=False)
        conversion = self._conversion_repository.find_conversion_by_document_id(
            document_id
        )
        if conversion is None:
            raise WorkerProcessingError("CONVERSION_REQUEST_NOT_FOUND", retryable=False)
        if conversion.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED:
            return source_document, processing_run, conversion
        if (
            conversion.conversion_status
            is not DocumentConversionStatus.CONVERSION_REQUESTED
            or conversion.execution_phase
            not in {
                DocumentConversionExecutionPhase.QUEUED,
                DocumentConversionExecutionPhase.RUNNING,
            }
        ):
            raise WorkerProcessingError("CONVERSION_NOT_EXECUTABLE", retryable=False)
        return source_document, processing_run, conversion


def build_routed_document_conversion_worker(
    *,
    source_document_repository: Any,
    processing_run_repository: Any,
    conversion_repository: RoutedConversionRepository,
    original_source_store: OriginalPathResolver,
    native_asset_manifest_path: Path,
    native_assets_root: Path,
    granite_asset_manifest_path: Path,
    granite_assets_root: Path,
    ocrmypdf_manifest_path: Path,
    audit_root: Path,
    timeout_seconds: float,
    llm_gateway_url: str,
    llm_gateway_timeout_seconds: int,
    llm_gateway_max_output_tokens: int,
    expected_gemma_model_id: str,
    artifact_store: CanonicalArtifactStore,
    max_parallel_pages: int,
    docling_max_concurrency: int,
    granite_max_concurrency: int,
    granite_capacity_controller: GraniteCapacityController,
    granite_worker: GraniteWorker,
    granite_lease_seconds: int,
    granite_heartbeat_seconds: float,
    job_heartbeat_control: JobHeartbeatControl,
) -> RoutedDocumentConversionWorker:
    """Construit le worker uniquement si tous les runtimes réels annoncés sont prêts."""

    from app.source_processing.adapters.ocrmypdf_container import OcrmyPdfImageManifest

    OcrmyPdfImageManifest.load(
        manifest_path=ocrmypdf_manifest_path,
        require_local_image=True,
    )
    return RoutedDocumentConversionWorker(
        source_document_repository=source_document_repository,
        processing_run_repository=processing_run_repository,
        conversion_repository=conversion_repository,
        original_source_store=original_source_store,
        native_converter=IsolatedNativeDoclingConverter(
            asset_manifest_path=native_asset_manifest_path,
            assets_root=native_assets_root,
            timeout_seconds=timeout_seconds,
        ),
        granite_converter=IsolatedGraniteDoclingConverter(
            asset_manifest_path=granite_asset_manifest_path,
            assets_root=granite_assets_root,
            timeout_seconds=timeout_seconds,
        ),
        gemma_converter=IsolatedGemmaVisionPageConverter(
            timeout_seconds=llm_gateway_timeout_seconds,
        ),
        granite_capacity_controller=granite_capacity_controller,
        granite_worker=granite_worker,
        granite_lease_seconds=granite_lease_seconds,
        granite_heartbeat_seconds=granite_heartbeat_seconds,
        job_heartbeat_control=job_heartbeat_control,
        llm_gateway_url=llm_gateway_url,
        llm_gateway_timeout_seconds=llm_gateway_timeout_seconds,
        llm_gateway_max_output_tokens=llm_gateway_max_output_tokens,
        expected_gemma_model_id=expected_gemma_model_id,
        ocrmypdf_manifest_path=ocrmypdf_manifest_path,
        audit_root=audit_root,
        ocrmypdf_timeout_seconds=timeout_seconds,
        artifact_store=artifact_store,
        max_parallel_pages=max_parallel_pages,
        docling_max_concurrency=docling_max_concurrency,
        granite_max_concurrency=granite_max_concurrency,
    )


def _page_output(
    *,
    response: NativeDoclingConversionResponse,
    page_number: PageNumber,
    route_name: PageRouteName,
    tool_name: ConversionToolName,
    expected_artifact_ref: str,
) -> PageConversionArtifact:
    pages = tuple(
        page for page in response.pages if page.page_number == page_number.value
    )
    if len(pages) != 1 or len(response.pages) != 1:
        raise ValueError("réponse Docling partielle")
    page = pages[0]
    items = tuple(
        PageConversionItem(
            label=PageConversionItemLabel.TEXT,
            text=item.text,
            geometry=PageItemGeometry(
                left=item.bbox[0],
                top=item.bbox[1],
                right=item.bbox[2],
                bottom=item.bbox[3],
                page_width=1.0,
                page_height=1.0,
            ),
            content_hash=hashlib.sha256(item.text.encode("utf-8")).hexdigest(),
        )
        for item in page.items
    )
    artifact_payload = {
        "page_number": page.page_number,
        "route_name": route_name.value,
        "tool_name": tool_name.value,
        "items": [
            {
                "text": item.text,
                "bbox": list(item.bbox),
                "provenance": dict(item.provenance),
            }
            for item in page.items
        ],
    }
    return PageConversionArtifact(
        page_number=page_number,
        route_name=route_name,
        tool_name=tool_name,
        tool_version=response.tool_version,
        artifact_hash=hashlib.sha256(
            json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest(),
        audit_artifact_ref=expected_artifact_ref,
        items=items,
    )


def _gemma_page_output(
    *,
    response: GemmaVisionConversionResponse,
    page_number: PageNumber,
    route_name: PageRouteName,
    expected_artifact_ref: str,
    granite_error_code: str,
) -> PageConversionArtifact:
    items = tuple(
        PageConversionItem(
            label=PageConversionItemLabel.TEXT,
            text=item.text,
            geometry=PageItemGeometry(
                left=item.bbox[0],
                top=item.bbox[1],
                right=item.bbox[2],
                bottom=item.bbox[3],
                page_width=1000.0,
                page_height=1000.0,
            ),
            content_hash=hashlib.sha256(item.text.encode("utf-8")).hexdigest(),
        )
        for item in response.items
    )
    artifact_payload = {
        "page_number": page_number.value,
        "route_name": route_name.value,
        "tool_name": ConversionToolName.GEMMA_VISION.value,
        "tool_version": response.tool_version,
        "fallback_trace": {
            "triggering_tool_name": ConversionToolName.GRANITE_DOCLING.value,
            "triggering_error_code": granite_error_code,
        },
        "items": [
            {"text": item.text, "bbox": list(item.bbox)} for item in response.items
        ],
    }
    return PageConversionArtifact(
        page_number=page_number,
        route_name=route_name,
        tool_name=ConversionToolName.GEMMA_VISION,
        tool_version=response.tool_version,
        artifact_hash=hashlib.sha256(
            json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest(),
        audit_artifact_ref=expected_artifact_ref,
        items=items,
        fallback_trace=PageConversionFallbackTrace(
            triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
            triggering_error_code=granite_error_code,
        ),
    )


def _authority_manifest(
    *,
    processing_run: Any,
    page_outputs: Sequence[PageConversionArtifact],
) -> TextAuthorityManifest:
    policy = TextAuthoritySelectionPolicy(policy_version="m004-routed-docling-v1")
    skipped_pages: list[SkippedEmptyPage] = []
    for route in processing_run.route_plan.page_routes:
        if route.route_name is not PageRouteName.SKIP_EMPTY:
            continue
        decision = next(
            candidate
            for candidate in processing_run.page_decisions
            if candidate.page_number == route.page_number
        )
        resolution = decision.manual_review_resolution
        if resolution is None:
            if decision.page_state is not PageDecisionState.EMPTY:
                raise ValueError("SKIP_EMPTY sans diagnostic EMPTY")
            skipped_pages.append(
                SkippedEmptyPage(
                    page_number=route.page_number,
                    source=SkippedEmptyPageSource.DIAGNOSTIC_EMPTY,
                    policy_version=route.routing_policy_version.value,
                    justification=decision.justification,
                )
            )
        else:
            if resolution.decision is not ManualReviewDecisionType.CONFIRM_EMPTY:
                raise ValueError("SKIP_EMPTY sans confirmation manuelle")
            skipped_pages.append(
                SkippedEmptyPage(
                    page_number=route.page_number,
                    source=SkippedEmptyPageSource.MANUAL_CONFIRMED_EMPTY,
                    policy_version=route.routing_policy_version.value,
                    justification=resolution.reason,
                    reviewer_id=resolution.reviewer_id,
                )
            )
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=processing_run.page_manifest,
        page_decisions=tuple(
            policy.select(
                page_number=output.page_number,
                candidates=(
                    PageConversionCandidate(
                        candidate_id=f"AUTH-P{output.page_number.value:03d}",
                        page_output=output,
                    ),
                ),
                selected_candidate_ids=(f"AUTH-P{output.page_number.value:03d}",),
                justification=f"{output.tool_name.value} est l'autorité unique imposée par {output.route_name.value}.",
            )
            for output in page_outputs
        ),
        skipped_empty_pages=tuple(skipped_pages),
    )


def _pre_conversion_report(
    *, processing_run: Any, policy_version: str
) -> PreConversionQualityReport:
    route_plan = processing_run.route_plan
    selection = CriticalPageSamplingPolicy(
        policy_version=policy_version, low_confidence_threshold=0.85
    ).select(
        page_manifest=processing_run.page_manifest,
        page_diagnostics=processing_run.page_decisions,
        route_plan=route_plan,
    )
    return PreConversionQualityReport(
        policy_version=policy_version,
        critical_page_selection=selection,
        route_comparisons=tuple(
            PreConversionRouteComparison(
                page_number=route.page_number,
                current_route_name=route.route_name,
                alternative_route_name=None,
                status=QualityDecisionStatus.PASS,
                justification="Route M-003 confirmée sans alternative implicite.",
            )
            for route in route_plan.page_routes
        ),
        status=QualityDecisionStatus.PASS,
    )


def _canonical_version_id(source_sha256: str) -> str:
    return f"CVER-M004-ROUTED-{source_sha256[:24].upper()}"


def _sha256_file(path: Path) -> str:
    if not isinstance(path, Path) or not path.is_file():
        raise GraniteDoclingConversionError("GRANITE_DOCLING_UNAVAILABLE")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise WorkerProcessingError(
            f"JOB_PAYLOAD_INVALID_{field_name.upper()}", retryable=False
        )
    return value


def _required_text_value(value: Any, message: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(message)
    return value


def _required_positive_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _required_gateway_url(value: Any) -> str:
    endpoint = _required_text_value(value, "URL gateway LLM invalide")
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        raise ValueError("URL gateway LLM invalide")
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/infer"):
        return endpoint
    return endpoint + "/v1/infer"


__all__ = [
    "NON_NATIVE_TERMINAL_ERROR_CODES",
    "RoutedDocumentConversionWorker",
    "build_routed_document_conversion_worker",
]
