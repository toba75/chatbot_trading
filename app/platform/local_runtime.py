"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.contracts.identity import DomainIdentifier
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
from app.platform.observability import InMemoryObservabilityCollector


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
_M005_INDEX_PATH_PATTERN = re.compile(r"^/v1/documents/([^/]+)/index$")
_LLM_GATEWAY_LOCK = threading.Lock()
_LLM_GATEWAY_INSTANCE: OpenAICompatibleLocalLanguageModelGateway | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime technique local M-002.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve-http")
    serve_parser.add_argument("service_id")
    serve_parser.add_argument("port", type=int)

    worker_parser = subparsers.add_parser("run-worker")
    worker_parser.add_argument("service_id")

    check_parser = subparsers.add_parser("check-worker")
    check_parser.add_argument("service_id")

    args = parser.parse_args()
    if args.command == "serve-http":
        _serve_http(service_id=args.service_id, port=args.port)
    if args.command == "run-worker":
        _run_worker(service_id=args.service_id)
    if args.command == "check-worker":
        _require_worker_service(args.service_id)
        return 0
    raise ValueError(f"Commande runtime locale inconnue: {args.command}")


def _serve_http(*, service_id: str, port: int) -> None:
    expected_port = HTTP_SERVICE_PORTS.get(service_id)
    if expected_port is None:
        raise ValueError(f"Service HTTP local inconnu: {service_id}")
    if port != expected_port:
        raise ValueError(f"Port HTTP local invalide pour {service_id}: {port}")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/", "/health"}:
                self.send_response(404)
                self.end_headers()
                return
            _write_json_response(
                self,
                status_code=200,
                body={"service": service_id, "status": "healthy"},
            )

        def do_POST(self) -> None:
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
            )
            _write_json_response(self, status_code=status_code, body=response_body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


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


def _local_post_response(*, service_id: str, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if service_id == "llm-gateway":
        return _llm_gateway_post_response(path=path, body=body, environment=os.environ)
    if service_id != "orchestrator-api":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}
    if path == "/v1/search":
        return 503, {
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/search",
        }
    index_match = _M005_INDEX_PATH_PATTERN.fullmatch(path)
    if index_match is not None:
        try:
            document_id = str(DomainIdentifier.parse_with_prefix(index_match.group(1), "DOC"))
        except ValueError:
            return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}
        return 503, {
            "document_id": document_id,
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/documents/{document_id}/index",
        }
    return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}


def _llm_gateway_post_response(
    *,
    path: str,
    body: dict[str, Any],
    environment: Any,
) -> tuple[int, dict[str, Any]]:
    if path != "/v1/infer":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}

    try:
        gateway = _get_local_language_model_gateway(environment=environment)
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


def _get_local_language_model_gateway(*, environment: Any) -> OpenAICompatibleLocalLanguageModelGateway:
    global _LLM_GATEWAY_INSTANCE
    with _LLM_GATEWAY_LOCK:
        if _LLM_GATEWAY_INSTANCE is None:
            _LLM_GATEWAY_INSTANCE = _build_local_language_model_gateway(environment=environment)
        return _LLM_GATEWAY_INSTANCE


def _build_local_language_model_gateway(*, environment: Any) -> OpenAICompatibleLocalLanguageModelGateway:
    auth_mode = _required_environment_text(environment, "GEMMA_AUTH_MODE")
    tls_mode = _required_environment_text(environment, "GEMMA_TLS_MODE")
    api_key = None
    if auth_mode == "api_key_file":
        api_key_path = _required_environment_text(environment, "GEMMA_API_KEY_FILE")
        api_key = Path(api_key_path).read_text(encoding="utf-8").strip()
    tls_ca_bundle_path = None
    if tls_mode == "ca_bundle":
        tls_ca_bundle_path = _required_environment_text(environment, "GEMMA_CA_BUNDLE")

    configuration = GatewayConfiguration(
        base_url=_required_environment_text(environment, "GEMMA_BASE_URL"),
        served_model=_required_environment_text(environment, "GEMMA_MODEL"),
        model_revision=_required_environment_text(environment, "GEMMA_MODEL_REVISION"),
        runtime_version=_required_environment_text(environment, "GEMMA_RUNTIME_VERSION"),
        auth_mode=auth_mode,
        api_key=api_key,
        tls_mode=tls_mode,
        tls_ca_bundle_path=tls_ca_bundle_path,
        timeout_seconds=_required_environment_positive_int(environment, "GEMMA_TIMEOUT_SECONDS"),
    )
    collector = InMemoryObservabilityCollector()
    return OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration,
        transport=UrllibOpenAICompatibleTransport(),
        retry_policy=GatewayRetryPolicy(
            max_retries_before_first_token=_required_environment_non_negative_int(
                environment,
                "GEMMA_RETRY_BEFORE_FIRST_TOKEN",
            )
        ),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(
                failure_threshold=_required_environment_positive_int(
                    environment,
                    "GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
                ),
                open_seconds=_required_environment_positive_int(
                    environment,
                    "GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS",
                ),
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


def _required_environment_text(environment: Any, name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError("LOCAL_RUNTIME_ENVIRONMENT_REQUIRED", f"Variable requise absente: {name}")
    if value != value.strip():
        raise LLMGatewayContractError("LOCAL_RUNTIME_ENVIRONMENT_REQUIRED", f"Variable non normalisee: {name}")
    return value


def _required_environment_positive_int(environment: Any, name: str) -> int:
    value = _required_environment_text(environment, name)
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise LLMGatewayContractError("LOCAL_RUNTIME_ENVIRONMENT_REQUIRED", f"Entier positif requis: {name}")
    return int(value)


def _required_environment_non_negative_int(environment: Any, name: str) -> int:
    value = _required_environment_text(environment, name)
    if not re.fullmatch(r"(0|[1-9][0-9]*)", value):
        raise LLMGatewayContractError("LOCAL_RUNTIME_ENVIRONMENT_REQUIRED", f"Entier positif ou nul requis: {name}")
    return int(value)


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


def _run_worker(*, service_id: str) -> None:
    _require_worker_service(service_id)
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
