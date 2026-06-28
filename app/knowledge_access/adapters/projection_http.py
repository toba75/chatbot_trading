"""Adaptateur HTTP mince pour les commandes KA de projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.application.request_projection import (
    ProjectionAlreadyRequestedError,
    ProjectionProfileInvalidError,
    RequestKnowledgeProjectionAcceptance,
    RequestKnowledgeProjectionCommand,
    SourceNotCanonicalError,
    SourceNotFoundError,
    SourceQuarantinedError,
)
from app.knowledge_access.domain.knowledge_projection import ProjectionProfile


_PROFILE_BODY_FIELDS = frozenset(
    {
        "projection_profile_id",
        "chunking_profile",
        "embedding_model",
        "sparse_profile",
        "index_schema",
    }
)


class KnowledgeProjectionCommandPort(Protocol):
    """Port applicatif KA appelé par l'adaptateur HTTP."""

    def request_projection(
        self,
        command: RequestKnowledgeProjectionCommand,
    ) -> RequestKnowledgeProjectionAcceptance:
        """Demande la création d'une projection de connaissance."""


@dataclass(frozen=True)
class HttpRequest:
    """Requête HTTP minimale et testable sans framework."""

    method: str
    path: str
    body: Mapping[str, Any]
    authenticated_context: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))
        object.__setattr__(
            self,
            "authenticated_context",
            _ensure_authenticated_context(self.authenticated_context),
        )


@dataclass(frozen=True)
class HttpResponse:
    """Réponse HTTP minimale et stable pour le contrat KA."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


class KnowledgeProjectionHttpAdapter:
    """Route explicitement POST /v1/documents/{document_id}/index côté KA."""

    def __init__(self, *, projection_commands: KnowledgeProjectionCommandPort) -> None:
        if not callable(getattr(projection_commands, "request_projection", None)):
            raise ValueError("projection_commands sans RequestKnowledgeProjection")
        self._projection_commands = projection_commands

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        indexed_document_id = _document_id_from_index_path(parsed_request.path)
        if parsed_request.method == "POST" and indexed_document_id is not None:
            return self._handle_request_projection(parsed_request, indexed_document_id)
        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_request_projection(
        self,
        request: HttpRequest,
        document_id: str,
    ) -> HttpResponse:
        try:
            _ensure_document_id(document_id)
        except ValueError:
            return _bad_request_response("document_id")

        if len(request.body) == 0:
            return _bad_request_response("body")
        body_fields = frozenset(request.body.keys())
        unexpected_fields = body_fields - _PROFILE_BODY_FIELDS
        if len(unexpected_fields) > 0:
            return _bad_request_response("body")
        missing_fields = _PROFILE_BODY_FIELDS - body_fields
        if len(missing_fields) > 0:
            return _profile_invalid_response(sorted(missing_fields)[0])

        try:
            projection_profile = ProjectionProfile.from_payload(request.body)
        except ValueError as exc:
            return _profile_invalid_response(str(exc))

        try:
            acceptance = self._projection_commands.request_projection(
                RequestKnowledgeProjectionCommand(
                    document_id=document_id,
                    projection_profile=projection_profile,
                )
            )
        except SourceNotFoundError as exc:
            return HttpResponse(
                status_code=404,
                body={"error_code": "SOURCE_NOT_FOUND", "document_id": exc.document_id},
            )
        except SourceQuarantinedError as exc:
            return HttpResponse(
                status_code=409,
                body={"error_code": "SOURCE_QUARANTINED", "document_id": exc.document_id},
            )
        except SourceNotCanonicalError as exc:
            return HttpResponse(
                status_code=409,
                body={"error_code": "SOURCE_NOT_CANONICAL", "document_id": exc.document_id},
            )
        except ProjectionAlreadyRequestedError as exc:
            return HttpResponse(
                status_code=409,
                body={
                    "error_code": "PROJECTION_ALREADY_REQUESTED",
                    "projection_id": exc.projection_id,
                },
            )
        except ProjectionProfileInvalidError as exc:
            return _profile_invalid_response(exc.reason)

        return HttpResponse(
            status_code=202,
            body={
                "document_id": acceptance.document_id,
                "projection_id": acceptance.projection_id,
                "projection_status": acceptance.projection_status.value,
                "canonical_version_id": acceptance.canonical_version_id,
            },
        )


def _document_id_from_index_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/documents/"
    suffix = "/index"
    if not parsed_path.startswith(prefix) or not parsed_path.endswith(suffix):
        return None
    return parsed_path[len(prefix) : -len(suffix)]


def _ensure_http_request(value: HttpRequest) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requete HTTP invalide")
    return value


def _ensure_http_method(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("methode HTTP invalide")
    if value.strip() == "":
        raise ValueError("methode HTTP vide")
    if value != value.strip():
        raise ValueError("methode HTTP non normalisee")
    if value != value.upper():
        raise ValueError("methode HTTP non normalisee")
    return value


def _ensure_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip():
        raise ValueError("chemin HTTP non normalise")
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


def _ensure_document_id(value: str) -> str:
    return str(DomainIdentifier.parse_with_prefix(value, "DOC"))


def _ensure_authenticated_context(value: Any) -> str:
    text = _ensure_request_text(value, "authenticated_context")
    if text not in {"KA", "RA", "EG"}:
        raise ValueError("authenticated_context inconnu")
    return text


def _ensure_request_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _profile_invalid_response(reason: str) -> HttpResponse:
    return HttpResponse(
        status_code=422,
        body={"error_code": "PROJECTION_PROFILE_INVALID", "reason": reason},
    )


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "KnowledgeProjectionCommandPort",
    "KnowledgeProjectionHttpAdapter",
]
