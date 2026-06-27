"""Adaptateur HTTP mince pour les commandes documentaires SP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.source_processing.application.document_commands import (
    CanonicalQualityRejectedError,
    ConversionAlreadyRequestedError,
    DiagnosisAlreadyRequestedError,
    DocumentConversionAcceptance,
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
    SourceNotFoundError,
    SourceNotRoutedError,
    SourceQuarantinedError,
    SourceUnreadableError,
)
from app.source_processing.domain.source_document import DocumentId


class DocumentCommandPort(Protocol):
    """Port applicatif appelé par l'adaptateur de transport."""

    def register_source_document(
        self,
        *,
        original_content: bytes,
        bibliographic_metadata: Mapping[str, Any],
    ) -> RegisterDocumentAcceptance:
        """Enregistre un PDF original via SP."""

    def start_document_processing(
        self,
        *,
        document_id: str,
    ) -> DocumentDiagnosisAcceptance:
        """Demande le diagnostic documentaire via SP."""

    def request_document_conversion(
        self,
        *,
        document_id: str,
    ) -> DocumentConversionAcceptance:
        """Demande la conversion canonique documentaire via SP."""


@dataclass(frozen=True)
class HttpRequest:
    """Requête HTTP minimale et testable sans framework."""

    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class HttpResponse:
    """Réponse HTTP minimale et stable pour les tests de contrat."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


class SourceProcessingHttpAdapter:
    """Route uniquement les endpoints documentaires SP publiés par M-003."""

    def __init__(self, document_commands: DocumentCommandPort) -> None:
        if not callable(getattr(document_commands, "register_source_document", None)):
            raise ValueError("document_commands sans RegisterSourceDocument")
        if not callable(getattr(document_commands, "start_document_processing", None)):
            raise ValueError("document_commands sans StartDocumentProcessing")
        self._document_commands = document_commands

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/documents":
            return self._handle_register_document(parsed_request)

        diagnosed_document_id = _document_id_from_diagnose_path(parsed_request.path)
        if parsed_request.method == "POST" and diagnosed_document_id is not None:
            return self._handle_start_diagnosis(diagnosed_document_id)

        converted_document_id = _document_id_from_convert_path(parsed_request.path)
        if parsed_request.method == "POST" and converted_document_id is not None:
            return self._handle_request_conversion(parsed_request, converted_document_id)

        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_register_document(self, request: HttpRequest) -> HttpResponse:
        body = request.body
        if "original_content" not in body:
            return _bad_request_response("original_content")
        if "bibliographic_metadata" not in body:
            return _bad_request_response("bibliographic_metadata")
        try:
            acceptance = self._document_commands.register_source_document(
                original_content=body["original_content"],
                bibliographic_metadata=body["bibliographic_metadata"],
            )
        except SourceUnreadableError as exc:
            return HttpResponse(
                status_code=422,
                body={"error_code": "SOURCE_UNREADABLE", "reason": exc.reason},
            )

        if acceptance.duplicate:
            return HttpResponse(
                status_code=200,
                body={
                    "document_id": acceptance.document_id.value,
                    "document_status": acceptance.document_status,
                    "duplicate": True,
                },
            )

        return HttpResponse(
            status_code=201,
            body={
                "document_id": acceptance.document_id.value,
                "document_status": acceptance.document_status,
            },
        )

    def _handle_start_diagnosis(self, document_id: str) -> HttpResponse:
        try:
            DocumentId.from_value(document_id)
        except ValueError:
            return _bad_request_response("document_id")

        try:
            acceptance = self._document_commands.start_document_processing(
                document_id=document_id
            )
        except SourceNotFoundError as exc:
            return HttpResponse(
                status_code=404,
                body={"error_code": "SOURCE_NOT_FOUND", "document_id": exc.document_id},
            )
        except DiagnosisAlreadyRequestedError as exc:
            return HttpResponse(
                status_code=409,
                body={
                    "error_code": "DIAGNOSTIC_ALREADY_REQUESTED",
                    "document_id": exc.document_id,
                },
            )
        except SourceUnreadableError as exc:
            return HttpResponse(
                status_code=422,
                body={"error_code": "SOURCE_UNREADABLE", "reason": exc.reason},
            )

        return HttpResponse(
            status_code=202,
            body={
                "document_id": acceptance.document_id.value,
                "diagnostic_status": acceptance.diagnostic_status,
            },
        )

    def _handle_request_conversion(
        self,
        request: HttpRequest,
        document_id: str,
    ) -> HttpResponse:
        if len(request.body) != 0:
            return _bad_request_response("body")
        try:
            DocumentId.from_value(document_id)
        except ValueError:
            return _bad_request_response("document_id")
        request_document_conversion = getattr(
            self._document_commands,
            "request_document_conversion",
            None,
        )
        if not callable(request_document_conversion):
            raise ValueError("document_commands sans RequestDocumentConversion")

        try:
            acceptance = request_document_conversion(document_id=document_id)
        except SourceNotFoundError as exc:
            return HttpResponse(
                status_code=404,
                body={"error_code": "SOURCE_NOT_FOUND", "document_id": exc.document_id},
            )
        except SourceQuarantinedError as exc:
            return HttpResponse(
                status_code=409,
                body={
                    "error_code": "SOURCE_QUARANTINED",
                    "document_id": exc.document_id,
                },
            )
        except SourceNotRoutedError as exc:
            return HttpResponse(
                status_code=409,
                body={
                    "error_code": "SOURCE_NOT_ROUTED",
                    "document_id": exc.document_id,
                    "status": exc.status,
                },
            )
        except ConversionAlreadyRequestedError as exc:
            return HttpResponse(
                status_code=409,
                body={
                    "error_code": "CONVERSION_ALREADY_REQUESTED",
                    "document_id": exc.document_id,
                },
            )
        except CanonicalQualityRejectedError as exc:
            return HttpResponse(
                status_code=422,
                body={
                    "error_code": exc.error_code,
                    "document_id": exc.document_id,
                },
            )

        body: dict[str, Any] = {
            "document_id": acceptance.document_id.value,
            "conversion_status": acceptance.conversion_status.value,
        }
        if acceptance.canonical_version_id is not None:
            body["canonical_version_id"] = acceptance.canonical_version_id
        return HttpResponse(status_code=202, body=body)


def _document_id_from_diagnose_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/documents/"
    suffix = "/diagnose"
    if not parsed_path.startswith(prefix) or not parsed_path.endswith(suffix):
        return None
    document_id = parsed_path[len(prefix) : -len(suffix)]
    return document_id


def _document_id_from_convert_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/documents/"
    suffix = "/convert"
    if not parsed_path.startswith(prefix) or not parsed_path.endswith(suffix):
        return None
    document_id = parsed_path[len(prefix) : -len(suffix)]
    return document_id


def _ensure_http_request(value: HttpRequest) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requête HTTP invalide")
    return value


def _ensure_http_method(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("méthode HTTP invalide")
    if value != value.upper():
        raise ValueError("méthode HTTP non normalisée")
    if value.strip() == "":
        raise ValueError("méthode HTTP vide")
    if value != value.strip():
        raise ValueError("méthode HTTP non normalisée")
    return value


def _ensure_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip():
        raise ValueError("chemin HTTP non normalisé")
    if not value.startswith("/"):
        raise ValueError("chemin HTTP invalide")
    return value


def _ensure_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_status_code(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


__all__ = [
    "DocumentCommandPort",
    "HttpRequest",
    "HttpResponse",
    "SourceProcessingHttpAdapter",
]
