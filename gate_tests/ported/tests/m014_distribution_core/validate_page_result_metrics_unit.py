"""Tests unitaires des mesures techniques du résultat de page M-014."""

from __future__ import annotations

from dataclasses import replace

import pytest


SHA_A = "a" * 64


def test_metriques_resultat_page_strictes_par_route() -> None:
    from app.contracts.technical_jobs import JobEnvironmentIdentity
    from app.source_processing.domain.distribution_contracts import (
        CONVERT_PAGE_CONTRACT_VERSION,
        PAGE_RESULT_CONTRACT_VERSION,
        DistributionContractError,
        GraniteSlotExecutionIdentity,
        LocalArtifactDescriptor,
        LocalArtifactIdentity,
        PageExecutionIdentity,
        PageGpuMetrics,
        PageResultContract,
        PageResultStatus,
        PageTechnicalMetrics,
        convert_page_idempotence_key,
    )

    identity = JobEnvironmentIdentity("test", "ostrading-test-ci", SHA_A)
    execution = PageExecutionIdentity(
        job_id="JOB-M002-000314",
        claim_generation=2,
        claim_token="7af3de41-8ce4-4f89-9bbb-bd8f0014cc95",
        worker_instance_id="worker-documents-test-2",
    )
    slot = GraniteSlotExecutionIdentity(
        slot_ordinal=2,
        slot_generation=4,
        slot_token="87847b5b-8343-49c6-bd62-9651a69d2d0b",
    )
    gpu = PageGpuMetrics(
        peak_vram_bytes=1_426_063_360,
        peak_utilization_percent=93.0,
        peak_power_watts=41.5,
    )
    granite_metrics = PageTechnicalMetrics(
        duration_seconds=20.582,
        peak_ram_bytes=1_610_612_736,
        gpu=gpu,
    )
    standard_metrics = PageTechnicalMetrics(
        duration_seconds=1.25,
        peak_ram_bytes=268_435_456,
        gpu=None,
    )

    def result(*, page_number: int, route_name: str, metrics, granite_slot):
        return PageResultContract(
            contract_version=PAGE_RESULT_CONTRACT_VERSION,
            environment_identity=identity,
            document_id="DOC-M014-METRICS",
            processing_run_id="RUN-M014-METRICS",
            page_number=page_number,
            route_name=route_name,
            routing_policy_version="routing-m014-v1",
            request_idempotence_key=convert_page_idempotence_key(
                processing_run_id="RUN-M014-METRICS",
                page_number=page_number,
                route_name=route_name,
                routing_policy_version="routing-m014-v1",
                contract_version=CONVERT_PAGE_CONTRACT_VERSION,
            ),
            execution=execution,
            granite_slot_execution=granite_slot,
            status=PageResultStatus.SUCCEEDED,
            result_artifact=LocalArtifactDescriptor(
                identity=LocalArtifactIdentity(
                    environment="test",
                    artifact_ref=(
                        "artifact:source_processing.local/test/results/"
                        f"page-{page_number}.json"
                    ),
                    relative_path=f"results/page-{page_number}.json",
                ),
                sha256=SHA_A,
                size_bytes=1024,
            ),
            tool_name="GRANITE_DOCLING" if granite_slot is not None else "DOCLING",
            tool_version="2.111.0",
            error_code=None,
            technical_metrics=metrics,
        )

    granite = result(
        page_number=1,
        route_name="SCAN_GRANITE",
        metrics=granite_metrics,
        granite_slot=slot,
    )
    standard = result(
        page_number=2,
        route_name="NATIVE_STANDARD",
        metrics=standard_metrics,
        granite_slot=None,
    )
    assert PageResultContract.from_json(granite.to_json()) == granite
    assert PageResultContract.from_json(standard.to_json()) == standard

    for invalid_metrics in (
        replace(granite_metrics, duration_seconds=0),
        replace(granite_metrics, duration_seconds=float("inf")),
        replace(granite_metrics, peak_ram_bytes=0),
    ):
        with pytest.raises(
            DistributionContractError,
            match="PAGE_RESULT_METRICS_INVALID",
        ):
            replace(granite, technical_metrics=invalid_metrics)

    for invalid_gpu in (
        replace(gpu, peak_vram_bytes=-1),
        replace(gpu, peak_utilization_percent=100.1),
        replace(gpu, peak_power_watts=-0.1),
    ):
        with pytest.raises(
            DistributionContractError,
            match="PAGE_RESULT_GPU_METRICS_INVALID",
        ):
            replace(granite_metrics, gpu=invalid_gpu)

    with pytest.raises(
        DistributionContractError,
        match="PAGE_RESULT_GPU_METRICS_REQUIRED",
    ):
        replace(granite, technical_metrics=replace(granite_metrics, gpu=None))
    with pytest.raises(
        DistributionContractError,
        match="PAGE_RESULT_GPU_METRICS_FORBIDDEN",
    ):
        replace(standard, technical_metrics=replace(standard_metrics, gpu=gpu))

    missing_metrics = granite.to_mapping()
    del missing_metrics["technical_metrics"]
    with pytest.raises(DistributionContractError, match="CONTRACT_FIELDS_INVALID"):
        PageResultContract.from_mapping(missing_metrics)

    unknown_gpu_metric = granite.to_mapping()
    unknown_gpu_metric["technical_metrics"]["gpu"]["temperature_celsius"] = 60
    with pytest.raises(DistributionContractError, match="CONTRACT_FIELDS_INVALID"):
        PageResultContract.from_mapping(unknown_gpu_metric)

    skipped = PageResultContract(
        contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id="DOC-M014-METRICS",
        processing_run_id="RUN-M014-METRICS",
        page_number=3,
        route_name="SKIP_EMPTY",
        routing_policy_version="routing-m014-v1",
        request_idempotence_key=convert_page_idempotence_key(
            processing_run_id="RUN-M014-METRICS",
            page_number=3,
            route_name="SKIP_EMPTY",
            routing_policy_version="routing-m014-v1",
            contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        ),
        execution=None,
        granite_slot_execution=None,
        status=PageResultStatus.SKIP_EMPTY,
        result_artifact=None,
        tool_name=None,
        tool_version=None,
        error_code=None,
        technical_metrics=None,
    )
    assert PageResultContract.from_json(skipped.to_json()) == skipped
    with pytest.raises(
        DistributionContractError,
        match="SKIP_EMPTY_METRICS_FORBIDDEN",
    ):
        replace(skipped, technical_metrics=standard_metrics)
