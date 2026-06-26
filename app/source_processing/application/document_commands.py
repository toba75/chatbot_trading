"""Commandes documentaires applicatives exposées par le contexte SP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.platform.job_runtime import (
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
    JobSubmissionDecision,
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
from app.source_processing.domain.document_processing_run import ProcessingRunId
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

    def find_by_document_id(self, document_id: DocumentId) -> object | None:
        """Retourne une tentative déjà demandée pour ce document."""


class DiagnosisJobQueue(Protocol):
    """Port de soumission idempotente au runtime de jobs M-002."""

    def submit(
        self,
        request: JobRequest,
        *,
        recalculate: bool,
    ) -> JobSubmissionDecision:
        """Soumet une demande technique DIAGNOSE."""


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


@dataclass(frozen=True)
class RegisterDocumentAcceptance:
    """Réponse applicative publique d'enregistrement documentaire."""

    document_id: DocumentId
    document_status: str

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        if self.document_status != SourceDocumentStatus.REGISTERED.value:
            raise ValueError("document_status invalide")


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
        job_queue: DiagnosisJobQueue,
        diagnosis_configuration_hash: str,
        code_version: str,
        model_version: str,
    ) -> None:
        if not callable(getattr(source_document_repository, "find_by_document_id", None)):
            raise ValueError("source_document_repository sans lecture par document_id")
        if not callable(getattr(processing_run_repository, "find_by_document_id", None)):
            raise ValueError("processing_run_repository sans lecture par document_id")
        if not callable(getattr(job_queue, "submit", None)):
            raise ValueError("job_queue invalide")
        self._source_document_repository = source_document_repository
        self._processing_run_repository = processing_run_repository
        self._job_queue = job_queue
        self._diagnosis_configuration_hash = _ensure_sha256(
            diagnosis_configuration_hash,
            "diagnosis_configuration_hash",
        )
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

    def register_source_document(
        self,
        *,
        original_content: bytes,
        bibliographic_metadata: Mapping[str, Any],
    ) -> RegisterDocumentAcceptance:
        result = self._register_handler.handle(
            RegisterSourceDocumentCommand(
                original_content=original_content,
                bibliographic_metadata=bibliographic_metadata,
            )
        )

        if result.decision == "REVIEW_REQUIRED":
            raise SourceUnreadableError(reason=_ensure_text(result.review_reason, "reason"))

        if result.decision == "BINARY_DUPLICATE":
            return RegisterDocumentAcceptance(
                document_id=_ensure_document_id(result.duplicate_document_id),
                document_status=SourceDocumentStatus.REGISTERED.value,
            )

        if result.decision in {"REGISTERED", "DISTINCT_EDITION_REGISTERED"}:
            source_document = _ensure_source_document(result.source_document)
            return RegisterDocumentAcceptance(
                document_id=source_document.document_id,
                document_status=source_document.status.value,
            )

        raise ValueError(f"décision RegisterSourceDocument non exposée: {result.decision}")

    def start_document_processing(self, *, document_id: str) -> DocumentDiagnosisAcceptance:
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

        processing_run_id = ProcessingRunId.from_value(
            f"RUN-DIAGNOSE-{parsed_document_id.value}"
        )
        processing_run = self._start_handler.handle(
            StartDocumentProcessingCommand(
                processing_run_id=processing_run_id,
                source_document=parsed_source_document,
            )
        )
        submission = self._job_queue.submit(
            request=JobRequest(
                job_name="DIAGNOSE",
                priority=JobPriority.P1,
                idempotence_key=JobIdempotenceKey(
                    job_name="DIAGNOSE",
                    input_hash=parsed_source_document.fingerprint.value,
                    configuration_hash=self._diagnosis_configuration_hash,
                    code_version=self._code_version,
                    model_version=self._model_version,
                ),
                payload={
                    "document_id": parsed_document_id.value,
                    "processing_run_id": processing_run.processing_run_id.value,
                    "original_storage_ref": parsed_source_document.original_storage_ref.value,
                    "source_sha256": parsed_source_document.fingerprint.value,
                },
            ),
            recalculate=False,
        )
        if not submission.created:
            raise DiagnosisAlreadyRequestedError(document_id=parsed_document_id.value)

        return DocumentDiagnosisAcceptance(
            document_id=parsed_document_id,
            diagnostic_status="DIAGNOSTIC_REQUESTED",
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


def _ensure_source_document(value: SourceDocument | None) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


__all__ = [
    "DiagnosisAlreadyRequestedError",
    "DiagnosisJobQueue",
    "DocumentCommandError",
    "DocumentCommandService",
    "DocumentDiagnosisAcceptance",
    "ProcessingRunLookupRepository",
    "RegisterDocumentAcceptance",
    "SourceDocumentLookupRepository",
    "SourceNotFoundError",
    "SourceUnreadableError",
]
