"""Assemblage M-014 d'une version canonique depuis les seuls faits persistés SP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.event_envelope import EventEnvelope
from app.contracts.source_references import CanonicalSourceRef
from app.contracts.technical_jobs import ClaimedJob, JobRequest, JobStatus
from app.source_processing.application.publish_canonical_source import (
    CanonicalArtifactStore,
    PublishCanonicalSourceCommand,
    PublishCanonicalSourceHandler,
)
from app.source_processing.application.publish_canonical_source_event import (
    build_canonical_source_published_event,
)
from app.source_processing.domain.distribution_contracts import (
    ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
    PAGE_RESULT_CONTRACT_VERSION,
    AssembleCanonicalDocumentContract,
    DistributionContractError,
    LocalArtifactDescriptor,
    PageResultContract,
    PageResultStatus,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    PageDecisionState,
    PageNumber,
    PageRouteName,
)
from app.source_processing.domain.page_conversion import (
    CanonicalAcceptancePolicy,
    ConversionToolName,
    CriticalPageSamplingPolicy,
    PageConversionArtifact,
    PageConversionCandidate,
    PageConversionFallbackTrace,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    PreConversionQualityReport,
    PreConversionRouteComparison,
    QualityDecisionStatus,
    SkippedEmptyPage,
    SkippedEmptyPageSource,
    TargetedEnrichmentAdjudicationTrace,
    TextAuthorityManifest,
    TextAuthoritySelectionPolicy,
)
from app.source_processing.domain.source_document import SourceDocument


CANONICAL_ASSEMBLY_QUALITY_POLICY_VERSION = "m014-canonical-assembly-v1"


class CanonicalAssemblyArtifactReader(Protocol):
    def read(self, descriptor: LocalArtifactDescriptor) -> bytes: ...


class CanonicalAssemblyRepository(Protocol):
    def load_snapshot(
        self, contract: AssembleCanonicalDocumentContract
    ) -> "CanonicalAssemblySnapshot": ...

    def publish_atomic(self, publication: "CanonicalAssemblyPublication") -> bool: ...

    def mark_failed(
        self, contract: AssembleCanonicalDocumentContract, *, error_code: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CanonicalAssemblySnapshot:
    source_document: SourceDocument
    processing_run: DocumentProcessingRun
    page_results: tuple[PageResultContract, ...]
    accepted_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_document, SourceDocument):
            raise ValueError("CANONICAL_ASSEMBLY_SOURCE_INVALID")
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("CANONICAL_ASSEMBLY_RUN_INVALID")
        if any(not isinstance(result, PageResultContract) for result in self.page_results):
            raise ValueError("CANONICAL_ASSEMBLY_RESULTS_INVALID")
        _text(self.accepted_at, "CANONICAL_ASSEMBLY_ACCEPTED_AT_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalAssemblyPublication:
    contract: AssembleCanonicalDocumentContract
    canonical_ref: CanonicalSourceRef
    canonical_artifact_ref: str
    route_name: PageRouteName
    tool_version: str
    event: EventEnvelope
    result_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.contract, AssembleCanonicalDocumentContract):
            raise ValueError("CANONICAL_ASSEMBLY_CONTRACT_INVALID")
        if not isinstance(self.canonical_ref, CanonicalSourceRef):
            raise ValueError("CANONICAL_ASSEMBLY_REF_INVALID")
        _text(self.canonical_artifact_ref, "CANONICAL_ASSEMBLY_ARTIFACT_REF_INVALID")
        if not isinstance(self.route_name, PageRouteName):
            raise ValueError("CANONICAL_ASSEMBLY_ROUTE_INVALID")
        _text(self.tool_version, "CANONICAL_ASSEMBLY_TOOL_VERSION_INVALID")
        if not isinstance(self.event, EventEnvelope):
            raise ValueError("CANONICAL_ASSEMBLY_EVENT_INVALID")
        _sha256(self.result_fingerprint, "CANONICAL_ASSEMBLY_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalAssemblyOutcome:
    created: bool
    canonical_ref: CanonicalSourceRef
    event: EventEnvelope


class CanonicalAssemblyPolicy:
    """Valide la complétude et reconstruit les sorties sans appel à un modèle."""

    def validate_results(
        self,
        *,
        contract: AssembleCanonicalDocumentContract,
        results: tuple[PageResultContract, ...],
    ) -> tuple[PageResultContract, ...]:
        if not isinstance(contract, AssembleCanonicalDocumentContract):
            raise ValueError("CANONICAL_ASSEMBLY_CONTRACT_INVALID")
        parsed = tuple(results)
        if any(not isinstance(result, PageResultContract) for result in parsed):
            raise ValueError("CANONICAL_ASSEMBLY_RESULTS_INVALID")
        pages = tuple(result.page_number for result in parsed)
        if len(pages) != len(set(pages)):
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")
        if set(pages) != set(range(1, contract.page_count + 1)):
            raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
        ordered = tuple(sorted(parsed, key=lambda result: result.page_number))
        for result in ordered:
            if (
                result.contract_version != contract.page_result_contract_version
                or result.contract_version != PAGE_RESULT_CONTRACT_VERSION
                or result.environment_identity != contract.environment_identity
                or result.document_id != contract.document_id
                or result.processing_run_id != contract.processing_run_id
            ):
                raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")
            if result.status is PageResultStatus.FAILED:
                raise DistributionContractError("PAGE_RESULT_TERMINAL_FAILURE")
        return ordered

    def read_page_outputs(
        self,
        *,
        results: tuple[PageResultContract, ...],
        artifact_reader: CanonicalAssemblyArtifactReader,
    ) -> tuple[PageConversionArtifact, ...]:
        if not callable(getattr(artifact_reader, "read", None)):
            raise ValueError("CANONICAL_ASSEMBLY_ARTIFACT_READER_INVALID")
        outputs: list[PageConversionArtifact] = []
        for result in results:
            if result.status is PageResultStatus.SKIP_EMPTY:
                continue
            descriptor = result.result_artifact
            if descriptor is None:
                raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
            content = artifact_reader.read(descriptor)
            descriptor.verify_content(content)
            output = _page_output_from_bytes(content)
            if (
                output.page_number.value != result.page_number
                or output.route_name is not result.route_name
                or output.tool_name.value != result.tool_name
                or output.tool_version != result.tool_version
            ):
                raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")
            outputs.append(output)
        if len(outputs) == 0:
            raise DistributionContractError("PAGE_AUTHORITY_MISSING")
        return tuple(outputs)


class AssembleCanonicalDocumentHandler:
    """Prépare l'artefact, puis délègue la visibilité à une transaction SP."""

    def __init__(
        self,
        *,
        repository: CanonicalAssemblyRepository,
        page_artifact_reader: CanonicalAssemblyArtifactReader,
        canonical_artifact_store: CanonicalArtifactStore,
    ) -> None:
        if any(
            not callable(getattr(repository, method, None))
            for method in ("load_snapshot", "publish_atomic", "mark_failed")
        ):
            raise ValueError("CANONICAL_ASSEMBLY_REPOSITORY_INVALID")
        if not callable(getattr(page_artifact_reader, "read", None)):
            raise ValueError("CANONICAL_ASSEMBLY_ARTIFACT_READER_INVALID")
        self._repository = repository
        self._page_artifact_reader = page_artifact_reader
        self._publication_handler = PublishCanonicalSourceHandler(
            artifact_store=canonical_artifact_store
        )
        self._policy = CanonicalAssemblyPolicy()

    def handle(self, *, request: JobRequest, trace_id: str) -> CanonicalAssemblyOutcome:
        if not isinstance(request, JobRequest) or request.job_name != ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME:
            raise DistributionContractError("JOB_ENVELOPE_NAME_INVALID")
        contract = AssembleCanonicalDocumentContract.from_job_request(request)
        snapshot = self._repository.load_snapshot(contract)
        ordered = self._policy.validate_results(
            contract=contract,
            results=snapshot.page_results,
        )
        outputs = self._policy.read_page_outputs(
            results=ordered,
            artifact_reader=self._page_artifact_reader,
        )
        authority_manifest = _authority_manifest(
            processing_run=snapshot.processing_run,
            page_outputs=outputs,
        )
        canonical_version_id = _canonical_version_id(contract.idempotence_key)
        docling_document = PagewiseDoclingFusionService().merge_authorized(
            document_id=snapshot.source_document.document_id,
            canonical_version_id=canonical_version_id,
            source_sha256=snapshot.source_document.fingerprint,
            original_storage_ref=snapshot.source_document.original_storage_ref,
            page_manifest=snapshot.processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
        )
        quality_policy = CanonicalAcceptancePolicy(
            policy_version=CANONICAL_ASSEMBLY_QUALITY_POLICY_VERSION
        )
        pre_report = _pre_conversion_report(
            processing_run=snapshot.processing_run,
            policy_version=quality_policy.policy_version,
        )
        post_report = quality_policy.evaluate_post_conversion(
            page_manifest=snapshot.processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
            docling_document=docling_document,
            findings=(),
        )
        decision = quality_policy.decide(
            source_document=snapshot.source_document,
            page_manifest=snapshot.processing_run.page_manifest,
            text_authority_manifest=authority_manifest,
            pre_conversion_report=pre_report,
            post_conversion_report=post_report,
        )
        published = self._publication_handler.handle(
            PublishCanonicalSourceCommand(
                source_document=snapshot.source_document,
                docling_document=docling_document,
                text_authority_manifest=authority_manifest,
                quality_decision=decision,
                accepted_at=snapshot.accepted_at,
                expected_current_version_id=None,
                existing_canonical_source=None,
            )
        )
        if published.stored_artifact_ref != contract.expected_canonical_artifact:
            raise DistributionContractError("CANONICAL_ARTIFACT_REF_MISMATCH")
        _text(trace_id, "CANONICAL_ASSEMBLY_TRACE_INVALID")
        event = build_canonical_source_published_event(
            canonical_ref=published.canonical_ref,
            aggregate_version=1,
            correlation_id=f"CORR-M014-ASSEMBLY-{contract.idempotence_key[:24].upper()}",
            causation_id=f"CMD-ASSEMBLE-{contract.idempotence_key[:32].upper()}",
        )
        route_names = {output.route_name for output in outputs}
        route_name = next(iter(route_names)) if len(route_names) == 1 else PageRouteName.MIXED_PAGEWISE
        tool_version = ";".join(sorted({output.tool_version for output in outputs}))
        fingerprint = _publication_fingerprint(
            contract=contract,
            canonical_ref=published.canonical_ref,
            canonical_artifact_ref=published.stored_artifact_ref,
            route_name=route_name,
            tool_version=tool_version,
            event=event,
        )
        publication = CanonicalAssemblyPublication(
            contract=contract,
            canonical_ref=published.canonical_ref,
            canonical_artifact_ref=published.stored_artifact_ref,
            route_name=route_name,
            tool_version=tool_version,
            event=event,
            result_fingerprint=fingerprint,
        )
        created = self._repository.publish_atomic(publication)
        return CanonicalAssemblyOutcome(
            created=created,
            canonical_ref=published.canonical_ref,
            event=event,
        )

    def mark_failed(self, *, request: JobRequest, error_code: str) -> None:
        contract = AssembleCanonicalDocumentContract.from_job_request(request)
        self._repository.mark_failed(
            contract,
            error_code=_text(error_code, "CANONICAL_ASSEMBLY_ERROR_CODE_INVALID"),
        )


class CanonicalAssemblyWorker:
    """Worker dédié au job technique d'assemblage, sans port de modèle."""

    def __init__(self, *, handler: AssembleCanonicalDocumentHandler) -> None:
        if not isinstance(handler, AssembleCanonicalDocumentHandler):
            raise ValueError("CANONICAL_ASSEMBLY_HANDLER_INVALID")
        self._handler = handler

    def execute(self, claimed_job: ClaimedJob) -> dict[str, Any]:
        if (
            not isinstance(claimed_job, ClaimedJob)
            or claimed_job.job.status is not JobStatus.RUNNING
            or claimed_job.job.request.job_name
            != ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME
        ):
            raise ValueError("ASSEMBLE_CANONICAL_DOCUMENT_RUNNING_REQUIRED")
        outcome = self._handler.handle(
            request=claimed_job.job.request,
            trace_id=claimed_job.trace_id,
        )
        return {
            "document_id": outcome.canonical_ref.document_id,
            "canonical_version_id": outcome.canonical_ref.canonical_version_id,
            "canonical_artifact_sha256": (
                outcome.canonical_ref.canonical_artifact_sha256
            ),
            "created": outcome.created,
        }

    def mark_failed(self, claimed_job: ClaimedJob, error_code: str) -> None:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("ASSEMBLE_CANONICAL_DOCUMENT_RUNNING_REQUIRED")
        self._handler.mark_failed(
            request=claimed_job.job.request,
            error_code=error_code,
        )


def _authority_manifest(
    *,
    processing_run: DocumentProcessingRun,
    page_outputs: tuple[PageConversionArtifact, ...],
) -> TextAuthorityManifest:
    policy = TextAuthoritySelectionPolicy(
        policy_version=CANONICAL_ASSEMBLY_QUALITY_POLICY_VERSION
    )
    skipped: list[SkippedEmptyPage] = []
    decisions_by_page = {
        decision.page_number: decision for decision in processing_run.page_decisions
    }
    for route in processing_run.route_plan.page_routes:
        if route.route_name is not PageRouteName.SKIP_EMPTY:
            continue
        try:
            decision = decisions_by_page[route.page_number]
        except KeyError as error:
            raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE") from error
        resolution = decision.manual_review_resolution
        if resolution is None:
            if decision.page_state is not PageDecisionState.EMPTY:
                raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
            skipped.append(
                SkippedEmptyPage(
                    page_number=route.page_number,
                    source=SkippedEmptyPageSource.DIAGNOSTIC_EMPTY,
                    policy_version=route.routing_policy_version.value,
                    justification=decision.justification,
                )
            )
        else:
            skipped.append(
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
                justification=(
                    f"{output.tool_name.value} est l'autorité unique de "
                    f"{output.route_name.value}."
                ),
            )
            for output in page_outputs
        ),
        skipped_empty_pages=tuple(skipped),
    )


def _pre_conversion_report(
    *, processing_run: DocumentProcessingRun, policy_version: str
) -> PreConversionQualityReport:
    selection = CriticalPageSamplingPolicy(
        policy_version=policy_version,
        low_confidence_threshold=0.85,
    ).select(
        page_manifest=processing_run.page_manifest,
        page_diagnostics=processing_run.page_decisions,
        route_plan=processing_run.route_plan,
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
            for route in processing_run.route_plan.page_routes
        ),
        status=QualityDecisionStatus.PASS,
    )


def _page_output_from_bytes(content: bytes) -> PageConversionArtifact:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE") from error
    if not isinstance(payload, dict):
        raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")
    try:
        page_number_payload = payload["page_number"]
        page_number = (
            page_number_payload["value"]
            if isinstance(page_number_payload, dict)
            else page_number_payload
        )
        items = tuple(
            PageConversionItem(
                label=PageConversionItemLabel(item["label"]),
                text=item["text"],
                geometry=PageItemGeometry(**item["geometry"]),
                content_hash=item["content_hash"],
            )
            for item in payload["items"]
        )
        fallback_payload = payload["fallback_trace"]
        fallback = (
            None
            if fallback_payload is None
            else PageConversionFallbackTrace(
                triggering_tool_name=ConversionToolName(
                    fallback_payload["triggering_tool_name"]
                ),
                triggering_error_code=fallback_payload["triggering_error_code"],
            )
        )
        adjudication_payload = payload["adjudication_trace"]
        adjudication = (
            None
            if adjudication_payload is None
            else TargetedEnrichmentAdjudicationTrace(
                policy_version=adjudication_payload["policy_version"],
                selected_tool_name=ConversionToolName(
                    adjudication_payload["selected_tool_name"]
                ),
                native_candidate_artifact_hash=adjudication_payload[
                    "native_candidate_artifact_hash"
                ],
                native_candidate_artifact_ref=adjudication_payload[
                    "native_candidate_artifact_ref"
                ],
                granite_candidate_artifact_hash=adjudication_payload[
                    "granite_candidate_artifact_hash"
                ],
                granite_candidate_artifact_ref=adjudication_payload[
                    "granite_candidate_artifact_ref"
                ],
                granite_error_code=adjudication_payload["granite_error_code"],
                justification=adjudication_payload["justification"],
            )
        )
        return PageConversionArtifact(
            page_number=PageNumber.from_value(page_number),
            route_name=PageRouteName(payload["route_name"]),
            tool_name=ConversionToolName(payload["tool_name"]),
            tool_version=payload["tool_version"],
            artifact_hash=payload["artifact_hash"],
            audit_artifact_ref=payload["audit_artifact_ref"],
            items=items,
            fallback_trace=fallback,
            adjudication_trace=adjudication,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE") from error


def _canonical_version_id(idempotence_key: str) -> str:
    return f"CVER-M014-{_sha256(idempotence_key, 'IDEMPOTENCE_KEY_INVALID')[:24].upper()}"


def _publication_fingerprint(
    *,
    contract: AssembleCanonicalDocumentContract,
    canonical_ref: CanonicalSourceRef,
    canonical_artifact_ref: str,
    route_name: PageRouteName,
    tool_version: str,
    event: EventEnvelope,
) -> str:
    payload = {
        "contract": contract.to_mapping(),
        "canonical_ref": canonical_ref.to_payload(),
        "canonical_artifact_ref": canonical_artifact_ref,
        "route_name": route_name.value,
        "tool_version": tool_version,
        "event": event.to_payload(),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sha256(value: Any, code: str) -> str:
    text = _text(value, code)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text.lower()):
        raise ValueError(code)
    return text.lower()


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(code)
    return value


__all__ = [
    "AssembleCanonicalDocumentHandler",
    "CANONICAL_ASSEMBLY_QUALITY_POLICY_VERSION",
    "CanonicalAssemblyOutcome",
    "CanonicalAssemblyPolicy",
    "CanonicalAssemblyPublication",
    "CanonicalAssemblyRepository",
    "CanonicalAssemblySnapshot",
    "CanonicalAssemblyWorker",
]
