"""Cas d'usage CV du contrat public de conversation produit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import time

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


@dataclass(frozen=True, slots=True)
class ProductConversationHandler:
    served_model: str
    configuration_hash: str
    gateway_endpoint: str
    inference_gateway: LlmInferenceGateway

    def __post_init__(self) -> None:
        for field_name in ("served_model", "configuration_hash", "gateway_endpoint"):
            _required_text(getattr(self, field_name), field_name)
        if not callable(getattr(self.inference_gateway, "infer", None)):
            raise ValueError("port d'inférence obligatoire")

    def handle(self, body: JsonObject, *, trace_id: str) -> PublicResponse:
        model = _matching_model(body, self.served_model)
        _required_text(_value(body, "conversation_id"), "conversation_id")
        messages_payload = _required_sequence(_value(body, "messages"), "messages")
        messages = [
            LlmInferenceMessage(
                role="system",
                content=(
                    "Tu es le chat produit OSTrading local. Réponds uniquement avec "
                    "un JSON conforme au schéma."
                ),
            )
        ]
        for message in messages_payload:
            if not isinstance(message, Mapping):
                raise LlmContractError("HTTP_REQUEST_INVALID", "Message chat produit non objet.")
            messages.append(
                LlmInferenceMessage(
                    role=_required_text(message.get("role"), "role"),
                    content=_required_text(message.get("content"), "content"),
                )
            )
        response = self.inference_gateway.infer(
            LlmInferenceRequest(
                messages=tuple(messages),
                output_schema={
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
                schema_name="m13_reality_product_chat",
                schema_version="1.0",
                trace_id=_required_text(trace_id, "trace_id"),
                request_id=_required_text(_value(body, "request_id"), "request_id"),
                idempotency_key=_required_text(
                    _value(body, "idempotency_key"),
                    "idempotency_key",
                ),
                prompt_id="PROMPT-M013-REALITY-PRODUCT-CHAT",
                prompt_version="1.0",
                sampling_parameters=_required_mapping(
                    _value(body, "sampling_parameters"),
                    "sampling_parameters",
                ),
            )
        )
        parsed_response = _inference_response(response)
        gateway_payload = dict(parsed_response.payload)
        if parsed_response.status_code != 200:
            return parsed_response.status_code, gateway_payload
        structured = _required_mapping(gateway_payload.get("structured_output"), "structured_output")
        provenance = dict(_required_mapping(gateway_payload.get("provenance"), "provenance"))
        existing_hash = provenance.get("configuration_hash")
        if existing_hash is not None and existing_hash != self.configuration_hash:
            raise LlmContractError(
                "LLM_GATEWAY_RESPONSE_INVALID",
                "Hash de configuration gateway incohérent.",
            )
        provenance["configuration_hash"] = self.configuration_hash
        return 200, {
            "id": _required_text(_value(body, "request_id"), "request_id"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": _required_text(structured.get("answer"), "answer"),
                    },
                    "finish_reason": "stop",
                }
            ],
            "ost_product": {
                "execution_mode": "live_spark",
                "path_segments": list(_PATH_SEGMENTS),
                "gateway_endpoint": self.gateway_endpoint,
                "raw_response_id": _required_text(
                    gateway_payload.get("raw_response_id"),
                    "raw_response_id",
                ),
                "provenance": provenance,
            },
        }


def _matching_model(body: JsonObject, expected: str) -> str:
    model = _required_text(_value(body, "model"), "model")
    if model != expected:
        raise LlmContractError(
            "LOCAL_RUNTIME_MODEL_MISMATCH",
            f"Modele local attendu {expected}, obtenu {model}.",
        )
    return model


def _value(body: JsonObject, name: str) -> JsonValue:
    if not isinstance(body, Mapping):
        raise LlmContractError("HTTP_REQUEST_INVALID", "Corps JSON objet requis.")
    return body.get(name)


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise LlmContractError("HTTP_REQUEST_INVALID", f"Champ requis absent: {name}")
    return value


def _required_mapping(value: object, name: str) -> JsonObject:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise LlmContractError("HTTP_REQUEST_INVALID", f"Objet requis absent: {name}")
    return value


def _required_sequence(value: object, name: str) -> list[JsonValue]:
    if not isinstance(value, list) or len(value) == 0:
        raise LlmContractError("HTTP_REQUEST_INVALID", f"Liste requise absente: {name}")
    return value


def _inference_response(value: object) -> LlmInferenceResponse:
    if not isinstance(value, LlmInferenceResponse):
        raise TypeError("réponse du port d'inférence invalide")
    return value


__all__ = ["ProductConversationHandler", "PublicResponse"]
