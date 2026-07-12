"""Routeur FastAPI du read-model documentaire de projection KA."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.contracts.identity import DomainIdentifier
from app.platform.orchestrator_api_models import (
    ProjectionResponse,
    PUBLIC_ERROR_RESPONSES,
    parse_public_document_id,
    public_error,
)
from app.knowledge_access.application.projection_queries import (
    KnowledgeProjectionView,
    ProjectionNotRequestedView,
    ProjectionView,
)


class ProjectionQueryPort(Protocol):
    """Port applicatif KA injecté dans le routeur documentaire public."""

    def read_projection(self, document_id: str) -> ProjectionView:
        """Lit la projection courante sans exposer son stockage."""


def build_projection_query_router(
    *,
    projection_queries: ProjectionQueryPort,
) -> APIRouter:
    """Construit la route de lecture T-009 et injecte le query service KA."""

    parsed_queries = _ensure_projection_queries(projection_queries)
    router = APIRouter()

    @router.get(
        "/v1/documents/{document_id}/projection",
        response_model=ProjectionResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def read_projection(document_id: str) -> JSONResponse:
        if not _is_valid_document_id(document_id):
            return _invalid_document_id_response()
        view = parsed_queries.read_projection(document_id)
        if not isinstance(view, (ProjectionNotRequestedView, KnowledgeProjectionView)):
            raise TypeError("read-model de projection invalide")
        return JSONResponse(status_code=200, content=asdict(view))

    return router


def _invalid_document_id_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=public_error("HTTP_REQUEST_INVALID", field="document_id"),
    )


def _is_valid_document_id(value: str) -> bool:
    try:
        parse_public_document_id(value)
    except ValueError:
        return False
    return True


def _ensure_projection_queries(value: Any) -> ProjectionQueryPort:
    if not callable(getattr(value, "read_projection", None)):
        raise ValueError("projection_queries sans lecture projection")
    return value


__all__ = ["ProjectionQueryPort", "build_projection_query_router"]
