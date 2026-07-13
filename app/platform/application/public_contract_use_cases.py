"""Délégations de compatibilité vers les handlers propriétaires CV, EX et KA."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.contracts.llm_inference import (
    JsonObject,
    JsonValue,
    LlmInferenceMessage,
    LlmInferenceRequest,
    LlmInferenceResponse,
)
from app.platform.configuration import ApplicationConfiguration
from app.platform.llm_gateway.orchestrator_http import UrllibLlmInferenceGateway
from app.platform.orchestrator_public_services import build_public_contract_services


PublicResponse = tuple[int, dict[str, JsonValue]]


@dataclass(frozen=True, slots=True)
class _CompatibilityInferenceGateway:
    configuration: ApplicationConfiguration

    def infer(self, request: LlmInferenceRequest) -> LlmInferenceResponse:
        status_code, payload, latency_ms = _infer(
            request.to_payload(),
            self.configuration,
        )
        return LlmInferenceResponse(
            status_code=status_code,
            payload=payload,
            latency_ms=latency_ms,
        )


def product_chat_completions_post_response(
    *,
    body: JsonObject,
    application_configuration: ApplicationConfiguration,
) -> PublicResponse:
    services = _services(application_configuration)
    return services.conversation.handle(body, trace_id=_trace_id(body))


def llm_real_path_benchmark_post_response(
    *,
    body: JsonObject,
    application_configuration: ApplicationConfiguration,
) -> PublicResponse:
    services = _services(application_configuration)
    return services.evaluation.handle(body, trace_id=_trace_id(body))


def search_post_response() -> PublicResponse:
    return 503, {
        "error_code": "SERVICE_NOT_CONFIGURED",
        "endpoint": "POST /v1/search",
    }


def index_post_response(*, document_id: str) -> PublicResponse:
    return 503, {
        "document_id": document_id,
        "error_code": "SERVICE_NOT_CONFIGURED",
        "endpoint": "POST /v1/documents/{document_id}/index",
    }


def _services(configuration: ApplicationConfiguration):
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    return build_public_contract_services(
        configuration,
        inference_gateway=_CompatibilityInferenceGateway(configuration),
    )


def _infer(
    body: JsonObject,
    application_configuration: ApplicationConfiguration,
) -> tuple[int, dict[str, JsonValue], float]:
    gateway = UrllibLlmInferenceGateway(
        endpoint_url=f"{application_configuration.services.llm_gateway.url.rstrip('/')}/v1/infer",
        timeout_seconds=application_configuration.services.llm_gateway.timeout_seconds,
    )
    response = gateway.infer(_request_from_payload(body))
    return response.status_code, dict(response.payload), response.latency_ms


def _request_from_payload(body: JsonObject) -> LlmInferenceRequest:
    messages_payload = _sequence(body.get("messages"), "messages")
    messages: list[LlmInferenceMessage] = []
    for message in messages_payload:
        if not isinstance(message, Mapping):
            raise ValueError("message d'inférence invalide")
        messages.append(
            LlmInferenceMessage(
                role=_text(message.get("role"), "role"),
                content=_text(message.get("content"), "content"),
            )
        )
    return LlmInferenceRequest(
        messages=tuple(messages),
        output_schema=_mapping(body.get("output_schema"), "output_schema"),
        schema_name=_text(body.get("schema_name"), "schema_name"),
        schema_version=_text(body.get("schema_version"), "schema_version"),
        trace_id=_text(body.get("trace_id"), "trace_id"),
        request_id=_text(body.get("request_id"), "request_id"),
        idempotency_key=_text(body.get("idempotency_key"), "idempotency_key"),
        prompt_id=_text(body.get("prompt_id"), "prompt_id"),
        prompt_version=_text(body.get("prompt_version"), "prompt_version"),
        sampling_parameters=_mapping(
            body.get("sampling_parameters"),
            "sampling_parameters",
        ),
    )


def _trace_id(body: JsonObject) -> str:
    return _text(body.get("trace_id"), "trace_id")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _mapping(value: object, field_name: str) -> JsonObject:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _sequence(value: object, field_name: str) -> list[JsonValue]:
    if not isinstance(value, list) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = [
    "index_post_response",
    "llm_real_path_benchmark_post_response",
    "product_chat_completions_post_response",
    "search_post_response",
]
