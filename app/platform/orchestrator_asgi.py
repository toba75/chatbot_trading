from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
import json
from tempfile import SpooledTemporaryFile
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from starlette.concurrency import run_in_threadpool

from app.platform.configuration import ApplicationConfiguration
from app.platform.orchestrator_composition import OrchestratorCompositionRoot
from app.platform.orchestrator_contract_routers import (
    build_conversation_router,
    build_evaluation_router,
    build_health_router,
    build_indexing_router,
    build_search_router,
)


CompositionRootFactory = Callable[[ApplicationConfiguration], OrchestratorCompositionRoot]
MAX_REQUEST_BODY_BYTES = 54_000_000
REQUEST_BODY_MEMORY_SPOOL_BYTES = 1024 * 1024
REQUEST_BODY_REPLAY_CHUNK_BYTES = 64 * 1024


class BoundedRequestBodyMiddleware:
    """Borne et spoule le corps complet avant tout parsing applicatif."""

    def __init__(
        self,
        application: Any,
        *,
        max_body_bytes: int,
        memory_spool_bytes: int,
        replay_chunk_bytes: int,
    ) -> None:
        if not callable(application):
            raise ValueError("application ASGI invalide")
        self._application = application
        self._max_body_bytes = _ensure_positive_integer(
            max_body_bytes,
            "max_body_bytes",
        )
        self._memory_spool_bytes = _ensure_positive_integer(
            memory_spool_bytes,
            "memory_spool_bytes",
        )
        self._replay_chunk_bytes = _ensure_positive_integer(
            replay_chunk_bytes,
            "replay_chunk_bytes",
        )

    async def __call__(self, scope: Any, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self._application(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is None:
            await self._buffer_and_forward(scope, receive, send)
            return
        if content_length < 0:
            await _send_invalid_content_length(send)
            return
        if content_length > self._max_body_bytes:
            await _send_body_too_large(send, self._max_body_bytes)
            return
        await self._buffer_and_forward(scope, receive, send)

    async def _buffer_and_forward(
        self,
        scope: Any,
        receive: Callable,
        send: Callable,
    ) -> None:
        spool = SpooledTemporaryFile(max_size=self._memory_spool_bytes, mode="w+b")
        consumed = 0
        try:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    raise ValueError("message ASGI de requête invalide")
                body = message.get("body", b"")
                if not isinstance(body, bytes):
                    raise ValueError("chunk HTTP non binaire")
                consumed += len(body)
                if consumed > self._max_body_bytes:
                    await _send_body_too_large(send, self._max_body_bytes)
                    return
                if body:
                    await run_in_threadpool(spool.write, body)
                if not message.get("more_body", False):
                    break

            await run_in_threadpool(spool.seek, 0)

            async def replay_receive() -> dict[str, Any]:
                chunk = await run_in_threadpool(
                    spool.read,
                    self._replay_chunk_bytes,
                )
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": len(chunk) > 0 and spool.tell() < consumed,
                }

            forwarded_scope = dict(scope)
            forwarded_scope["headers"] = [
                (name, value)
                for name, value in scope.get("headers", ())
                if name.lower() != b"content-length"
            ] + [(b"content-length", str(consumed).encode("ascii"))]
            await self._application(forwarded_scope, replay_receive, send)
        finally:
            await run_in_threadpool(spool.close)


def create_orchestrator_app(
    *,
    configuration: ApplicationConfiguration,
    composition_root_factory: CompositionRootFactory,
) -> FastAPI:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        composition_root = composition_root_factory(configuration)
        if not isinstance(composition_root, OrchestratorCompositionRoot):
            raise TypeError("composition_root_factory doit construire OrchestratorCompositionRoot")

        await composition_root.open()
        application.state.composition_root = composition_root
        application.include_router(composition_root.document_command_router)
        try:
            yield
        finally:
            await composition_root.close()

    application = FastAPI(
        lifespan=lifespan,
        title="OSTrading orchestrator-api",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    application.add_middleware(
        BoundedRequestBodyMiddleware,
        max_body_bytes=MAX_REQUEST_BODY_BYTES,
        memory_spool_bytes=REQUEST_BODY_MEMORY_SPOOL_BYTES,
        replay_chunk_bytes=REQUEST_BODY_REPLAY_CHUNK_BYTES,
    )

    @application.middleware("http")
    async def trace_request(request: Request, call_next: Callable) -> JSONResponse:
        trace_id = _request_trace_id(request)
        started_ns = time.perf_counter_ns()
        response = await call_next(request)
        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        response.headers["X-Trace-ID"] = trace_id
        print(
            json.dumps(
                {
                    "configuration_hash": configuration.configuration_hash,
                    "duration_ms": round(duration_ms, 3),
                    "event_type": "orchestrator_http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "trace_id": trace_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return response
    application.include_router(build_health_router())
    application.include_router(build_conversation_router(configuration))
    application.include_router(build_evaluation_router(configuration))
    application.include_router(build_search_router())
    application.include_router(build_indexing_router())

    @application.get("/ready")
    async def ready() -> JSONResponse:
        composition_root = application.state.composition_root
        dependencies = composition_root.readiness_snapshot()
        is_ready = all(dependency.status == "ready" for dependency in dependencies)
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "service": "orchestrator-api",
                "status": "ready" if is_ready else "not_ready",
                "dependencies": [asdict(dependency) for dependency in dependencies],
            },
        )

    return application


def _request_trace_id(request: Request) -> str:
    provided = request.headers.get("X-Trace-ID")
    if provided is None:
        return f"TRACE-{uuid4().hex.upper()}"
    if provided == "" or provided != provided.strip() or len(provided) > 128:
        raise ValueError("TRACE_ID_INVALID")
    return provided


def _content_length(scope: Any) -> int | None:
    values = [
        value
        for name, value in scope.get("headers", ())
        if name.lower() == b"content-length"
    ]
    if len(values) == 0:
        return None
    if len(values) != 1:
        return -1
    try:
        text = values[0].decode("ascii")
    except UnicodeDecodeError:
        return -1
    if not text.isdecimal():
        return -1
    return int(text)


async def _send_body_too_large(send: Callable, max_body_bytes: int) -> None:
    await _send_json_response(
        send,
        status_code=413,
        content={
            "error_code": "HTTP_REQUEST_TOO_LARGE",
            "max_body_bytes": max_body_bytes,
        },
    )


async def _send_invalid_content_length(send: Callable) -> None:
    await _send_json_response(
        send,
        status_code=400,
        content={"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"},
    )


async def _send_json_response(
    send: Callable,
    *,
    status_code: int,
    content: dict[str, Any],
) -> None:
    body = json.dumps(content, separators=(",", ":")).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-length", str(len(body)).encode("ascii")),
                (b"content-type", b"application/json"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def serve_orchestrator_app(
    *,
    configuration: ApplicationConfiguration,
    composition_root_factory: CompositionRootFactory,
) -> None:
    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=composition_root_factory,
    )
    uvicorn.run(
        application,
        host=configuration.services.api.bind_host,
        port=configuration.services.api.port,
    )


__all__ = [
    "BoundedRequestBodyMiddleware",
    "CompositionRootFactory",
    "MAX_REQUEST_BODY_BYTES",
    "create_orchestrator_app",
    "serve_orchestrator_app",
]
