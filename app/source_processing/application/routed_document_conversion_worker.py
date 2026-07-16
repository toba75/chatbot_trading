"""Worker M-004 de toutes les routes M-003, sans conversion de remplacement."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.contracts.technical_jobs import ClaimedJob, JobStatus
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
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_worker import WorkerProcessingError
from app.source_processing.application.granite_gemma_recovery import (
    GEMMA_RECOVERY_GRANITE_ERROR_CODES,
    GraniteConversionFailure,
    GraniteThenGemmaPageConverter,
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
from app.source_processing.domain.canonical_source import canonical_source_id_for
from app.source_processing.domain.document_processing_run import PageNumber, PageRouteName
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


class RoutedConversionRepository(Protocol):
    def find_conversion_by_document_id(self, document_id: DocumentId) -> DocumentConversionState | None:
        """Lit l'état durable de conversion."""

    def complete_native_conversion(self, publication: NativeCanonicalPublication) -> None:
        """Persiste une unique publication canonique, quelle que soit sa route."""

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        """Persiste RUNNING avant tout processus d'outil."""

    def record_conversion_progress(self, *, document_id: DocumentId, completed_units: int) -> None:
        """Persiste chaque page réellement convertie avant la lecture publique."""

    def reject_native_conversion(self, *, document_id: DocumentId, error_code: str) -> None:
        """Persiste un échec terminal sans route de secours."""


class _NativePageConverter:
    def __init__(self, *, converter: IsolatedNativeDoclingConverter, resolve_source_path: Callable[[str], Path]) -> None:
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
    def __init__(self, *, converter: IsolatedGraniteDoclingConverter, resolve_source_path: Callable[[str], Path]) -> None:
        self._converter = converter
        self._resolve_source_path = resolve_source_path

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        source_path = self._resolve_source_path(request.source_artifact_ref)
        try:
            response = self._converter.convert(
                GraniteDoclingConversionRequest(
                    document_id=request.document_id.value,
                    processing_run_id=request.processing_run_id.value,
                    source_sha256=_sha256_file(source_path),
                    source_pdf_path=source_path,
                    page_number=request.page_number.value,
                    source_page_number=(
                        1
                        if request.source_artifact_ref.startswith(
                            "artifact:source_processing.page_conversion/"
                        )
                        else request.page_number.value
                    ),
                    route_name=request.route_name.value,
                    routing_policy_version=request.routing_policy_version.value,
                )
            )
        except GraniteDoclingConversionError as error:
            raise GraniteConversionFailure(error.code) from error
        return _page_output(
            response=response,
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.GRANITE_DOCLING,
            expected_artifact_ref=request.expected_output_artifact_ref,
        )


class _GemmaVisionFallbackPageConverter:
    """Produit une page Gemma seulement après l'échec Granite explicitement admis."""

    def __init__(
        self,
        *,
        converter: IsolatedGemmaVisionPageConverter,
        resolve_source_path: Callable[[str], Path],
        gateway_endpoint_url: str,
        gateway_timeout_seconds: int,
        gateway_max_output_tokens: int,
        expected_model_id: str,
    ) -> None:
        self._converter = converter
        self._resolve_source_path = resolve_source_path
        self._gateway_endpoint_url = gateway_endpoint_url
        self._gateway_timeout_seconds = gateway_timeout_seconds
        self._gateway_max_output_tokens = _required_positive_int(
            gateway_max_output_tokens,
            "maximum de sortie gateway LLM invalide",
        )
        self._expected_model_id = expected_model_id

    def recover_page(
        self,
        request: PageConversionRequest,
        *,
        granite_error_code: str,
    ) -> PageConversionArtifact:
        if granite_error_code not in GEMMA_RECOVERY_GRANITE_ERROR_CODES:
            raise ValueError("récupération Gemma non autorisée")
        source_path = self._resolve_source_path(request.source_artifact_ref)

        def gemma_request(
            *,
            render_rotation_degrees: int,
            render_segment_index: int | None = None,
            render_segment_count: int | None = None,
        ) -> GemmaVisionConversionRequest:
            return GemmaVisionConversionRequest(
                document_id=request.document_id.value,
                processing_run_id=request.processing_run_id.value,
                source_sha256=_sha256_file(source_path),
                source_pdf_path=source_path,
                page_number=request.page_number.value,
                source_page_number=(
                    1
                    if request.source_artifact_ref.startswith(
                        "artifact:source_processing.page_conversion/"
                    )
                    else request.page_number.value
                ),
                route_name=request.route_name.value,
                routing_policy_version=request.routing_policy_version.value,
                gateway_endpoint_url=self._gateway_endpoint_url,
                gateway_timeout_seconds=self._gateway_timeout_seconds,
                max_output_tokens=self._gateway_max_output_tokens,
                expected_model_id=self._expected_model_id,
                render_rotation_degrees=render_rotation_degrees,
                render_segment_index=render_segment_index,
                render_segment_count=render_segment_count,
            )
        try:
            response = self._converter.convert(gemma_request(render_rotation_degrees=0))
        except GemmaVisionConversionError as error:
            if error.code != "GEMMA_VISION_OUTPUT_INVALID":
                raise
            try:
                response = self._converter.convert(gemma_request(render_rotation_degrees=90))
            except GemmaVisionConversionError as rotated_error:
                if rotated_error.code != "GEMMA_VISION_OUTPUT_TRUNCATED":
                    raise
                segment_responses = tuple(
                    self._converter.convert(
                        gemma_request(
                            render_rotation_degrees=90,
                            render_segment_index=segment_index,
                            render_segment_count=GEMMA_DENSE_RENDER_SEGMENT_COUNT,
                        )
                    )
                    for segment_index in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
                )
                response = _merge_gemma_segment_responses(segment_responses)
        return _gemma_page_output(
            response=response,
            page_number=request.page_number,
            route_name=request.route_name,
            expected_artifact_ref=request.expected_output_artifact_ref,
            granite_error_code=granite_error_code,
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
            f"{base_version};render-segments-"
            f"{GEMMA_DENSE_RENDER_SEGMENT_COUNT:02d}"
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
        llm_gateway_url: str,
        llm_gateway_timeout_seconds: int,
        llm_gateway_max_output_tokens: int,
        expected_gemma_model_id: str,
        ocrmypdf_manifest_path: Path,
        audit_root: Path,
        ocrmypdf_timeout_seconds: float,
        artifact_store: CanonicalArtifactStore,
        max_parallel_pages: int,
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
            (granite_converter, "convert"),
            (gemma_converter, "convert"),
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

    def execute(self, claimed_job: ClaimedJob) -> Mapping[str, Any]:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        job = claimed_job.job
        if job.status is not JobStatus.RUNNING or job.request.job_name != "CONVERT_DOCUMENT":
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
        original_path = self._original_source_store.resolve_internal_path(source_document.original_storage_ref)

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
            native_page_converter = _NativePageConverter(
                converter=self._native_converter,
                resolve_source_path=resolve_source_path,
            )
            raw_granite_page_converter = _GranitePageConverter(
                converter=self._granite_converter,
                resolve_source_path=resolve_source_path,
            )
            handler = ConvertRoutedPagesHandler(
                native_converter=native_page_converter,
                granite_converter=GraniteThenGemmaPageConverter(
                    granite_converter=raw_granite_page_converter,
                    gemma_converter=_GemmaVisionFallbackPageConverter(
                        converter=self._gemma_converter,
                        resolve_source_path=resolve_source_path,
                        gateway_endpoint_url=self._llm_gateway_url,
                        gateway_timeout_seconds=self._llm_gateway_timeout_seconds,
                        gateway_max_output_tokens=self._llm_gateway_max_output_tokens,
                        expected_model_id=self._expected_gemma_model_id,
                    ),
                ),
                targeted_enrichment_converter=TargetedEnrichmentPageConverter(
                    native_converter=native_page_converter,
                    granite_converter=raw_granite_page_converter,
                    policy_version="targeted-enrichment-v1",
                ),
                ocrmypdf_preprocessor=preprocessor,
                max_parallel_pages=self._max_parallel_pages,
            )
            completed_lock = threading.Lock()
            completed_units = 0

            def record_completed_page(page_output: PageConversionArtifact) -> None:
                del page_output
                nonlocal completed_units
                with completed_lock:
                    completed_units += 1
                    completed = completed_units
                self._conversion_repository.record_conversion_progress(
                    document_id=document_id,
                    completed_units=completed,
                )

            result = handler.handle(
                ConvertRoutedPagesCommand(
                    source_document=source_document,
                    processing_run=processing_run,
                    canonical_version_id=_canonical_version_id(source_sha256),
                ),
                on_page_converted=record_completed_page,
            )
        except (DoclingAssetManifestError, OcrmyPdfImageManifestError) as error:
            raise WorkerProcessingError("CONVERSION_ASSET_MANIFEST_INVALID", retryable=False) from error
        except (
            DoclingNativeConversionError,
            GraniteDoclingConversionError,
            GraniteConversionFailure,
            GemmaVisionConversionError,
            OcrmyPdfContainerError,
        ) as error:
            raise WorkerProcessingError(getattr(error, "code", str(error)), retryable=False) from error
        except ValueError as error:
            raise WorkerProcessingError("DOCLING_PAGE_MANIFEST_MISMATCH", retryable=False) from error

        authority_manifest = _authority_manifest(page_manifest=processing_run.page_manifest, page_outputs=result.page_outputs)
        canonical_version_id = _canonical_version_id(source_sha256)
        docling_document = result.docling_document
        quality_policy = CanonicalAcceptancePolicy(policy_version="m004-routed-docling-v1")
        pre_report = _pre_conversion_report(processing_run=processing_run, policy_version=quality_policy.policy_version)
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
            publication = PublishCanonicalSourceHandler(artifact_store=self._artifact_store).handle(
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
                    tool_version=";".join(sorted({output.tool_version for output in result.page_outputs})),
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
        self._conversion_repository.reject_native_conversion(document_id=document_id, error_code=error_code)

    def _load_executable_state(self, *, document_id: DocumentId, processing_run_id: str, source_sha256: str, routing_policy_version: str):
        source_document = self._source_document_repository.find_by_document_id(document_id)
        if source_document is None:
            raise WorkerProcessingError("SOURCE_NOT_FOUND", retryable=False)
        if source_document.fingerprint.value != source_sha256:
            raise WorkerProcessingError("SOURCE_FINGERPRINT_MISMATCH", retryable=False)
        processing_run = self._processing_run_repository.find_by_document_id(document_id)
        if processing_run is None:
            raise WorkerProcessingError("PROCESSING_RUN_NOT_FOUND", retryable=False)
        if processing_run.processing_run_id.value != processing_run_id:
            raise WorkerProcessingError("PROCESSING_RUN_ID_MISMATCH", retryable=False)
        if processing_run.route_plan is None or processing_run.route_plan.routing_policy_version.value != routing_policy_version:
            raise WorkerProcessingError("SOURCE_NOT_ROUTED", retryable=False)
        conversion = self._conversion_repository.find_conversion_by_document_id(document_id)
        if conversion is None:
            raise WorkerProcessingError("CONVERSION_REQUEST_NOT_FOUND", retryable=False)
        if conversion.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED:
            return source_document, processing_run, conversion
        if conversion.conversion_status is not DocumentConversionStatus.CONVERSION_REQUESTED or conversion.execution_phase not in {
            DocumentConversionExecutionPhase.QUEUED,
            DocumentConversionExecutionPhase.RUNNING,
        }:
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
        llm_gateway_url=llm_gateway_url,
        llm_gateway_timeout_seconds=llm_gateway_timeout_seconds,
        llm_gateway_max_output_tokens=llm_gateway_max_output_tokens,
        expected_gemma_model_id=expected_gemma_model_id,
        ocrmypdf_manifest_path=ocrmypdf_manifest_path,
        audit_root=audit_root,
        ocrmypdf_timeout_seconds=timeout_seconds,
        artifact_store=artifact_store,
        max_parallel_pages=max_parallel_pages,
    )


def _page_output(*, response: NativeDoclingConversionResponse, page_number: PageNumber, route_name: PageRouteName, tool_name: ConversionToolName, expected_artifact_ref: str) -> PageConversionArtifact:
    pages = tuple(page for page in response.pages if page.page_number == page_number.value)
    if len(pages) != 1 or len(response.pages) != 1:
        raise ValueError("réponse Docling partielle")
    page = pages[0]
    items = tuple(
        PageConversionItem(
            label=PageConversionItemLabel.TEXT,
            text=item.text,
            geometry=PageItemGeometry(
                left=item.bbox[0], top=item.bbox[1], right=item.bbox[2], bottom=item.bbox[3], page_width=1.0, page_height=1.0
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
            {"text": item.text, "bbox": list(item.bbox), "provenance": dict(item.provenance)}
            for item in page.items
        ],
    }
    return PageConversionArtifact(
        page_number=page_number,
        route_name=route_name,
        tool_name=tool_name,
        tool_version=response.tool_version,
        artifact_hash=hashlib.sha256(json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
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
            {"text": item.text, "bbox": list(item.bbox)}
            for item in response.items
        ],
    }
    return PageConversionArtifact(
        page_number=page_number,
        route_name=route_name,
        tool_name=ConversionToolName.GEMMA_VISION,
        tool_version=response.tool_version,
        artifact_hash=hashlib.sha256(
            json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        audit_artifact_ref=expected_artifact_ref,
        items=items,
        fallback_trace=PageConversionFallbackTrace(
            triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
            triggering_error_code=granite_error_code,
        ),
    )


def _authority_manifest(*, page_manifest: Any, page_outputs: Sequence[PageConversionArtifact]) -> TextAuthorityManifest:
    policy = TextAuthoritySelectionPolicy(policy_version="m004-routed-docling-v1")
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=tuple(
            policy.select(
                page_number=output.page_number,
                candidates=(PageConversionCandidate(candidate_id=f"AUTH-P{output.page_number.value:03d}", page_output=output),),
                selected_candidate_ids=(f"AUTH-P{output.page_number.value:03d}",),
                justification=f"{output.tool_name.value} est l'autorité unique imposée par {output.route_name.value}.",
            )
            for output in page_outputs
        ),
    )


def _pre_conversion_report(*, processing_run: Any, policy_version: str) -> PreConversionQualityReport:
    route_plan = processing_run.route_plan
    selection = CriticalPageSamplingPolicy(policy_version=policy_version, low_confidence_threshold=0.85).select(
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
        raise WorkerProcessingError(f"JOB_PAYLOAD_INVALID_{field_name.upper()}", retryable=False)
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
