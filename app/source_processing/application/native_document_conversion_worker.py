"""Worker M-004 du seul parcours de conversion native réellement livré."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from app.contracts.technical_jobs import ClaimedJob, JobStatus
from app.source_processing.adapters.docling_native_conversion import (
    DoclingAssetManifestError,
    DoclingNativeConversionError,
    NativeDoclingConversionRequest,
    NativeDoclingConversionResponse,
)
from app.source_processing.application.document_commands import (
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_worker import WorkerProcessingError
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
    PageConversionCandidate,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    PreConversionQualityReport,
    PreConversionRouteComparison,
    QualityDecisionStatus,
    TextAuthorityManifest,
    TextAuthoritySelectionPolicy,
)
from app.source_processing.domain.source_document import DocumentId


class NativeDoclingConverter(Protocol):
    def convert(self, request: NativeDoclingConversionRequest) -> NativeDoclingConversionResponse:
        """Convertit le PDF uniquement au moyen du processus Docling standard isolé."""


class OriginalPathResolver(Protocol):
    def resolve_internal_path(self, storage_ref: Any) -> Any:
        """Résout l'original immuable sans exposer ce chemin hors SP."""


@dataclass(frozen=True)
class NativeCanonicalPublication:
    document_id: DocumentId
    canonical_source_id: str
    canonical_version_id: str
    canonical_artifact_ref: str
    canonical_artifact_sha256: str
    route_name: str
    tool_version: str


class NativeConversionRepository(Protocol):
    def find_conversion_by_document_id(self, document_id: DocumentId) -> DocumentConversionState | None:
        """Lit l'état durable de conversion."""

    def complete_native_conversion(self, publication: NativeCanonicalPublication) -> None:
        """Persiste en une transaction la référence, le hash et l'acceptation canonique."""

    def reject_native_conversion(self, *, document_id: DocumentId, error_code: str) -> None:
        """Rend une indisponibilité terminale persistante, sans changement de route."""


class NativeDocumentConversionWorker:
    """Exécute `CONVERT_DOCUMENT` seulement si toutes les pages sont NATIVE_STANDARD."""

    def __init__(
        self,
        *,
        source_document_repository: Any,
        processing_run_repository: Any,
        conversion_repository: NativeConversionRepository,
        original_source_store: OriginalPathResolver,
        native_converter: NativeDoclingConverter,
        artifact_store: CanonicalArtifactStore,
    ) -> None:
        for dependency, method in (
            (source_document_repository, "find_by_document_id"),
            (processing_run_repository, "find_by_document_id"),
            (conversion_repository, "find_conversion_by_document_id"),
            (conversion_repository, "complete_native_conversion"),
            (conversion_repository, "reject_native_conversion"),
            (original_source_store, "resolve_internal_path"),
            (native_converter, "convert"),
            (artifact_store, "store_docling_json"),
        ):
            if not callable(getattr(dependency, method, None)):
                raise ValueError(f"dépendance conversion native invalide: {method}")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._conversion_repository = conversion_repository
        self._original_source_store = original_source_store
        self._native_converter = native_converter
        self._artifact_store = artifact_store

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
        if any(route.route_name is not PageRouteName.NATIVE_STANDARD for route in processing_run.route_plan.page_routes):
            raise WorkerProcessingError("NATIVE_STANDARD_ROUTE_REQUIRED", retryable=False)
        conversion = self._conversion_repository.find_conversion_by_document_id(document_id)
        if conversion is None:
            raise WorkerProcessingError("CONVERSION_REQUEST_NOT_FOUND", retryable=False)
        if conversion.conversion_status is DocumentConversionStatus.CANONICAL_ACCEPTED:
            return {
                "document_id": document_id.value,
                "conversion_status": conversion.conversion_status.value,
                "canonical_version_id": conversion.canonical_version_id,
            }
        if conversion.conversion_status is not DocumentConversionStatus.CONVERSION_REQUESTED:
            raise WorkerProcessingError("CONVERSION_NOT_EXECUTABLE", retryable=False)

        canonical_version_id = _canonical_version_id(source_sha256)
        source_path = self._original_source_store.resolve_internal_path(source_document.original_storage_ref)
        try:
            response = self._native_converter.convert(
                NativeDoclingConversionRequest(
                    document_id=document_id.value,
                    processing_run_id=processing_run_id,
                    source_sha256=source_sha256,
                    source_pdf_path=source_path,
                    expected_page_numbers=tuple(
                        entry.page_number.value for entry in processing_run.page_manifest.entries
                    ),
                    routing_policy_version=routing_policy_version,
                )
            )
        except DoclingAssetManifestError as error:
            raise WorkerProcessingError(str(error), retryable=False) from error
        except DoclingNativeConversionError as error:
            raise WorkerProcessingError(error.code, retryable=False) from error
        page_outputs = _page_outputs(
            response=response,
            processing_run_id=processing_run_id,
        )
        authority_manifest = _authority_manifest(
            page_manifest=processing_run.page_manifest,
            page_outputs=page_outputs,
        )
        docling_document = PagewiseDoclingFusionService().merge_authorized(
            document_id=document_id,
            canonical_version_id=canonical_version_id,
            source_sha256=source_document.fingerprint,
            original_storage_ref=source_document.original_storage_ref,
            page_manifest=processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
        )
        quality_policy = CanonicalAcceptancePolicy(policy_version="m004-native-docling-v1")
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
                route_name=PageRouteName.NATIVE_STANDARD.value,
                tool_version=response.tool_version,
            )
        )
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


def _page_outputs(*, response: NativeDoclingConversionResponse, processing_run_id: str) -> tuple[PageConversionArtifact, ...]:
    outputs: list[PageConversionArtifact] = []
    for page in response.pages:
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
            "items": [
                {
                    "text": item.text,
                    "bbox": list(item.bbox),
                    "provenance": dict(item.provenance),
                }
                for item in page.items
            ],
        }
        outputs.append(
            PageConversionArtifact(
                page_number=PageNumber.from_value(page.page_number),
                route_name=PageRouteName.NATIVE_STANDARD,
                tool_name=ConversionToolName.DOCLING_STANDARD,
                tool_version=response.tool_version,
                artifact_hash=hashlib.sha256(json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                audit_artifact_ref=f"artifact:source_processing.page_conversion/{processing_run_id}/page-{page.page_number:03d}-native_standard.json",
                items=items,
            )
        )
    return tuple(outputs)


def _authority_manifest(*, page_manifest: Any, page_outputs: Sequence[PageConversionArtifact]) -> TextAuthorityManifest:
    policy = TextAuthoritySelectionPolicy(policy_version="m004-native-docling-v1")
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=tuple(
            policy.select(
                page_number=output.page_number,
                candidates=(PageConversionCandidate(candidate_id=f"AUTH-P{output.page_number.value:03d}", page_output=output),),
                selected_candidate_ids=(f"AUTH-P{output.page_number.value:03d}",),
                justification="Docling standard est l'autorité unique imposée par la route native.",
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
                justification="Route native M-003 confirmée sans alternative implicite.",
            )
            for route in route_plan.page_routes
        ),
        status=QualityDecisionStatus.PASS,
    )


def _canonical_version_id(source_sha256: str) -> str:
    return f"CVER-M004-NATIVE-{source_sha256[:24].upper()}"


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise WorkerProcessingError(f"JOB_PAYLOAD_INVALID_{field_name.upper()}", retryable=False)
    return value


__all__ = ["NativeCanonicalPublication", "NativeDocumentConversionWorker"]
