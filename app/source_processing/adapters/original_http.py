"""Routeur FastAPI de restitution contrôlée du PDF original SP."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.responses import Response

from app.source_processing.application.document_commands import SourceNotFoundError
from app.source_processing.application.original_queries import (
    OriginalHashMismatchError,
    OriginalPdfContent,
)
from app.source_processing.domain.source_document import DocumentId


class OriginalPdfQueryPort(Protocol):
    """Port applicatif injecté au contrôleur de l'original."""

    def read_original(self, document_id: str) -> OriginalPdfContent:
        """Lit un original par son identité publique."""


def build_original_pdf_router(*, original_pdf_queries: OriginalPdfQueryPort) -> APIRouter:
    """Construit la route publique sans accepter de référence de stockage."""

    parsed_queries = _ensure_original_pdf_queries(original_pdf_queries)
    router = APIRouter()

    @router.get("/v1/documents/{document_id}/original")
    def read_original(document_id: str) -> Response:
        if not _is_valid_document_id(document_id):
            return _invalid_document_id_response()
        try:
            original = parsed_queries.read_original(document_id)
        except SourceNotFoundError as exc:
            return _source_not_found_response(exc)
        except OriginalHashMismatchError:
            return _hash_mismatch_response(document_id)
        if not isinstance(original, OriginalPdfContent):
            raise TypeError("contenu PDF original invalide")
        return StreamingResponse(
            content=original.content_chunks,
            media_type="application/pdf",
            headers={
                "Content-Length": str(original.content_length),
                "Content-Disposition": (
                    f'inline; filename="{original.public_filename}"'
                ),
                "ETag": f'"{original.source_sha256}"',
            },
            background=BackgroundTask(original.close),
        )

    return router


def _source_not_found_response(error: SourceNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error_code": "SOURCE_NOT_FOUND", "document_id": error.document_id},
    )


def _hash_mismatch_response(document_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error_code": "ORIGINAL_HASH_MISMATCH",
            "document_id": document_id,
        },
    )


def _invalid_document_id_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"},
    )


def _is_valid_document_id(value: str) -> bool:
    try:
        DocumentId.from_value(value)
    except ValueError:
        return False
    return True


def _ensure_original_pdf_queries(value: Any) -> OriginalPdfQueryPort:
    if not callable(getattr(value, "read_original", None)):
        raise ValueError("original_pdf_queries sans lecture originale")
    return value


__all__ = ["OriginalPdfQueryPort", "build_original_pdf_router"]
