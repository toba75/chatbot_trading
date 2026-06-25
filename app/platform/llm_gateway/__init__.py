"""Contrat technique du gateway LLM local M-002."""

from __future__ import annotations

import hashlib
import json
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse


GATEWAY_CLIENT_ID = "llm-gateway"
SECRET_MASK = "<secret-masked>"
_FORBIDDEN_SAMPLING_KEYS = frozenset({"model", "messages", "response_format"})


class LLMGatewayContractError(ValueError):
    """Erreur technique explicite du contrat gateway LLM."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, repr=False)
class GatewayConfiguration:
    base_url: str
    served_model: str
    api_key: str
    tls_ca_bundle_path: str
    timeout_seconds: int

    def __post_init__(self) -> None:
        _require_text(self.base_url, "base_url", "LLM_GATEWAY_BASE_URL_REQUIRED")
        _require_text(self.served_model, "served_model", "LLM_GATEWAY_MODEL_REQUIRED")
        _require_text(self.api_key, "api_key", "LLM_GATEWAY_API_KEY_REQUIRED")
        _require_text(self.tls_ca_bundle_path, "tls_ca_bundle_path", "LLM_GATEWAY_TLS_CA_REQUIRED")

        parsed_base_url = urlparse(self.base_url)
        if parsed_base_url.scheme != "https" or parsed_base_url.netloc == "":
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_REQUIRED",
                "Le gateway LLM exige une URL Spark HTTPS explicite.",
            )

        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds <= 0:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TIMEOUT_REQUIRED",
                "Le timeout du gateway LLM doit être un entier strictement positif.",
            )

    def masked_for_logs(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "served_model": self.served_model,
            "api_key": SECRET_MASK,
            "tls_ca_bundle_path": self.tls_ca_bundle_path,
            "timeout_seconds": self.timeout_seconds,
        }

    def __repr__(self) -> str:
        return f"GatewayConfiguration({self.masked_for_logs()!r})"


@dataclass(frozen=True)
class InferenceMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        _require_text(self.role, "role", "LLM_MESSAGE_ROLE_REQUIRED")
        _require_text(self.content, "content", "LLM_MESSAGE_CONTENT_REQUIRED")
        if self.role not in {"system", "user", "assistant", "tool"}:
            raise LLMGatewayContractError(
                "LLM_MESSAGE_ROLE_INVALID",
                f"Rôle OpenAI compatible invalide: {self.role}",
            )


@dataclass(frozen=True)
class InferenceRequest:
    messages: tuple[InferenceMessage, ...]
    output_schema: Mapping[str, Any]
    schema_name: str
    schema_version: str
    trace_id: str
    request_id: str
    idempotency_key: str
    prompt_id: str
    prompt_version: str
    sampling_parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple) or len(self.messages) == 0:
            raise LLMGatewayContractError(
                "LLM_MESSAGES_REQUIRED",
                "Une demande d'inférence doit contenir au moins un message.",
            )
        for message in self.messages:
            if not isinstance(message, InferenceMessage):
                raise LLMGatewayContractError(
                    "LLM_MESSAGE_INVALID",
                    "Chaque message d'inférence doit utiliser InferenceMessage.",
                )

        _require_mapping(self.output_schema, "output_schema", "LLM_OUTPUT_SCHEMA_REQUIRED")
        _require_text(self.schema_name, "schema_name", "LLM_OUTPUT_SCHEMA_REQUIRED")
        _require_text(self.schema_version, "schema_version", "LLM_SCHEMA_VERSION_REQUIRED")
        _require_text(self.trace_id, "trace_id", "LLM_TRACE_ID_REQUIRED")
        _require_text(self.request_id, "request_id", "LLM_REQUEST_ID_REQUIRED")
        _require_text(self.idempotency_key, "idempotency_key", "LLM_IDEMPOTENCY_KEY_REQUIRED")
        _require_text(self.prompt_id, "prompt_id", "LLM_PROMPT_ID_REQUIRED")
        _require_text(self.prompt_version, "prompt_version", "LLM_PROMPT_VERSION_REQUIRED")
        _require_mapping(self.sampling_parameters, "sampling_parameters", "LLM_SAMPLING_REQUIRED")

        forbidden_keys = sorted(set(self.sampling_parameters).intersection(_FORBIDDEN_SAMPLING_KEYS))
        if len(forbidden_keys) > 0:
            raise LLMGatewayContractError(
                "LLM_SAMPLING_PARAMETER_FORBIDDEN",
                f"Paramètres réservés au gateway: {', '.join(forbidden_keys)}",
            )


@dataclass(frozen=True)
class ModelProvenance:
    model_id: str
    model_revision: str
    runtime_version: str
    prompt_id: str
    prompt_version: str
    schema_version: str
    sampling_parameters: Mapping[str, Any]
    input_hash: str
    output_hash: str
    started_at: str
    completed_at: str


@dataclass(frozen=True)
class InferenceResult:
    structured_output: Mapping[str, Any]
    provenance: ModelProvenance
    raw_response_id: str


@dataclass(frozen=True)
class OpenAICompatibleResponse:
    payload: Mapping[str, Any]
    headers: Mapping[str, str]


class LocalLanguageModelGateway(Protocol):
    def infer(self, request: InferenceRequest) -> InferenceResult:
        raise NotImplementedError


class OpenAICompatibleTransport(Protocol):
    def post_chat_completion(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: int,
        tls_ca_bundle_path: str,
    ) -> OpenAICompatibleResponse:
        raise NotImplementedError


class OpenAICompatibleLocalLanguageModelGateway:
    def __init__(
        self,
        *,
        configuration: GatewayConfiguration,
        transport: OpenAICompatibleTransport,
    ) -> None:
        self._configuration = configuration
        self._transport = transport

    def infer(self, request: InferenceRequest) -> InferenceResult:
        started_at = _utc_now()
        body = build_openai_chat_completion_request(configuration=self._configuration, request=request)
        response = self._transport.post_chat_completion(
            base_url=self._configuration.base_url,
            headers=_build_headers(configuration=self._configuration, request=request),
            body=body,
            timeout_seconds=self._configuration.timeout_seconds,
            tls_ca_bundle_path=self._configuration.tls_ca_bundle_path,
        )
        structured_output = _extract_structured_output(response.payload)
        completed_at = _utc_now()
        provenance = _build_provenance(
            response=response,
            request=request,
            body=body,
            structured_output=structured_output,
            started_at=started_at,
            completed_at=completed_at,
        )
        return InferenceResult(
            structured_output=structured_output,
            provenance=provenance,
            raw_response_id=_required_payload_text(response.payload, "id", "LLM_RESPONSE_ID_MISSING"),
        )


class UrllibOpenAICompatibleTransport:
    def post_chat_completion(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: int,
        tls_ca_bundle_path: str,
    ) -> OpenAICompatibleResponse:
        url = f"{base_url.rstrip('/')}/chat/completions"
        request = urllib.request.Request(
            url=url,
            data=_canonical_json(body).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        context = ssl.create_default_context(cafile=tls_ca_bundle_path)
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context) as response:
            response_body = response.read().decode("utf-8")
            try:
                payload = json.loads(response_body)
            except JSONDecodeError as exc:
                raise LLMGatewayContractError(
                    "LLM_RESPONSE_INVALID_JSON",
                    "La réponse vLLM compatible OpenAI n'est pas un JSON syntaxiquement valide.",
                ) from exc
            if not isinstance(payload, Mapping):
                raise LLMGatewayContractError(
                    "LLM_RESPONSE_INVALID",
                    "La réponse vLLM compatible OpenAI doit être un objet JSON.",
                )
            return OpenAICompatibleResponse(
                payload=payload,
                headers={key.lower(): value for key, value in response.headers.items()},
            )


def build_openai_chat_completion_request(
    *,
    configuration: GatewayConfiguration,
    request: InferenceRequest,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": configuration.served_model,
        "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_name,
                "schema": dict(request.output_schema),
                "strict": True,
            },
        },
    }
    payload.update(dict(request.sampling_parameters))
    return payload


def _build_headers(
    *,
    configuration: GatewayConfiguration,
    request: InferenceRequest,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {configuration.api_key}",
        "Content-Type": "application/json",
        "X-OST-Client": GATEWAY_CLIENT_ID,
        "X-Trace-Id": request.trace_id,
        "X-Request-Id": request.request_id,
        "Idempotency-Key": request.idempotency_key,
    }


def _extract_structured_output(payload: Mapping[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        raise LLMGatewayContractError(
            "LLM_RESPONSE_CHOICE_MISSING",
            "La réponse compatible OpenAI ne contient aucun choix.",
        )

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_CHOICE_INVALID",
            "Le premier choix compatible OpenAI doit être un objet.",
        )

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_MESSAGE_MISSING",
            "Le premier choix compatible OpenAI ne contient pas de message.",
        )

    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        raise LLMGatewayContractError(
            "LLM_RESPONSE_CONTENT_MISSING",
            "Le message compatible OpenAI ne contient pas de sortie structurée.",
        )

    try:
        structured_output = json.loads(content)
    except JSONDecodeError as exc:
        raise LLMGatewayContractError(
            "LLM_RESPONSE_INVALID_JSON",
            "La sortie structurée du LLM n'est pas un JSON syntaxiquement valide.",
        ) from exc

    if not isinstance(structured_output, dict):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_INVALID_JSON",
            "La sortie structurée du LLM doit être un objet JSON.",
        )
    return structured_output


def _build_provenance(
    *,
    response: OpenAICompatibleResponse,
    request: InferenceRequest,
    body: Mapping[str, Any],
    structured_output: Mapping[str, Any],
    started_at: str,
    completed_at: str,
) -> ModelProvenance:
    model_id = _required_payload_text(response.payload, "model", "LLM_RESPONSE_PROVENANCE_MISSING")
    model_revision = _required_payload_text(
        response.payload,
        "model_revision",
        "LLM_RESPONSE_PROVENANCE_MISSING",
    )
    runtime_version = _required_payload_text(
        response.payload,
        "runtime_version",
        "LLM_RESPONSE_PROVENANCE_MISSING",
    )

    return ModelProvenance(
        model_id=model_id,
        model_revision=model_revision,
        runtime_version=runtime_version,
        prompt_id=request.prompt_id,
        prompt_version=request.prompt_version,
        schema_version=request.schema_version,
        sampling_parameters=dict(request.sampling_parameters),
        input_hash=_sha256_json(body),
        output_hash=_sha256_json(structured_output),
        started_at=started_at,
        completed_at=completed_at,
    )


def _required_payload_text(payload: Mapping[str, Any], field_name: str, code: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError(code, f"Champ de réponse requis absent: {field_name}")
    if value != value.strip():
        raise LLMGatewayContractError(code, f"Champ de réponse non normalisé: {field_name}")
    return value


def _require_text(value: object, field_name: str, code: str) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError(code, f"Champ requis absent: {field_name}")
    if value != value.strip():
        raise LLMGatewayContractError(code, f"Champ non normalisé: {field_name}")


def _require_mapping(value: object, field_name: str, code: str) -> None:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise LLMGatewayContractError(code, f"Objet requis absent: {field_name}")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


__all__ = [
    "GatewayConfiguration",
    "InferenceMessage",
    "InferenceRequest",
    "InferenceResult",
    "LLMGatewayContractError",
    "LocalLanguageModelGateway",
    "ModelProvenance",
    "OpenAICompatibleLocalLanguageModelGateway",
    "OpenAICompatibleResponse",
    "OpenAICompatibleTransport",
    "UrllibOpenAICompatibleTransport",
    "build_openai_chat_completion_request",
]
