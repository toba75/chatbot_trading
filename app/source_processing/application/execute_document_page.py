"""Exécution stricte d'un job ``CONVERT_PAGE`` sous son autorisation fenced."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.page_execution import (
    GranitePageTerminalEnvelope,
    GranitePageTerminalStatus,
    GraniteSlotLease,
)
from app.contracts.technical_jobs import ClaimedJob
from app.source_processing.domain.distribution_contracts import (
    ConvertPageContract,
    DistributionContractError,
    ExecutionCapability,
    GraniteSlotExecutionIdentity,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    PAGE_RESULT_CONTRACT_VERSION,
    PageExecutionIdentity,
    PageResultContract,
    PageResultErrorCode,
    PageResultStatus,
    PageTechnicalMetrics,
)
from app.source_processing.domain.document_processing_run import PageRouteName


_EXECUTED_PAGE_ROUTES = frozenset(
    {
        PageRouteName.NATIVE_STANDARD,
        PageRouteName.SCAN_GRANITE,
        PageRouteName.PREPROCESS_GRANITE,
        PageRouteName.BAD_OCR_TO_GRANITE,
        PageRouteName.MIXED_PAGEWISE,
        PageRouteName.TARGETED_ENRICHMENT,
    }
)


class PageArtifactReader(Protocol):
    def read(self, descriptor: LocalArtifactDescriptor) -> bytes: ...


class ImmutablePageArtifactWriter(Protocol):
    def write_immutable(
        self,
        *,
        identity: LocalArtifactIdentity,
        content: bytes,
    ) -> LocalArtifactDescriptor: ...


class RoutedPageConverter(Protocol):
    def convert_page(
        self,
        *,
        contract: ConvertPageContract,
        source_content: bytes,
        granite_lease: GraniteSlotLease | None,
    ) -> "PageConversionOutput": ...


class StandardPageCompletion(Protocol):
    def complete_standard_page_execution(
        self,
        claimed_job: ClaimedJob,
        envelope: GranitePageTerminalEnvelope,
    ) -> Any: ...


class GranitePageCompletion(Protocol):
    def complete_page_execution(
        self,
        lease: GraniteSlotLease,
        envelope: GranitePageTerminalEnvelope,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class PageConversionOutput:
    """Sortie calculée avant son écriture immutable dans le stockage SP."""

    content: bytes
    tool_name: str
    tool_version: str
    technical_metrics: PageTechnicalMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes) or len(self.content) == 0:
            raise ValueError("PAGE_CONVERSION_CONTENT_INVALID")
        _text(self.tool_name, "PAGE_CONVERSION_TOOL_INVALID")
        _text(self.tool_version, "PAGE_CONVERSION_TOOL_VERSION_INVALID")
        if not isinstance(self.technical_metrics, PageTechnicalMetrics):
            raise ValueError("PAGE_CONVERSION_METRICS_INVALID")


class PageConversionFailure(RuntimeError):
    """Échec convertisseur fermé transportable comme résultat terminal SP."""

    def __init__(
        self,
        *,
        error_code: PageResultErrorCode,
        technical_metrics: PageTechnicalMetrics,
    ) -> None:
        if not isinstance(error_code, PageResultErrorCode):
            raise ValueError("PAGE_CONVERSION_ERROR_CODE_INVALID")
        if not isinstance(technical_metrics, PageTechnicalMetrics):
            raise ValueError("PAGE_CONVERSION_METRICS_INVALID")
        self.error_code = error_code
        self.technical_metrics = technical_metrics
        super().__init__(error_code.value)


@dataclass(frozen=True, slots=True)
class PageRouteConverters:
    """Dispatch fermé : chaque route non vide possède un port explicite."""

    native_standard: RoutedPageConverter
    scan_granite: RoutedPageConverter
    preprocess_granite: RoutedPageConverter
    bad_ocr_to_granite: RoutedPageConverter
    mixed_pagewise: RoutedPageConverter
    targeted_enrichment: RoutedPageConverter

    def __post_init__(self) -> None:
        for converter in (
            self.native_standard,
            self.scan_granite,
            self.preprocess_granite,
            self.bad_ocr_to_granite,
            self.mixed_pagewise,
            self.targeted_enrichment,
        ):
            if not callable(getattr(converter, "convert_page", None)):
                raise ValueError("PAGE_ROUTE_CONVERTER_INVALID")

    @property
    def route_names(self) -> frozenset[PageRouteName]:
        return _EXECUTED_PAGE_ROUTES

    def for_route(self, route_name: PageRouteName) -> RoutedPageConverter:
        converters = {
            PageRouteName.NATIVE_STANDARD: self.native_standard,
            PageRouteName.SCAN_GRANITE: self.scan_granite,
            PageRouteName.PREPROCESS_GRANITE: self.preprocess_granite,
            PageRouteName.BAD_OCR_TO_GRANITE: self.bad_ocr_to_granite,
            PageRouteName.MIXED_PAGEWISE: self.mixed_pagewise,
            PageRouteName.TARGETED_ENRICHMENT: self.targeted_enrichment,
        }
        try:
            return converters[route_name]
        except KeyError as error:
            raise DistributionContractError("PAGE_ROUTE_CONVERTER_INVALID") from error


@dataclass(frozen=True, slots=True)
class PageExecutionOutcome:
    result: PageResultContract
    envelope: GranitePageTerminalEnvelope

    def __post_init__(self) -> None:
        if not isinstance(self.result, PageResultContract):
            raise ValueError("PAGE_RESULT_INVALID")
        if not isinstance(self.envelope, GranitePageTerminalEnvelope):
            raise ValueError("PAGE_TERMINAL_ENVELOPE_INVALID")


class ExecuteDocumentPageHandler:
    """Calcule une page, crée l'enveloppe platform, sans écrire le résultat SP."""

    def __init__(
        self,
        *,
        artifact_reader: PageArtifactReader,
        artifact_writer: ImmutablePageArtifactWriter,
        converters: PageRouteConverters,
        standard_completion: StandardPageCompletion,
        granite_completion: GranitePageCompletion,
    ) -> None:
        required_ports = (
            (artifact_reader, "read"),
            (artifact_writer, "write_immutable"),
            (standard_completion, "complete_standard_page_execution"),
            (granite_completion, "complete_page_execution"),
        )
        if any(not callable(getattr(port, method, None)) for port, method in required_ports):
            raise ValueError("PAGE_EXECUTION_PORT_INCOMPLETE")
        if not isinstance(converters, PageRouteConverters):
            raise ValueError("PAGE_ROUTE_CONVERTERS_INVALID")
        self._artifact_reader = artifact_reader
        self._artifact_writer = artifact_writer
        self._converters = converters
        self._standard_completion = standard_completion
        self._granite_completion = granite_completion

    def execute_standard(self, claimed_job: ClaimedJob) -> PageExecutionOutcome:
        claimed = _claimed_job(claimed_job)
        contract = ConvertPageContract.from_job_request(claimed.job.request)
        if contract.required_capacity.capability is not ExecutionCapability.DOCUMENT_STANDARD:
            raise DistributionContractError("GRANITE_SLOT_IDENTITY_REQUIRED")
        outcome = self._execute(
            claimed=claimed,
            contract=contract,
            granite_lease=None,
        )
        self._standard_completion.complete_standard_page_execution(
            claimed,
            outcome.envelope,
        )
        return outcome

    def execute_granite(self, lease: GraniteSlotLease) -> PageExecutionOutcome:
        if not isinstance(lease, GraniteSlotLease):
            raise DistributionContractError("GRANITE_SLOT_IDENTITY_REQUIRED")
        claimed = lease.claimed_job
        contract = ConvertPageContract.from_job_request(claimed.job.request)
        if contract.required_capacity.capability is not ExecutionCapability.GRANITE_CUDA:
            raise DistributionContractError("GRANITE_SLOT_IDENTITY_FORBIDDEN")
        outcome = self._execute(
            claimed=claimed,
            contract=contract,
            granite_lease=lease,
        )
        self._granite_completion.complete_page_execution(lease, outcome.envelope)
        return outcome

    def _execute(
        self,
        *,
        claimed: ClaimedJob,
        contract: ConvertPageContract,
        granite_lease: GraniteSlotLease | None,
    ) -> PageExecutionOutcome:
        execution = PageExecutionIdentity(
            job_id=claimed.job.job_id,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            worker_instance_id=claimed.lease_owner,
        )
        slot_execution = (
            None
            if granite_lease is None
            else GraniteSlotExecutionIdentity(
                slot_ordinal=granite_lease.slot_ordinal,
                slot_generation=granite_lease.slot_generation,
                slot_token=granite_lease.slot_token,
            )
        )
        source_content = self._artifact_reader.read(contract.source_artifact)
        contract.source_artifact.verify_content(source_content)
        converter = self._converters.for_route(contract.route_name)
        try:
            converted = converter.convert_page(
                contract=contract,
                source_content=source_content,
                granite_lease=granite_lease,
            )
        except PageConversionFailure as failure:
            result = PageResultContract(
                contract_version=PAGE_RESULT_CONTRACT_VERSION,
                environment_identity=contract.environment_identity,
                document_id=contract.document_id,
                processing_run_id=contract.processing_run_id,
                page_number=contract.page_number,
                route_name=contract.route_name,
                routing_policy_version=contract.routing_policy_version,
                request_idempotence_key=contract.idempotence_key,
                execution=execution,
                granite_slot_execution=slot_execution,
                status=PageResultStatus.FAILED,
                result_artifact=None,
                tool_name=None,
                tool_version=None,
                error_code=failure.error_code,
                technical_metrics=failure.technical_metrics,
            )
            return _outcome(
                claimed=claimed,
                granite_lease=granite_lease,
                result=result,
            )
        if not isinstance(converted, PageConversionOutput):
            raise ValueError("PAGE_CONVERSION_OUTPUT_INVALID")
        artifact = self._artifact_writer.write_immutable(
            identity=contract.expected_result_artifact,
            content=converted.content,
        )
        if (
            not isinstance(artifact, LocalArtifactDescriptor)
            or artifact.identity != contract.expected_result_artifact
        ):
            raise DistributionContractError("PAGE_RESULT_ARTIFACT_IDENTITY_DIVERGENT")
        artifact.verify_content(converted.content)
        result = PageResultContract(
            contract_version=PAGE_RESULT_CONTRACT_VERSION,
            environment_identity=contract.environment_identity,
            document_id=contract.document_id,
            processing_run_id=contract.processing_run_id,
            page_number=contract.page_number,
            route_name=contract.route_name,
            routing_policy_version=contract.routing_policy_version,
            request_idempotence_key=contract.idempotence_key,
            execution=execution,
            granite_slot_execution=slot_execution,
            status=PageResultStatus.SUCCEEDED,
            result_artifact=artifact,
            tool_name=converted.tool_name,
            tool_version=converted.tool_version,
            error_code=None,
            technical_metrics=converted.technical_metrics,
        )
        return _outcome(
            claimed=claimed,
            granite_lease=granite_lease,
            result=result,
        )


def _outcome(
    *,
    claimed: ClaimedJob,
    granite_lease: GraniteSlotLease | None,
    result: PageResultContract,
) -> PageExecutionOutcome:
    completion_id = page_completion_id(
        claimed_job=claimed,
        granite_lease=granite_lease,
    )
    succeeded = result.status is PageResultStatus.SUCCEEDED
    envelope = GranitePageTerminalEnvelope.from_payload(
        completion_id=completion_id,
        status=(
            GranitePageTerminalStatus.SUCCEEDED
            if succeeded
            else GranitePageTerminalStatus.FAILED
        ),
        payload=result.to_mapping(),
        failure_reason=None if succeeded else result.error_code.value,
    )
    return PageExecutionOutcome(result=result, envelope=envelope)


def page_completion_id(
    *,
    claimed_job: ClaimedJob,
    granite_lease: GraniteSlotLease | None,
) -> str:
    claimed = _claimed_job(claimed_job)
    if granite_lease is not None and granite_lease.claimed_job != claimed:
        raise DistributionContractError("GRANITE_SLOT_CLAIM_DIVERGENT")
    parts = (
        claimed.job.job_id,
        str(claimed.claim_generation),
        claimed.claim_token,
        "STANDARD" if granite_lease is None else str(granite_lease.slot_ordinal),
        "NONE" if granite_lease is None else str(granite_lease.slot_generation),
        "NONE" if granite_lease is None else granite_lease.slot_token,
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"PAGE-M014-{digest[:40].upper()}"


def _claimed_job(value: Any) -> ClaimedJob:
    if not isinstance(value, ClaimedJob):
        raise DistributionContractError("PAGE_EXECUTION_CLAIM_REQUIRED")
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(code)
    return value


__all__ = [
    "ExecuteDocumentPageHandler",
    "ImmutablePageArtifactWriter",
    "PageArtifactReader",
    "PageConversionFailure",
    "PageConversionOutput",
    "PageExecutionOutcome",
    "PageRouteConverters",
    "RoutedPageConverter",
    "page_completion_id",
]
