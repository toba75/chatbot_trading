"""Commandes documentaires applicatives exposées par le contexte SP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
    JobSubmissionDecision,
)
from app.source_processing.application.canonical_audit_signals import (
    PreCanonicalAuditEvent,
)
from app.source_processing.application.register_source_document import (
    OriginalSourceStore,
    RegisterSourceDocumentCommand,
    RegisterSourceDocumentHandler,
    SourceDocumentRepository,
)
from app.source_processing.application.start_document_processing import (
    DocumentInspector,
    ProcessingRunRepository,
    StartDocumentProcessingCommand,
    StartDocumentProcessingHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import (
    DocumentId,
    SourceDocument,
    SourceDocumentStatus,
)


class SourceDocumentLookupRepository(SourceDocumentRepository, Protocol):
    """Dépôt de sources avec lecture par identité métier."""

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        """Retourne la source documentaire connue pour l'identité donnée."""


class ProcessingRunLookupRepository(ProcessingRunRepository, Protocol):
    """Dépôt de tentatives avec lecture par document."""

    def find_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None:
        """Retourne une tentative déjà demandée pour ce document."""

    def submit_processing_run(
        self,
        processing_run: DocumentProcessingRun,
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        """Persiste la tentative et soumet le job DIAGNOSE en une opération atomique."""


class DocumentConversionRepository(Protocol):
    """Dépôt dédié aux demandes de conversion canonique M-004."""

    def find_conversion_by_document_id(
        self,
        document_id: DocumentId,
    ) -> "DocumentConversionState | None":
        """Retourne l'état de conversion canonique déjà connu."""

    def submit_conversion_request(
        self,
        conversion_state: "DocumentConversionState",
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        """Persiste la demande de conversion et soumet le job CONVERT_DOCUMENT."""


class DocumentCommandError(ValueError):
    """Erreur métier stable des commandes documentaires SP."""


class SourceNotFoundError(DocumentCommandError):
    """Erreur produite quand le DocumentId n'est pas connu de SP."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        super().__init__(f"source documentaire inconnue: {self.document_id}")


class SourceUnreadableError(DocumentCommandError):
    """Erreur produite quand le PDF original ne peut pas devenir source prête."""

    def __init__(self, reason: str) -> None:
        self.reason = _ensure_text(reason, "reason")
        super().__init__(self.reason)


class DiagnosisAlreadyRequestedError(DocumentCommandError):
    """Erreur produite quand une demande de diagnostic existe déjà."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        super().__init__(f"diagnostic déjà demandé: {self.document_id}")


class SourceQuarantinedError(DocumentCommandError):
    """Erreur produite quand une source ou tentative est explicitement en quarantaine."""

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        self.reason = _ensure_text(reason, "reason")
        super().__init__(f"source en quarantaine: {self.document_id}; {self.reason}")


class SourceNotRoutedError(DocumentCommandError):
    """Erreur produite quand la source n'a pas de route M-003 publiable."""

    def __init__(self, document_id: str, status: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        self.status = _ensure_text(status, "status")
        super().__init__(f"source non routée: {self.document_id}; {self.status}")


class ConversionAlreadyRequestedError(DocumentCommandError):
    """Erreur produite quand une conversion canonique est déjà demandée."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        super().__init__(f"conversion déjà demandée: {self.document_id}")


class CanonicalQualityRejectedError(DocumentCommandError):
    """Erreur produite quand une QA canonique refuse la publication."""

    def __init__(self, document_id: str, error_code: str) -> None:
        self.document_id = _ensure_text(document_id, "document_id")
        self.error_code = _ensure_quality_rejection_error_code(error_code)
        super().__init__(
            f"version canonique refusée: {self.document_id}; {self.error_code}"
        )


class DocumentConversionStatus(str, Enum):
    """Statut public de la conversion documentaire M-004."""

    CONVERSION_REQUESTED = "CONVERSION_REQUESTED"
    QA_REJECTED = "QA_REJECTED"
    CANONICAL_ACCEPTED = "CANONICAL_ACCEPTED"

    @classmethod
    def from_value(
        cls,
        value: "DocumentConversionStatus | str",
    ) -> "DocumentConversionStatus":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("conversion_status invalide")
        for status in cls:
            if status.value == value:
                return status
        raise ValueError("conversion_status invalide")


class DocumentConversionExecutionPhase(str, Enum):
    """Phase durable de l'action CONVERT_DOCUMENT, distincte du statut métier."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

    @classmethod
    def from_value(
        cls,
        value: "DocumentConversionExecutionPhase | str",
    ) -> "DocumentConversionExecutionPhase":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("conversion_execution_phase invalide")
        for phase in cls:
            if phase.value == value:
                return phase
        raise ValueError("conversion_execution_phase invalide")


@dataclass(frozen=True)
class DocumentConversionState:
    """État applicatif strict d'une demande de conversion documentaire."""

    document_id: DocumentId
    conversion_status: DocumentConversionStatus
    canonical_version_id: str | None
    rejection_error_code: str | None
    execution_phase: DocumentConversionExecutionPhase
    completed_units: int
    total_units: int
    failure_error_code: str | None

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "conversion_status",
            DocumentConversionStatus.from_value(self.conversion_status),
        )
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_for_status(
                status=self.conversion_status,
                canonical_version_id=self.canonical_version_id,
            ),
        )
        object.__setattr__(
            self,
            "rejection_error_code",
            _ensure_rejection_error_code_for_status(
                status=self.conversion_status,
                rejection_error_code=self.rejection_error_code,
            ),
        )
        object.__setattr__(
            self,
            "execution_phase",
            DocumentConversionExecutionPhase.from_value(self.execution_phase),
        )
        object.__setattr__(
            self,
            "completed_units",
            _ensure_non_negative_int(self.completed_units, "completed_units"),
        )
        object.__setattr__(
            self,
            "total_units",
            _ensure_positive_int(self.total_units, "total_units"),
        )
        if self.completed_units > self.total_units:
            raise ValueError("progression de conversion incohérente")
        object.__setattr__(
            self,
            "failure_error_code",
            _ensure_conversion_failure_error_code(
                status=self.conversion_status,
                phase=self.execution_phase,
                rejection_error_code=self.rejection_error_code,
                failure_error_code=self.failure_error_code,
                completed_units=self.completed_units,
                total_units=self.total_units,
            ),
        )


@dataclass(frozen=True)
class DocumentConversionAcceptance:
    """Réponse applicative publique de demande de conversion documentaire."""

    document_id: DocumentId
    conversion_status: DocumentConversionStatus
    canonical_version_id: str | None

    @classmethod
    def from_state(
        cls, state: DocumentConversionState
    ) -> "DocumentConversionAcceptance":
        parsed_state = _ensure_document_conversion_state(state)
        if parsed_state.conversion_status is DocumentConversionStatus.QA_REJECTED:
            raise ValueError("statut de conversion non publiable")
        return cls(
            document_id=parsed_state.document_id,
            conversion_status=parsed_state.conversion_status,
            canonical_version_id=parsed_state.canonical_version_id,
        )

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "conversion_status",
            DocumentConversionStatus.from_value(self.conversion_status),
        )
        if self.conversion_status is DocumentConversionStatus.QA_REJECTED:
            raise ValueError("conversion_status invalide")
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_for_status(
                status=self.conversion_status,
                canonical_version_id=self.canonical_version_id,
            ),
        )


@dataclass(frozen=True)
class RegisterDocumentAcceptance:
    """Réponse applicative publique d'enregistrement documentaire."""

    document_id: DocumentId
    document_status: str
    duplicate: bool

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        if self.document_status not in {
            SourceDocumentStatus.REGISTERED.value,
            "DUPLICATE_SOURCE",
        }:
            raise ValueError("document_status invalide")
        if not isinstance(self.duplicate, bool):
            raise ValueError("duplicate invalide")
        if (
            self.document_status == SourceDocumentStatus.REGISTERED.value
            and self.duplicate
        ):
            raise ValueError("duplicate interdit pour enregistrement")
        if self.document_status == "DUPLICATE_SOURCE" and not self.duplicate:
            raise ValueError("duplicate requis pour doublon")


@dataclass(frozen=True)
class DocumentDiagnosisAcceptance:
    """Réponse applicative publique de demande de diagnostic."""

    document_id: DocumentId
    diagnostic_status: str

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        if self.diagnostic_status != "DIAGNOSTIC_REQUESTED":
            raise ValueError("diagnostic_status invalide")


class DocumentCommandService:
    """Surface applicative contrôlée pour les commandes documentaires SP."""

    def __init__(
        self,
        original_source_store: OriginalSourceStore,
        source_document_repository: SourceDocumentLookupRepository,
        document_inspector: DocumentInspector,
        processing_run_repository: ProcessingRunLookupRepository,
        environment: str,
        deployment_id: str,
        diagnosis_configuration_hash: str,
        code_version: str,
        model_version: str,
    ) -> None:
        if not callable(
            getattr(source_document_repository, "find_by_document_id", None)
        ):
            raise ValueError("source_document_repository sans lecture par document_id")
        if not callable(getattr(document_inspector, "inspect_content", None)):
            raise ValueError("document_inspector sans validation d'enregistrement")
        if not callable(
            getattr(processing_run_repository, "find_by_document_id", None)
        ):
            raise ValueError("processing_run_repository sans lecture par document_id")
        if not callable(
            getattr(processing_run_repository, "submit_processing_run", None)
        ):
            raise ValueError("processing_run_repository sans soumission atomique")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._diagnosis_configuration_hash = _ensure_sha256(
            diagnosis_configuration_hash,
            "diagnosis_configuration_hash",
        )
        identity = JobEnvironmentIdentity(
            environment=environment,
            deployment_id=deployment_id,
            configuration_hash=self._diagnosis_configuration_hash,
        )
        self._environment = identity.environment
        self._deployment_id = identity.deployment_id
        self._code_version = _ensure_text(code_version, "code_version")
        self._model_version = _ensure_text(model_version, "model_version")
        self._register_handler = RegisterSourceDocumentHandler(
            original_source_store=original_source_store,
            source_document_repository=source_document_repository,
        )
        self._start_handler = StartDocumentProcessingHandler(
            document_inspector=document_inspector,
            processing_run_repository=processing_run_repository,
        )
        self._document_inspector = document_inspector

    def register_source_document_path(
        self,
        *,
        original_path: Path,
        bibliographic_metadata: Mapping[str, Any] | None,
    ) -> RegisterDocumentAcceptance:
        inspect_path = getattr(self._document_inspector, "inspect_path", None)
        if not callable(inspect_path):
            raise ValueError("document_inspector sans inspection de chemin")
        try:
            inspect_path(original_path)
        except ValueError as exc:
            raise SourceUnreadableError(reason=str(exc)) from exc
        result = self._register_handler.handle_path(
            original_path=original_path,
            bibliographic_metadata=bibliographic_metadata,
        )
        if result.decision == "REVIEW_REQUIRED":
            raise SourceUnreadableError(
                reason=_ensure_text(result.review_reason, "reason")
            )
        if result.decision == "BINARY_DUPLICATE":
            return RegisterDocumentAcceptance(
                document_id=_ensure_document_id(result.duplicate_document_id),
                document_status="DUPLICATE_SOURCE",
                duplicate=True,
            )
        source_document = _ensure_source_document(result.source_document)
        return RegisterDocumentAcceptance(
            document_id=source_document.document_id,
            document_status=source_document.status.value,
            duplicate=False,
        )

    def register_source_document(
        self,
        *,
        original_content: bytes,
        bibliographic_metadata: Mapping[str, Any] | None,
    ) -> RegisterDocumentAcceptance:
        try:
            self._document_inspector.inspect_content(original_content)
        except ValueError as exc:
            raise SourceUnreadableError(reason=str(exc)) from exc
        result = self._register_handler.handle(
            RegisterSourceDocumentCommand(
                original_content=original_content,
                bibliographic_metadata=bibliographic_metadata,
            )
        )

        if result.decision == "REVIEW_REQUIRED":
            raise SourceUnreadableError(
                reason=_ensure_text(result.review_reason, "reason")
            )

        if result.decision == "BINARY_DUPLICATE":
            return RegisterDocumentAcceptance(
                document_id=_ensure_document_id(result.duplicate_document_id),
                document_status="DUPLICATE_SOURCE",
                duplicate=True,
            )

        if result.decision in {"REGISTERED", "DISTINCT_EDITION_REGISTERED"}:
            source_document = _ensure_source_document(result.source_document)
            return RegisterDocumentAcceptance(
                document_id=source_document.document_id,
                document_status=source_document.status.value,
                duplicate=False,
            )

        raise ValueError(
            f"décision RegisterSourceDocument non exposée: {result.decision}"
        )

    def start_document_processing(
        self, *, document_id: str
    ) -> DocumentDiagnosisAcceptance:
        parsed_document_id = DocumentId.from_value(document_id)
        existing_run = self._processing_run_repository.find_by_document_id(
            parsed_document_id
        )
        if existing_run is not None:
            raise DiagnosisAlreadyRequestedError(document_id=parsed_document_id.value)

        source_document = self._source_document_repository.find_by_document_id(
            parsed_document_id
        )
        if source_document is None:
            raise SourceNotFoundError(document_id=parsed_document_id.value)
        parsed_source_document = _ensure_source_document(source_document)
        try:
            parsed_source_document.ensure_documentary_publication_allowed()
        except ValueError as exc:
            raise SourceUnreadableError(reason=str(exc)) from exc

        processing_run_id = ProcessingRunId.from_value(
            f"RUN-DIAGNOSE-{parsed_document_id.value}"
        )
        start_command = StartDocumentProcessingCommand(
            processing_run_id=processing_run_id,
            source_document=parsed_source_document,
        )
        processing_run = self._start_handler.prepare(start_command)
        job_request = JobRequest(
            environment=self._environment,
            deployment_id=self._deployment_id,
            job_name="DIAGNOSE",
            priority=JobPriority.P1,
            idempotence_key=JobIdempotenceKey(
                job_name="DIAGNOSE",
                input_hash=parsed_source_document.fingerprint.value,
                configuration_hash=self._diagnosis_configuration_hash,
                code_version=self._code_version,
                model_version=self._model_version,
            ),
            execution_requirements=None,
            payload={
                "document_id": parsed_document_id.value,
                "processing_run_id": processing_run.processing_run_id.value,
                "original_storage_ref": parsed_source_document.original_storage_ref.value,
                "source_sha256": parsed_source_document.fingerprint.value,
            },
        )
        submission = self._processing_run_repository.submit_processing_run(
            processing_run=processing_run,
            job_request=job_request,
        )
        if not submission.created:
            raise DiagnosisAlreadyRequestedError(document_id=parsed_document_id.value)

        return DocumentDiagnosisAcceptance(
            document_id=parsed_document_id,
            diagnostic_status="DIAGNOSTIC_REQUESTED",
        )


class DocumentConversionCommandService:
    """Surface applicative M-004 dédiée à la conversion canonique documentaire."""

    def __init__(
        self,
        source_document_repository: SourceDocumentLookupRepository,
        processing_run_repository: ProcessingRunLookupRepository,
        document_conversion_repository: DocumentConversionRepository,
        environment: str,
        deployment_id: str,
        conversion_configuration_hash: str,
        code_version: str,
        model_version: str,
    ) -> None:
        if not callable(
            getattr(source_document_repository, "find_by_document_id", None)
        ):
            raise ValueError("source_document_repository sans lecture par document_id")
        if not callable(
            getattr(processing_run_repository, "find_by_document_id", None)
        ):
            raise ValueError("processing_run_repository sans lecture par document_id")
        if not callable(
            getattr(
                document_conversion_repository, "find_conversion_by_document_id", None
            )
        ):
            raise ValueError(
                "document_conversion_repository sans lecture de conversion"
            )
        if not callable(
            getattr(document_conversion_repository, "submit_conversion_request", None)
        ):
            raise ValueError(
                "document_conversion_repository sans soumission de conversion"
            )
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._document_conversion_repository = document_conversion_repository
        self._conversion_configuration_hash = _ensure_sha256(
            conversion_configuration_hash,
            "conversion_configuration_hash",
        )
        identity = JobEnvironmentIdentity(
            environment=environment,
            deployment_id=deployment_id,
            configuration_hash=self._conversion_configuration_hash,
        )
        self._environment = identity.environment
        self._deployment_id = identity.deployment_id
        self._code_version = _ensure_text(code_version, "code_version")
        self._model_version = _ensure_text(model_version, "model_version")
        self._canonical_audit_events: list[PreCanonicalAuditEvent] = []

    def canonical_audit_events(self) -> tuple[PreCanonicalAuditEvent, ...]:
        return tuple(self._canonical_audit_events)

    def request_document_conversion(
        self,
        *,
        document_id: str,
    ) -> DocumentConversionAcceptance:
        parsed_document_id = DocumentId.from_value(document_id)
        source_document = self._source_document_repository.find_by_document_id(
            parsed_document_id
        )
        if source_document is None:
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="SOURCE_NOT_FOUND",
                page_count=0,
            )
            raise SourceNotFoundError(document_id=parsed_document_id.value)
        parsed_source_document = _ensure_source_document(source_document)
        try:
            parsed_source_document.ensure_documentary_publication_allowed()
        except ValueError as exc:
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="QUARANTINED",
                error_code="SOURCE_QUARANTINED",
                page_count=0,
            )
            raise SourceQuarantinedError(
                document_id=parsed_document_id.value,
                reason=str(exc),
            ) from exc

        processing_run = self._processing_run_repository.find_by_document_id(
            parsed_document_id
        )
        if processing_run is None:
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="SOURCE_NOT_ROUTED",
                page_count=0,
            )
            raise SourceNotRoutedError(
                document_id=parsed_document_id.value,
                status="ABSENT",
            )
        parsed_processing_run = _ensure_processing_run(processing_run)
        try:
            parsed_processing_run.ensure_documentary_publication_allowed()
        except ValueError as exc:
            if parsed_processing_run.status is DocumentProcessingRunStatus.QUARANTINED:
                self._record_conversion_audit_event(
                    document_id=parsed_document_id,
                    status="QUARANTINED",
                    error_code="SOURCE_QUARANTINED",
                    page_count=parsed_processing_run.page_manifest.source_page_count,
                )
                raise SourceQuarantinedError(
                    document_id=parsed_document_id.value,
                    reason=str(exc),
                ) from exc
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="SOURCE_NOT_ROUTED",
                page_count=parsed_processing_run.page_manifest.source_page_count,
            )
            raise SourceNotRoutedError(
                document_id=parsed_document_id.value,
                status=parsed_processing_run.status.value,
            ) from exc

        existing_conversion = (
            self._document_conversion_repository.find_conversion_by_document_id(
                parsed_document_id
            )
        )
        if existing_conversion is not None:
            parsed_existing_conversion = _ensure_document_conversion_state(
                existing_conversion
            )
            if (
                parsed_existing_conversion.conversion_status
                is DocumentConversionStatus.QA_REJECTED
            ):
                self._record_conversion_audit_event(
                    document_id=parsed_document_id,
                    status="REJECTED",
                    error_code=parsed_existing_conversion.rejection_error_code,
                    page_count=parsed_processing_run.page_manifest.source_page_count,
                )
                raise CanonicalQualityRejectedError(
                    document_id=parsed_document_id.value,
                    error_code=parsed_existing_conversion.rejection_error_code,
                )
            if (
                parsed_existing_conversion.conversion_status
                is DocumentConversionStatus.CANONICAL_ACCEPTED
            ):
                return DocumentConversionAcceptance.from_state(
                    parsed_existing_conversion
                )
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="CONVERSION_ALREADY_REQUESTED",
                page_count=parsed_processing_run.page_manifest.source_page_count,
            )
            raise ConversionAlreadyRequestedError(document_id=parsed_document_id.value)

        route_plan = parsed_processing_run.route_plan
        if route_plan is None:
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="SOURCE_NOT_ROUTED",
                page_count=parsed_processing_run.page_manifest.source_page_count,
            )
            raise SourceNotRoutedError(
                document_id=parsed_document_id.value,
                status=parsed_processing_run.status.value,
            )

        conversion_state = DocumentConversionState(
            document_id=parsed_document_id,
            conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
            canonical_version_id=None,
            rejection_error_code=None,
            execution_phase=DocumentConversionExecutionPhase.QUEUED,
            completed_units=0,
            total_units=len(route_plan.page_routes),
            failure_error_code=None,
        )
        job_request = JobRequest(
            environment=self._environment,
            deployment_id=self._deployment_id,
            job_name="CONVERT_DOCUMENT",
            priority=JobPriority.P1,
            idempotence_key=JobIdempotenceKey(
                job_name="CONVERT_DOCUMENT",
                input_hash=parsed_source_document.fingerprint.value,
                configuration_hash=self._conversion_configuration_hash,
                code_version=self._code_version,
                model_version=self._model_version,
            ),
            execution_requirements=None,
            payload={
                "document_id": parsed_document_id.value,
                "processing_run_id": parsed_processing_run.processing_run_id.value,
                "source_sha256": parsed_source_document.fingerprint.value,
                "routing_policy_version": route_plan.routing_policy_version.value,
                "route_count": len(route_plan.page_routes),
            },
        )
        submission = self._document_conversion_repository.submit_conversion_request(
            conversion_state=conversion_state,
            job_request=job_request,
        )
        if not submission.created:
            self._record_conversion_audit_event(
                document_id=parsed_document_id,
                status="REJECTED",
                error_code="CONVERSION_ALREADY_REQUESTED",
                page_count=len(route_plan.page_routes),
            )
            raise ConversionAlreadyRequestedError(document_id=parsed_document_id.value)
        self._record_conversion_audit_event(
            document_id=parsed_document_id,
            status="REQUESTED",
            error_code=None,
            page_count=len(route_plan.page_routes),
        )
        return DocumentConversionAcceptance.from_state(conversion_state)

    def _record_conversion_audit_event(
        self,
        *,
        document_id: DocumentId,
        status: str,
        error_code: str | None,
        page_count: int,
    ) -> None:
        self._canonical_audit_events.append(
            PreCanonicalAuditEvent(
                trace_id=_conversion_audit_trace_id(document_id),
                document_id=document_id.value,
                phase="document_conversion_request",
                status=status,
                page_count=page_count,
                error_code=error_code,
            )
        )


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in "0123456789abcdef":
            raise ValueError(f"{field_name} invalide")
    return text_value


def _ensure_document_id(value: DocumentId | None) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_processing_run(value: object) -> DocumentProcessingRun:
    if not isinstance(value, DocumentProcessingRun):
        raise ValueError("processing_run invalide")
    return value


def _ensure_source_document(value: SourceDocument | None) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


def _ensure_document_conversion_state(value: object) -> DocumentConversionState:
    if not isinstance(value, DocumentConversionState):
        raise ValueError("conversion_state invalide")
    return value


def _ensure_canonical_version_for_status(
    *,
    status: DocumentConversionStatus,
    canonical_version_id: str | None,
) -> str | None:
    if status is DocumentConversionStatus.CANONICAL_ACCEPTED:
        if canonical_version_id is None:
            raise ValueError("canonical_version_id obligatoire")
        return _ensure_canonical_version_id(canonical_version_id)
    if canonical_version_id is not None:
        raise ValueError("canonical_version_id interdit")
    return None


def _ensure_rejection_error_code_for_status(
    *,
    status: DocumentConversionStatus,
    rejection_error_code: str | None,
) -> str | None:
    if status is DocumentConversionStatus.QA_REJECTED:
        if rejection_error_code is None:
            raise ValueError("rejection_error_code obligatoire")
        return _ensure_quality_rejection_error_code(rejection_error_code)
    if rejection_error_code is not None:
        raise ValueError("rejection_error_code interdit")
    return None


def _ensure_quality_rejection_error_code(value: Any) -> str:
    text = _ensure_text(value, "rejection_error_code")
    if text not in {
        "SOURCE_NOT_CANONICAL",
        "PAGE_AUTHORITY_MISSING",
        "DOCLING_STANDARD_UNAVAILABLE",
        "GRANITE_DOCLING_UNAVAILABLE",
        "GRANITE_DOCLING_TIMEOUT",
        "GEMMA_VISION_TIMEOUT",
        "JOB_LEASE_LOST",
        "GRANITE_CAPACITY_CONFIGURATION_INVALID",
        "OCRMYPDF_UNAVAILABLE",
        "CONVERSION_ASSET_MANIFEST_INVALID",
        "CANONICAL_ARTIFACT_STORE_UNAVAILABLE",
        "SOURCE_FINGERPRINT_MISMATCH",
        "PROCESSING_RUN_NOT_FOUND",
        "PROCESSING_RUN_ID_MISMATCH",
        "SOURCE_NOT_ROUTED",
        "NATIVE_STANDARD_ROUTE_REQUIRED",
        "CONVERSION_REQUEST_NOT_FOUND",
        "CONVERSION_NOT_EXECUTABLE",
        "DOCLING_PAGE_MANIFEST_MISMATCH",
        "DOCLING_PROVENANCE_MISSING",
        "GEMMA_VISION_UNAVAILABLE",
        "GEMMA_VISION_OUTPUT_INVALID",
        "GEMMA_VISION_OUTPUT_TRUNCATED",
        "GEMMA_VISION_MODEL_MISMATCH",
        "GEMMA_VISION_RENDERING_FAILED",
        "GEMMA_VISION_IMAGE_TOO_LARGE",
        "GEMMA_VISION_PAGE_MISSING",
        "GEMMA_VISION_SOURCE_INVALID",
        "GEMMA_VISION_REQUEST_INVALID",
        "GEMMA_VISION_WORKER_PROTOCOL_INVALID",
        "GEMMA_VISION_WORKER_UNEXPECTED",
        "POSTGRES_TRANSIENT_FAILURE",
        "POSTGRES_INTEGRITY_FAILURE",
        "POSTGRES_PERMANENT_FAILURE",
        "CONVERSION_PERSISTENCE_CONFLICT",
        "WORKER_UNEXPECTED_ERROR",
    }:
        raise ValueError("rejection_error_code invalide")
    return text


def _ensure_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_conversion_failure_error_code(
    *,
    status: DocumentConversionStatus,
    phase: DocumentConversionExecutionPhase,
    rejection_error_code: str | None,
    failure_error_code: Any,
    completed_units: int,
    total_units: int,
) -> str | None:
    if status is DocumentConversionStatus.CONVERSION_REQUESTED:
        if phase not in {
            DocumentConversionExecutionPhase.QUEUED,
            DocumentConversionExecutionPhase.RUNNING,
        }:
            raise ValueError("phase de conversion demandée invalide")
        if (
            phase is DocumentConversionExecutionPhase.QUEUED and completed_units != 0
        ) or failure_error_code is not None:
            raise ValueError("progression de conversion demandée invalide")
        return None
    if status is DocumentConversionStatus.CANONICAL_ACCEPTED:
        if (
            phase is not DocumentConversionExecutionPhase.SUCCEEDED
            or completed_units != total_units
            or failure_error_code is not None
        ):
            raise ValueError("progression de conversion acceptée invalide")
        return None
    if (
        phase is not DocumentConversionExecutionPhase.FAILED
        or not isinstance(failure_error_code, str)
        or failure_error_code != rejection_error_code
    ):
        raise ValueError("progression de conversion rejetée invalide")
    return _ensure_quality_rejection_error_code(failure_error_code)


def _conversion_audit_trace_id(document_id: DocumentId) -> str:
    _ensure_document_id(document_id)
    return f"TRACE-M004-CONVERT-{document_id.value.removeprefix('DOC-')}"


def _ensure_canonical_version_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical_version_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "CVER"))
    except ValueError as exc:
        raise ValueError(f"canonical_version_id invalide: {exc}") from exc


__all__ = [
    "CanonicalQualityRejectedError",
    "ConversionAlreadyRequestedError",
    "DiagnosisAlreadyRequestedError",
    "DocumentCommandError",
    "DocumentCommandService",
    "DocumentConversionAcceptance",
    "DocumentConversionCommandService",
    "DocumentConversionExecutionPhase",
    "DocumentConversionRepository",
    "DocumentConversionState",
    "DocumentConversionStatus",
    "DocumentDiagnosisAcceptance",
    "ProcessingRunLookupRepository",
    "RegisterDocumentAcceptance",
    "SourceDocumentLookupRepository",
    "SourceNotFoundError",
    "SourceNotRoutedError",
    "SourceQuarantinedError",
    "SourceUnreadableError",
]
