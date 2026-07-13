"""Port d'inférence partagé entre les cas d'usage et l'adaptateur LLM gateway."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias


JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]


class LlmContractError(ValueError):
    """Erreur publique stable produite avant l'appel du gateway."""

    def __init__(self, code: str, message: str) -> None:
        self.code = _required_text(code, "code")
        self.message = _required_text(message, "message")
        super().__init__(f"{self.code}: {self.message}")


@dataclass(frozen=True, slots=True)
class LlmInferenceMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        _required_text(self.role, "role")
        _required_text(self.content, "content")


@dataclass(frozen=True, slots=True)
class LlmInferenceRequest:
    messages: tuple[LlmInferenceMessage, ...]
    output_schema: JsonObject
    schema_name: str
    schema_version: str
    trace_id: str
    request_id: str
    idempotency_key: str
    prompt_id: str
    prompt_version: str
    sampling_parameters: JsonObject

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple) or len(self.messages) == 0:
            raise ValueError("messages d'inférence requis")
        if any(not isinstance(message, LlmInferenceMessage) for message in self.messages):
            raise ValueError("message d'inférence invalide")
        _required_mapping(self.output_schema, "output_schema")
        _required_mapping(self.sampling_parameters, "sampling_parameters")
        for field_name in (
            "schema_name",
            "schema_version",
            "trace_id",
            "request_id",
            "idempotency_key",
            "prompt_id",
            "prompt_version",
        ):
            _required_text(getattr(self, field_name), field_name)

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "messages": [
                {"role": message.role, "content": message.content}
                for message in self.messages
            ],
            "output_schema": dict(self.output_schema),
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "sampling_parameters": dict(self.sampling_parameters),
        }


@dataclass(frozen=True, slots=True)
class LlmInferenceResponse:
    status_code: int
    payload: JsonObject
    latency_ms: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or self.status_code < 100
            or self.status_code > 599
        ):
            raise ValueError("status_code gateway invalide")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload gateway invalide")
        if (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or self.latency_ms < 0
        ):
            raise ValueError("latence gateway invalide")


class LlmInferenceGateway(Protocol):
    def infer(self, request: LlmInferenceRequest) -> LlmInferenceResponse:
        """Exécute une inférence corrélée sans exposer le transport aux cas d'usage."""


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _required_mapping(value: object, field_name: str) -> JsonObject:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = [
    "JsonObject",
    "JsonValue",
    "LlmContractError",
    "LlmInferenceGateway",
    "LlmInferenceMessage",
    "LlmInferenceRequest",
    "LlmInferenceResponse",
]
