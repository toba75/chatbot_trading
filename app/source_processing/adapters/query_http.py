"""Routeur FastAPI des read-models publics documentaires SP."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.source_processing.application.document_queries import (
    ConversionNotRequestedError,
    DiagnosticNotRequestedError,
    DocumentConversionView,
    DocumentCorpusView,
    DocumentDiagnosticView,
    SourceNotFoundError,
)
from app.source_processing.domain.source_document import DocumentId
from app.platform.orchestrator_api_models import (
    DocumentConversionResponse,
    DocumentCorpusResponse,
    DocumentDiagnosticResponse,
    PUBLIC_ERROR_RESPONSES,
    parse_public_document_id,
    public_error,
)


class DocumentQueryPort(Protocol):
    """Port applicatif strict consommé par le routeur de lecture."""

    def list_documents(self) -> DocumentCorpusView:
        """Retourne le corpus public."""

    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView:
        """Retourne le diagnostic public d'un document."""

    def read_conversion(self, document_id: str) -> DocumentConversionView:
        """Retourne la conversion publique d'un document."""


def build_document_query_router(*, document_queries: DocumentQueryPort) -> APIRouter:
    """Construit uniquement les trois routes de lecture T-007."""

    parsed_queries = _ensure_document_queries(document_queries)
    router = APIRouter()

    @router.get(
        "/v1/documents",
        response_model=DocumentCorpusResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def list_documents() -> JSONResponse:
        view = parsed_queries.list_documents()
        if not isinstance(view, DocumentCorpusView):
            raise TypeError("read-model de corpus invalide")
        return JSONResponse(status_code=200, content=asdict(view))

    @router.get(
        "/v1/documents/{document_id}/diagnostic",
        response_model=DocumentDiagnosticResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def read_diagnostic(document_id: str) -> JSONResponse:
        if not _is_valid_document_id(document_id):
            return _invalid_document_id_response()
        try:
            view = parsed_queries.read_diagnostic(document_id)
        except SourceNotFoundError as exc:
            return _source_not_found_response(exc)
        except DiagnosticNotRequestedError as exc:
            return _diagnostic_not_requested_response(exc)
        if not isinstance(view, DocumentDiagnosticView):
            raise TypeError("read-model de diagnostic invalide")
        return JSONResponse(status_code=200, content=asdict(view))

    @router.get(
        "/v1/documents/{document_id}/conversion",
        response_model=DocumentConversionResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def read_conversion(document_id: str) -> JSONResponse:
        if not _is_valid_document_id(document_id):
            return _invalid_document_id_response()
        try:
            view = parsed_queries.read_conversion(document_id)
        except SourceNotFoundError as exc:
            return _source_not_found_response(exc)
        except ConversionNotRequestedError as exc:
            return _conversion_not_requested_response(exc)
        if not isinstance(view, DocumentConversionView):
            raise TypeError("read-model de conversion invalide")
        return JSONResponse(status_code=200, content=asdict(view))

    return router


def _source_not_found_response(error: SourceNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=public_error("SOURCE_NOT_FOUND", document_id=error.document_id),
    )


def _diagnostic_not_requested_response(
    error: DiagnosticNotRequestedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=public_error("DIAGNOSTIC_NOT_REQUESTED", document_id=error.document_id),
    )


def _conversion_not_requested_response(
    error: ConversionNotRequestedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=public_error("CONVERSION_NOT_REQUESTED", document_id=error.document_id),
    )


def _invalid_document_id_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=public_error("HTTP_REQUEST_INVALID", field="document_id"),
    )


def _is_valid_document_id(value: str) -> bool:
    try:
        DocumentId.from_value(parse_public_document_id(value))
    except ValueError:
        return False
    return True


def _ensure_document_queries(value: Any) -> DocumentQueryPort:
    if not callable(getattr(value, "list_documents", None)):
        raise ValueError("document_queries sans liste documentaire")
    if not callable(getattr(value, "read_diagnostic", None)):
        raise ValueError("document_queries sans lecture diagnostic")
    if not callable(getattr(value, "read_conversion", None)):
        raise ValueError("document_queries sans lecture conversion")
    return value


__all__ = ["DocumentQueryPort", "build_document_query_router"]
