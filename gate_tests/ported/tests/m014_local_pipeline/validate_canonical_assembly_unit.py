"""Tests unitaires T-007 : complétude, ordre, autorité et rejeu canonique."""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256

import pytest

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.source_processing.application.assemble_canonical_document import (
    CanonicalAssemblyPolicy,
)
from app.source_processing.domain.distribution_contracts import (
    ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
    PAGE_RESULT_CONTRACT_VERSION,
    AssembleCanonicalDocumentContract,
    DistributionContractError,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    PageExecutionIdentity,
    PageResultContract,
    PageResultErrorCode,
    PageResultStatus,
    PageTechnicalMetrics,
    assemble_canonical_document_idempotence_key,
    convert_page_idempotence_key,
)
from app.source_processing.domain.document_processing_run import PageNumber, PageRouteName
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
)


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
)


def _contract(page_count: int = 3) -> AssembleCanonicalDocumentContract:
    manifest_hash = "a" * 64
    return AssembleCanonicalDocumentContract(
        contract_version=ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
        environment_identity=IDENTITY,
        document_id="DOC-M014-ASSEMBLY-UNIT",
        processing_run_id="RUN-M014-ASSEMBLY-UNIT",
        page_count=page_count,
        page_manifest_sha256=manifest_hash,
        page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        expected_canonical_artifact=(
            "artifact:source_processing.canonical_sources/"
            "CSRC-M014-ASSEMBLY-UNIT/"
            "CVER-M014-"
            + assemble_canonical_document_idempotence_key(
                processing_run_id="RUN-M014-ASSEMBLY-UNIT",
                page_manifest_sha256=manifest_hash,
                page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
                contract_version=ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
            )[:24].upper()
            + "/docling.json"
        ),
        idempotence_key=assemble_canonical_document_idempotence_key(
            processing_run_id="RUN-M014-ASSEMBLY-UNIT",
            page_manifest_sha256=manifest_hash,
            page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
            contract_version=ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
        ),
    )


def _page_bytes(page: int, text: str) -> bytes:
    artifact = PageConversionArtifact(
        page_number=PageNumber.from_value(page),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-m014-unit-v1",
        artifact_hash=f"{page:064x}",
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M014-ASSEMBLY-UNIT/page-{page:03d}.json"
        ),
        items=(
            PageConversionItem(
                label=PageConversionItemLabel.TEXT,
                text=text,
                geometry=PageItemGeometry(
                    left=10,
                    top=10,
                    right=90,
                    bottom=30,
                    page_width=100,
                    page_height=100,
                ),
                content_hash=sha256(text.encode()).hexdigest(),
            ),
        ),
    )
    return json.dumps(asdict(artifact), default=lambda value: value.value, sort_keys=True).encode()


def _result(page: int, *, status: PageResultStatus = PageResultStatus.SUCCEEDED) -> PageResultContract:
    route = PageRouteName.SKIP_EMPTY if status is PageResultStatus.SKIP_EMPTY else PageRouteName.NATIVE_STANDARD
    artifact = None
    if status is PageResultStatus.SUCCEEDED:
        content = _page_bytes(page, f"Texte canonique page {page}.")
        identity = LocalArtifactIdentity(
            environment="test",
            artifact_ref=f"artifact:source_processing.local/test/pages/page-{page:03d}.json",
            relative_path=f"pages/page-{page:03d}.json",
        )
        artifact = LocalArtifactDescriptor(
            identity=identity,
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
        )
    key = convert_page_idempotence_key(
        processing_run_id="RUN-M014-ASSEMBLY-UNIT",
        page_number=page,
        route_name=route,
        routing_policy_version="routing-m014-unit-v1",
        contract_version="1.0",
    )
    return PageResultContract(
        contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=IDENTITY,
        document_id="DOC-M014-ASSEMBLY-UNIT",
        processing_run_id="RUN-M014-ASSEMBLY-UNIT",
        page_number=page,
        route_name=route,
        routing_policy_version="routing-m014-unit-v1",
        request_idempotence_key=key,
        execution=(
            None
            if status is PageResultStatus.SKIP_EMPTY
            else PageExecutionIdentity(
                job_id=f"JOB-M002-{page:06d}",
                claim_generation=1,
                claim_token=f"00000000-0000-4000-8000-{page:012d}",
                worker_instance_id="worker-documents-a",
            )
        ),
        granite_slot_execution=None,
        status=status,
        result_artifact=artifact,
        tool_name=(
            "DOCLING_STANDARD" if status is PageResultStatus.SUCCEEDED else None
        ),
        tool_version=(
            "docling-m014-unit-v1" if status is PageResultStatus.SUCCEEDED else None
        ),
        error_code=(
            PageResultErrorCode.ARTIFACT_HASH_MISMATCH
            if status is PageResultStatus.FAILED
            else None
        ),
        technical_metrics=(
            None
            if status is PageResultStatus.SKIP_EMPTY
            else PageTechnicalMetrics(
                duration_seconds=0.1,
                peak_ram_bytes=1024,
                gpu=None,
            )
        ),
    )


def test_politique_assemblage_refuse_incomplet_echec_divergence_reordonne_et_ne_rehache_pas(
    monkeypatch,
) -> None:
    policy = CanonicalAssemblyPolicy()
    contract = _contract()
    # La politique travaille sur les faits SP et ne peut assimiler une absence à SKIP_EMPTY.
    with pytest.raises(DistributionContractError, match="PAGE_MANIFEST_INCOMPLETE"):
        policy.validate_results(contract=contract, results=(_result(1), _result(2)))
    with pytest.raises(DistributionContractError, match="PAGE_RESULT_TERMINAL_FAILURE"):
        policy.validate_results(
            contract=contract,
            results=(_result(1), _result(2, status=PageResultStatus.FAILED), _result(3)),
        )
    ordered = policy.validate_results(
        contract=contract,
        results=(_result(3), _result(1), _result(2)),
    )
    assert tuple(result.page_number for result in ordered) == (1, 2, 3)
    with pytest.raises(DistributionContractError, match="PAGE_RESULT_REPLAY_DIVERGENCE"):
        policy.validate_results(
            contract=contract,
            results=(_result(1), _result(1), _result(3)),
        )
    content = _page_bytes(1, "Texte canonique page 1.")
    result = _result(1)
    verifications = 0

    def count_verification(self, candidate: bytes) -> None:
        nonlocal verifications
        del self, candidate
        verifications += 1

    monkeypatch.setattr(LocalArtifactDescriptor, "verify_content", count_verification)
    outputs = CanonicalAssemblyPolicy().read_page_outputs(
        results=(result,),
        artifact_reader=type(
            "VerifiedReader",
            (),
            {"read": lambda self, descriptor: content},
        )(),
    )

    assert len(outputs) == 1
    assert verifications == 0
