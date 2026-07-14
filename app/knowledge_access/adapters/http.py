"""Routeur FastAPI du read-model documentaire de projection KA."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.platform.orchestrator_api_models import (
    IndexAcceptedResponse,
    IndexRequest,
    ProjectionResponse,
    PUBLIC_ERROR_RESPONSES,
    parse_public_document_id,
    public_error,
)
from app.knowledge_access.adapters.projection_http import (
    HttpRequest as ProjectionHttpRequest,
    HttpResponse as ProjectionHttpResponse,
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


class ProjectionCommandHttpAdapter(Protocol):
    """Adaptateur KA de la commande publique d'indexation."""

    def handle(self, request: ProjectionHttpRequest) -> ProjectionHttpResponse:
        """Demande une projection sans connaÃ®tre FastAPI."""


def build_projection_command_router(
    *,
    projection_command_adapter: ProjectionCommandHttpAdapter,
) -> APIRouter:
    """Expose POST /index via le cas d'usage KA, sans stub historique."""

    parsed_adapter = _ensure_projection_command_adapter(projection_command_adapter)
    router = APIRouter()

    @router.post(
        "/v1/documents/{document_id}/index",
        response_model=IndexAcceptedResponse,
        status_code=202,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def request_projection(
        document_id: str,
        payload: IndexRequest,
    ) -> JSONResponse:
        if not _is_valid_document_id(document_id):
            return _invalid_document_id_response()
        response = await run_in_threadpool(
            parsed_adapter.handle,
            ProjectionHttpRequest(
                method="POST",
                path=f"/v1/documents/{document_id}/index",
                body=payload.model_dump(mode="json"),
                authenticated_context="KA",
            ),
        )
        if not isinstance(response, ProjectionHttpResponse):
            raise TypeError("rÃ©ponse de commande projection invalide")
        return JSONResponse(status_code=response.status_code, content=dict(response.body))

    return router


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
        view = await run_in_threadpool(parsed_queries.read_projection, document_id)
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


def _ensure_projection_command_adapter(value: Any) -> ProjectionCommandHttpAdapter:
    if not callable(getattr(value, "handle", None)):
        raise ValueError("projection_command_adapter invalide")
    return value


__all__ = [
    "ProjectionCommandHttpAdapter",
    "ProjectionQueryPort",
    "build_projection_command_router",
    "build_projection_query_router",
]
