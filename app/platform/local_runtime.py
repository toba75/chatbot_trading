"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from app.platform.configuration import (
    ApplicationConfiguration,
    ApplicationConfigurationError,
    CONFIG_FILE_REQUIRED,
    load_application_configuration,
)
from app.platform.configured_datastore_identity import build_configured_datastore_preflight
from app.platform.llm_gateway import (
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayConfiguration,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceImage,
    InferenceImageMessage,
    InferenceMessage,
    InferenceRequest,
    LLMGatewayContractError,
    LLMGatewayInferenceError,
    OpenAICompatibleLocalLanguageModelGateway,
    SystemGatewayClock,
    UrllibOpenAICompatibleTransport,
)
from app.platform.observability import GatewayObservation, InMemoryObservabilityCollector
from app.platform.orchestrator_asgi import MAX_REQUEST_BODY_BYTES
from app.platform.worker_environment import build_worker_environment_binding
from app.platform.ui_corpus import (
    CorpusPdfScreenState,
    build_unavailable_corpus_pdf_state,
    render_document_inspection,
    ui_get_response,
)


def _benchmark_marker_for_task(task_name: str) -> str:
    """Compatibilité du harness M-013-config, sans logique d'exécution métier."""

    if not isinstance(task_name, str) or task_name.strip() == "":
        raise ValueError("task_name invalide")
    return f"M013-REALITY-{task_name}"
from app.platform.ui_document_api import (
    ORCHESTRATOR_API_UNAVAILABLE,
    UiDocumentApiClient,
    UiDocumentCommandForbiddenError,
    UiDocumentApiPublicError,
    UiDocumentApiUnavailableError,
    UiDocumentApiResponse,
    UiDocumentApiStreamResponse,
    UiDocumentJsonResponse,
    UrllibUiDocumentApiTransport,
)


HTTP_SERVICE_PORTS = {
    "ui": 8081,
    "orchestrator-api": 8080,
    "llm-gateway": 8090,
    "granite-docling": 8001,
    "embedding-service": 8101,
    "reranker-service": 8102,
    "backtest-engine": 8200,
}
WORKER_SERVICE_IDS = frozenset(("worker-documents", "worker-research", "worker-backtest"))
_UI_DOCUMENT_INSPECTION_PATH_PATTERN = re.compile(
    r"^/ui/documents/(?P<document_id>[^/]+)/(?P<step>diagnostic|conversion|projection)$"
)
_UI_PDF_CONTENT_PATH_PATTERN = re.compile(
    r"^/ui/documents/(?P<document_id>[^/]+)/pdf/content$"
)
from app.platform.ui_conversation import (
    render_conversation_page,
    render_new_conversation_page,
)
from app.platform.ui_conversation_api import (
    UiConversationApiClient,
    UiConversationApiPublicError,
    UiConversationApiUnavailableError,
)
_DIAGNOSE_PATH_PATTERN = re.compile(r"^/v1/documents/(?P<document_id>[^/]+)/diagnose$")
_CONVERT_PATH_PATTERN = re.compile(r"^/v1/documents/(?P<document_id>[^/]+)/convert$")
_MANUAL_REVIEW_PATH_PATTERN = re.compile(
    r"^/v1/documents/(?P<document_id>[^/]+)/manual-review$"
)
_INDEX_PATH_PATTERN = re.compile(r"^/v1/documents/(?P<document_id>[^/]+)/index$")
_UI_CONVERSATION_PATH_PATTERN = re.compile(r"^/ui/conversations/(?P<conversation_id>CONV-[^/]+)$")
_UI_CONVERSATION_MESSAGE_PATH_PATTERN = re.compile(
    r"^/ui/conversations/(?P<conversation_id>CONV-[^/]+)/messages$"
)
_LLM_GATEWAY_LOCK = threading.Lock()
_LLM_GATEWAY_INSTANCE: OpenAICompatibleLocalLanguageModelGateway | None = None
_LLM_GATEWAY_CONFIGURATION_HASH: str | None = None
UI_MAX_CONCURRENT_TRANSFERS = 4
UI_SOCKET_TIMEOUT_SECONDS = 30
_UI_CONVERSATION_FORM_FIELDS = frozenset(
    {"body", "message", "requested_mode", "selected_documents"}
)


class UiConversationFormError(ValueError):
    """Erreur de formulaire UI nommant le champ refusé avant l'appel CV."""

    def __init__(self, field: str) -> None:
        if field not in _UI_CONVERSATION_FORM_FIELDS:
            raise ValueError("champ de formulaire conversationnel invalide")
        self.field = field
        super().__init__(field)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Serveur UI dont la capacité et la durée de lecture sont bornées."""

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_class)
        self.socket_timeout_seconds = UI_SOCKET_TIMEOUT_SECONDS
        self._capacity = threading.BoundedSemaphore(UI_MAX_CONCURRENT_TRANSFERS)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        if not self._capacity.acquire(blocking=False):
            body = (
                "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>Service occupé</title></head><body><h1>Service occupé</h1>"
                "<p>UI_TRANSFER_CAPACITY_EXHAUSTED</p></body></html>"
            ).encode("utf-8")
            request.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/html; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii")
                + body
            )
            request.shutdown(socket.SHUT_WR)
            request.settimeout(0.25)
            try:
                while request.recv(4096):
                    pass
            except (TimeoutError, OSError):
                pass
            finally:
                self.close_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._capacity.release()


class _StdoutGatewayObservabilityCollector(InMemoryObservabilityCollector):
    """Collecteur runtime qui publie les observations gateway en JSON lines."""

    def record_gateway_observation(self, observation: GatewayObservation) -> None:
        previous_metric_count = len(self.metrics())
        super().record_gateway_observation(observation)
        emitted_metrics = self.metrics()[previous_metric_count:]
        payload = {
            "event_type": "llm_gateway_observation",
            "log": self.logs()[-1].to_mapping(),
            "metrics": [metric.to_mapping() for metric in emitted_metrics],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime technique local M-002.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve-http")
    serve_parser.add_argument("service_id")
    serve_parser.add_argument("port", type=int)
    serve_parser.add_argument("--config")

    worker_parser = subparsers.add_parser("run-worker")
    worker_parser.add_argument("service_id")
    worker_parser.add_argument("--config")
    worker_parser.add_argument("--worker-id")
    worker_parser.add_argument("--lease-seconds", type=int)
    worker_parser.add_argument("--poll-seconds", type=float)
    worker_parser.add_argument("--max-jobs", type=int)

    check_parser = subparsers.add_parser("check-worker")
    check_parser.add_argument("service_id")

    args = parser.parse_args()
    if args.command == "serve-http" and args.service_id == "orchestrator-api":
        print("ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN: utiliser uv run api.", file=sys.stderr)
        return 2
    try:
        if args.command == "serve-http":
            _serve_http(
                service_id=args.service_id,
                port=args.port,
                application_configuration=_load_runtime_application_configuration(args.config),
                ui_execution_context=("compose" if args.service_id == "ui" else None),
            )
        if args.command == "run-worker":
            _run_worker(
                service_id=args.service_id,
                application_configuration=_load_runtime_application_configuration(args.config),
                owner_id=args.worker_id,
                lease_seconds=args.lease_seconds,
                poll_seconds=args.poll_seconds,
                max_jobs=args.max_jobs,
            )
            return 0
        if args.command == "check-worker":
            _require_worker_service(args.service_id)
            return 0
        raise ValueError(f"Commande runtime locale inconnue: {args.command}")
    except ApplicationConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _load_runtime_application_configuration(config_path: str | None) -> ApplicationConfiguration:
    if config_path is None:
        raise ApplicationConfigurationError(CONFIG_FILE_REQUIRED, "chemin --config absent")
    return load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )


def _serve_http(
    *,
    service_id: str,
    port: int,
    application_configuration: ApplicationConfiguration,
    ui_execution_context: str | None,
) -> None:
    if service_id == "orchestrator-api":
        raise ValueError("ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65_535:
        raise ValueError(f"Port HTTP local invalide pour {service_id}: {port}")
    expected_port = _configured_http_port(service_id, application_configuration)
    if service_id != "ui" and port != expected_port:
        raise ValueError(f"Port HTTP local invalide pour {service_id}: {port}")
    bind_host = _configured_http_bind_host(service_id, application_configuration)

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(self.server.socket_timeout_seconds)

        def do_GET(self) -> None:
            parsed_url = urlsplit(self.path)
            request_path = parsed_url.path
            if service_id == "ui" and request_path != "/health":
                api_client = _build_ui_document_api_client(
                    application_configuration=application_configuration,
                    execution_context=_require_ui_execution_context(ui_execution_context),
                )
                pdf_match = _UI_PDF_CONTENT_PATH_PATTERN.fullmatch(request_path)
                if pdf_match is not None:
                    try:
                        response = api_client.read_original_pdf_stream(pdf_match.group("document_id"))
                    except UiDocumentApiUnavailableError:
                        _write_json_response(
                            self,
                            status_code=503,
                            body={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                        )
                        return
                    if isinstance(response, UiDocumentApiStreamResponse):
                        _write_stream_response(
                            self,
                            status_code=response.status_code,
                            content_type=response.content_type,
                            content_length=response.content_length,
                            content_chunks=response.content_chunks,
                            close=response.close,
                        )
                    else:
                        _write_text_response(
                            self,
                            status_code=response.status_code,
                            content_type="text/html; charset=utf-8",
                            body=render_document_inspection(
                                title="PDF original",
                                response=_json_response_for_ui_error(response),
                                action_progress=None,
                            ),
                        )
                    return
                inspection_match = _UI_DOCUMENT_INSPECTION_PATH_PATTERN.fullmatch(request_path)
                if inspection_match is not None:
                    document_id = inspection_match.group("document_id")
                    step = inspection_match.group("step")
                    try:
                        response = _read_ui_document_step(
                            api_client=api_client,
                            document_id=document_id,
                            step=step,
                        )
                        action_progress = (
                            api_client.read_document_action_progress(
                                document_id,
                                "DIAGNOSE"
                                if step == "diagnostic"
                                else (
                                    "CONVERT_DOCUMENT"
                                    if step == "conversion"
                                    else "PROJECT_DOCUMENT"
                                ),
                            )
                            if step in {"diagnostic", "conversion", "projection"}
                            and response.status_code < 400
                            else None
                        )
                    except UiDocumentApiUnavailableError:
                        response = UiDocumentJsonResponse(
                            status_code=503,
                            payload={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                        )
                        action_progress = None
                    _write_text_response(
                        self,
                        status_code=response.status_code,
                        content_type="text/html; charset=utf-8",
                        body=render_document_inspection(
                            title=step.capitalize(),
                            response=response,
                            action_progress=action_progress,
                        ),
                    )
                    return
                if request_path == "/ui/chat":
                    state = _build_ui_corpus_state(
                        application_configuration=application_configuration,
                        api_client=api_client,
                    )
                    _write_text_response(
                        self,
                        status_code=200,
                        content_type="text/html; charset=utf-8",
                        body=render_new_conversation_page(
                            selectable_documents=_selectable_documents_for_conversation(state),
                        ),
                    )
                    return
                conversation_match = _UI_CONVERSATION_PATH_PATTERN.fullmatch(request_path)
                if conversation_match is not None:
                    state = _build_ui_corpus_state(
                        application_configuration=application_configuration,
                        api_client=api_client,
                    )
                    conversation_client = _build_ui_conversation_api_client(
                        application_configuration=application_configuration,
                        execution_context=_require_ui_execution_context(ui_execution_context),
                    )
                    try:
                        conversation = conversation_client.read_conversation(
                            conversation_match.group("conversation_id")
                        )
                        turns = conversation_client.read_turns(
                            conversation_match.group("conversation_id")
                        )
                        body = render_conversation_page(
                            conversation=conversation,
                            turns=turns,
                            selectable_documents=_selectable_documents_for_conversation(state),
                        )
                        status_code = 200
                    except UiConversationApiPublicError as exc:
                        body = render_new_conversation_page(
                            selectable_documents=_selectable_documents_for_conversation(state),
                            error_code=str(exc),
                        )
                        status_code = exc.status_code
                    except UiConversationApiUnavailableError:
                        body = render_new_conversation_page(
                            selectable_documents=_selectable_documents_for_conversation(state),
                            error_code=ORCHESTRATOR_API_UNAVAILABLE,
                        )
                        status_code = 503
                    _write_text_response(
                        self,
                        status_code=status_code,
                        content_type="text/html; charset=utf-8",
                        body=body,
                    )
                    return
                status_code, content_type, response_body = ui_get_response(
                    path=request_path,
                    state=_build_ui_corpus_state(
                        application_configuration=application_configuration,
                        api_client=api_client,
                        cursor=_ui_cursor(parsed_url.query),
                        registration_notice=_ui_registration_notice(parsed_url.query),
                    ),
                )
                _write_text_response(
                    self,
                    status_code=status_code,
                    content_type=content_type,
                    body=response_body,
                )
                return
            if request_path not in {"/", "/health"}:
                self.send_response(404)
                self.end_headers()
                return
            if service_id == "llm-gateway" and request_path == "/health":
                status_code, response_body = _llm_gateway_readiness_response(
                    application_configuration=application_configuration,
                )
                _write_json_response(self, status_code=status_code, body=response_body)
                return
            _write_json_response(
                self,
                status_code=200,
                body={"service": service_id, "status": "healthy"},
            )

        def do_POST(self) -> None:
            if service_id == "ui":
                origin_refusal = _validate_same_origin_request(self)
                if origin_refusal is not None:
                    _write_text_response(
                        self,
                        status_code=403,
                        content_type="text/html; charset=utf-8",
                        body=_accessible_ui_error_page("UI_ORIGIN_FORBIDDEN"),
                    )
                    return
                content_length = _request_content_length(self)
                if content_length is None:
                    _write_text_response(self, status_code=400, content_type="text/html; charset=utf-8", body=_accessible_ui_error_page("HTTP_REQUEST_INVALID"))
                    return
                if content_length > MAX_REQUEST_BODY_BYTES:
                    _write_text_response(self, status_code=413, content_type="text/html; charset=utf-8", body=_accessible_ui_error_page("HTTP_REQUEST_TOO_LARGE"))
                    return
                content_type = self.headers.get("Content-Type")
                if content_type is None:
                    _write_text_response(self, status_code=400, content_type="text/html; charset=utf-8", body=_accessible_ui_error_page("HTTP_REQUEST_INVALID"))
                    return
                try:
                    message_match = _UI_CONVERSATION_MESSAGE_PATH_PATTERN.fullmatch(self.path)
                    if self.path == "/ui/conversations" or message_match is not None:
                        if content_type.split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                            raise ValueError("format conversation UI invalide")
                        form = parse_qs(
                            self.rfile.read(content_length).decode("utf-8"),
                            strict_parsing=True,
                        )
                        conversation_client = _build_ui_conversation_api_client(
                            application_configuration=application_configuration,
                            execution_context=_require_ui_execution_context(ui_execution_context),
                        )
                        if self.path == "/ui/conversations":
                            response = _create_ui_conversation_from_form(
                                conversation_client=conversation_client,
                                form=form,
                            )
                            _write_redirect_response(
                                self,
                                location=f"/ui/conversations/{response.conversation_id}",
                            )
                            return
                        assert message_match is not None
                        try:
                            _post_ui_conversation_message_from_form(
                                conversation_client=conversation_client,
                                conversation_id=message_match.group("conversation_id"),
                                form=form,
                            )
                        except UiConversationFormError as exc:
                            document_client = _build_ui_document_api_client(
                                application_configuration=application_configuration,
                                execution_context=_require_ui_execution_context(ui_execution_context),
                            )
                            state = _build_ui_corpus_state(
                                application_configuration=application_configuration,
                                api_client=document_client,
                            )
                            conversation_id = message_match.group("conversation_id")
                            conversation = conversation_client.read_conversation(conversation_id)
                            turns = conversation_client.read_turns(conversation_id)
                            message_values = form.get("message", [])
                            draft_message = (
                                message_values[0]
                                if len(message_values) == 1
                                and message_values[0].strip() != ""
                                and message_values[0] == message_values[0].strip()
                                else None
                            )
                            _write_text_response(
                                self,
                                status_code=400,
                                content_type="text/html; charset=utf-8",
                                body=render_conversation_page(
                                    conversation=conversation,
                                    turns=turns,
                                    selectable_documents=_selectable_documents_for_conversation(state),
                                    error_code="HTTP_REQUEST_INVALID",
                                    error_field=exc.field,
                                    draft_message=draft_message,
                                ),
                            )
                            return
                        _write_redirect_response(
                            self,
                            location=(
                                "/ui/conversations/"
                                f"{message_match.group('conversation_id')}"
                            ),
                        )
                        return
                    client = _build_ui_document_api_client(
                        application_configuration=application_configuration,
                        execution_context=_require_ui_execution_context(
                            ui_execution_context
                        ),
                    )
                    manual_review_match = _MANUAL_REVIEW_PATH_PATTERN.fullmatch(self.path)
                    if manual_review_match is not None:
                        raw_body = self.rfile.read(content_length)
                        if content_type.split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                            raise UiDocumentCommandForbiddenError("format revue manuelle UI invalide")
                        form = parse_qs(raw_body.decode("utf-8"), strict_parsing=True)
                        if any(len(values) != 1 for values in form.values()):
                            raise UiDocumentCommandForbiddenError("formulaire revue manuelle invalide")
                        decision_values = form.get("decision")
                        reviewer_values = form.get("reviewer_id")
                        reason_values = form.get("reason")
                        if decision_values is None or reviewer_values is None or reason_values is None:
                            raise UiDocumentCommandForbiddenError("formulaire revue manuelle incomplet")
                        decision = decision_values[0]
                        allowed_fields = {"decision", "reviewer_id", "reason"}
                        payload: dict[str, Any] = {
                            "decision": decision,
                            "reviewer_id": reviewer_values[0],
                            "reason": reason_values[0],
                        }
                        if decision != "REJECT_DOCUMENT":
                            page_values = form.get("page_number")
                            if page_values is None or not page_values[0].isdecimal():
                                raise UiDocumentCommandForbiddenError("page de revue manuelle invalide")
                            payload["page_number"] = int(page_values[0])
                            allowed_fields.add("page_number")
                        if decision == "ASSIGN_ROUTE":
                            route_values = form.get("route_name")
                            if route_values is None:
                                raise UiDocumentCommandForbiddenError("route de revue manuelle absente")
                            payload["route_name"] = route_values[0]
                            allowed_fields.add("route_name")
                        if set(form) != allowed_fields:
                            raise UiDocumentCommandForbiddenError("champs de revue manuelle interdits")
                        response = client.forward_document_command(
                            path=self.path,
                            body=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                            content_type="application/json",
                        )
                    elif _INDEX_PATH_PATTERN.fullmatch(self.path) is not None:
                        raw_body = self.rfile.read(content_length)
                        if content_type.split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                            raise UiDocumentCommandForbiddenError("format projection UI invalide")
                        form = parse_qs(raw_body.decode("utf-8"), strict_parsing=True)
                        required_profile_fields = {
                            "projection_profile_id",
                            "chunking_profile",
                            "embedding_model",
                            "sparse_profile",
                            "index_schema",
                        }
                        if set(form) != required_profile_fields or any(len(form[field]) != 1 for field in required_profile_fields):
                            raise UiDocumentCommandForbiddenError("profil projection UI invalide")
                        response = client.forward_document_command(
                            path=self.path,
                            body=json.dumps(
                                {field: form[field][0] for field in sorted(required_profile_fields)},
                                separators=(",", ":"),
                            ).encode("utf-8"),
                            content_type="application/json",
                        )
                    elif content_length == 0:
                        response = client.forward_document_command(
                            path=self.path,
                            body=b"",
                            content_type=content_type,
                        )
                    else:
                        response = client.forward_document_command_stream(
                            path=self.path,
                            source=self.rfile,
                            content_length=content_length,
                            content_type=content_type,
                        )
                except (UiDocumentApiUnavailableError, UiConversationApiUnavailableError):
                    response = UiDocumentJsonResponse(
                        status_code=503,
                        payload={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                    )
                except UiDocumentCommandForbiddenError:
                    response = UiDocumentJsonResponse(
                        status_code=404,
                        payload={"error_code": "UI_DOCUMENT_COMMAND_FORBIDDEN"},
                    )
                except UiConversationApiPublicError as exc:
                    _write_text_response(
                        self,
                        status_code=exc.status_code,
                        content_type="text/html; charset=utf-8",
                        body=_accessible_ui_error_page(str(exc)),
                    )
                    return
                except (UnicodeDecodeError, ValueError):
                    response = UiDocumentJsonResponse(
                        status_code=400,
                        payload={"error_code": "HTTP_REQUEST_INVALID", "field": "body"},
                    )
                diagnosis_match = _DIAGNOSE_PATH_PATTERN.fullmatch(self.path)
                if response.status_code < 400 and diagnosis_match is not None:
                    document_id = str(response.payload.get("document_id", ""))
                    _write_redirect_response(
                        self,
                        location=f"/ui/documents/{document_id}/diagnostic",
                    )
                elif response.status_code < 400 and _CONVERT_PATH_PATTERN.fullmatch(self.path):
                    document_id = str(response.payload.get("document_id", ""))
                    _write_redirect_response(
                        self,
                        location=f"/ui/documents/{document_id}/conversion",
                    )
                elif response.status_code < 400 and _MANUAL_REVIEW_PATH_PATTERN.fullmatch(self.path):
                    document_id = str(response.payload.get("document_id", ""))
                    _write_redirect_response(
                        self,
                        location=f"/ui/documents/{document_id}/diagnostic",
                    )
                elif response.status_code < 400 and _INDEX_PATH_PATTERN.fullmatch(self.path):
                    document_id = str(response.payload.get("document_id", ""))
                    _write_redirect_response(
                        self,
                        location=f"/ui/documents/{document_id}/projection",
                    )
                elif response.status_code < 400:
                    query = urlencode(
                        {
                            "document_id": str(response.payload.get("document_id", "")),
                            "duplicate": str(bool(response.payload.get("duplicate", False))).lower(),
                        }
                    )
                    _write_redirect_response(self, location=f"/ui/corpus-pdf?{query}")
                else:
                    _write_text_response(
                        self,
                        status_code=response.status_code,
                        content_type="text/html; charset=utf-8",
                        body=render_document_inspection(
                            title="Erreur documentaire",
                            response=response,
                            action_progress=None,
                        ),
                    )
                return
            body_result = _read_json_body(self)
            if body_result[0] != 200:
                _write_json_response(
                    self,
                    status_code=body_result[0],
                    body=body_result[1],
                )
                return
            status_code, response_body = _local_post_response(
                service_id=service_id,
                path=self.path,
                body=body_result[1],
                application_configuration=application_configuration,
            )
            _write_json_response(self, status_code=status_code, body=response_body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = BoundedThreadingHTTPServer((bind_host, port), Handler)
    server.serve_forever()


def serve_http_service(*, service_id: str, port: int, config_path: str) -> None:
    _serve_http(
        service_id=service_id,
        port=port,
        application_configuration=_load_runtime_application_configuration(config_path),
        ui_execution_context=("host" if service_id == "ui" else None),
    )


def _configured_http_port(service_id: str, application_configuration: ApplicationConfiguration) -> int:
    if service_id == "orchestrator-api":
        return application_configuration.services.api.port
    if service_id == "llm-gateway":
        return application_configuration.services.llm_gateway.port
    expected_port = HTTP_SERVICE_PORTS.get(service_id)
    if expected_port is None:
        raise ValueError(f"Service HTTP local inconnu: {service_id}")
    return expected_port


def _configured_http_bind_host(service_id: str, application_configuration: ApplicationConfiguration) -> str:
    if service_id == "orchestrator-api":
        return application_configuration.services.api.bind_host
    _configured_http_port(service_id, application_configuration)
    return application_configuration.deployment.hosts.docker_local.container_listen_host


def _llm_gateway_readiness_response(
    *,
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, Any]]:
    try:
        _build_gateway_configuration_from_application_configuration(application_configuration)
    except LLMGatewayContractError as exc:
        return 503, {
            "service": "llm-gateway",
            "status": "not_ready",
            "error_code": exc.code,
            "message": exc.message,
            "configuration_hash": application_configuration.configuration_hash,
        }
    return 200, {
        "service": "llm-gateway",
        "status": "ready",
        "environment": application_configuration.application.environment,
        "deployment_id": application_configuration.application.deployment_id,
        "configuration_hash": application_configuration.configuration_hash,
    }


def _write_json_response(handler: BaseHTTPRequestHandler, *, status_code: int, body: dict[str, Any]) -> None:
    payload = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _write_text_response(
    handler: BaseHTTPRequestHandler,
    *,
    status_code: int,
    content_type: str,
    body: str,
) -> None:
    payload = body.encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _write_binary_response(
    handler: BaseHTTPRequestHandler,
    *,
    status_code: int,
    content_type: str,
    body: bytes,
) -> None:
    handler.send_response(status_code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _write_stream_response(
    handler: BaseHTTPRequestHandler,
    *,
    status_code: int,
    content_type: str,
    content_length: int,
    content_chunks: Any,
    close: Any,
) -> None:
    handler.send_response(status_code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(content_length))
    handler.end_headers()
    try:
        for chunk in content_chunks:
            handler.wfile.write(chunk)
            handler.wfile.flush()
    finally:
        close()


def _write_redirect_response(
    handler: BaseHTTPRequestHandler,
    *,
    location: str,
) -> None:
    if not isinstance(location, str) or not location.startswith("/"):
        raise ValueError("location de redirection UI invalide")
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _json_response_for_ui_error(response: Any) -> UiDocumentJsonResponse:
    status_code = getattr(response, "status_code", None)
    body = getattr(response, "body", None)
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("statut erreur PDF invalide")
    if not isinstance(body, bytes):
        raise ValueError("corps erreur PDF invalide")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("erreur PDF publique non JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("erreur PDF publique non objet")
    return UiDocumentJsonResponse(status_code=status_code, payload=payload)


def _runtime_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _read_json_body(handler: BaseHTTPRequestHandler) -> tuple[int, dict[str, Any]]:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    try:
        content_length = int(raw_length)
    except ValueError:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    if content_length < 0:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    if content_length == 0:
        return 200, {}
    raw_body = handler.rfile.read(content_length)
    try:
        parsed_body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}
    if not isinstance(parsed_body, dict):
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}
    return 200, parsed_body


def _request_content_length(handler: BaseHTTPRequestHandler) -> int | None:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None or not raw_length.isdecimal():
        return None
    return int(raw_length)


def _validate_same_origin_request(handler: BaseHTTPRequestHandler) -> str | None:
    origin = handler.headers.get("Origin")
    host = handler.headers.get("Host")
    if origin is None or host is None:
        return "UI_ORIGIN_FORBIDDEN"
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or parsed.netloc != host:
        return "UI_ORIGIN_FORBIDDEN"
    fetch_site = handler.headers.get("Sec-Fetch-Site")
    if fetch_site is not None and fetch_site != "same-origin":
        return "UI_ORIGIN_FORBIDDEN"
    return None


def _accessible_ui_error_page(error_code: str) -> str:
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Erreur de transfert</title></head><body><main role="alert">'
        f'<h1>Action impossible</h1><p><code>{error_code}</code></p>'
        '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p></main></body></html>'
    )


def _ui_cursor(query: str) -> str | None:
    if query == "":
        return None
    values = parse_qs(query, strict_parsing=True)
    unexpected = set(values) - {"cursor", "document_id", "duplicate"}
    if unexpected:
        raise ValueError("pagination UI invalide")
    cursors = values.get("cursor", [])
    if len(cursors) > 1:
        raise ValueError("pagination UI invalide")
    return None if len(cursors) == 0 else cursors[0]


def _ui_registration_notice(query: str) -> dict[str, Any] | None:
    if query == "":
        return None
    values = parse_qs(query, strict_parsing=True)
    identifiers = values.get("document_id", [])
    duplicates = values.get("duplicate", [])
    if len(identifiers) == 0 and len(duplicates) == 0:
        return None
    if len(identifiers) != 1 or len(duplicates) != 1 or duplicates[0] not in ("true", "false"):
        raise ValueError("confirmation d'enregistrement UI invalide")
    return {"document_id": identifiers[0], "duplicate": duplicates[0] == "true"}


def _build_ui_corpus_state(
    *,
    application_configuration: ApplicationConfiguration,
    api_client: UiDocumentApiClient,
    cursor: str | None = None,
    registration_notice: dict[str, Any] | None = None,
) -> CorpusPdfScreenState:
    _required_application_configuration(application_configuration)
    if not isinstance(api_client, UiDocumentApiClient):
        raise TypeError("client API documentaire UI requis")
    try:
        return api_client.build_corpus_state(
            active_selected_document_ids=(),
            cursor=cursor,
            registration_notice=registration_notice,
        )
    except UiDocumentApiPublicError as exc:
        return build_unavailable_corpus_pdf_state(public_error=exc.response.payload)
    except UiDocumentApiUnavailableError:
        return build_unavailable_corpus_pdf_state(
            public_error={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
        )


def _build_ui_document_api_client(
    *,
    application_configuration: ApplicationConfiguration,
    execution_context: str,
) -> UiDocumentApiClient:
    configuration = _required_application_configuration(application_configuration)
    return UiDocumentApiClient(
        transport=UrllibUiDocumentApiTransport(
            orchestrator_origin=build_ui_orchestrator_origin(
                configuration,
                execution_context=execution_context,
            ),
            timeout_seconds=min(configuration.runtime.timeouts.request_seconds, UI_SOCKET_TIMEOUT_SECONDS),
            token_path=configuration.security.secrets.local_api_token_path,
        )
    )


def build_ui_orchestrator_origin(
    application_configuration: ApplicationConfiguration,
    *,
    execution_context: str,
) -> str:
    """Résout explicitement l'origine UI selon le runtime hôte ou Compose."""

    configuration = _required_application_configuration(application_configuration)
    if execution_context == "host":
        host = configuration.deployment.hosts.docker_local.bind_host
    elif execution_context == "compose":
        host = "orchestrator-api"
    else:
        raise ValueError("contexte d'exécution UI invalide")
    if not isinstance(host, str) or host.strip() == "" or host != host.strip():
        raise ValueError("hôte orchestrateur UI invalide")
    if host == "0.0.0.0":
        raise ValueError("hôte orchestrateur UI non adressable")
    return f"http://{host}:{configuration.services.api.port}"


def _require_ui_execution_context(value: str | None) -> str:
    if value not in ("host", "compose"):
        raise ValueError("contexte d'exécution UI requis")
    return value


def _read_ui_document_step(
    *,
    api_client: UiDocumentApiClient,
    document_id: str,
    step: str,
) -> UiDocumentJsonResponse:
    if step == "diagnostic":
        return api_client.read_diagnostic(document_id)
    if step == "conversion":
        return api_client.read_conversion(document_id)
    if step == "projection":
        return api_client.read_projection(document_id)
    raise ValueError("étape documentaire UI inconnue")


def _local_post_response(
    *,
    service_id: str,
    path: str,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration | None = None,
) -> tuple[int, dict[str, Any]]:
    if service_id == "llm-gateway":
        return _llm_gateway_post_response(
            path=path,
            body=body,
            application_configuration=_required_application_configuration(application_configuration),
        )
    if service_id != "orchestrator-api":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}
    return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}


def _required_application_configuration(
    application_configuration: ApplicationConfiguration | None,
) -> ApplicationConfiguration:
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise LLMGatewayContractError(CONFIG_FILE_REQUIRED, "Configuration applicative requise.")
    return application_configuration


def _llm_gateway_post_response(
    *,
    path: str,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, Any]]:
    if path != "/v1/infer":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}

    try:
        gateway = _get_local_language_model_gateway(application_configuration=application_configuration)
    except LLMGatewayContractError as exc:
        return 503, {"error_code": exc.code, "message": exc.message}
    try:
        result = gateway.infer(_build_inference_request(body))
    except LLMGatewayContractError as exc:
        return 400, {"error_code": exc.code, "message": exc.message}
    except LLMGatewayInferenceError as exc:
        return 502, {
            "error_code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
            "publishable": exc.publishable,
        }

    return 200, {
        "structured_output": dict(result.structured_output),
        "provenance": {
            "model_id": result.provenance.model_id,
            "model_revision": result.provenance.model_revision,
            "runtime_version": result.provenance.runtime_version,
            "prompt_id": result.provenance.prompt_id,
            "prompt_version": result.provenance.prompt_version,
            "schema_version": result.provenance.schema_version,
            "input_hash": result.provenance.input_hash,
            "output_hash": result.provenance.output_hash,
            "started_at": result.provenance.started_at,
            "completed_at": result.provenance.completed_at,
        },
        "raw_response_id": result.raw_response_id,
    }


def _get_local_language_model_gateway(
    *,
    application_configuration: ApplicationConfiguration,
) -> OpenAICompatibleLocalLanguageModelGateway:
    global _LLM_GATEWAY_INSTANCE
    global _LLM_GATEWAY_CONFIGURATION_HASH
    with _LLM_GATEWAY_LOCK:
        if (
            _LLM_GATEWAY_INSTANCE is None
            or _LLM_GATEWAY_CONFIGURATION_HASH != application_configuration.configuration_hash
        ):
            _LLM_GATEWAY_INSTANCE = _build_local_language_model_gateway(
                application_configuration=application_configuration,
            )
            _LLM_GATEWAY_CONFIGURATION_HASH = application_configuration.configuration_hash
        return _LLM_GATEWAY_INSTANCE


def _build_gateway_configuration_from_application_configuration(
    application_configuration: ApplicationConfiguration,
) -> GatewayConfiguration:
    gateway_service = application_configuration.services.llm_gateway
    llm_model = application_configuration.models.llm
    security = application_configuration.security

    api_key = None
    if gateway_service.auth_mode == "api_key_file":
        api_key_path = security.secrets.llm_gateway_api_key_path
        try:
            api_key = Path(api_key_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_API_KEY_FILE_UNREADABLE",
                f"Fichier de clé API Spark illisible: {api_key_path}",
            ) from exc
    tls_ca_bundle_path = None
    if gateway_service.tls_mode == "ca_bundle":
        tls_ca_bundle_path = security.secrets.tls_ca_certificate_path
        if not Path(tls_ca_bundle_path).is_file():
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_CA_FILE_UNREADABLE",
                f"Bundle CA Spark illisible: {tls_ca_bundle_path}",
            )

    return GatewayConfiguration(
        base_url=gateway_service.spark_endpoint_url,
        served_model=llm_model.served_model_name,
        model_revision=llm_model.model_revision,
        runtime_version=llm_model.runtime_version,
        configuration_hash=application_configuration.configuration_hash,
        auth_mode=gateway_service.auth_mode,
        api_key=api_key,
        tls_mode=gateway_service.tls_mode,
        tls_ca_bundle_path=tls_ca_bundle_path,
        timeout_seconds=gateway_service.timeout_seconds,
        allowed_spark_hosts=(
            application_configuration.deployment.hosts.spark_inference.dns_name,
            *application_configuration.deployment.hosts.spark_inference.endpoint_hosts,
        ),
    )


def _build_local_language_model_gateway(
    *,
    application_configuration: ApplicationConfiguration,
) -> OpenAICompatibleLocalLanguageModelGateway:
    gateway_service = application_configuration.services.llm_gateway
    configuration = _build_gateway_configuration_from_application_configuration(application_configuration)
    collector = _StdoutGatewayObservabilityCollector()
    return OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration,
        transport=UrllibOpenAICompatibleTransport(),
        retry_policy=GatewayRetryPolicy(
            max_retries_before_first_token=gateway_service.retry_before_first_token,
        ),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(
                failure_threshold=gateway_service.circuit_breaker_failure_threshold,
                open_seconds=gateway_service.circuit_breaker_reset_seconds,
            ),
            clock=SystemGatewayClock(),
        ),
        failure_metric_recorder=GatewayFailureMetricRecorder(observability_collector=collector),
    )


def _build_inference_request(body: dict[str, Any]) -> InferenceRequest:
    messages_payload = _required_body_sequence(body, "messages")
    messages = []
    for item in messages_payload:
        if not isinstance(item, dict):
            raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Message d'inference non objet.")
        role = _required_body_text(item, "role")
        content = item.get("content")
        if isinstance(content, str):
            messages.append(InferenceMessage(role=role, content=content))
            continue
        if isinstance(content, list):
            messages.append(_build_inference_image_message(role=role, content=content))
            continue
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Contenu de message invalide.")

    return InferenceRequest(
        messages=tuple(messages),
        output_schema=_required_body_mapping(body, "output_schema"),
        schema_name=_required_body_text(body, "schema_name"),
        schema_version=_required_body_text(body, "schema_version"),
        trace_id=_required_body_text(body, "trace_id"),
        request_id=_required_body_text(body, "request_id"),
        idempotency_key=_required_body_text(body, "idempotency_key"),
        prompt_id=_required_body_text(body, "prompt_id"),
        prompt_version=_required_body_text(body, "prompt_version"),
        sampling_parameters=_required_body_mapping(body, "sampling_parameters"),
    )


def _build_ui_conversation_api_client(
    *,
    application_configuration: ApplicationConfiguration,
    execution_context: str,
) -> UiConversationApiClient:
    configuration = _required_application_configuration(application_configuration)
    return UiConversationApiClient(
        transport=UrllibUiDocumentApiTransport(
            orchestrator_origin=build_ui_orchestrator_origin(
                configuration,
                execution_context=execution_context,
            ),
            timeout_seconds=min(configuration.runtime.timeouts.request_seconds, UI_SOCKET_TIMEOUT_SECONDS),
            token_path=configuration.security.secrets.local_api_token_path,
        )
    )


def _selectable_documents_for_conversation(
    state: CorpusPdfScreenState,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(state, CorpusPdfScreenState):
        raise TypeError("état corpus UI invalide")
    selectable: list[tuple[str, str]] = []
    for document in state.documents:
        if not document.selectable_for_conversation:
            continue
        if document.title is None:
            raise ValueError("titre sélectionnable absent")
        selectable.append((document.document_id, document.title))
    return tuple(selectable)


def _create_ui_conversation_from_form(
    *,
    conversation_client: UiConversationApiClient,
    form: dict[str, list[str]],
):
    required = {"title", "allowed_universe", "language", "detail_level", "format", "citation_style"}
    if set(form) != required or any(len(form[field]) != 1 for field in required):
        raise ValueError("formulaire de conversation invalide")
    return conversation_client.create_conversation(
        title=form["title"][0],
        default_mandate={
            "allowed_universe": [form["allowed_universe"][0]],
            "language": form["language"][0],
            "detail_level": form["detail_level"][0],
        },
        presentation_preferences={
            "format": form["format"][0],
            "citation_style": form["citation_style"][0],
        },
        occurred_at=_ui_now(),
    )


def _post_ui_conversation_message_from_form(
    *,
    conversation_client: UiConversationApiClient,
    conversation_id: str,
    form: dict[str, list[str]],
):
    required = {"message", "requested_mode", "selected_documents"}
    if not set(form).issubset(required):
        raise UiConversationFormError("body")
    if "message" not in form or len(form["message"]) != 1:
        raise UiConversationFormError("message")
    message = form["message"][0]
    if message.strip() == "" or message != message.strip():
        raise UiConversationFormError("message")
    if "requested_mode" not in form or len(form["requested_mode"]) != 1:
        raise UiConversationFormError("requested_mode")
    if form["requested_mode"][0] != "CHAT_DOCUMENTAIRE":
        raise UiConversationFormError("requested_mode")
    if "selected_documents" not in form:
        raise UiConversationFormError("selected_documents")
    selected_documents = tuple(form["selected_documents"])
    if len(selected_documents) == 0 or len(selected_documents) != len(set(selected_documents)):
        raise UiConversationFormError("selected_documents")
    return conversation_client.send_message(
        conversation_id=conversation_id,
        message=message,
        idempotency_key=f"ui-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        occurred_at=_ui_now(),
        requested_mode=form["requested_mode"][0],
        selected_documents=selected_documents,
    )


def _ui_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_inference_image_message(*, role: str, content: list[Any]) -> InferenceImageMessage:
    if len(content) < 2:
        raise LLMGatewayContractError(
            "HTTP_REQUEST_INVALID",
            "Un message multimodal exige un texte et au moins une image.",
        )
    text_part = content[0]
    if not isinstance(text_part, dict) or set(text_part) != {"type", "text"} or text_part["type"] != "text":
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Première partie multimodale invalide.")
    images = []
    for image_part in content[1:]:
        if (
            not isinstance(image_part, dict)
            or set(image_part) != {"type", "media_type", "data_base64", "sha256"}
            or image_part["type"] != "image"
        ):
            raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Partie image multimodale invalide.")
        images.append(
            InferenceImage(
                media_type=image_part["media_type"],
                data_base64=image_part["data_base64"],
                sha256=image_part["sha256"],
            )
        )
    return InferenceImageMessage(
        role=role,
        content=_required_body_text(text_part, "text"),
        images=tuple(images),
    )


def _required_body_text(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Champ requis absent: {name}")
    if value != value.strip():
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Champ non normalise: {name}")
    return value


def _required_body_mapping(body: dict[str, Any], name: str) -> dict[str, Any]:
    value = body.get(name)
    if not isinstance(value, dict) or len(value) == 0:
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Objet requis absent: {name}")
    return value


def _required_body_sequence(body: dict[str, Any], name: str) -> list[Any]:
    value = body.get(name)
    if not isinstance(value, list) or len(value) == 0:
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Liste requise absente: {name}")
    return value


def _run_worker(
    *,
    service_id: str,
    application_configuration: ApplicationConfiguration,
    owner_id: str | None,
    lease_seconds: int | None,
    poll_seconds: float | None,
    max_jobs: int | None,
) -> None:
    _required_application_configuration(application_configuration)
    _require_worker_service(service_id)
    if service_id == "worker-documents":
        raise RuntimeError("DOCUMENT_WORKER_COMMAND_REQUIRED")
    if owner_id != service_id:
        raise ValueError("WORKER_IDENTITY_INVALID")
    if lease_seconds is not None or poll_seconds is not None or max_jobs is not None:
        raise ValueError("WORKER_ARGUMENTS_UNSUPPORTED")
    build_configured_datastore_preflight(
        application_configuration,
        include_postgres=True,
        include_qdrant=False,
        file_root_names=(),
    ).run(initialize_if_empty=False)
    binding = build_worker_environment_binding(
        application_configuration,
        worker_id=service_id,
    )
    print(
        json.dumps(binding.health_snapshot().to_mapping(), sort_keys=True),
        flush=True,
    )
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
