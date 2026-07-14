"""Port d'inférence partagé entre les cas d'usage et l'adaptateur LLM gateway."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias


JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]
_MAX_INFERENCE_IMAGE_BYTES = 10 * 1024 * 1024


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
class LlmInferenceImage:
    """Image bornée et hachée transmise au seul gateway LLM."""

    media_type: str
    data_base64: str
    sha256: str

    def __post_init__(self) -> None:
        _required_text(self.media_type, "media_type")
        if self.media_type not in {"image/png", "image/jpeg"}:
            raise LlmContractError("LLM_IMAGE_MEDIA_TYPE_INVALID", "Type MIME image refusé.")
        image_data = _decode_image_data(self.data_base64)
        if len(image_data) > _MAX_INFERENCE_IMAGE_BYTES:
            raise LlmContractError("LLM_IMAGE_TOO_LARGE", "Image d'inférence trop grande.")
        if self.media_type == "image/png" and not image_data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise LlmContractError("LLM_IMAGE_PAYLOAD_INVALID", "Signature PNG absente.")
        if self.media_type == "image/jpeg" and not image_data.startswith(b"\xff\xd8\xff"):
            raise LlmContractError("LLM_IMAGE_PAYLOAD_INVALID", "Signature JPEG absente.")
        _required_text(self.sha256, "sha256")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise LlmContractError("LLM_IMAGE_HASH_INVALID", "SHA-256 image invalide.")
        if hashlib.sha256(image_data).hexdigest() != self.sha256:
            raise LlmContractError("LLM_IMAGE_HASH_INVALID", "SHA-256 image divergent.")


@dataclass(frozen=True, slots=True)
class LlmInferenceImageMessage:
    """Message multimodal explicite et compatible avec le contrat HTTP du gateway."""

    role: str
    content: str
    images: tuple[LlmInferenceImage, ...]

    def __post_init__(self) -> None:
        _required_text(self.role, "role")
        _required_text(self.content, "content")
        if not isinstance(self.images, tuple) or len(self.images) == 0:
            raise ValueError("images d'inférence requises")
        if any(not isinstance(image, LlmInferenceImage) for image in self.images):
            raise ValueError("image d'inférence invalide")


@dataclass(frozen=True, slots=True)
class LlmInferenceRequest:
    messages: tuple[LlmInferenceMessage | LlmInferenceImageMessage, ...]
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
        if any(
            not isinstance(message, LlmInferenceMessage | LlmInferenceImageMessage)
            for message in self.messages
        ):
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
                _message_payload(message)
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


def _decode_image_data(data_base64: object) -> bytes:
    _required_text(data_base64, "data_base64")
    try:
        image_data = base64.b64decode(data_base64.encode("ascii"), validate=True)
    except (AttributeError, UnicodeEncodeError, binascii.Error) as error:
        raise LlmContractError("LLM_IMAGE_PAYLOAD_INVALID", "Base64 image invalide.") from error
    if base64.b64encode(image_data).decode("ascii") != data_base64:
        raise LlmContractError("LLM_IMAGE_PAYLOAD_INVALID", "Base64 image non canonique.")
    return image_data


def _message_payload(
    message: LlmInferenceMessage | LlmInferenceImageMessage,
) -> dict[str, JsonValue]:
    if isinstance(message, LlmInferenceMessage):
        return {"role": message.role, "content": message.content}
    return {
        "role": message.role,
        "content": [
            {"type": "text", "text": message.content},
            *[
                {
                    "type": "image",
                    "media_type": image.media_type,
                    "data_base64": image.data_base64,
                    "sha256": image.sha256,
                }
                for image in message.images
            ],
        ],
    }


__all__ = [
    "JsonObject",
    "JsonValue",
    "LlmContractError",
    "LlmInferenceGateway",
    "LlmInferenceImage",
    "LlmInferenceImageMessage",
    "LlmInferenceMessage",
    "LlmInferenceRequest",
    "LlmInferenceResponse",
]
