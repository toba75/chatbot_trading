"""Routeurs FastAPI minces des contrats publics historiques."""

from __future__ import annotations

from typing import TypeVar

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.contracts.llm_inference import LlmContractError
from app.platform.orchestrator_api_models import (
    BenchmarkRequest,
    BenchmarkResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    IndexRequest,
    IndexUnavailableResponse,
    PUBLIC_ERROR_RESPONSES,
    PublicErrorResponse,
    ProductConversationCreateRequest,
    ProductConversationMessageRequest,
    ProductConversationMessageResponse,
    ProductConversationResponse,
    ProductConversationTurnsResponse,
    SearchRequest,
    SearchUnavailableResponse,
)
from app.conversation.adapters.product_conversation_http import (
    HttpRequest as ProductConversationHttpRequest,
    ProductConversationHttpAdapter,
)
from app.platform.orchestrator_public_services import (
    IndexCommandHandler,
    JsonCommandHandler,
    PublicContractServices,
)
from app.platform.request_context import current_trace_id


PublicModel = TypeVar("PublicModel", bound=BaseModel)


def build_health_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"service": "orchestrator-api", "status": "healthy"}

    return router


def build_conversation_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "conversation")
    router = APIRouter()

    @router.post(
        "/v1/chat/completions",
        response_model=ChatCompletionResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def chat_completions(payload: ChatCompletionRequest) -> JSONResponse:
        try:
            response = await run_in_threadpool(
                parsed_handler.handle,
                payload.model_dump(mode="json"),
                trace_id=current_trace_id(),
            )
        except LlmContractError as error:
            response = 400, {"error_code": error.code, "message": error.message}
        return _validated_response(
            response,
            success_model=ChatCompletionResponse,
        )

    return router


def build_product_conversation_router(
    adapter: ProductConversationHttpAdapter,
) -> APIRouter:
    """Expose le contrat CV natif, distinct de la compatibilité externe."""

    if not isinstance(adapter, ProductConversationHttpAdapter):
        raise TypeError("adaptateur conversation produit obligatoire")
    router = APIRouter()

    @router.post(
        "/v1/conversations",
        response_model=ProductConversationResponse,
        status_code=201,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def create_conversation(payload: ProductConversationCreateRequest) -> JSONResponse:
        response = await run_in_threadpool(
            adapter.handle,
            ProductConversationHttpRequest(
                method="POST",
                path="/v1/conversations",
                body=payload.model_dump(mode="json"),
            ),
        )
        return _product_response(
            response.status_code,
            response.body,
            success_status=201,
            success_model=ProductConversationResponse,
        )

    @router.get(
        "/v1/conversations/{conversation_id}",
        response_model=ProductConversationResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def read_conversation(conversation_id: str) -> JSONResponse:
        response = await run_in_threadpool(
            adapter.handle,
            ProductConversationHttpRequest(
                method="GET",
                path=f"/v1/conversations/{conversation_id}",
                body={},
            ),
        )
        return _product_response(
            response.status_code,
            response.body,
            success_status=200,
            success_model=ProductConversationResponse,
        )

    @router.get(
        "/v1/conversations/{conversation_id}/turns",
        response_model=ProductConversationTurnsResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def read_conversation_turns(conversation_id: str) -> JSONResponse:
        response = await run_in_threadpool(
            adapter.handle,
            ProductConversationHttpRequest(
                method="GET",
                path=f"/v1/conversations/{conversation_id}/turns",
                body={},
            ),
        )
        return _product_response(
            response.status_code,
            response.body,
            success_status=200,
            success_model=ProductConversationTurnsResponse,
        )

    @router.post(
        "/v1/conversations/{conversation_id}/messages",
        response_model=ProductConversationMessageResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def post_message(
        conversation_id: str,
        payload: ProductConversationMessageRequest,
    ) -> JSONResponse:
        response = await run_in_threadpool(
            adapter.handle,
            ProductConversationHttpRequest(
                method="POST",
                path=f"/v1/conversations/{conversation_id}/messages",
                body=payload.model_dump(mode="json", exclude_none=True),
            ),
        )
        return _product_response(
            response.status_code,
            response.body,
            success_status=200,
            success_model=ProductConversationMessageResponse,
        )

    return router


def build_evaluation_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "evaluation")
    router = APIRouter()

    @router.post(
        "/v1/evaluation/llm-real-path-benchmark",
        response_model=BenchmarkResponse,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    async def llm_real_path_benchmark(payload: BenchmarkRequest) -> JSONResponse:
        try:
            response = await run_in_threadpool(
                parsed_handler.handle,
                payload.model_dump(mode="json"),
                trace_id=current_trace_id(),
            )
        except LlmContractError as error:
            response = 400, {"error_code": error.code, "message": error.message}
        return _validated_response(response, success_model=BenchmarkResponse)

    return router


def build_search_router(handler: JsonCommandHandler) -> APIRouter:
    parsed_handler = _require_json_handler(handler, "recherche")
    router = APIRouter()

    @router.post(
        "/v1/search",
        response_model=SearchUnavailableResponse,
        status_code=503,
        responses={**PUBLIC_ERROR_RESPONSES, 503: {"model": SearchUnavailableResponse}},
    )
    async def search(payload: SearchRequest) -> JSONResponse:
        response = await run_in_threadpool(
            parsed_handler.handle,
            payload.model_dump(mode="json"),
            trace_id=current_trace_id(),
        )
        return _validated_response(
            response,
            success_model=SearchUnavailableResponse,
            success_status=503,
        )

    return router


def build_indexing_router(handler: IndexCommandHandler) -> APIRouter:
    parsed_handler = _require_index_handler(handler)
    router = APIRouter()

    @router.post(
        "/v1/documents/{document_id}/index",
        response_model=IndexUnavailableResponse,
        status_code=503,
        responses={**PUBLIC_ERROR_RESPONSES, 503: {"model": IndexUnavailableResponse}},
    )
    async def index_document(document_id: str, payload: IndexRequest) -> JSONResponse:
        response = await run_in_threadpool(
            parsed_handler.handle,
            document_id,
            payload.model_dump(mode="json"),
            trace_id=current_trace_id(),
        )
        return _validated_response(
            response,
            success_model=IndexUnavailableResponse,
            success_status=503,
        )

    return router


def build_public_contract_router(
    services: PublicContractServices,
    *,
    include_indexing_router: bool = True,
) -> APIRouter:
    if not isinstance(services, PublicContractServices):
        raise TypeError("services de contrats publics obligatoires")
    router = APIRouter()
    router.include_router(build_conversation_router(services.conversation))
    router.include_router(build_evaluation_router(services.evaluation))
    router.include_router(build_search_router(services.search))
    if include_indexing_router:
        router.include_router(build_indexing_router(services.indexing))
    return router


def _validated_response(
    response: tuple[int, dict[str, object]],
    *,
    success_model: type[PublicModel],
    success_status: int = 200,
) -> JSONResponse:
    status_code, body = response
    model_type: type[BaseModel]
    if status_code == success_status:
        model_type = success_model
    else:
        model_type = PublicErrorResponse
    validated = model_type.model_validate(body)
    return JSONResponse(
        status_code=status_code,
        content=validated.model_dump(mode="json", exclude_unset=True),
    )


def _product_response(
    status_code: int,
    body: dict[str, object],
    *,
    success_status: int,
    success_model: type[PublicModel],
) -> JSONResponse:
    model_type: type[BaseModel] = success_model if status_code == success_status else PublicErrorResponse
    validated = model_type.model_validate(body)
    return JSONResponse(
        status_code=status_code,
        content=validated.model_dump(mode="json", exclude_unset=True),
    )


def _require_json_handler(value: object, label: str) -> JsonCommandHandler:
    if not callable(getattr(value, "handle", None)):
        raise TypeError(f"handler {label} obligatoire")
    return value


def _require_index_handler(value: object) -> IndexCommandHandler:
    if not callable(getattr(value, "handle", None)):
        raise TypeError("handler indexation obligatoire")
    return value


__all__ = [
    "build_conversation_router",
    "build_evaluation_router",
    "build_health_router",
    "build_indexing_router",
    "build_product_conversation_router",
    "build_public_contract_router",
    "build_search_router",
]
