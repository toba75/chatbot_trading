"""Tests unitaires T-005 du fan-out documentaire local."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.source_processing.application.fan_out_document_pages import (
    DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    FanOutDocumentPagesHandler,
)
from app.source_processing.domain.distribution_contracts import (
    CONVERT_PAGE_JOB_NAME,
    DistributionContractError,
    ExecutionCapability,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    LockedAssetVersion,
    PageResultStatus,
    page_manifest_sha256,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PagePreprocessingAction,
    PageRoute,
    PageRouteName,
    ProcessingRunId,
    RouteDecisionMode,
    RoutePlan,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


POLICY_VERSION = "routing-m014-fanout-v1"


def _source() -> SourceDocument:
    content = b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            "artifact:source_processing.original_sources/"
            f"{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Fan-out M14",
                "authors": ["Équipe OSTrading"],
                "publication_year": 2026,
                "edition": "1re édition",
            }
        ),
    )


def _route(page_number: int, route_name: PageRouteName) -> PageRoute:
    return PageRoute(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        decision_mode=RouteDecisionMode.AUTO,
        confidence_score=0.99,
        preprocessing_action=PagePreprocessingAction.NONE,
        routing_policy_version=RoutingPolicyVersion.from_value(POLICY_VERSION),
        justification=f"Route figée de la page {page_number}.",
    )


def _planned_run(source: SourceDocument) -> DocumentProcessingRun:
    manifest = PageManifest.from_entries(
        source_page_count=4,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(page_number),
                state=PageManifestEntryState.PRESENT,
            )
            for page_number in range(1, 5)
        ),
    )
    started = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M014-FANOUT-UNIT"),
        source_document=source,
        page_manifest=manifest,
    )
    decisions = tuple(
        PageDecision(
            page_number=PageNumber.from_value(page_number),
            page_state=PageDecisionState.NATIVE_OK,
            signals=PageDiagnosticSignals(
                native_text_state="RELIABLE",
                image_state="NONE",
                existing_ocr_state="NONE",
                layout_complexity="SIMPLE",
                corruption_state="NONE",
                mixed_content_detected=False,
                has_table=False,
                has_formula=False,
            ),
            diagnostic_version=DiagnosticVersion.from_value("diag-m014-fanout-v1"),
            justification=f"Diagnostic figé de la page {page_number}.",
        )
        for page_number in range(1, 5)
    )
    diagnosed = started.record_page_diagnostics(decisions)
    routes = (
        _route(1, PageRouteName.NATIVE_STANDARD),
        _route(2, PageRouteName.SKIP_EMPTY),
        _route(3, PageRouteName.SCAN_GRANITE),
        _route(4, PageRouteName.NATIVE_STANDARD),
    )
    plan = RoutePlan(
        routing_policy_version=RoutingPolicyVersion.from_value(POLICY_VERSION),
        page_routes=routes,
        dominant_route_name=PageRouteName.NATIVE_STANDARD,
        page_exceptions=(routes[1], routes[2]),
        confidence_score=0.99,
    )
    return DocumentProcessingRun(
        processing_run_id=diagnosed.processing_run_id,
        document_id=diagnosed.document_id,
        page_manifest=diagnosed.page_manifest,
        page_decisions=diagnosed.page_decisions,
        route_plan=plan,
        manual_review_reason=None,
        blocking_policy_version=None,
        status=DocumentProcessingRunStatus.ROUTE_PLANNED,
        aggregate_version=diagnosed.aggregate_version + 1,
        events=diagnosed.events,
    )


def _identity() -> JobEnvironmentIdentity:
    return JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash="c" * 64,
    )


def _source_artifact(source: SourceDocument, *, sha256: str | None = None) -> LocalArtifactDescriptor:
    relative_path = (
        f"documents/{source.document_id.value}/{source.fingerprint.value}.pdf"
    )
    return LocalArtifactDescriptor(
        identity=LocalArtifactIdentity(
            environment="test",
            artifact_ref=f"artifact:source_processing.local/test/{relative_path}",
            relative_path=relative_path,
        ),
        sha256=source.fingerprint.value if sha256 is None else sha256,
        size_bytes=42,
    )


def _parent_job(source: SourceDocument, run: DocumentProcessingRun, **overrides: object) -> JobRequest:
    payload: dict[str, object] = {
        "document_id": source.document_id.value,
        "processing_run_id": run.processing_run_id.value,
        "source_sha256": source.fingerprint.value,
        "routing_policy_version": POLICY_VERSION,
        "route_count": 4,
        "orchestration_version": DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    }
    payload.update(overrides)
    return JobRequest(
        environment="test",
        deployment_id="ostrading-test-local",
        job_name="CONVERT_DOCUMENT",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_DOCUMENT",
            input_hash=source.fingerprint.value,
            configuration_hash="c" * 64,
            code_version="m014-fanout-code-v1",
            model_version="m014-fanout-assets-v1",
        ),
        execution_requirements=None,
        payload=payload,
    )


def _assets(*, sha256: str = "a" * 64) -> tuple[LockedAssetVersion, ...]:
    return (
        LockedAssetVersion(
            name="document-conversion-assets",
            version="m014-fanout-assets-v1",
            sha256=sha256,
        ),
    )


class _ProcessingRuns:
    def __init__(self, run: DocumentProcessingRun) -> None:
        self.run = run

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self.run if document_id == self.run.document_id else None


class _FanOutRepository:
    def __init__(self) -> None:
        self.plan = None

    def persist_page_fan_out(self, plan, *, trace_id: str) -> bool:
        assert trace_id == "TRACE-M014-FANOUT-UNIT"
        if self.plan is None:
            self.plan = plan
            return True
        self.plan.assert_replay_compatible(plan)
        return False


def _handler(run: DocumentProcessingRun, repository: _FanOutRepository, *, assets=None):
    return FanOutDocumentPagesHandler(
        processing_run_repository=_ProcessingRuns(run),
        page_fan_out_repository=repository,
        locked_assets=_assets() if assets is None else assets,
    )


def test_fan_out_deterministe_skip_empty_total_et_rejeu_strict() -> None:
    source = _source()
    run = _planned_run(source)
    repository = _FanOutRepository()
    handler = _handler(run, repository)
    parent = _parent_job(source, run)

    first = handler.handle(
        parent_job=parent,
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )
    replay = handler.handle(
        parent_job=parent,
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )

    assert first.created is True
    assert replay.created is False
    assert first.total_units == replay.total_units == 4
    assert first.completed_units == replay.completed_units == 1
    assert first.page_job_count == replay.page_job_count == 3

    plan = repository.plan
    assert plan is not None
    assert tuple(request.job_name for request in plan.page_jobs) == (
        CONVERT_PAGE_JOB_NAME,
        CONVERT_PAGE_JOB_NAME,
        CONVERT_PAGE_JOB_NAME,
    )
    assert tuple(request.payload["page_number"] for request in plan.page_jobs) == (
        1,
        3,
        4,
    )
    assert plan.skipped_results[0].result.status is PageResultStatus.SKIP_EMPTY
    assert plan.skipped_results[0].result.page_number == 2
    assert plan.skipped_results[0].result.execution is None
    assert plan.skipped_results[0].result.result_artifact is None
    assert plan.skipped_results[0].result.technical_metrics is None
    assert plan.page_jobs[0].execution_requirements.capacity_capability == (
        ExecutionCapability.DOCUMENT_STANDARD.value
    )
    assert plan.page_jobs[1].execution_requirements.capacity_capability == (
        ExecutionCapability.GRANITE_CUDA.value
    )
    assert tuple(
        request.idempotence_key.input_hash for request in plan.page_jobs
    ) == tuple(request.payload["idempotence_key"] for request in plan.page_jobs)

    same_hash = page_manifest_sha256(
        document_id=run.document_id,
        processing_run_id=run.processing_run_id,
        page_manifest=run.page_manifest,
        page_routes=run.route_plan.page_routes,
        routing_policy_version=run.route_plan.routing_policy_version,
    )
    assert same_hash == plan.page_manifest_sha256

    divergent = replace(
        plan,
        locked_assets=_assets(sha256="b" * 64),
    )
    with pytest.raises(
        DistributionContractError,
        match="PAGE_FAN_OUT_REPLAY_DIVERGENCE",
    ):
        plan.assert_replay_compatible(divergent)


@pytest.mark.parametrize(
    ("payload_override", "expected_code"),
    (
        ({"orchestration_version": "m004-inline-v1"}, "PAGE_FAN_OUT_ORCHESTRATION_VERSION_UNSUPPORTED"),
        ({"routing_policy_version": "routing-divergent-v1"}, "PAGE_FAN_OUT_ROUTING_POLICY_DIVERGENT"),
        ({"route_count": 3}, "PAGE_FAN_OUT_ROUTE_COUNT_DIVERGENT"),
        ({"source_sha256": "f" * 64}, "PAGE_FAN_OUT_SOURCE_HASH_DIVERGENT"),
    ),
)
def test_fan_out_refuse_activation_ou_identite_divergente(
    payload_override: dict[str, object],
    expected_code: str,
) -> None:
    source = _source()
    run = _planned_run(source)
    with pytest.raises(DistributionContractError, match=expected_code):
        _handler(run, _FanOutRepository()).handle(
            parent_job=_parent_job(source, run, **payload_override),
            source_artifact=_source_artifact(source),
            trace_id="TRACE-M014-FANOUT-UNIT",
        )


def test_hash_manifeste_refuse_page_absente_dupliquee_hors_manifeste_ou_desordonnee() -> None:
    source = _source()
    run = _planned_run(source)
    routes = run.route_plan.page_routes
    route_5 = _route(5, PageRouteName.NATIVE_STANDARD)
    invalid = (
        (routes[:3], "PAGE_MANIFEST_ROUTE_MISSING"),
        ((routes[0], routes[0], routes[2], routes[3]), "PAGE_MANIFEST_ROUTE_DUPLICATED"),
        ((routes[0], routes[1], routes[2], route_5), "PAGE_MANIFEST_ROUTE_OUTSIDE"),
        ((routes[1], routes[0], routes[2], routes[3]), "PAGE_MANIFEST_ROUTE_ORDER_INVALID"),
    )
    for page_routes, code in invalid:
        with pytest.raises(DistributionContractError, match=code):
            page_manifest_sha256(
                document_id=run.document_id,
                processing_run_id=run.processing_run_id,
                page_manifest=run.page_manifest,
                page_routes=page_routes,
                routing_policy_version=run.route_plan.routing_policy_version,
            )

