from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.platform.llm_gateway import LLMGatewayContractError
from app.platform.orchestrator_public_services import (
    IndexCommandHandler,
    JsonCommandHandler,
    PublicContractServices,
)


def build_health_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"service": "orchestrator-api", "status": "healthy"}

    return router


def build_conversation_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "conversation")
    router = APIRouter()

    @router.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        body_result = await _read_json_object(request)
        if isinstance(body_result, JSONResponse):
            return body_result
        try:
            response = await run_in_threadpool(parsed_handler.handle, body_result)
        except LLMGatewayContractError as exc:
            response = 400, {"error_code": exc.code, "message": exc.message}
        return _json_response(response)

    return router


def build_evaluation_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "evaluation")
    router = APIRouter()

    @router.post("/v1/evaluation/llm-real-path-benchmark")
    async def llm_real_path_benchmark(request: Request) -> JSONResponse:
        body_result = await _read_json_object(request)
        if isinstance(body_result, JSONResponse):
            return body_result
        try:
            response = await run_in_threadpool(parsed_handler.handle, body_result)
        except LLMGatewayContractError as exc:
            response = 400, {"error_code": exc.code, "message": exc.message}
        return _json_response(response)

    return router


def build_search_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "recherche")
    router = APIRouter()

    @router.post("/v1/search")
    async def search(request: Request) -> JSONResponse:
        body_result = await _read_json_object(request)
        if isinstance(body_result, JSONResponse):
            return body_result
        return _json_response(await run_in_threadpool(parsed_handler.handle, body_result))

    return router


def build_indexing_router(handler: IndexCommandHandler) -> APIRouter:
    parsed_handler = _require_index_handler(handler)
    router = APIRouter()

    @router.post("/v1/documents/{document_id}/index")
    async def index_document(document_id: str, request: Request) -> JSONResponse:
        body_result = await _read_json_object(request)
        if isinstance(body_result, JSONResponse):
            return body_result
        return _json_response(
            await run_in_threadpool(parsed_handler.handle, document_id, body_result)
        )

    return router


def build_public_contract_router(services: PublicContractServices) -> APIRouter:
    if not isinstance(services, PublicContractServices):
        raise TypeError("services de contrats publics obligatoires")
    router = APIRouter()
    router.include_router(build_conversation_router(services.conversation))
    router.include_router(build_evaluation_router(services.evaluation))
    router.include_router(build_search_router(services.search))
    router.include_router(build_indexing_router(services.indexing))
    return router


async def _read_json_object(request: Request) -> dict[str, Any] | JSONResponse:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        return _invalid_request_response("content_length")
    try:
        content_length = int(raw_length)
    except ValueError:
        return _invalid_request_response("content_length")
    if content_length < 0:
        return _invalid_request_response("content_length")
    if content_length == 0:
        return {}

    raw_body = await request.body()
    try:
        parsed_body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _invalid_request_response("body")
    if not isinstance(parsed_body, dict):
        return _invalid_request_response("body")
    return parsed_body


def _invalid_request_response(field: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error_code": "HTTP_REQUEST_INVALID", "field": field},
    )


def _json_response(response: tuple[int, dict[str, Any]]) -> JSONResponse:
    status_code, body = response
    return JSONResponse(status_code=status_code, content=body)


def _require_json_handler(value: Any, label: str) -> JsonCommandHandler:
    if not callable(getattr(value, "handle", None)):
        raise TypeError(f"handler {label} obligatoire")
    return value


def _require_index_handler(value: Any) -> IndexCommandHandler:
    if not callable(getattr(value, "handle", None)):
        raise TypeError("handler indexation obligatoire")
    return value


__all__ = [
    "build_conversation_router",
    "build_evaluation_router",
    "build_health_router",
    "build_indexing_router",
    "build_public_contract_router",
    "build_search_router",
]
