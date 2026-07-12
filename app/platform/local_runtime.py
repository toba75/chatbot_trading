"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.contracts.identity import DomainIdentifier
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
from app.platform.ui_corpus import (
    CorpusPdfScreenState,
    ORCHESTRATOR_API_CONTRACT_NOT_WIRED,
    UI_FUNCTION_NOT_OPERATIONAL,
    build_unconnected_corpus_pdf_state,
    ui_get_response,
    ui_unavailable_pdf_content_response,
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
_UI_DOCUMENT_COMMAND_PATH_PATTERN = re.compile(
    r"^/v1/documents(?:/[^/]+/(?:diagnose|convert|index))?$"
)
_LLM_GATEWAY_LOCK = threading.Lock()
_LLM_GATEWAY_INSTANCE: OpenAICompatibleLocalLanguageModelGateway | None = None
_LLM_GATEWAY_CONFIGURATION_HASH: str | None = None
_M013_REALITY_PATH_SEGMENTS = ("docker-local", "orchestrator-api", "llm-gateway", "vllm-spark")
_M013_PRODUCT_CHAT_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
_M013_LLM_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task_name": {"type": "string"},
        "evaluation_marker": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["task_name", "evaluation_marker", "answer"],
    "additionalProperties": False,
}
_M013_REQUIRED_LLM_TASKS = (
    "json_valide",
    "extraction_atomique",
    "conservation_negations",
    "exactitude_nombres",
    "conditions_application",
    "limites",
    "entailment",
    "contradiction",
    "synthese_fr_en",
    "tool_calling",
    "citations",
)
_M013_REQUIRED_LLM_TECHNICAL_METRICS = (
    "llm_gateway_latency_ms",
    "llm_network_latency_ms",
    "llm_vllm_queue_time_ms",
    "llm_time_to_first_token_ms",
    "llm_tokens_per_second",
    "llm_error_rate",
    "llm_retry_before_first_token_total",
    "llm_structured_output_stability_rate",
    "llm_spark_restart_recovery_rate",
)


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

    check_parser = subparsers.add_parser("check-worker")
    check_parser.add_argument("service_id")

    args = parser.parse_args()
    try:
        if args.command == "serve-http":
            _serve_http(
                service_id=args.service_id,
                port=args.port,
                application_configuration=_load_runtime_application_configuration(args.config),
            )
        if args.command == "run-worker":
            _run_worker(
                service_id=args.service_id,
                application_configuration=_load_runtime_application_configuration(args.config),
            )
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


def _serve_http(*, service_id: str, port: int, application_configuration: ApplicationConfiguration) -> None:
    expected_port = _configured_http_port(service_id, application_configuration)
    if port != expected_port:
        raise ValueError(f"Port HTTP local invalide pour {service_id}: {port}")
    bind_host = _configured_http_bind_host(service_id, application_configuration)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if service_id == "ui" and self.path != "/health":
                if self.path.endswith("/pdf/content"):
                    status_code, content_type, response_body = ui_unavailable_pdf_content_response(
                        path=self.path,
                    )
                    _write_binary_response(
                        self,
                        status_code=status_code,
                        content_type=content_type,
                        body=response_body,
                    )
                    return
                status_code, content_type, response_body = ui_get_response(
                    path=self.path,
                    state=_build_ui_corpus_state(
                        application_configuration=application_configuration,
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
                status_code, response_body = _local_post_response(
                    service_id=service_id,
                    path=self.path,
                    body={},
                    application_configuration=application_configuration,
                )
                _write_json_response(self, status_code=status_code, body=response_body)
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


def _build_ui_corpus_state(
    *,
    application_configuration: ApplicationConfiguration,
) -> CorpusPdfScreenState:
    _required_application_configuration(application_configuration)
    return build_unconnected_corpus_pdf_state()


def _ui_post_response(
    *,
    path: str,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration | None,
) -> tuple[int, dict[str, Any]]:
    if _UI_DOCUMENT_COMMAND_PATH_PATTERN.fullmatch(path) is None:
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}
    if application_configuration is not None:
        _required_application_configuration(application_configuration)
    return 503, {
        "error_code": UI_FUNCTION_NOT_OPERATIONAL,
        "reason": ORCHESTRATOR_API_CONTRACT_NOT_WIRED,
        "endpoint": path,
    }


def _local_post_response(
    *,
    service_id: str,
    path: str,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration | None = None,
) -> tuple[int, dict[str, Any]]:
    if service_id == "ui":
        return _ui_post_response(
            path=path,
            body=body,
            application_configuration=application_configuration,
        )
    if service_id == "llm-gateway":
        return _llm_gateway_post_response(
            path=path,
            body=body,
            application_configuration=_required_application_configuration(application_configuration),
        )
    if service_id != "orchestrator-api":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}
    return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}


def _search_post_response() -> tuple[int, dict[str, Any]]:
    return 503, {
        "error_code": "SERVICE_NOT_CONFIGURED",
        "endpoint": "POST /v1/search",
    }


def _index_post_response(*, document_id: str) -> tuple[int, dict[str, Any]]:
    try:
        validated_document_id = str(DomainIdentifier.parse_with_prefix(document_id, "DOC"))
    except ValueError:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}
    return 503, {
        "document_id": validated_document_id,
        "error_code": "SERVICE_NOT_CONFIGURED",
        "endpoint": "POST /v1/documents/{document_id}/index",
    }


def _required_application_configuration(
    application_configuration: ApplicationConfiguration | None,
) -> ApplicationConfiguration:
    if not isinstance(application_configuration, ApplicationConfiguration):
        raise LLMGatewayContractError(CONFIG_FILE_REQUIRED, "Configuration applicative requise.")
    return application_configuration


def _product_chat_completions_post_response(
    *,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, Any]]:
    status_code, gateway_body, _gateway_latency_ms = _post_local_gateway_inference(
        body=_build_product_chat_inference_body(body, application_configuration=application_configuration),
        application_configuration=application_configuration,
    )
    if status_code != 200:
        return status_code, gateway_body

    structured_output = _required_gateway_mapping(gateway_body, "structured_output")
    answer = _required_gateway_text(structured_output, "answer")
    provenance = _provenance_with_configuration_hash(
        _required_gateway_mapping(gateway_body, "provenance"),
        application_configuration=application_configuration,
    )
    raw_response_id = _required_gateway_text(gateway_body, "raw_response_id")
    model = _required_matching_model(body, application_configuration=application_configuration)

    return 200, {
        "id": _required_body_text(body, "request_id"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "ost_product": {
            "execution_mode": "live_spark",
            "path_segments": list(_M013_REALITY_PATH_SEGMENTS),
            "gateway_endpoint": _local_gateway_infer_endpoint(application_configuration),
            "raw_response_id": raw_response_id,
            "provenance": provenance,
        },
    }


def _llm_real_path_benchmark_post_response(
    *,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, Any]]:
    model = _required_matching_model(body, application_configuration=application_configuration)
    run_id = _required_body_text(body, "run_id")
    task_results: list[dict[str, Any]] = []
    for task_index, task_name in enumerate(_M013_REQUIRED_LLM_TASKS, start=1):
        status_code, gateway_body, gateway_latency_ms = _post_local_gateway_inference(
            body=_build_live_benchmark_task_inference_body(
                body,
                task_name=task_name,
                task_index=task_index,
                application_configuration=application_configuration,
            ),
            application_configuration=application_configuration,
        )
        if status_code != 200:
            return status_code, {
                "error_code": "LLM_REAL_PATH_BENCHMARK_TASK_FAILED",
                "task_name": task_name,
                "gateway_status_code": status_code,
                "gateway_response": gateway_body,
            }
        task_results.append(
            _build_live_benchmark_task_result(
                task_name=task_name,
                gateway_body=gateway_body,
                gateway_latency_ms=gateway_latency_ms,
                application_configuration=application_configuration,
            )
        )

    return 200, {
        "object": "llm_real_path_benchmark.run",
        "run_id": run_id,
        "execution_mode": "live_spark",
        "model": model,
        "configuration_hash": application_configuration.configuration_hash,
        "path_segments": list(_M013_REALITY_PATH_SEGMENTS),
        "task_names": list(_M013_REQUIRED_LLM_TASKS),
        "task_results": task_results,
        "technical_metric_names": list(_M013_REQUIRED_LLM_TECHNICAL_METRICS),
        "technical_metrics": _build_live_benchmark_technical_metrics(task_results),
    }


def _build_product_chat_inference_body(
    body: dict[str, Any],
    *,
    application_configuration: ApplicationConfiguration,
) -> dict[str, Any]:
    _required_matching_model(body, application_configuration=application_configuration)
    _required_body_text(body, "conversation_id")
    messages_payload = _required_body_sequence(body, "messages")
    messages = [
        {
            "role": "system",
            "content": (
                "Tu es le chat produit OSTrading local. Réponds uniquement avec un JSON conforme au schéma. "
                "Le champ answer contient la réponse publiable à l'utilisateur."
            ),
        }
    ]
    for item in messages_payload:
        if not isinstance(item, dict):
            raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Message chat produit non objet.")
        messages.append(
            {
                "role": _required_body_text(item, "role"),
                "content": _required_body_text(item, "content"),
            }
        )

    return {
        "messages": messages,
        "output_schema": dict(_M013_PRODUCT_CHAT_SCHEMA),
        "schema_name": "m13_reality_product_chat",
        "schema_version": "1.0",
        "trace_id": _required_body_text(body, "trace_id"),
        "request_id": _required_body_text(body, "request_id"),
        "idempotency_key": _required_body_text(body, "idempotency_key"),
        "prompt_id": "PROMPT-M013-REALITY-PRODUCT-CHAT",
        "prompt_version": "1.0",
        "sampling_parameters": _required_body_mapping(body, "sampling_parameters"),
    }


def _build_live_benchmark_task_inference_body(
    body: dict[str, Any],
    *,
    task_name: str,
    task_index: int,
    application_configuration: ApplicationConfiguration,
) -> dict[str, Any]:
    _required_matching_model(body, application_configuration=application_configuration)
    if task_name not in _M013_REQUIRED_LLM_TASKS:
        raise LLMGatewayContractError("LOCAL_RUNTIME_LLM_TASK_UNKNOWN", f"Tâche LLM inconnue: {task_name}")
    if isinstance(task_index, bool) or not isinstance(task_index, int) or task_index < 1:
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Index de tâche LLM invalide.")

    base_trace_id = _required_body_text(body, "trace_id")
    base_request_id = _required_body_text(body, "request_id")
    base_idempotency_key = _required_body_text(body, "idempotency_key")
    marker = _benchmark_marker_for_task(task_name)
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu exécutes une évaluation LLM M13-reality sur le chemin réel. "
                    "Réponds uniquement avec le JSON demandé."
                ),
            },
            {
                "role": "user",
                "content": _benchmark_prompt_for_task(task_name=task_name, marker=marker),
            },
        ],
        "output_schema": dict(_M013_LLM_TASK_SCHEMA),
        "schema_name": "m13_reality_llm_benchmark_task",
        "schema_version": "1.0",
        "trace_id": f"{base_trace_id}-{task_name}",
        "request_id": f"{base_request_id}-{task_index:02d}",
        "idempotency_key": f"{base_idempotency_key}-{task_name}",
        "prompt_id": f"PROMPT-M013-REALITY-LLM-TASK-{task_name}",
        "prompt_version": "1.0",
        "sampling_parameters": _required_body_mapping(body, "sampling_parameters"),
    }


def _post_local_gateway_inference(
    *,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, Any], float]:
    request = urllib.request.Request(
        _local_gateway_infer_endpoint(application_configuration),
        data=_canonical_json(body).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    started_ns = time.perf_counter_ns()
    timeout_seconds = application_configuration.services.llm_gateway.timeout_seconds
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return 502, {"error_code": "LLM_GATEWAY_RESPONSE_INVALID"}, _elapsed_ms_since(started_ns)
            if not isinstance(payload, dict):
                return 502, {"error_code": "LLM_GATEWAY_RESPONSE_INVALID"}, _elapsed_ms_since(started_ns)
            return response.status, payload, _elapsed_ms_since(started_ns)
    except urllib.error.HTTPError as exc:
        return exc.code, _read_http_error_payload(exc), _elapsed_ms_since(started_ns)
    except (TimeoutError, urllib.error.URLError) as exc:
        return (
            502,
            {
                "error_code": "LLM_GATEWAY_UNAVAILABLE",
                "message": str(exc),
            },
            _elapsed_ms_since(started_ns),
        )


def _read_http_error_payload(error: urllib.error.HTTPError) -> dict[str, Any]:
    raw_body = error.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"error_code": "LLM_GATEWAY_HTTP_ERROR", "status_code": error.code, "body": raw_body}
    if not isinstance(payload, dict):
        return {"error_code": "LLM_GATEWAY_HTTP_ERROR", "status_code": error.code, "body": payload}
    return payload


def _build_live_benchmark_task_result(
    *,
    task_name: str,
    gateway_body: dict[str, Any],
    gateway_latency_ms: float,
    application_configuration: ApplicationConfiguration,
) -> dict[str, Any]:
    structured_output = _required_gateway_mapping(gateway_body, "structured_output")
    provenance = _provenance_with_configuration_hash(
        _required_gateway_mapping(gateway_body, "provenance"),
        application_configuration=application_configuration,
    )
    raw_response_id = _required_gateway_text(gateway_body, "raw_response_id")
    answer = _required_gateway_text(structured_output, "answer")
    output_task_name = _required_gateway_text(structured_output, "task_name")
    evaluation_marker = _required_gateway_text(structured_output, "evaluation_marker")
    return {
        "task_name": task_name,
        "passed": output_task_name == task_name and evaluation_marker == _benchmark_marker_for_task(task_name),
        "raw_response_id": raw_response_id,
        "response_json_sha256": _sha256_json(structured_output),
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "gateway_latency_ms": _format_metric(gateway_latency_ms),
        "provenance": provenance,
    }


def _provenance_with_configuration_hash(
    provenance: dict[str, Any],
    *,
    application_configuration: ApplicationConfiguration,
) -> dict[str, Any]:
    enriched = dict(provenance)
    existing_hash = enriched.get("configuration_hash")
    if existing_hash is not None and existing_hash != application_configuration.configuration_hash:
        raise LLMGatewayContractError(
            "LLM_GATEWAY_RESPONSE_INVALID",
            "Hash de configuration gateway incohérent.",
        )
    enriched["configuration_hash"] = application_configuration.configuration_hash
    return enriched


def _build_live_benchmark_technical_metrics(task_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_tasks = len(task_results)
    passed_tasks = sum(1 for result in task_results if result.get("passed") is True)
    failed_tasks = total_tasks - passed_tasks
    gateway_latency_values = [float(result["gateway_latency_ms"]) for result in task_results]
    average_gateway_latency = sum(gateway_latency_values) / total_tasks
    success_rate = passed_tasks / total_tasks
    error_rate = failed_tasks / total_tasks
    return [
        _measured_metric("llm_gateway_latency_ms", average_gateway_latency, total_tasks, total_tasks),
        _measured_metric("llm_network_latency_ms", average_gateway_latency, total_tasks, total_tasks),
        _unavailable_metric("llm_vllm_queue_time_ms", "metrique_non_exposee_par_llm_gateway_v1"),
        _unavailable_metric("llm_time_to_first_token_ms", "metrique_non_exposee_par_llm_gateway_v1"),
        _unavailable_metric("llm_tokens_per_second", "usage_tokens_non_expose_par_llm_gateway_v1"),
        _measured_metric("llm_error_rate", error_rate, failed_tasks, total_tasks),
        _unavailable_metric("llm_retry_before_first_token_total", "retry_count_non_expose_par_llm_gateway_v1"),
        _measured_metric("llm_structured_output_stability_rate", success_rate, passed_tasks, total_tasks),
        _unavailable_metric("llm_spark_restart_recovery_rate", "drill_redemarrage_spark_non_execute_par_ce_endpoint"),
    ]


def _measured_metric(name: str, value: float, numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "name": name,
        "value": _format_metric(value),
        "numerator": numerator,
        "denominator": denominator,
        "measured": True,
    }


def _unavailable_metric(name: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": None,
        "numerator": None,
        "denominator": None,
        "measured": False,
        "unavailable_reason": reason,
    }


def _benchmark_prompt_for_task(*, task_name: str, marker: str) -> str:
    prompts = {
        "json_valide": "Contrôle la production JSON stricte.",
        "extraction_atomique": "Extrait le fait atomique: le chiffre d'affaires vaut 42 millions EUR.",
        "conservation_negations": "Préserve la négation: la société n'a pas de dette nette.",
        "exactitude_nombres": "Préserve les nombres: marge 12,5 pour cent et 3 incidents.",
        "conditions_application": "Préserve la condition: acheter seulement si marge supérieure à 20 pour cent.",
        "limites": "Préserve la limite: conclusion limitée aux données 2024.",
        "entailment": "Vérifie l'entailment: si A implique B et A est vrai, B est vrai.",
        "contradiction": "Détecte la contradiction: marge supérieure à 20 pour cent et marge inférieure à 10 pour cent.",
        "synthese_fr_en": "Synthèse en français: revenue grew but cash flow decreased.",
        "tool_calling": "Choisis l'outil lookup_document pour le document DOC-M013.",
        "citations": "Associe la réponse à la citation source SRC-M013-1.",
    }
    prompt = prompts.get(task_name)
    if prompt is None:
        raise LLMGatewayContractError("LOCAL_RUNTIME_LLM_TASK_UNKNOWN", f"Tâche LLM inconnue: {task_name}")
    return (
        f"{prompt} Retourne exactement un objet JSON avec task_name=\"{task_name}\", "
        f"evaluation_marker=\"{marker}\" et answer non vide."
    )


def _benchmark_marker_for_task(task_name: str) -> str:
    if task_name not in _M013_REQUIRED_LLM_TASKS:
        raise LLMGatewayContractError("LOCAL_RUNTIME_LLM_TASK_UNKNOWN", f"Tâche LLM inconnue: {task_name}")
    return f"M013-REALITY-{task_name}"


def _local_gateway_infer_endpoint(application_configuration: ApplicationConfiguration) -> str:
    return f"{application_configuration.services.llm_gateway.url.rstrip('/')}/v1/infer"


def _required_matching_model(
    body: dict[str, Any],
    *,
    application_configuration: ApplicationConfiguration,
) -> str:
    model = _required_body_text(body, "model")
    expected_model = application_configuration.models.llm.served_model_name
    if model != expected_model:
        raise LLMGatewayContractError(
            "LOCAL_RUNTIME_MODEL_MISMATCH",
            f"Modele local attendu {expected_model}, obtenu {model}.",
        )
    return model


def _required_gateway_mapping(body: dict[str, Any], name: str) -> dict[str, Any]:
    value = body.get(name)
    if not isinstance(value, dict) or len(value) == 0:
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", f"Objet gateway requis absent: {name}")
    return value


def _required_gateway_text(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", f"Champ gateway requis absent: {name}")
    if value != value.strip():
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", f"Champ gateway non normalise: {name}")
    return value


def _elapsed_ms_since(started_ns: int) -> float:
    elapsed_ns = time.perf_counter_ns() - started_ns
    if elapsed_ns < 0:
        raise LLMGatewayContractError("LOCAL_RUNTIME_CLOCK_INVALID", "Horloge monotone locale invalide.")
    return elapsed_ns / 1_000_000


def _format_metric(value: float) -> str:
    return f"{value:.12f}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


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


def _run_worker(*, service_id: str, application_configuration: ApplicationConfiguration) -> None:
    _required_application_configuration(application_configuration)
    _require_worker_service(service_id)
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
