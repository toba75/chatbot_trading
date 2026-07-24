"""Tests unitaires des value objects de distribution locale M-014."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SHA_A = "a" * 64
SHA_B = "b" * 64


def test_value_objects_et_serialisation_fermee(tmp_path: Path) -> None:
    from app.contracts.technical_jobs import (
        JobEnvironmentIdentity,
        JobExecutionRequirements,
        JobPriority,
        JobRequest,
    )
    from app.source_processing.domain.distribution_contracts import (
        CONVERT_PAGE_CONTRACT_VERSION,
        PAGE_RESULT_CONTRACT_VERSION,
        ConvertPageContract,
        DistributionContractError,
        ExecutionCapacityRequirement,
        LocalArtifactDescriptor,
        LocalArtifactIdentity,
        LockedAssetVersion,
        PageResultContract,
        PageResultStatus,
        convert_page_idempotence_key,
    )

    identity = JobEnvironmentIdentity("test", "ostrading-test-ci", SHA_A)
    source = LocalArtifactDescriptor(
        identity=LocalArtifactIdentity(
            environment="test",
            artifact_ref="artifact:source_processing.local/test/originals/DOC-U.pdf",
            relative_path="originals/DOC-U.pdf",
        ),
        sha256=SHA_B,
        size_bytes=10,
    )
    output = LocalArtifactIdentity(
        environment="test",
        artifact_ref="artifact:source_processing.local/test/results/RUN-U/page-1.json",
        relative_path="results/RUN-U/page-1.json",
    )
    key = convert_page_idempotence_key(
        processing_run_id="RUN-U",
        page_number=1,
        route_name="NATIVE_STANDARD",
        routing_policy_version="routing-v1",
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
    )
    contract = ConvertPageContract(
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id="DOC-U",
        processing_run_id="RUN-U",
        page_number=1,
        route_name="NATIVE_STANDARD",
        routing_policy_version="routing-v1",
        source_artifact=source,
        expected_result_artifact=output,
        required_capacity=ExecutionCapacityRequirement(
            capability="DOCUMENT_STANDARD",
            slots=0,
            device=None,
        ),
        locked_assets=(LockedAssetVersion("docling", "2.111.0", SHA_A),),
        idempotence_key=key,
    )
    assert ConvertPageContract.from_mapping(contract.to_mapping()) == contract
    assert json.loads(contract.to_json())["contract_version"] == "1.0"

    requirement_fields = tuple(field.name for field in fields(JobExecutionRequirements))
    assert requirement_fields == (
        "contract_name",
        "contract_version",
        "capacity_capability",
        "capacity_slots",
        "capacity_device",
        "storage_environment",
    )
    request = contract.to_job_request(
        priority=JobPriority.P1,
        code_version="m014-cycle3",
        model_version="docling-2.111.0",
    )
    assert ConvertPageContract.from_job_request(request) == contract
    assert request.execution_requirements == JobExecutionRequirements(
        contract_name="CONVERT_PAGE",
        contract_version="1.0",
        capacity_capability="DOCUMENT_STANDARD",
        capacity_slots=0,
        capacity_device=None,
        storage_environment="test",
    )
    assert not hasattr(request.execution_requirements, "route_name")
    assert not hasattr(request.execution_requirements, "source_artifact_ref")
    assert not hasattr(request.execution_requirements, "result_artifact_ref")

    neutral_request = JobRequest(
        environment="test",
        deployment_id="ostrading-test-ci",
        job_name="GENERIC_TECHNICAL_JOB",
        priority=JobPriority.P2,
        idempotence_key=replace(
            request.idempotence_key,
            job_name="GENERIC_TECHNICAL_JOB",
        ),
        execution_requirements=JobExecutionRequirements(
            contract_name="GENERIC_TECHNICAL_CONTRACT",
            contract_version="7.3",
            capacity_capability="GENERIC_CAPABILITY",
            capacity_slots=0,
            capacity_device=None,
            storage_environment="test",
        ),
        payload={"contract_version": "7.3"},
    )
    assert neutral_request.execution_requirements.contract_version == "7.3"

    with pytest.raises(ValueError, match="storage_environment incohérent"):
        JobRequest(
            environment=request.environment,
            deployment_id=request.deployment_id,
            job_name=request.job_name,
            priority=request.priority,
            idempotence_key=request.idempotence_key,
            execution_requirements=replace(
                request.execution_requirements,
                storage_environment="development",
            ),
            payload=request.payload,
        )

    for divergent_fields in (
        {"capacity_capability": "GRANITE_CUDA"},
        {"capacity_slots": 1, "capacity_device": "cuda:0"},
        {"capacity_slots": 1, "capacity_device": "cpu"},
    ):
        divergent_request = JobRequest(
            environment=request.environment,
            deployment_id=request.deployment_id,
            job_name=request.job_name,
            priority=request.priority,
            idempotence_key=request.idempotence_key,
            execution_requirements=replace(
                request.execution_requirements,
                **divergent_fields,
            ),
            payload=request.payload,
        )
        with pytest.raises(
            DistributionContractError,
            match="JOB_EXECUTION_REQUIREMENTS_MISMATCH",
        ):
            ConvertPageContract.from_job_request(divergent_request)

    mutations = (
        (
            {
                key: value
                for key, value in contract.to_mapping().items()
                if key != "route_name"
            },
            "CONTRACT_FIELDS_INVALID",
        ),
        (
            contract.to_mapping() | {"route_name": "SKIP_EMPTY"},
            "CONVERT_PAGE_ROUTE_INVALID",
        ),
        (contract.to_mapping() | {"page_number": 0}, "PAGE_NUMBER_INVALID"),
        (
            contract.to_mapping() | {"contract_version": "2.0"},
            "CONTRACT_VERSION_UNSUPPORTED",
        ),
        (
            contract.to_mapping() | {"idempotence_key": SHA_B},
            "IDEMPOTENCE_KEY_DIVERGENT",
        ),
    )
    for payload, code in mutations:
        with pytest.raises(DistributionContractError, match=code):
            ConvertPageContract.from_mapping(payload)

    duplicate_field_json = contract.to_json().replace(
        '"contract_version":"1.0",',
        '"contract_version":"1.0","contract_version":"1.0",',
        1,
    )
    with pytest.raises(DistributionContractError, match="CONTRACT_JSON_INVALID"):
        ConvertPageContract.from_json(duplicate_field_json)

    skipped = PageResultContract(
        contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id="DOC-U",
        processing_run_id="RUN-U",
        page_number=2,
        route_name="SKIP_EMPTY",
        routing_policy_version="routing-v1",
        request_idempotence_key=convert_page_idempotence_key(
            processing_run_id="RUN-U",
            page_number=2,
            route_name="SKIP_EMPTY",
            routing_policy_version="routing-v1",
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

    invalid_skipped = skipped.to_mapping()
    invalid_skipped["tool_name"] = "GRANITE_DOCLING"
    with pytest.raises(
        DistributionContractError, match="SKIP_EMPTY_CONVERTER_FORBIDDEN"
    ):
        PageResultContract.from_mapping(invalid_skipped)

    _assert_schema_de_configuration_refuse_toute_derive(tmp_path)
    _assert_codes_terminaux_relis_publiquement()


def _assert_codes_terminaux_relis_publiquement() -> None:
    from app.source_processing.application.document_commands import (
        DocumentConversionExecutionPhase,
        DocumentConversionState,
        DocumentConversionStatus,
    )
    from app.source_processing.domain.source_document import DocumentId

    for code in (
        "GRANITE_DOCLING_TIMEOUT",
        "GEMMA_VISION_TIMEOUT",
        "JOB_LEASE_LOST",
        "GRANITE_CAPACITY_CONFIGURATION_INVALID",
    ):
        state = DocumentConversionState(
            document_id=DocumentId.from_value("DOC-AAAAAAAAAAAAAAAA"),
            conversion_status=DocumentConversionStatus.QA_REJECTED,
            canonical_version_id=None,
            rejection_error_code=code,
            execution_phase=DocumentConversionExecutionPhase.FAILED,
            completed_units=0,
            total_units=1,
            failure_error_code=code,
        )
        assert state.failure_error_code == code


def _assert_schema_de_configuration_refuse_toute_derive(tmp_path: Path) -> None:
    from app.platform.configuration import (
        ApplicationConfigurationError,
        load_application_configuration,
    )

    source = (REPOSITORY_ROOT / "config" / "environments" / "test.yaml").read_text(
        encoding="utf-8"
    )
    valid_path = tmp_path / "valid.yaml"
    valid_path.write_text(source, encoding="utf-8")
    configuration = load_application_configuration(
        config_path=valid_path,
        environment_snapshot={},
    )
    assert configuration.services.workers.local_distribution.granite_device == "cuda:0"

    mutations = {
        "replica_3": ("      replicas: 2", "      replicas: 3"),
        "memory_null": ("      memory_bytes: 2147483648", "      memory_bytes: null"),
        "cpu_string": ("      cpus: 4", '      cpus: "4"'),
        "device_auto": ("      granite_device: cuda:0", "      granite_device: auto"),
        "device_cpu": ("      granite_device: cuda:0", "      granite_device: cpu"),
        "global_3": (
            "      granite_slots_global: 2",
            "      granite_slots_global: 3",
        ),
        "per_worker_2": (
            "      granite_slots_per_worker: 1",
            "      granite_slots_per_worker: 2",
        ),
        "granite_concurrency_2": (
            "    granite_concurrency: 1",
            "    granite_concurrency: 2",
        ),
    }
    for name, (old, new) in mutations.items():
        assert old in source
        path = tmp_path / f"{name}.yaml"
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
        with pytest.raises(
            ApplicationConfigurationError, match="CONFIG_SCHEMA_INVALID"
        ):
            load_application_configuration(config_path=path, environment_snapshot={})

    missing = tmp_path / "missing.yaml"
    missing.write_text(
        source.replace(
            "      granite_slots_per_worker: 1\n",
            "",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ApplicationConfigurationError, match="CONFIG_KEY_MISSING"):
        load_application_configuration(config_path=missing, environment_snapshot={})

    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(
        source.replace(
            "      granite_slots_per_worker: 1\n",
            "      granite_slots_per_worker: 1\n      fallback_device: cpu\n",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ApplicationConfigurationError, match="CONFIG_SCHEMA_INVALID"):
        load_application_configuration(config_path=unknown, environment_snapshot={})
