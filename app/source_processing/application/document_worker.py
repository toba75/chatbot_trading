"""Exécution idempotente des diagnostics documentaires SP."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from app.contracts.technical_jobs import ClaimedJob, JobStatus
from app.source_processing.application.approve_route_plan import (
    ApproveRoutePlanCommand,
    ApproveRoutePlanHandler,
)
from app.source_processing.application.record_page_diagnostics import (
    PageDiagnosticInput,
    RecordPageDiagnosticsCommand,
    RecordPageDiagnosticsHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRunStatus,
    PageRoutingConfiguration,
)
from app.source_processing.domain.source_document import DocumentId


@runtime_checkable
class DiagnosticInspector(Protocol):
    """Port SP d'inspection bornée de l'original sans dépendance à pypdf."""

    def inspect(self, original_storage_ref: str) -> tuple[PageDiagnosticInput, ...]:
        """Retourne un diagnostic réel pour chaque page de l'original."""


class WorkerProcessingError(RuntimeError):
    """Erreur stable classée pour la politique de reprise du worker."""

    def __init__(self, error_code: str, *, retryable: bool) -> None:
        self.error_code = _required_error_code(error_code)
        if not isinstance(retryable, bool):
            raise ValueError("retryable non booléen")
        self.retryable = retryable
        super().__init__(self.error_code)


class DocumentDiagnosticWorker:
    """Consomme un job DIAGNOSE et persiste les sorties page par page dans SP."""

    def __init__(
        self,
        *,
        source_document_repository: Any,
        processing_run_repository: Any,
        diagnostic_inspector: DiagnosticInspector,
        routing_configuration: PageRoutingConfiguration,
    ) -> None:
        if not callable(getattr(source_document_repository, "find_by_document_id", None)):
            raise ValueError("source_document_repository invalide")
        if not callable(getattr(processing_run_repository, "find_by_document_id", None)):
            raise ValueError("processing_run_repository invalide")
        if not callable(getattr(processing_run_repository, "save", None)):
            raise ValueError("processing_run_repository sans sauvegarde")
        if not isinstance(diagnostic_inspector, DiagnosticInspector):
            raise ValueError("diagnostic_inspector invalide")
        if not isinstance(routing_configuration, PageRoutingConfiguration):
            raise ValueError("routing_configuration invalide")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._diagnostic_inspector = diagnostic_inspector
        self._routing_configuration = routing_configuration
        self._diagnostics_handler = RecordPageDiagnosticsHandler(
            processing_run_repository=processing_run_repository
        )
        self._route_plan_handler = ApproveRoutePlanHandler(
            processing_run_repository=processing_run_repository
        )

    def execute(self, claimed_job: ClaimedJob) -> Mapping[str, Any]:
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        job = claimed_job.job
        if job.status is not JobStatus.RUNNING or job.request.job_name != "DIAGNOSE":
            raise ValueError("job DIAGNOSE running requis")
        payload = dict(job.request.payload)
        document_id = DocumentId.from_value(_required_text(payload, "document_id"))
        processing_run_id = _required_text(payload, "processing_run_id")
        original_storage_ref = _required_text(payload, "original_storage_ref")
        source_sha256 = _required_text(payload, "source_sha256")

        source = self._source_document_repository.find_by_document_id(document_id)
        if source is None:
            raise WorkerProcessingError("SOURCE_NOT_FOUND", retryable=False)
        if source.fingerprint.value != source_sha256:
            raise WorkerProcessingError("SOURCE_FINGERPRINT_MISMATCH", retryable=False)
        if source.original_storage_ref.value != original_storage_ref:
            raise WorkerProcessingError("ORIGINAL_STORAGE_REF_MISMATCH", retryable=False)
        processing_run = self._processing_run_repository.find_by_document_id(document_id)
        if processing_run is None:
            raise WorkerProcessingError("PROCESSING_RUN_NOT_FOUND", retryable=False)
        if processing_run.processing_run_id.value != processing_run_id:
            raise WorkerProcessingError("PROCESSING_RUN_ID_MISMATCH", retryable=False)

        if processing_run.status is DocumentProcessingRunStatus.DIAGNOSED:
            return _diagnosis_result(self._approve_route_plan(processing_run))
        if processing_run.status is DocumentProcessingRunStatus.FAILED:
            raise WorkerProcessingError(
                processing_run.failure_error_code or "PROCESSING_RUN_FAILED",
                retryable=False,
            )
        if processing_run.status is DocumentProcessingRunStatus.MANIFEST_CREATED:
            processing_run = processing_run.begin_diagnosis()
            self._processing_run_repository.save(processing_run)
        if processing_run.status is not DocumentProcessingRunStatus.DIAGNOSING:
            raise WorkerProcessingError("PROCESSING_RUN_STATUS_INVALID", retryable=False)

        diagnostics = self._diagnostic_inspector.inspect(source.original_storage_ref.value)
        diagnosed = self._diagnostics_handler.handle(
            RecordPageDiagnosticsCommand(
                processing_run=processing_run,
                diagnostics=diagnostics,
            )
        )
        return _diagnosis_result(self._approve_route_plan(diagnosed))

    def _approve_route_plan(self, processing_run: Any) -> Any:
        """Termine la chaîne DIAGNOSE avec l'unique politique M-003 versionnée."""

        return self._route_plan_handler.handle(
            ApproveRoutePlanCommand(
                processing_run=processing_run,
                routing_configuration=self._routing_configuration,
            )
        )

    def mark_failed(self, claimed_job: ClaimedJob, error_code: str) -> None:
        """Rend l'échec terminal visible dans l'agrégat SP public."""

        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        parsed_error_code = _required_error_code(error_code)
        payload = dict(claimed_job.job.request.payload)
        document_id = DocumentId.from_value(_required_text(payload, "document_id"))
        processing_run = self._processing_run_repository.find_by_document_id(document_id)
        if processing_run is None:
            raise WorkerProcessingError("PROCESSING_RUN_NOT_FOUND", retryable=False)
        if processing_run.status is DocumentProcessingRunStatus.FAILED:
            if processing_run.failure_error_code != parsed_error_code:
                raise WorkerProcessingError("PROCESSING_RUN_FAILURE_CONFLICT", retryable=False)
            return
        self._processing_run_repository.save(processing_run.fail(parsed_error_code))


def _diagnosis_result(processing_run: Any) -> Mapping[str, Any]:
    return {
        "document_id": processing_run.document_id.value,
        "processing_run_id": processing_run.processing_run_id.value,
        "diagnosed_page_count": len(processing_run.page_decisions),
        "diagnostic_status": processing_run.status.value,
        "aggregate_version": processing_run.aggregate_version,
    }


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise WorkerProcessingError(f"JOB_PAYLOAD_INVALID_{field_name.upper()}", retryable=False)
    return value


def _required_error_code(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("error_code invalide")
    if not value.replace("_", "").isalnum() or value.upper() != value:
        raise ValueError("error_code invalide")
    return value


__all__ = ["DiagnosticInspector", "DocumentDiagnosticWorker", "WorkerProcessingError"]
