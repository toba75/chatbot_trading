"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.platform.configuration import (
    ApplicationConfiguration,
    ApplicationConfigurationError,
    CONFIG_FILE_REQUIRED,
    load_application_configuration,
)
from app.platform.llm_gateway import (
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayConfiguration,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
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
_LLM_GATEWAY_LOCK = threading.Lock()
_LLM_GATEWAY_INSTANCE: OpenAICompatibleLocalLanguageModelGateway | None = None
_LLM_GATEWAY_CONFIGURATION_HASH: str | None = None


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
        def do_GET(self) -> None:
            if service_id == "ui" and self.path != "/health":
                api_client = _build_ui_document_api_client(
                    application_configuration=application_configuration,
                    execution_context=_require_ui_execution_context(ui_execution_context),
                )
                pdf_match = _UI_PDF_CONTENT_PATH_PATTERN.fullmatch(self.path)
                if pdf_match is not None:
                    try:
                        response = api_client.read_original_pdf(pdf_match.group("document_id"))
                    except UiDocumentApiUnavailableError:
                        _write_json_response(
                            self,
                            status_code=503,
                            body={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                        )
                        return
                    if response.status_code == 200:
                        _write_binary_response(
                            self,
                            status_code=response.status_code,
                            content_type=response.content_type,
                            body=response.body,
                        )
                    else:
                        _write_text_response(
                            self,
                            status_code=response.status_code,
                            content_type="text/html; charset=utf-8",
                            body=render_document_inspection(
                                title="PDF original",
                                response=_json_response_for_ui_error(response),
                            ),
                        )
                    return
                inspection_match = _UI_DOCUMENT_INSPECTION_PATH_PATTERN.fullmatch(self.path)
                if inspection_match is not None:
                    document_id = inspection_match.group("document_id")
                    step = inspection_match.group("step")
                    try:
                        response = _read_ui_document_step(
                            api_client=api_client,
                            document_id=document_id,
                            step=step,
                        )
                    except UiDocumentApiUnavailableError:
                        response = UiDocumentJsonResponse(
                            status_code=503,
                            payload={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                        )
                    _write_text_response(
                        self,
                        status_code=response.status_code,
                        content_type="text/html; charset=utf-8",
                        body=render_document_inspection(
                            title=step.capitalize(),
                            response=response,
                        ),
                    )
                    return
                status_code, content_type, response_body = ui_get_response(
                    path=self.path,
                    state=_build_ui_corpus_state(
                        application_configuration=application_configuration,
                        api_client=api_client,
                    ),
                )
                _write_text_response(
                    self,
                    status_code=status_code,
                    content_type=content_type,
                    body=response_body,
                )
                return
            if self.path not in {"/", "/health"}:
                self.send_response(404)
                self.end_headers()
                return
            if service_id == "llm-gateway" and self.path == "/health":
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
                body_result = _read_raw_body(self)
                if body_result[0] != 200:
                    _write_json_response(self, status_code=body_result[0], body=body_result[1])
                    return
                raw_body = body_result[1]
                if not isinstance(raw_body, bytes):
                    raise TypeError("body UI brut invalide")
                content_type = self.headers.get("Content-Type")
                if content_type is None:
                    _write_json_response(
                        self,
                        status_code=400,
                        body={"error_code": "HTTP_REQUEST_INVALID", "field": "content_type"},
                    )
                    return
                try:
                    response = _build_ui_document_api_client(
                        application_configuration=application_configuration,
                        execution_context=_require_ui_execution_context(
                            ui_execution_context
                        ),
                    ).forward_document_command(
                        path=self.path,
                        body=raw_body,
                        content_type=content_type,
                    )
                except UiDocumentApiUnavailableError:
                    response = UiDocumentJsonResponse(
                        status_code=503,
                        payload={"error_code": ORCHESTRATOR_API_UNAVAILABLE},
                    )
                except UiDocumentCommandForbiddenError:
                    response = UiDocumentJsonResponse(
                        status_code=404,
                        payload={"error_code": "UI_DOCUMENT_COMMAND_FORBIDDEN"},
                    )
                if response.status_code < 400:
                    _write_redirect_response(self, location="/ui/corpus-pdf")
                else:
                    _write_text_response(
                        self,
                        status_code=response.status_code,
                        content_type="text/html; charset=utf-8",
                        body=render_document_inspection(
                            title="Erreur documentaire",
                            response=response,
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

    server = ThreadingHTTPServer((bind_host, port), Handler)
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


def _read_raw_body(
    handler: BaseHTTPRequestHandler,
) -> tuple[int, bytes | dict[str, Any]]:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None or not raw_length.isdecimal():
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    content_length = int(raw_length)
    if content_length > MAX_REQUEST_BODY_BYTES:
        return 413, {
            "error_code": "HTTP_REQUEST_TOO_LARGE",
            "max_body_bytes": MAX_REQUEST_BODY_BYTES,
        }
    return 200, handler.rfile.read(content_length)


def _build_ui_corpus_state(
    *,
    application_configuration: ApplicationConfiguration,
    api_client: UiDocumentApiClient,
) -> CorpusPdfScreenState:
    _required_application_configuration(application_configuration)
    if not isinstance(api_client, UiDocumentApiClient):
        raise TypeError("client API documentaire UI requis")
    try:
        return api_client.build_corpus_state(active_selected_document_ids=())
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
            timeout_seconds=configuration.runtime.timeouts.request_seconds,
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
        messages.append(
            InferenceMessage(
                role=_required_body_text(item, "role"),
                content=_required_body_text(item, "content"),
            )
        )

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
    del owner_id, lease_seconds, poll_seconds, max_jobs
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
