"""Régressions unitaires du fencing runtime final M-014."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from app.contracts.page_execution import PageCompletionMessage
from app.source_processing.adapters import distributed_page_conversion
from app.source_processing.adapters.worker_runtime import _settle_processing_failure
from app.source_processing.application import routed_document_conversion_worker
from app.source_processing.application.fan_out_document_pages import PageFanOutPlan
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
    PageResultErrorCode,
)
from validate_page_execution_unit import _claimed, _granite_lease, _page_jobs
from validate_page_fan_out_unit import (
    _FanOutRepository,
    _handler,
    _parent_job,
    _planned_run,
    _source,
    _source_artifact,
)


class _Heartbeat:
    def finalize(self, operation):
        return operation()


class _ExpiredPlatformQueue:
    def mark_failed(self, **_kwargs):
        raise RuntimeError("JOB_LEASE_LOST")


class _SourceProcessingWorker:
    def __init__(self) -> None:
        self.failures: list[tuple[object, str]] = []

    def mark_failed(self, claimed, error_code: str) -> None:
        self.failures.append((claimed, error_code))


def test_given_claim_sp_expire_when_terminalisation_then_aucune_mutation_sp() -> None:
    request, _, _ = _page_jobs()
    claimed = _claimed(request, job_number=141, owner="worker-documents-a")
    worker = _SourceProcessingWorker()

    with pytest.raises(RuntimeError, match="JOB_LEASE_LOST"):
        _settle_processing_failure(
            claimed=claimed,
            error_code="DOCLING_STANDARD_UNAVAILABLE",
            retryable=False,
            max_attempts=3,
            worker=worker,
            job_queue=_ExpiredPlatformQueue(),
            heartbeat=_Heartbeat(),
        )

    assert worker.failures == []


def test_given_plan_fan_out_when_un_enfant_diverge_then_persistence_refusee() -> None:
    source = _source()
    run = _planned_run(source)
    repository = _FanOutRepository()
    parent = _parent_job(source, run)
    _handler(run, repository).handle(
        parent_job=parent,
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )
    assert repository.plan is not None
    plan = repository.plan
    assert plan.environment_identity == parent.environment_identity
    first = plan.page_jobs[0]
    divergent_payload = dict(first.payload)
    divergent_payload["document_id"] = "DOC-M014-DIVERGENT"
    divergent = replace(first, payload=divergent_payload)

    with pytest.raises(DistributionContractError, match="PAGE_FAN_OUT_CHILD_DIVERGENT"):
        PageFanOutPlan(
            orchestration_version=plan.orchestration_version,
            environment_identity=plan.environment_identity,
            document_id=plan.document_id,
            processing_run_id=plan.processing_run_id,
            page_manifest_sha256=plan.page_manifest_sha256,
            total_units=plan.total_units,
            source_artifact=plan.source_artifact,
            locked_assets=plan.locked_assets,
            page_jobs=(divergent, *plan.page_jobs[1:]),
            skipped_results=plan.skipped_results,
        )


def test_completion_rejouee_utilise_le_contrat_commun_complet() -> None:
    _, request, _ = _page_jobs()
    claimed = _claimed(request, job_number=142, owner="worker-documents-a")
    lease = _granite_lease(claimed)
    payload = {"page": 2, "status": "FAILED"}
    fingerprint = sha256(
        b'{"page":2,"status":"FAILED"}'
    ).hexdigest()
    expected = PageCompletionMessage(
        completion_id="PCOMP-M014-FENCING-0001",
        environment=request.environment,
        deployment_id=request.deployment_id,
        configuration_hash=request.idempotence_key.configuration_hash,
        job_id=claimed.job.job_id,
        trace_id=claimed.trace_id,
        claim_generation=claimed.claim_generation,
        claim_token=claimed.claim_token,
        worker_instance_id=claimed.lease_owner,
        slot_ordinal=lease.slot_ordinal,
        slot_generation=lease.slot_generation,
        slot_token=lease.slot_token,
        payload=payload,
        payload_fingerprint=fingerprint,
        terminal_status="failed",
        failure_reason="GRANITE_DOCLING_UNAVAILABLE",
    )
    row = (
        expected.environment,
        expected.deployment_id,
        expected.configuration_hash,
        expected.job_id,
        expected.trace_id,
        expected.claim_generation,
        expected.claim_token,
        expected.worker_instance_id,
        expected.slot_ordinal,
        expected.slot_generation,
        expected.slot_token,
        dict(expected.payload),
        expected.payload_fingerprint,
        expected.terminal_status,
        expected.failure_reason,
    )

    parsed = PageCompletionMessage.from_database_row(
        completion_id=expected.completion_id,
        row=row,
    )

    assert parsed == expected


def test_erreurs_reelles_sont_classees_meme_dans_un_exception_group() -> None:
    for code in (
        "DOCLING_PAGE_MANIFEST_MISMATCH",
        "GRANITE_DOCLING_UNAVAILABLE",
        "GEMMA_VISION_OUTPUT_INVALID",
        "GEMMA_VISION_MODEL_MISMATCH",
    ):
        error = RuntimeError(code)
        grouped = ExceptionGroup("conversion supervisée", [error])
        assert distributed_page_conversion._known_error_code(grouped) is (
            PageResultErrorCode(code)
        )


def test_convertisseurs_reutilises_exposent_un_contrat_public() -> None:
    assert routed_document_conversion_worker.NativePageConverter is not None
    assert routed_document_conversion_worker.GranitePageConverter is not None
