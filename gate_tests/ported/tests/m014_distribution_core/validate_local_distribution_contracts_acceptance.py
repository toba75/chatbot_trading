"""Acceptation BDD des contrats publics de distribution locale M-014."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SHA_A = "a" * 64
SHA_B = "b" * 64
CLAIM_TOKEN = "7af3de41-8ce4-4f89-9bbb-bd8f0014cc95"


def test_contrats_locaux_versionnes_et_refusables() -> None:
    from app.contracts.technical_jobs import (
        JobEnvironmentIdentity,
        JobPriority,
        JobRequest,
    )
    from app.source_processing.domain.distribution_contracts import (
        CONVERT_PAGE_CONTRACT_VERSION,
        PAGE_RESULT_CONTRACT_VERSION,
        ArtifactContractError,
        AssembleCanonicalDocumentContract,
        ConvertPageContract,
        DistributionContractError,
        ExecutionCapacityRequirement,
        LocalArtifactDescriptor,
        LocalArtifactIdentity,
        LockedAssetVersion,
        PageExecutionIdentity,
        GraniteSlotExecutionIdentity,
        PageResultContract,
        PageResultErrorCode,
        PageResultStatus,
        assemble_canonical_document_idempotence_key,
        convert_page_idempotence_key,
    )

    # Given un job CONVERT_PAGE versionné désigne une page routée et un
    # artefact Source Processing appartenant à l'environnement test.
    identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
        configuration_hash=SHA_A,
    )
    source_identity = LocalArtifactIdentity(
        environment="test",
        artifact_ref="artifact:source_processing.local/test/originals/DOC-A.pdf",
        relative_path="originals/DOC-A.pdf",
    )
    result_identity = LocalArtifactIdentity(
        environment="test",
        artifact_ref=(
            "artifact:source_processing.local/test/processing/RUN-A/page-002-mixed.json"
        ),
        relative_path="processing/RUN-A/page-002-mixed.json",
    )
    capacity = ExecutionCapacityRequirement(
        capability="GRANITE_CUDA",
        slots=1,
        device="cuda:0",
    )
    request_key = convert_page_idempotence_key(
        processing_run_id="RUN-A",
        page_number=2,
        route_name="MIXED_PAGEWISE",
        routing_policy_version="routing-v1",
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
    )
    contract = ConvertPageContract(
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id="DOC-A",
        processing_run_id="RUN-A",
        page_number=2,
        route_name="MIXED_PAGEWISE",
        routing_policy_version="routing-v1",
        source_artifact=LocalArtifactDescriptor(
            identity=source_identity,
            sha256=SHA_B,
            size_bytes=4096,
        ),
        expected_result_artifact=result_identity,
        required_capacity=capacity,
        locked_assets=(
            LockedAssetVersion(
                name="granite-docling",
                version="ibm-granite/granite-docling-258M@locked",
                sha256=SHA_A,
            ),
        ),
        idempotence_key=request_key,
    )

    # When le worker valide le contrat et la configuration de capacité.
    serialized_request = contract.to_json()
    parsed_request = ConvertPageContract.from_json(serialized_request)
    technical_job = parsed_request.to_job_request(
        priority=JobPriority.P2,
        code_version="m014-contracts-v1",
        model_version="granite-docling-locked",
    )

    # Then le DTO technique reste neutre et le contrat SP est déterministe.
    assert isinstance(technical_job, JobRequest)
    assert technical_job.job_name == "CONVERT_PAGE"
    assert dict(technical_job.payload) == parsed_request.to_mapping()
    assert parsed_request == contract
    assert parsed_request.to_json() == serialized_request
    assert parsed_request.required_capacity == capacity

    incompatible_envelope = JobRequest(
        environment="test",
        deployment_id="ostrading-test-rogue",
        job_name="CONVERT_PAGE",
        priority=JobPriority.P2,
        idempotence_key=technical_job.idempotence_key,
        payload=parsed_request.to_mapping(),
    )
    with pytest.raises(
        DistributionContractError,
        match="JOB_ENVELOPE_IDENTITY_MISMATCH",
    ):
        ConvertPageContract.from_job_request(incompatible_envelope)

    execution = PageExecutionIdentity(
        job_id="JOB-M002-000314",
        claim_generation=2,
        claim_token=CLAIM_TOKEN,
        worker_instance_id="worker-documents-test-2",
    )
    slot_execution = GraniteSlotExecutionIdentity(
        slot_ordinal=2,
        slot_generation=4,
        slot_token="87847b5b-8343-49c6-bd62-9651a69d2d0b",
    )
    page_result = PageResultContract(
        contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id="DOC-A",
        processing_run_id="RUN-A",
        page_number=2,
        route_name="MIXED_PAGEWISE",
        routing_policy_version="routing-v1",
        request_idempotence_key=request_key,
        execution=execution,
        granite_slot_execution=slot_execution,
        status=PageResultStatus.SUCCEEDED,
        result_artifact=LocalArtifactDescriptor(
            identity=result_identity,
            sha256=SHA_A,
            size_bytes=1024,
        ),
        tool_name="GRANITE_DOCLING",
        tool_version="2.111.0",
        error_code=None,
    )
    assert PageResultContract.from_json(page_result.to_json()) == page_result
    assert PageResultContract.from_json(
        page_result.to_json()
    ).granite_slot_execution == (slot_execution)
    page_result.assert_replay_compatible(
        PageResultContract.from_json(page_result.to_json())
    )

    divergent_replay = replace(
        page_result,
        result_artifact=replace(page_result.result_artifact, sha256=SHA_B),
    )
    with pytest.raises(
        DistributionContractError, match="PAGE_RESULT_REPLAY_DIVERGENCE"
    ):
        page_result.assert_replay_compatible(divergent_replay)

    assembly_key = assemble_canonical_document_idempotence_key(
        processing_run_id="RUN-A",
        page_manifest_sha256=SHA_B,
        page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        contract_version="1.0",
    )
    assembly = AssembleCanonicalDocumentContract(
        contract_version="1.0",
        environment_identity=identity,
        document_id="DOC-A",
        processing_run_id="RUN-A",
        page_count=2,
        page_manifest_sha256=SHA_B,
        page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        expected_canonical_artifact=LocalArtifactIdentity(
            environment="test",
            artifact_ref="artifact:source_processing.local/test/canonical/DOC-A-v1.json",
            relative_path="canonical/DOC-A-v1.json",
        ),
        idempotence_key=assembly_key,
    )
    assert AssembleCanonicalDocumentContract.from_json(assembly.to_json()) == assembly
    assert (
        assembly.to_job_request(
            priority=JobPriority.P2,
            code_version="m014-contracts-v1",
            model_version="document-authority-m004",
        ).job_name
        == "ASSEMBLE_CANONICAL_DOCUMENT"
    )

    # Toute divergence est refusée avant le premier accès au modèle.
    mismatched_environment = contract.to_mapping()
    mismatched_environment["source_artifact"]["identity"]["environment"] = "production"
    with pytest.raises(
        DistributionContractError, match="CONTRACT_ENVIRONMENT_MISMATCH"
    ):
        ConvertPageContract.from_mapping(mismatched_environment)

    unknown_field = contract.to_mapping()
    unknown_field["fallback"] = "cpu"
    with pytest.raises(DistributionContractError, match="CONTRACT_FIELDS_INVALID"):
        ConvertPageContract.from_mapping(unknown_field)

    invalid_capacity = contract.to_mapping()
    invalid_capacity["required_capacity"]["device"] = "auto"
    with pytest.raises(DistributionContractError, match="CAPACITY_DEVICE_INVALID"):
        ConvertPageContract.from_mapping(invalid_capacity)

    with pytest.raises(ArtifactContractError, match="ARTIFACT_PATH_INVALID"):
        LocalArtifactIdentity(
            environment="test",
            artifact_ref="artifact:source_processing.local/test/../production/source.pdf",
            relative_path="../production/source.pdf",
        )
    with pytest.raises(ArtifactContractError, match="ARTIFACT_HASH_MISMATCH"):
        contract.source_artifact.verify_content(b"contenu divergent")

    for error_code in (
        PageResultErrorCode.GRANITE_CAPACITY_CONFIGURATION_INVALID,
        PageResultErrorCode.GRANITE_CUDA_UNAVAILABLE,
        PageResultErrorCode.WORKER_MEMORY_LIMIT_EXCEEDED,
        PageResultErrorCode.ARTIFACT_NOT_FOUND,
        PageResultErrorCode.ARTIFACT_OUTSIDE_PROFILE_ROOT,
        PageResultErrorCode.ARTIFACT_HASH_MISMATCH,
    ):
        failed_result = replace(
            page_result,
            status=PageResultStatus.FAILED,
            result_artifact=None,
            tool_name=None,
            tool_version=None,
            error_code=error_code,
        )
        assert (
            PageResultContract.from_json(failed_result.to_json()).error_code
            is error_code
        )

    _assert_configuration_locale_des_trois_profils()


def _assert_configuration_locale_des_trois_profils() -> None:
    from app.platform.configuration import load_application_configuration
    from app.platform.environment_compose import (
        ENVIRONMENTS,
        environment_stack_definition,
        render_environment_compose,
        validate_environment_compose_matrix,
    )

    technical_environment = {
        "OSTRADING_IMAGE_REVISION": "a" * 40,
        "OSTRADING_POSTGRES_SCHEMA_VERSION": "021",
    }
    definitions = {
        environment: environment_stack_definition(
            environment,
            repository_root=REPOSITORY_ROOT,
        )
        for environment in ENVIRONMENTS
    }
    rendered = {
        environment: render_environment_compose(
            definition,
            technical_environment=technical_environment,
        )
        for environment, definition in definitions.items()
    }
    validate_environment_compose_matrix(rendered, definitions=definitions)

    for environment in ENVIRONMENTS:
        configuration = load_application_configuration(
            config_path=definitions[environment].configuration_path,
            environment_snapshot={},
        )
        distribution = configuration.services.workers.local_distribution
        assert distribution.replicas == 2
        assert distribution.memory_bytes == 2 * 1024**3
        assert distribution.cpus == 4
        assert distribution.granite_device == "cuda:0"
        assert distribution.granite_slots_global == 2
        assert distribution.granite_slots_per_worker == 1

        worker = rendered[environment]["services"]["worker-documents"]
        assert worker["deploy"]["replicas"] == distribution.replicas
        assert worker["deploy"]["resources"]["limits"]["memory"] == str(
            distribution.memory_bytes
        )
        assert worker["deploy"]["resources"]["limits"]["cpus"] == distribution.cpus
        assert "environment" not in worker and "env_file" not in worker
