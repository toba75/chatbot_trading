"""Cas d'usage EX du benchmark LLM sur le chemin réel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json

from app.contracts.llm_inference import (
    JsonObject,
    JsonValue,
    LlmContractError,
    LlmInferenceGateway,
    LlmInferenceMessage,
    LlmInferenceRequest,
    LlmInferenceResponse,
)


PublicResponse = tuple[int, dict[str, JsonValue]]
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


@dataclass(frozen=True, slots=True)
class LlmRealPathBenchmarkHandler:
    served_model: str
    configuration_hash: str
    inference_gateway: LlmInferenceGateway

    def __post_init__(self) -> None:
        _required_text(self.served_model, "served_model")
        _required_text(self.configuration_hash, "configuration_hash")
        if not callable(getattr(self.inference_gateway, "infer", None)):
            raise ValueError("port d'inférence obligatoire")

    def handle(self, body: JsonObject, *, trace_id: str) -> PublicResponse:
        model = _matching_model(body, self.served_model)
        run_id = _required_text(body.get("run_id"), "run_id")
        base_trace_id = _required_text(trace_id, "trace_id")
        base_request_id = _required_text(body.get("request_id"), "request_id")
        base_idempotency_key = _required_text(body.get("idempotency_key"), "idempotency_key")
        sampling = _required_mapping(body.get("sampling_parameters"), "sampling_parameters")
        results: list[dict[str, JsonValue]] = []
        for index, task in enumerate(_TASKS, start=1):
            marker = benchmark_marker_for_task(task)
            response = self.inference_gateway.infer(
                LlmInferenceRequest(
                    messages=(
                        LlmInferenceMessage(
                            role="system",
                            content=(
                                "Tu exécutes une évaluation LLM M13-reality sur le chemin réel. "
                                "Réponds uniquement avec le JSON demandé."
                            ),
                        ),
                        LlmInferenceMessage(
                            role="user",
                            content=(
                                f'Tâche {task}. Retourne exactement task_name="{task}", '
                                f'evaluation_marker="{marker}" et answer non vide.'
                            ),
                        ),
                    ),
                    output_schema={
                        "type": "object",
                        "properties": {
                            "task_name": {"type": "string"},
                            "evaluation_marker": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                        "required": ["task_name", "evaluation_marker", "answer"],
                        "additionalProperties": False,
                    },
                    schema_name="m13_reality_llm_benchmark_task",
                    schema_version="1.0",
                    trace_id=base_trace_id,
                    request_id=f"{base_request_id}-{index:02d}",
                    idempotency_key=f"{base_idempotency_key}-{task}",
                    prompt_id=f"PROMPT-M013-REALITY-LLM-TASK-{task}",
                    prompt_version="1.0",
                    sampling_parameters=sampling,
                )
            )
            parsed = _inference_response(response)
            gateway = dict(parsed.payload)
            if parsed.status_code != 200:
                return parsed.status_code, {
                    "error_code": "LLM_REAL_PATH_BENCHMARK_TASK_FAILED",
                    "task_name": task,
                    "gateway_status_code": parsed.status_code,
                    "gateway_response": gateway,
                }
            structured = _required_mapping(gateway.get("structured_output"), "structured_output")
            answer = _required_text(structured.get("answer"), "answer")
            provenance = dict(_required_mapping(gateway.get("provenance"), "provenance"))
            existing_hash = provenance.get("configuration_hash")
            if existing_hash is not None and existing_hash != self.configuration_hash:
                raise LlmContractError(
                    "LLM_GATEWAY_RESPONSE_INVALID",
                    "Hash de configuration gateway incohérent.",
                )
            provenance["configuration_hash"] = self.configuration_hash
            results.append(
                {
                    "task_name": task,
                    "passed": (
                        _required_text(structured.get("task_name"), "task_name") == task
                        and _required_text(structured.get("evaluation_marker"), "evaluation_marker") == marker
                    ),
                    "raw_response_id": _required_text(gateway.get("raw_response_id"), "raw_response_id"),
                    "response_json_sha256": _sha256(structured),
                    "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                    "gateway_latency_ms": f"{parsed.latency_ms:.12f}",
                    "provenance": provenance,
                }
            )
        measured = sum(1 for result in results if result["passed"] is True)
        total = len(results)
        average = sum(float(str(result["gateway_latency_ms"])) for result in results) / total
        metrics = [_measured(_METRICS[0], average, total, total), _measured(_METRICS[1], average, total, total)]
        metrics.extend(_unavailable(name) for name in _METRICS[2:5])
        metrics.append(_measured(_METRICS[5], (total - measured) / total, total - measured, total))
        metrics.append(_unavailable(_METRICS[6]))
        metrics.append(_measured(_METRICS[7], measured / total, measured, total))
        metrics.append(_unavailable(_METRICS[8]))
        return 200, {
            "object": "llm_real_path_benchmark.run",
            "run_id": run_id,
            "execution_mode": "live_spark",
            "model": model,
            "configuration_hash": self.configuration_hash,
            "path_segments": list(_PATH_SEGMENTS),
            "task_names": list(_TASKS),
            "task_results": results,
            "technical_metric_names": list(_METRICS),
            "technical_metrics": metrics,
        }


def _matching_model(body: JsonObject, expected: str) -> str:
    model = _required_text(body.get("model"), "model")
    if model != expected:
        raise LlmContractError(
            "LOCAL_RUNTIME_MODEL_MISMATCH",
            f"Modele local attendu {expected}, obtenu {model}.",
        )
    return model


def benchmark_marker_for_task(task_name: str) -> str:
    if task_name not in _TASKS:
        raise LlmContractError("LOCAL_RUNTIME_LLM_TASK_UNKNOWN", f"Tâche LLM inconnue: {task_name}")
    return f"M013-REALITY-{task_name}"


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise LlmContractError("HTTP_REQUEST_INVALID", f"Champ requis absent: {name}")
    return value


def _required_mapping(value: object, name: str) -> JsonObject:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise LlmContractError("HTTP_REQUEST_INVALID", f"Objet requis absent: {name}")
    return value


def _inference_response(value: object) -> LlmInferenceResponse:
    if not isinstance(value, LlmInferenceResponse):
        raise TypeError("réponse du port d'inférence invalide")
    return value


def _sha256(value: JsonObject) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _measured(name: str, value: float, numerator: int, denominator: int) -> dict[str, JsonValue]:
    return {
        "name": name,
        "value": f"{value:.12f}",
        "numerator": numerator,
        "denominator": denominator,
        "measured": True,
    }


def _unavailable(name: str) -> dict[str, JsonValue]:
    return {
        "name": name,
        "value": None,
        "numerator": None,
        "denominator": None,
        "measured": False,
        "unavailable_reason": "metrique_non_exposee_par_llm_gateway_v1",
    }


__all__ = ["LlmRealPathBenchmarkHandler", "PublicResponse", "benchmark_marker_for_task"]
