from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
import asyncio
import json
import re
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHttpException

from app.platform.configuration import ApplicationConfiguration
from app.platform.orchestrator_composition import OrchestratorCompositionRoot
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.platform.orchestrator_contract_routers import (
    build_health_router,
)


CompositionRootFactory = Callable[[ApplicationConfiguration], OrchestratorCompositionRoot]
MAX_REQUEST_BODY_BYTES = 54_000_000
REQUEST_BODY_MEMORY_SPOOL_BYTES = 1024 * 1024
REQUEST_BODY_REPLAY_CHUNK_BYTES = 64 * 1024


class RequestBodyTooLargeError(ValueError):
    """Le flux reçu dépasse la frontière agrégée avant son parsing."""


class BoundedReceive:
    """Décore ``receive`` sans recopier ni spouler le corps HTTP."""

    def __init__(self, receive: Callable, *, max_body_bytes: int) -> None:
        if not callable(receive):
            raise ValueError("receive ASGI invalide")
        self._receive = receive
        self._max_body_bytes = _ensure_positive_integer(max_body_bytes, "max_body_bytes")
        self._consumed = 0

    async def __call__(self) -> dict[str, Any]:
        message = await self._receive()
        if message.get("type") == "http.request":
            body = message.get("body", b"")
            if not isinstance(body, bytes):
                raise ValueError("chunk HTTP non binaire")
            self._consumed += len(body)
            if self._consumed > self._max_body_bytes:
                raise RequestBodyTooLargeError("HTTP_REQUEST_TOO_LARGE")
        return message


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
        if content_length is not None and content_length < 0:
            await _send_invalid_content_length(send)
            return
        if content_length is not None and content_length > self._max_body_bytes:
            await _send_body_too_large(send, self._max_body_bytes)
            return
        response_started = False

        async def tracked_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._application(
                scope,
                BoundedReceive(receive, max_body_bytes=self._max_body_bytes),
                tracked_send,
            )
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await _send_body_too_large(send, self._max_body_bytes)

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

        try:
            async with asyncio.timeout(configuration.runtime.timeouts.startup_seconds):
                await composition_root.open()
        except TimeoutError as exc:
            raise TimeoutError("ORCHESTRATOR_STARTUP_TIMEOUT") from exc
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

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        del request, exception
        return JSONResponse(
            status_code=422,
            content={"error_code": "HTTP_REQUEST_INVALID"},
        )

    @application.exception_handler(StarletteHttpException)
    async def http_error_handler(
        request: Request,
        exception: StarletteHttpException,
    ) -> JSONResponse:
        del request
        error_codes = {
            404: "HTTP_ROUTE_NOT_FOUND",
            405: "HTTP_METHOD_NOT_ALLOWED",
        }
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "error_code": error_codes.get(exception.status_code, "HTTP_ERROR")
            },
        )

    @application.middleware("http")
    async def trace_request(request: Request, call_next: Callable) -> Response:
        try:
            trace_id = _request_trace_id(request)
        except ValueError:
            trace_id = _new_trace_id()
            response = JSONResponse(
                status_code=400,
                content={"error_code": "TRACE_ID_INVALID"},
            )
            _complete_traced_response(
                response=response,
                trace_id=trace_id,
                configuration=configuration,
                request=request,
                started_ns=time.perf_counter_ns(),
            )
            return response
        started_ns = time.perf_counter_ns()
        trace_token = bind_trace_id(trace_id)
        try:
            try:
                async with asyncio.timeout(configuration.runtime.timeouts.request_seconds):
                    response = await call_next(request)
            except TimeoutError:
                response = JSONResponse(
                    status_code=504,
                    content={"error_code": "ORCHESTRATOR_REQUEST_TIMEOUT"},
                )
            except Exception:
                response = JSONResponse(
                    status_code=500,
                    content={"error_code": "ORCHESTRATOR_INTERNAL_ERROR"},
                )
        finally:
            reset_trace_id(trace_token)
        _complete_traced_response(
            response=response,
            trace_id=trace_id,
            configuration=configuration,
            request=request,
            started_ns=started_ns,
        )
        return response
    application.include_router(build_health_router())

    @application.get("/ready")
    async def ready() -> JSONResponse:
        composition_root = application.state.composition_root
        dependencies = await run_in_threadpool(composition_root.readiness_snapshot)
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
        return _new_trace_id()
    if (
        provided == ""
        or provided != provided.strip()
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", provided) is None
    ):
        raise ValueError("TRACE_ID_INVALID")
    return provided


def _new_trace_id() -> str:
    return f"TRACE-{uuid4().hex.upper()}"


def _complete_traced_response(
    *,
    response: Response,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
    started_ns: int,
) -> None:
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
                "success_count": 1 if response.status_code < 400 else 0,
                "error_count": 1 if response.status_code >= 400 else 0,
                "request_volume_bytes": _request_volume_bytes(request),
                "tracing_enabled": configuration.observability.tracing.enabled,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _request_volume_bytes(request: Request) -> int:
    raw = request.headers.get("content-length")
    if raw is None or not raw.isdecimal():
        return 0
    return int(raw)


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
        timeout_keep_alive=configuration.runtime.timeouts.request_seconds,
        timeout_graceful_shutdown=configuration.runtime.timeouts.shutdown_seconds,
    )


__all__ = [
    "BoundedRequestBodyMiddleware",
    "CompositionRootFactory",
    "MAX_REQUEST_BODY_BYTES",
    "create_orchestrator_app",
    "serve_orchestrator_app",
]
