from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
import asyncio
import json
from pathlib import Path
import re
import time
import traceback
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHttpException

from app.platform.configuration import ApplicationConfiguration
from app.platform.local_authorization import LocalMutationAuthorizer
from app.platform.orchestrator_composition import OrchestratorCompositionRoot
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.platform.orchestrator_contract_routers import (
    build_health_router,
)


CompositionRootFactory = Callable[[ApplicationConfiguration], OrchestratorCompositionRoot]
MAX_REQUEST_BODY_BYTES = 54_000_000
_STRICT_JSON_BODY_PATHS = frozenset(
    (
        "/v1/chat/completions",
        "/v1/evaluation/llm-real-path-benchmark",
        "/v1/search",
    )
)


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
    """Borne le flux reçu sans le recopier ni le spouler avant le parsing."""

    def __init__(
        self,
        application: Any,
        *,
        max_body_bytes: int,
    ) -> None:
        if not callable(application):
            raise ValueError("application ASGI invalide")
        self._application = application
        self._max_body_bytes = _ensure_positive_integer(
            max_body_bytes,
            "max_body_bytes",
        )

    async def __call__(self, scope: Any, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self._application(scope, receive, send)
            return

        content_length = _content_length(scope)
        if (
            scope.get("method") == "POST"
            and scope.get("path") in _STRICT_JSON_BODY_PATHS
            and content_length is None
        ):
            await _send_invalid_content_length(send)
            return
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


class LocalMutationAuthorizationMiddleware:
    """Exige le secret backend sur les mutations documentaires persistantes."""

    def __init__(self, application: Any, *, token_path: str) -> None:
        if not callable(application):
            raise ValueError("application ASGI invalide")
        if not isinstance(token_path, str) or token_path.strip() == "":
            raise ValueError("LOCAL_API_TOKEN_PATH_INVALID")
        self._application = application
        self._token_path = Path(token_path)

    async def __call__(self, scope: Any, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self._application(scope, receive, send)
            return
        method = scope.get("method")
        path = scope.get("path")
        if method != "POST" or not (
            path == "/v1/documents"
            or (
                isinstance(path, str)
                and path.startswith("/v1/documents/")
                and (
                    path.endswith("/diagnose")
                    or path.endswith("/convert")
                )
            )
        ):
            await self._application(scope, receive, send)
            return
        authorizer = LocalMutationAuthorizer.from_file(self._token_path)
        authorization = None
        for name, value in scope.get("headers", ()):
            if name.lower() == b"authorization":
                try:
                    authorization = value.decode("ascii")
                except UnicodeDecodeError:
                    authorization = ""
                break
        refusal = authorizer.authorize(
            method=method,
            path=path,
            authorization_header=authorization,
        )
        if refusal is not None:
            await _send_json_response(
                send,
                status_code=refusal[0],
                content={"error_code": refusal[1]},
            )
            return
        await self._application(scope, receive, send)


class StreamingFailureObservationMiddleware:
    """Observe une rupture après envoi des en-têtes, hors BaseHTTPMiddleware."""

    def __init__(
        self,
        application: Any,
        *,
        configuration: ApplicationConfiguration,
    ) -> None:
        if not callable(application):
            raise ValueError("application ASGI invalide")
        if not isinstance(configuration, ApplicationConfiguration):
            raise TypeError("configuration applicative validée obligatoire")
        self._application = application
        self._configuration = configuration

    async def __call__(self, scope: Any, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self._application(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        started_ns = time.perf_counter_ns()
        response_status: int | None = None
        response_volume_bytes = 0
        response_trace_id: str | None = None

        async def observed_send(message: dict[str, Any]) -> None:
            nonlocal response_status, response_trace_id, response_volume_bytes
            status: int | None = None
            trace_id: str | None = None
            body_size = 0
            if message.get("type") == "http.response.start":
                candidate_status = message.get("status")
                if isinstance(candidate_status, int):
                    status = candidate_status
                for name, value in message.get("headers", ()):
                    if name.lower() == b"x-trace-id":
                        trace_id = value.decode("ascii")
            elif message.get("type") == "http.response.body":
                body = message.get("body", b"")
                if isinstance(body, bytes):
                    body_size = len(body)
            await send(message)
            if status is not None:
                response_status = status
            if trace_id is not None:
                response_trace_id = trace_id
            response_volume_bytes += body_size

        try:
            await self._application(scope, receive, observed_send)
        except BaseException as exception:
            if response_status is not None:
                trace_id = response_trace_id or _safe_scope_trace_id(scope)
                response = Response(status_code=response_status)
                _print_http_observation(
                    response=response,
                    trace_id=trace_id,
                    configuration=self._configuration,
                    request=request,
                    started_ns=started_ns,
                    response_volume_bytes=response_volume_bytes,
                    error_code="HTTP_STREAM_INTERRUPTED",
                    succeeded=False,
                )
                _log_safe_exception(
                    event_type="orchestrator_http_stream_failure",
                    error_code="HTTP_STREAM_INTERRUPTED",
                    exception=exception,
                    trace_id=trace_id,
                    configuration=self._configuration,
                    request=request,
                )
            raise
        pending_observation = scope.pop("ost.http_stream_success_observation", None)
        if isinstance(pending_observation, dict):
            _print_http_observation(**pending_observation)

def create_orchestrator_app(
    *,
    configuration: ApplicationConfiguration,
    composition_root_factory: CompositionRootFactory,
) -> FastAPI:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")

    composition_root = composition_root_factory(configuration)
    if not isinstance(composition_root, OrchestratorCompositionRoot):
        raise TypeError("composition_root_factory doit construire OrchestratorCompositionRoot")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            async with asyncio.timeout(configuration.runtime.timeouts.startup_seconds):
                await composition_root.open()
        except TimeoutError as exc:
            raise TimeoutError("ORCHESTRATOR_STARTUP_TIMEOUT") from exc
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
    )
    application.add_middleware(
        LocalMutationAuthorizationMiddleware,
        token_path=configuration.security.secrets.local_api_token_path,
    )
    application.state.composition_root = composition_root
    application.include_router(composition_root.document_command_router)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        del request
        public_shape_errors = {"json_invalid", "model_attributes_type", "model_type"}
        if any(error.get("type") in public_shape_errors for error in exception.errors()):
            return JSONResponse(
                status_code=400,
                content={"error_code": "HTTP_REQUEST_INVALID", "field": "body"},
            )
        return JSONResponse(
            status_code=422,
            content={"error_code": "HTTP_REQUEST_INVALID"},
        )

    @application.exception_handler(StarletteHttpException)
    async def http_error_handler(
        request: Request,
        exception: StarletteHttpException,
    ) -> JSONResponse:
        error_codes = {
            404: "ENDPOINT_NOT_FOUND",
            405: "HTTP_METHOD_NOT_ALLOWED",
        }
        content: dict[str, Any] = {
            "error_code": error_codes.get(exception.status_code, "HTTP_ERROR")
        }
        if exception.status_code == 404:
            content["path"] = request.url.path
        return JSONResponse(
            status_code=exception.status_code,
            content=content,
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
            except Exception as exception:
                _log_internal_exception(
                    exception=exception,
                    trace_id=trace_id,
                    configuration=configuration,
                    request=request,
                )
                response = JSONResponse(
                    status_code=500,
                    content={"error_code": "ORCHESTRATOR_INTERNAL_ERROR"},
                )
        finally:
            reset_trace_id(trace_token)
        if hasattr(response, "body_iterator"):
            response.headers["X-Trace-ID"] = trace_id
            response.body_iterator = _observed_body_iterator(
                response.body_iterator,
                response=response,
                trace_id=trace_id,
                configuration=configuration,
                request=request,
                started_ns=started_ns,
            )
            return response
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
                "environment": configuration.application.environment,
                "deployment_id": configuration.application.deployment_id,
                "configuration_hash": configuration.configuration_hash,
                "dependencies": [
                    {
                        key: value
                        for key, value in asdict(dependency).items()
                        if value is not None
                    }
                    for dependency in dependencies
                ],
            },
        )

    application.add_middleware(
        StreamingFailureObservationMiddleware,
        configuration=configuration,
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


def _safe_scope_trace_id(scope: Any) -> str:
    for name, value in scope.get("headers", ()):
        if name.lower() == b"x-trace-id":
            try:
                trace_id = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", trace_id):
                return trace_id
            break
    return _new_trace_id()


async def _observed_body_iterator(
    body_iterator: AsyncIterator[bytes],
    *,
    response: Response,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
    started_ns: int,
) -> AsyncIterator[bytes]:
    response_volume_bytes = 0
    json_preview = bytearray()
    capture_json = response.headers.get("content-type", "").startswith("application/json")
    async for chunk in body_iterator:
        if not isinstance(chunk, bytes):
            raise TypeError("HTTP_RESPONSE_CHUNK_INVALID")
        response_volume_bytes += len(chunk)
        if capture_json and len(json_preview) < 65_536:
            remaining = 65_536 - len(json_preview)
            json_preview.extend(chunk[:remaining])
        yield chunk
    request.scope["ost.http_stream_success_observation"] = {
        "response": response,
        "trace_id": trace_id,
        "configuration": configuration,
        "request": request,
        "started_ns": started_ns,
        "response_volume_bytes": response_volume_bytes,
        "error_code": _error_code_from_json_bytes(
            bytes(json_preview), response.status_code
        ),
        "succeeded": response.status_code < 400,
    }


def _log_internal_exception(
    *,
    exception: BaseException,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
) -> None:
    _log_safe_exception(
        event_type="orchestrator_internal_error",
        error_code="ORCHESTRATOR_INTERNAL_ERROR",
        exception=exception,
        trace_id=trace_id,
        configuration=configuration,
        request=request,
    )


def _log_safe_exception(
    *,
    event_type: str,
    error_code: str,
    exception: BaseException,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
) -> None:
    stack = [
        {
            "file": Path(frame.filename).name,
            "function": frame.name,
            "line": frame.lineno,
        }
        for frame in traceback.extract_tb(exception.__traceback__)
    ]
    cause_types: list[str] = []
    cause = exception.__cause__
    while cause is not None:
        cause_types.append(type(cause).__name__)
        cause = cause.__cause__
    print(
        json.dumps(
            {
                "cause_types": cause_types,
                "configuration_hash": configuration.configuration_hash,
                "error_code": error_code,
                "event_type": event_type,
                "exception_type": type(exception).__name__,
                "method": request.method,
                "path": request.url.path,
                "stack": stack,
                "trace_id": trace_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _complete_traced_response(
    *,
    response: Response,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
    started_ns: int,
) -> None:
    response.headers["X-Trace-ID"] = trace_id
    body = getattr(response, "body", b"")
    response_volume_bytes = len(body) if isinstance(body, bytes) else 0
    _print_http_observation(
        response=response,
        trace_id=trace_id,
        configuration=configuration,
        request=request,
        started_ns=started_ns,
        response_volume_bytes=response_volume_bytes,
        error_code=_response_error_code(response),
        succeeded=response.status_code < 400,
    )


def _print_http_observation(
    *,
    response: Response,
    trace_id: str,
    configuration: ApplicationConfiguration,
    request: Request,
    started_ns: int,
    response_volume_bytes: int,
    error_code: str | None,
    succeeded: bool,
) -> None:
    duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
    print(
        json.dumps(
            {
                "configuration_hash": configuration.configuration_hash,
                "duration_ms": round(duration_ms, 3),
                "event_type": "orchestrator_http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "error_code": error_code,
                "trace_id": trace_id,
                "success_count": 1 if succeeded else 0,
                "error_count": 0 if succeeded else 1,
                "request_volume_bytes": _request_volume_bytes(request),
                "response_volume_bytes": response_volume_bytes,
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


def _response_error_code(response: Response) -> str | None:
    if response.status_code < 400:
        return None
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            error_code = payload.get("error_code")
            if isinstance(error_code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", error_code):
                return error_code
    return "HTTP_RESPONSE_ERROR"


def _error_code_from_json_bytes(body: bytes, status_code: int) -> str | None:
    if status_code < 400:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "HTTP_RESPONSE_ERROR"
    if not isinstance(payload, dict):
        return "HTTP_RESPONSE_ERROR"
    error_code = payload.get("error_code")
    if isinstance(error_code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", error_code):
        return error_code
    return "HTTP_RESPONSE_ERROR"


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
    "LocalMutationAuthorizationMiddleware",
    "CompositionRootFactory",
    "MAX_REQUEST_BODY_BYTES",
    "create_orchestrator_app",
    "serve_orchestrator_app",
]
