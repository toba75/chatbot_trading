"""Tests unitaires T-006 de l'exécution fenced d'une page."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import pytest

from app.contracts.technical_jobs import ClaimedJob, JobRecord, JobStatus
from app.contracts.page_execution import PageCompletionMessage
from app.platform.job_runtime.granite_capacity import GraniteSlotLease
from app.source_processing.application.execute_document_page import (
    ExecuteDocumentPageHandler,
    PageConversionFailure,
    PageConversionOutput,
    PageRouteConverters,
)
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
    LocalArtifactDescriptor,
    PageGpuMetrics,
    PageResultErrorCode,
    PageResultStatus,
    PageTechnicalMetrics,
)
from app.source_processing.domain.document_processing_run import PageRouteName
from validate_page_fan_out_unit import (
    _FanOutRepository,
    _assets,
    _handler,
    _parent_job,
    _planned_run,
    _source,
    _source_artifact,
)


def _page_jobs():
    source = _source()
    run = _planned_run(source)
    repository = _FanOutRepository()
    _handler(run, repository).handle(
        parent_job=_parent_job(source, run),
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )
    assert repository.plan is not None
    return repository.plan.page_jobs


def _claimed(request, *, job_number: int, owner: str) -> ClaimedJob:
    return ClaimedJob(
        job=JobRecord(
            sequence=job_number,
            job_id=f"JOB-M002-{job_number:06d}",
            request=request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id=f"TRACE-M014-PAGE-{job_number}",
        lease_owner=owner,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        claim_generation=1,
        claim_token=str(UUID(int=job_number, version=4)),
        execution_attempts=1,
    )


def _granite_lease(claimed: ClaimedJob) -> GraniteSlotLease:
    return GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=1,
        slot_generation=4,
        slot_token=str(UUID(int=91, version=4)),
        lease_until=claimed.lease_expires_at,
    )


def _standard_metrics() -> PageTechnicalMetrics:
    return PageTechnicalMetrics(
        duration_seconds=0.25,
        peak_ram_bytes=64 * 1024**2,
        gpu=None,
    )


def _granite_metrics() -> PageTechnicalMetrics:
    return PageTechnicalMetrics(
        duration_seconds=0.5,
        peak_ram_bytes=256 * 1024**2,
        gpu=PageGpuMetrics(
            peak_vram_bytes=1024**3,
            peak_utilization_percent=75.0,
            peak_power_watts=88.0,
        ),
    )


class _Reader:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.reads = 0
        self._temporary = TemporaryDirectory(prefix="ostrading-m014-reader-")
        self.path = Path(self._temporary.name) / "source.pdf"
        self.path.write_bytes(content)

    def resolve_verified_path(self, descriptor: LocalArtifactDescriptor) -> Path:
        self.reads += 1
        descriptor.verify_content(self.path.read_bytes())
        return self.path


class _Writer:
    def __init__(self) -> None:
        self.writes = 0

    def write_immutable(self, *, identity, content: bytes, authorize_publication):
        authorize_publication()
        self.writes += 1
        return LocalArtifactDescriptor(
            identity=identity,
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
        )


class _Converter:
    def __init__(self, *, metrics: PageTechnicalMetrics, failure=None) -> None:
        self.metrics = metrics
        self.failure = failure
        self.calls = []

    def convert_page(self, *, contract, source_path: Path, granite_lease):
        source_content = source_path.read_bytes()
        self.calls.append((contract.route_name, source_content, granite_lease))
        if self.failure is not None:
            raise self.failure
        return PageConversionOutput(
            content=(f"page:{contract.page_number}:{contract.route_name.value}").encode(),
            tool_name="docling",
            tool_version="2.48.0",
            technical_metrics=self.metrics,
        )


class _StandardCompletion:
    def __init__(self) -> None:
        self.calls = []
        self.messages = []

    def assert_standard_page_execution_current(self, claimed_job):
        self.current_claim = claimed_job

    def complete_standard_page_execution(self, claimed_job, envelope):
        self.calls.append((claimed_job, envelope))
        self.messages.append(
            PageCompletionMessage.from_execution(
                claimed_job=claimed_job,
                granite_lease=None,
                envelope=envelope,
            )
        )


class _GraniteCompletion:
    def __init__(self) -> None:
        self.calls = []
        self.messages = []

    def assert_page_execution_current(self, lease):
        self.current_lease = lease

    def complete_page_execution(self, lease, envelope):
        self.calls.append((lease, envelope))
        self.messages.append(
            PageCompletionMessage.from_execution(
                claimed_job=lease.claimed_job,
                granite_lease=lease,
                envelope=envelope,
            )
        )


def _converters(*, native=None, granite=None) -> PageRouteConverters:
    standard = native or _Converter(metrics=_standard_metrics())
    accelerated = granite or _Converter(metrics=_granite_metrics())
    return PageRouteConverters(
        native_standard=standard,
        scan_granite=accelerated,
        preprocess_granite=accelerated,
        bad_ocr_to_granite=accelerated,
        mixed_pagewise=accelerated,
        targeted_enrichment=accelerated,
    )


def _handler_for(
    content: bytes,
    *,
    converters=None,
    reader=None,
    expected_locked_assets=None,
):
    standard = _StandardCompletion()
    granite = _GraniteCompletion()
    reader = _Reader(content) if reader is None else reader
    writer = _Writer()
    return (
        ExecuteDocumentPageHandler(
            artifact_reader=reader,
            artifact_writer=writer,
            converters=converters or _converters(),
            standard_completion=standard,
            granite_completion=granite,
            expected_locked_assets=(
                _assets() if expected_locked_assets is None else expected_locked_assets
            ),
        ),
        reader,
        writer,
        standard,
        granite,
    )


def _execution_standard_et_granite_sont_strictement_discriminees() -> None:
    source_content = b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n"
    standard_request, granite_request, _ = _page_jobs()
    standard_claim = _claimed(
        standard_request,
        job_number=61,
        owner="worker-documents-a",
    )
    granite_claim = _claimed(
        granite_request,
        job_number=62,
        owner="worker-documents-b",
    )
    handler, reader, writer, standard, granite = _handler_for(source_content)

    standard_result = handler.execute_standard(standard_claim)
    granite_result = handler.execute_granite(_granite_lease(granite_claim))

    assert standard_result.result.status is PageResultStatus.SUCCEEDED
    assert standard_result.result.granite_slot_execution is None
    assert granite_result.result.status is PageResultStatus.SUCCEEDED
    assert granite_result.result.granite_slot_execution.slot_generation == 4
    assert len(standard.calls) == len(granite.calls) == 1
    assert reader.reads == writer.writes == 2

    with pytest.raises(DistributionContractError, match="GRANITE_SLOT_IDENTITY_REQUIRED"):
        handler.execute_standard(granite_claim)
    with pytest.raises(DistributionContractError, match="GRANITE_SLOT_IDENTITY_FORBIDDEN"):
        handler.execute_granite(_granite_lease(standard_claim))
    assert reader.reads == writer.writes == 2


def _artefact_est_verifie_avant_convertisseur() -> None:
    request, _, _ = _page_jobs()
    claim = _claimed(request, job_number=63, owner="worker-documents-a")
    converter = _Converter(metrics=_standard_metrics())
    handler, reader, writer, _, _ = _handler_for(
        b"contenu divergent",
        converters=_converters(native=converter),
    )
    outcome = handler.execute_standard(claim)
    assert outcome.result.status is PageResultStatus.FAILED
    assert outcome.result.error_code is PageResultErrorCode.ARTIFACT_HASH_MISMATCH
    assert reader.reads == 0 or reader.reads == 1
    assert converter.calls == []
    assert writer.writes == 0


def _echec_stable_devient_enveloppe_terminale_sans_artefact() -> None:
    source_content = b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n"
    _, granite_request, _ = _page_jobs()
    claim = _claimed(granite_request, job_number=64, owner="worker-documents-b")
    failure = PageConversionFailure(
        error_code=PageResultErrorCode.GRANITE_DOCLING_TIMEOUT,
        technical_metrics=_granite_metrics(),
    )
    converter = _Converter(metrics=_granite_metrics(), failure=failure)
    handler, _, writer, _, completion = _handler_for(
        source_content,
        converters=_converters(granite=converter),
    )
    outcome = handler.execute_granite(_granite_lease(claim))
    assert outcome.result.status is PageResultStatus.FAILED
    assert outcome.result.error_code is PageResultErrorCode.GRANITE_DOCLING_TIMEOUT
    assert outcome.result.result_artifact is None
    assert writer.writes == 0
    assert completion.calls[0][1].failure_reason == "GRANITE_DOCLING_TIMEOUT"


def _dispatch_couvre_exactement_les_routes_autorisees() -> None:
    converters = _converters()
    assert converters.route_names == frozenset(
        {
            PageRouteName.NATIVE_STANDARD,
            PageRouteName.SCAN_GRANITE,
            PageRouteName.PREPROCESS_GRANITE,
            PageRouteName.BAD_OCR_TO_GRANITE,
            PageRouteName.MIXED_PAGEWISE,
            PageRouteName.TARGETED_ENRICHMENT,
        }
    )
    with pytest.raises(ValueError, match="PAGE_ROUTE_CONVERTER_INVALID"):
        replace(converters, targeted_enrichment=None)


def test_execute_document_page_unit() -> None:
    _execution_standard_et_granite_sont_strictement_discriminees()
    _artefact_est_verifie_avant_convertisseur()
    _echec_stable_devient_enveloppe_terminale_sans_artefact()
    _dispatch_couvre_exactement_les_routes_autorisees()
