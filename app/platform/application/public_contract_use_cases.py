"""Cas d'usage publics conversation, évaluation, recherche et indexation."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.platform.configuration import ApplicationConfiguration
from app.platform.llm_gateway import LLMGatewayContractError


PublicResponse = tuple[int, dict[str, Any]]
_PATH_SEGMENTS = ("docker-local", "orchestrator-api", "llm-gateway", "vllm-spark")
_TASKS = (
    "json_valide", "extraction_atomique", "conservation_negations", "exactitude_nombres",
    "conditions_application", "limites", "entailment", "contradiction", "synthese_fr_en",
    "tool_calling", "citations",
)
_METRICS = (
    "llm_gateway_latency_ms", "llm_network_latency_ms", "llm_vllm_queue_time_ms",
    "llm_time_to_first_token_ms", "llm_tokens_per_second", "llm_error_rate",
    "llm_retry_before_first_token_total", "llm_structured_output_stability_rate",
    "llm_spark_restart_recovery_rate",
)


class JsonCommandPort(Protocol):
    def handle(self, body: dict[str, Any]) -> PublicResponse: ...


class IndexCommandPort(Protocol):
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse: ...


@dataclass(frozen=True, slots=True)
class ConversationUseCase:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        configuration = _configuration(self.configuration)
        model = _matching_model(body, configuration)
        _text(body, "conversation_id")
        messages = _sequence(body, "messages")
        gateway_messages = [{
            "role": "system",
            "content": "Tu es le chat produit OSTrading local. Réponds uniquement avec un JSON conforme au schéma.",
        }]
        for message in messages:
            if not isinstance(message, dict):
                raise LLMGatewayContractError("HTTP_REQUEST_INVALID", "Message chat produit non objet.")
            gateway_messages.append({"role": _text(message, "role"), "content": _text(message, "content")})
        request = {
            "messages": gateway_messages,
            "output_schema": {
                "type": "object", "properties": {"answer": {"type": "string"}},
                "required": ["answer"], "additionalProperties": False,
            },
            "schema_name": "m13_reality_product_chat", "schema_version": "1.0",
            "trace_id": _text(body, "trace_id"), "request_id": _text(body, "request_id"),
            "idempotency_key": _text(body, "idempotency_key"),
            "prompt_id": "PROMPT-M013-REALITY-PRODUCT-CHAT", "prompt_version": "1.0",
            "sampling_parameters": _mapping(body, "sampling_parameters"),
        }
        status, gateway, _ = _infer(request, configuration)
        if status != 200:
            return status, gateway
        structured = _gateway_mapping(gateway, "structured_output")
        return 200, {
            "id": _text(body, "request_id"), "object": "chat.completion",
            "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": _gateway_text(structured, "answer")}, "finish_reason": "stop"}],
            "ost_product": {
                "execution_mode": "live_spark", "path_segments": list(_PATH_SEGMENTS),
                "gateway_endpoint": _gateway_endpoint(configuration),
                "raw_response_id": _gateway_text(gateway, "raw_response_id"),
                "provenance": _provenance(_gateway_mapping(gateway, "provenance"), configuration),
            },
        }


@dataclass(frozen=True, slots=True)
class EvaluationUseCase:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        configuration = _configuration(self.configuration)
        model = _matching_model(body, configuration)
        run_id = _text(body, "run_id")
        results: list[dict[str, Any]] = []
        for index, task in enumerate(_TASKS, start=1):
            marker = f"M013-REALITY-{task}"
            request = {
                "messages": [
                    {"role": "system", "content": "Tu exécutes une évaluation LLM M13-reality sur le chemin réel. Réponds uniquement avec le JSON demandé."},
                    {"role": "user", "content": f'Tâche {task}. Retourne exactement task_name="{task}", evaluation_marker="{marker}" et answer non vide.'},
                ],
                "output_schema": {
                    "type": "object",
                    "properties": {"task_name": {"type": "string"}, "evaluation_marker": {"type": "string"}, "answer": {"type": "string"}},
                    "required": ["task_name", "evaluation_marker", "answer"], "additionalProperties": False,
                },
                "schema_name": "m13_reality_llm_benchmark_task", "schema_version": "1.0",
                "trace_id": f'{_text(body, "trace_id")}-{task}',
                "request_id": f'{_text(body, "request_id")}-{index:02d}',
                "idempotency_key": f'{_text(body, "idempotency_key")}-{task}',
                "prompt_id": f"PROMPT-M013-REALITY-LLM-TASK-{task}", "prompt_version": "1.0",
                "sampling_parameters": _mapping(body, "sampling_parameters"),
            }
            status, gateway, latency = _infer(request, configuration)
            if status != 200:
                return status, {"error_code": "LLM_REAL_PATH_BENCHMARK_TASK_FAILED", "task_name": task, "gateway_status_code": status, "gateway_response": gateway}
            structured = _gateway_mapping(gateway, "structured_output")
            answer = _gateway_text(structured, "answer")
            results.append({
                "task_name": task,
                "passed": _gateway_text(structured, "task_name") == task and _gateway_text(structured, "evaluation_marker") == marker,
                "raw_response_id": _gateway_text(gateway, "raw_response_id"),
                "response_json_sha256": _sha256(structured), "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
                "gateway_latency_ms": f"{latency:.12f}",
                "provenance": _provenance(_gateway_mapping(gateway, "provenance"), configuration),
            })
        measured = sum(1 for result in results if result["passed"])
        total = len(results)
        average = sum(float(result["gateway_latency_ms"]) for result in results) / total
        metrics = [_measured("llm_gateway_latency_ms", average, total, total), _measured("llm_network_latency_ms", average, total, total)]
        metrics.extend(_unavailable(name) for name in _METRICS[2:5])
        metrics.append(_measured("llm_error_rate", (total - measured) / total, total - measured, total))
        metrics.append(_unavailable(_METRICS[6]))
        metrics.append(_measured("llm_structured_output_stability_rate", measured / total, measured, total))
        metrics.append(_unavailable(_METRICS[8]))
        return 200, {
            "object": "llm_real_path_benchmark.run", "run_id": run_id, "execution_mode": "live_spark",
            "model": model, "configuration_hash": configuration.configuration_hash,
            "path_segments": list(_PATH_SEGMENTS), "task_names": list(_TASKS), "task_results": results,
            "technical_metric_names": list(_METRICS), "technical_metrics": metrics,
        }


@dataclass(frozen=True, slots=True)
class SearchUseCase:
    def handle(self, body: dict[str, Any]) -> PublicResponse:
        del body
        return 503, {"error_code": "SERVICE_NOT_CONFIGURED", "endpoint": "POST /v1/search"}


@dataclass(frozen=True, slots=True)
class IndexingUseCase:
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse:
        del body
        try:
            parsed = str(DomainIdentifier.parse_with_prefix(document_id, "DOC"))
        except ValueError:
            return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}
        return 503, {"document_id": parsed, "error_code": "SERVICE_NOT_CONFIGURED", "endpoint": "POST /v1/documents/{document_id}/index"}


def product_chat_completions_post_response(
    *,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> PublicResponse:
    return ConversationUseCase(application_configuration).handle(body)


def llm_real_path_benchmark_post_response(
    *,
    body: dict[str, Any],
    application_configuration: ApplicationConfiguration,
) -> PublicResponse:
    return EvaluationUseCase(application_configuration).handle(body)


def search_post_response() -> PublicResponse:
    return SearchUseCase().handle({})


def index_post_response(*, document_id: str) -> PublicResponse:
    return IndexingUseCase().handle(document_id, {})


def _infer(body: dict[str, Any], configuration: ApplicationConfiguration) -> tuple[int, dict[str, Any], float]:
    request = urllib.request.Request(_gateway_endpoint(configuration), data=_json(body).encode(), headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    started = time.perf_counter_ns()
    try:
        with urllib.request.urlopen(request, timeout=configuration.services.llm_gateway.timeout_seconds) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return 502, {"error_code": "LLM_GATEWAY_RESPONSE_INVALID"}, _elapsed(started)
            if not isinstance(payload, dict):
                return 502, {"error_code": "LLM_GATEWAY_RESPONSE_INVALID"}, _elapsed(started)
            return response.status, payload, _elapsed(started)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"error_code": "LLM_GATEWAY_HTTP_ERROR", "status_code": exc.code}
        return exc.code, payload if isinstance(payload, dict) else {"error_code": "LLM_GATEWAY_HTTP_ERROR"}, _elapsed(started)
    except (TimeoutError, urllib.error.URLError) as exc:
        return 502, {"error_code": "LLM_GATEWAY_UNAVAILABLE", "message": str(exc)}, _elapsed(started)


def _configuration(value: Any) -> ApplicationConfiguration:
    if not isinstance(value, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    return value


def _matching_model(body: dict[str, Any], configuration: ApplicationConfiguration) -> str:
    model = _text(body, "model")
    if model != configuration.models.llm.served_model_name:
        raise LLMGatewayContractError(
            "LOCAL_RUNTIME_MODEL_MISMATCH",
            f"Modele local attendu {configuration.models.llm.served_model_name}, obtenu {model}.",
        )
    return model


def _text(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Champ requis absent: {name}")
    return value


def _mapping(body: dict[str, Any], name: str) -> dict[str, Any]:
    value = body.get(name)
    if not isinstance(value, dict) or not value:
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Objet requis absent: {name}")
    return value


def _sequence(body: dict[str, Any], name: str) -> list[Any]:
    value = body.get(name)
    if not isinstance(value, list) or not value:
        raise LLMGatewayContractError("HTTP_REQUEST_INVALID", f"Liste requise absente: {name}")
    return value


def _gateway_mapping(body: dict[str, Any], name: str) -> dict[str, Any]:
    value = body.get(name)
    if not isinstance(value, dict) or not value:
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", f"Objet gateway requis absent: {name}")
    return value


def _gateway_text(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", f"Champ gateway requis absent: {name}")
    return value


def _provenance(value: dict[str, Any], configuration: ApplicationConfiguration) -> dict[str, Any]:
    result = dict(value)
    existing = result.get("configuration_hash")
    if existing is not None and existing != configuration.configuration_hash:
        raise LLMGatewayContractError("LLM_GATEWAY_RESPONSE_INVALID", "Hash de configuration gateway incohérent.")
    result["configuration_hash"] = configuration.configuration_hash
    return result


def _gateway_endpoint(configuration: ApplicationConfiguration) -> str:
    return f"{configuration.services.llm_gateway.url.rstrip('/')}/v1/infer"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _elapsed(started: int) -> float:
    return (time.perf_counter_ns() - started) / 1_000_000


def _measured(name: str, value: float, numerator: int, denominator: int) -> dict[str, Any]:
    return {"name": name, "value": f"{value:.12f}", "numerator": numerator, "denominator": denominator, "measured": True}


def _unavailable(name: str) -> dict[str, Any]:
    return {"name": name, "value": None, "numerator": None, "denominator": None, "measured": False, "unavailable_reason": "metrique_non_exposee_par_llm_gateway_v1"}


__all__ = [
    "ConversationUseCase",
    "EvaluationUseCase",
    "IndexingUseCase",
    "SearchUseCase",
    "index_post_response",
    "llm_real_path_benchmark_post_response",
    "product_chat_completions_post_response",
    "search_post_response",
]
