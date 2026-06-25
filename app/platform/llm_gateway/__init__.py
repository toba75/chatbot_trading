"""Contrat technique du gateway LLM local M-002."""

from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from app.platform.observability import GatewayObservation, InMemoryObservabilityCollector, sha256_text


GATEWAY_CLIENT_ID = "llm-gateway"
SECRET_MASK = "<secret-masked>"
_FORBIDDEN_SAMPLING_KEYS = frozenset({"model", "messages", "response_format"})


class LLMGatewayContractError(ValueError):
    """Erreur technique explicite du contrat gateway LLM."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class SparkUnavailableError(ConnectionError):
    """Panne réseau ou indisponibilité du Spark avant le premier token."""


class SparkTLSCertificateInvalidError(ConnectionError):
    """Refus dur lié à un certificat Spark invalide."""


class SparkFirstTokenTimeoutError(TimeoutError):
    """Timeout avant réception du premier token."""


class SparkStreamingInterruptedError(RuntimeError):
    """Interruption après émission d'au moins un token."""

    def __init__(self, message: str, partial_output: str) -> None:
        super().__init__(message)
        _require_text(partial_output, "partial_output", "LLM_PARTIAL_OUTPUT_REQUIRED")
        self.partial_output = partial_output


class LLMGatewayInferenceError(RuntimeError):
    """Panne d'inférence explicite et non publiable par défaut."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool,
        retry_pending: bool,
        publishable: bool,
        business_state_changed: bool,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_pending = retry_pending
        self.publishable = publishable
        self.business_state_changed = business_state_changed


@dataclass(frozen=True)
class GatewayFailureClassification:
    code: str
    message: str
    retryable: bool
    before_first_token: bool
    publishable: bool


@dataclass(frozen=True)
class GatewayRetryPolicy:
    max_retries_before_first_token: int

    def __post_init__(self) -> None:
        if not isinstance(self.max_retries_before_first_token, int) or self.max_retries_before_first_token < 0:
            raise LLMGatewayContractError(
                "LLM_RETRY_POLICY_INVALID",
                "Le nombre de retries avant premier token doit être un entier positif ou nul.",
            )


@dataclass(frozen=True)
class GatewayCircuitBreakerPolicy:
    failure_threshold: int
    open_seconds: int

    def __post_init__(self) -> None:
        if not isinstance(self.failure_threshold, int) or self.failure_threshold <= 0:
            raise LLMGatewayContractError(
                "LLM_CIRCUIT_BREAKER_THRESHOLD_INVALID",
                "Le seuil du circuit breaker doit être un entier strictement positif.",
            )
        if not isinstance(self.open_seconds, int) or self.open_seconds <= 0:
            raise LLMGatewayContractError(
                "LLM_CIRCUIT_BREAKER_OPEN_SECONDS_INVALID",
                "La durée d'ouverture du circuit breaker doit être un entier strictement positif.",
            )


class GatewayClock(Protocol):
    def monotonic_seconds(self) -> float:
        raise NotImplementedError


class SystemGatewayClock:
    def monotonic_seconds(self) -> float:
        return time.monotonic()


@dataclass(frozen=True)
class GatewayFailureMetricEvent:
    status: str
    code: str
    trace_id: str
    request_id: str
    idempotency_key: str
    attempt: int
    retry_pending: bool
    circuit_open: bool
    message: str


class GatewayFailureMetricRecorder:
    def __init__(self, *, observability_collector: InMemoryObservabilityCollector) -> None:
        if not isinstance(observability_collector, InMemoryObservabilityCollector):
            raise LLMGatewayContractError(
                "LLM_OBSERVABILITY_COLLECTOR_INVALID",
                "Le recorder gateway exige un collecteur d'observabilite local explicite.",
            )
        self.events: list[GatewayFailureMetricEvent] = []
        self._observability_collector = observability_collector

    def record(self, event: GatewayFailureMetricEvent) -> None:
        self.events.append(event)

    def record_gateway_observation(self, observation: GatewayObservation) -> None:
        self._observability_collector.record_gateway_observation(observation)


class GatewayCircuitBreaker:
    def __init__(self, *, policy: GatewayCircuitBreakerPolicy, clock: GatewayClock) -> None:
        self._policy = policy
        self._clock = clock
        self._failure_count = 0
        self._opened_until: float | None = None

    def is_open(self) -> bool:
        if self._opened_until is None:
            return False
        if self._clock.monotonic_seconds() < self._opened_until:
            return True
        self._opened_until = None
        self._failure_count = 0
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_until = None

    def record_failure(self, classification: GatewayFailureClassification) -> None:
        if not classification.retryable or not classification.before_first_token:
            return
        self._failure_count += 1
        if self._failure_count >= self._policy.failure_threshold:
            self._opened_until = self._clock.monotonic_seconds() + self._policy.open_seconds


def classify_gateway_failure(error: BaseException) -> GatewayFailureClassification:
    if isinstance(error, SparkTLSCertificateInvalidError):
        return GatewayFailureClassification(
            code="LLM_TLS_CERTIFICATE_INVALID",
            message="Le certificat TLS de spark-inference est invalide.",
            retryable=False,
            before_first_token=True,
            publishable=False,
        )
    if isinstance(error, SparkFirstTokenTimeoutError):
        return GatewayFailureClassification(
            code="LLM_FIRST_TOKEN_TIMEOUT",
            message="Le délai avant le premier token Spark est dépassé.",
            retryable=True,
            before_first_token=True,
            publishable=False,
        )
    if isinstance(error, SparkStreamingInterruptedError):
        return GatewayFailureClassification(
            code="LLM_PARTIAL_OUTPUT",
            message="Le flux Spark est interrompu après le premier token; la sortie partielle est non publiable.",
            retryable=False,
            before_first_token=False,
            publishable=False,
        )
    if isinstance(error, SparkUnavailableError):
        return GatewayFailureClassification(
            code="LLM_UNAVAILABLE",
            message="spark-inference est indisponible avant le premier token.",
            retryable=True,
            before_first_token=True,
            publishable=False,
        )
    raise error


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


@dataclass(frozen=True)
class _GatewayTransportSuccess:
    response: OpenAICompatibleResponse
    attempt: int
    latency_ms: float


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
        retry_policy: GatewayRetryPolicy,
        circuit_breaker: GatewayCircuitBreaker,
        failure_metric_recorder: GatewayFailureMetricRecorder,
    ) -> None:
        self._configuration = configuration
        self._transport = transport
        self._retry_policy = retry_policy
        self._circuit_breaker = circuit_breaker
        self._failure_metric_recorder = failure_metric_recorder

    def infer(self, request: InferenceRequest) -> InferenceResult:
        started_at = _utc_now()
        body = build_openai_chat_completion_request(configuration=self._configuration, request=request)
        headers = _build_headers(configuration=self._configuration, request=request)
        transport_success = self._post_chat_completion_with_failure_policy(
            request=request,
            headers=headers,
            body=body,
        )
        response = transport_success.response
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
        self._failure_metric_recorder.record_gateway_observation(
            _build_gateway_observation(
                configuration=self._configuration,
                request=request,
                body=body,
                status="SUCCEEDED",
                latency_ms=transport_success.latency_ms,
                response_payload=response.payload,
                model_revision=provenance.model_revision,
                runtime_version=provenance.runtime_version,
                ttft_ms=transport_success.latency_ms,
                retry_count=transport_success.attempt - 1,
                circuit_open=False,
                output_interrupted=False,
                error_code=None,
            )
        )
        return InferenceResult(
            structured_output=structured_output,
            provenance=provenance,
            raw_response_id=_required_payload_text(response.payload, "id", "LLM_RESPONSE_ID_MISSING"),
        )

    def _post_chat_completion_with_failure_policy(
        self,
        *,
        request: InferenceRequest,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
    ) -> _GatewayTransportSuccess:
        if self._circuit_breaker.is_open():
            error = LLMGatewayInferenceError(
                code="LLM_CIRCUIT_OPEN",
                message="Le circuit breaker du gateway LLM refuse l'appel Spark.",
                retryable=False,
                retry_pending=False,
                publishable=False,
                business_state_changed=False,
            )
            self._failure_metric_recorder.record(
                _build_failure_metric_event(
                    request=request,
                    status=error.code,
                    code=error.code,
                    message=error.message,
                    attempt=0,
                    retry_pending=False,
                    circuit_open=True,
                )
            )
            self._failure_metric_recorder.record_gateway_observation(
                _build_gateway_observation(
                    configuration=self._configuration,
                    request=request,
                    body=body,
                    status=error.code,
                    latency_ms=0.0,
                    response_payload=None,
                    model_revision=None,
                    runtime_version=None,
                    ttft_ms=None,
                    retry_count=0,
                    circuit_open=True,
                    output_interrupted=False,
                    error_code=error.code,
                )
            )
            raise error

        max_attempts = self._retry_policy.max_retries_before_first_token + 1
        for attempt in range(1, max_attempts + 1):
            attempt_started_ns = time.perf_counter_ns()
            try:
                response = self._transport.post_chat_completion(
                    base_url=self._configuration.base_url,
                    headers=headers,
                    body=body,
                    timeout_seconds=self._configuration.timeout_seconds,
                    tls_ca_bundle_path=self._configuration.tls_ca_bundle_path,
                )
            except (
                SparkUnavailableError,
                SparkFirstTokenTimeoutError,
                SparkTLSCertificateInvalidError,
                SparkStreamingInterruptedError,
            ) as exc:
                latency_ms = _elapsed_ms_since(attempt_started_ns)
                classification = classify_gateway_failure(exc)
                self._circuit_breaker.record_failure(classification)
                retry_pending = (
                    classification.retryable
                    and classification.before_first_token
                    and attempt <= self._retry_policy.max_retries_before_first_token
                    and not self._circuit_breaker.is_open()
                )
                self._failure_metric_recorder.record(
                    _build_failure_metric_event(
                        request=request,
                        status="RETRY_PENDING" if retry_pending else classification.code,
                        code=classification.code,
                        message=classification.message,
                        attempt=attempt,
                        retry_pending=retry_pending,
                        circuit_open=self._circuit_breaker.is_open(),
                    )
                )
                self._failure_metric_recorder.record_gateway_observation(
                    _build_gateway_observation(
                        configuration=self._configuration,
                        request=request,
                        body=body,
                        status="RETRY_PENDING" if retry_pending else classification.code,
                        latency_ms=latency_ms,
                        response_payload=None,
                        model_revision=None,
                        runtime_version=None,
                        ttft_ms=latency_ms if not classification.before_first_token else None,
                        retry_count=1 if retry_pending else attempt - 1,
                        circuit_open=self._circuit_breaker.is_open(),
                        output_interrupted=not classification.before_first_token,
                        error_code=classification.code,
                    )
                )
                if retry_pending:
                    continue
                raise LLMGatewayInferenceError(
                    code=classification.code,
                    message=classification.message,
                    retryable=classification.retryable,
                    retry_pending=False,
                    publishable=classification.publishable,
                    business_state_changed=False,
                ) from exc
            self._circuit_breaker.record_success()
            return _GatewayTransportSuccess(
                response=response,
                attempt=attempt,
                latency_ms=_elapsed_ms_since(attempt_started_ns),
            )

        raise LLMGatewayContractError(
            "LLM_RETRY_LOOP_EXHAUSTED",
            "La boucle de retry gateway s'est terminee sans reponse ni erreur explicite.",
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
        try:
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
        except ssl.SSLCertVerificationError as exc:
            raise SparkTLSCertificateInvalidError("Certificat TLS Spark invalide.") from exc
        except TimeoutError as exc:
            raise SparkFirstTokenTimeoutError("Timeout avant le premier token Spark.") from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise SparkTLSCertificateInvalidError("Certificat TLS Spark invalide.") from exc
            if isinstance(reason, TimeoutError):
                raise SparkFirstTokenTimeoutError("Timeout avant le premier token Spark.") from exc
            raise SparkUnavailableError("spark-inference indisponible.") from exc


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


def _build_failure_metric_event(
    *,
    request: InferenceRequest,
    status: str,
    code: str,
    message: str,
    attempt: int,
    retry_pending: bool,
    circuit_open: bool,
) -> GatewayFailureMetricEvent:
    return GatewayFailureMetricEvent(
        status=status,
        code=code,
        trace_id=request.trace_id,
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        attempt=attempt,
        retry_pending=retry_pending,
        circuit_open=circuit_open,
        message=message,
    )


def _build_gateway_observation(
    *,
    configuration: GatewayConfiguration,
    request: InferenceRequest,
    body: Mapping[str, Any],
    status: str,
    latency_ms: float,
    response_payload: Mapping[str, Any] | None,
    model_revision: str | None,
    runtime_version: str | None,
    ttft_ms: float | None,
    retry_count: int,
    circuit_open: bool,
    output_interrupted: bool,
    error_code: str | None,
) -> GatewayObservation:
    return GatewayObservation(
        trace_id=request.trace_id,
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        phase="spark_inference",
        status=status,
        latency_ms=latency_ms,
        served_model=configuration.served_model,
        model_revision=model_revision,
        runtime_version=runtime_version,
        prompt_hash=_prompt_hash(request),
        request_payload_bytes=_payload_size_bytes(body),
        response_payload_bytes=None if response_payload is None else _payload_size_bytes(response_payload),
        ttft_ms=ttft_ms,
        retry_count=retry_count,
        circuit_open=circuit_open,
        output_interrupted=output_interrupted,
        error_code=error_code,
    )


def _prompt_hash(request: InferenceRequest) -> str:
    prompt_payload = {
        "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        "prompt_id": request.prompt_id,
        "prompt_version": request.prompt_version,
    }
    return sha256_text(_canonical_json(prompt_payload))


def _payload_size_bytes(payload: Mapping[str, Any]) -> int:
    return len(_canonical_json(payload).encode("utf-8"))


def _elapsed_ms_since(started_ns: int) -> float:
    elapsed_ns = time.perf_counter_ns() - started_ns
    if elapsed_ns < 0:
        raise LLMGatewayContractError(
            "LLM_GATEWAY_CLOCK_INVALID",
            "L'horloge monotone du gateway a produit une duree negative.",
        )
    return elapsed_ns / 1_000_000


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
    "GatewayCircuitBreaker",
    "GatewayCircuitBreakerPolicy",
    "GatewayFailureClassification",
    "GatewayFailureMetricEvent",
    "GatewayFailureMetricRecorder",
    "GatewayRetryPolicy",
    "GatewayConfiguration",
    "InferenceMessage",
    "InferenceRequest",
    "InferenceResult",
    "LLMGatewayContractError",
    "LLMGatewayInferenceError",
    "LocalLanguageModelGateway",
    "ModelProvenance",
    "OpenAICompatibleLocalLanguageModelGateway",
    "OpenAICompatibleResponse",
    "OpenAICompatibleTransport",
    "SparkFirstTokenTimeoutError",
    "SparkStreamingInterruptedError",
    "SparkTLSCertificateInvalidError",
    "SparkUnavailableError",
    "SystemGatewayClock",
    "UrllibOpenAICompatibleTransport",
    "build_openai_chat_completion_request",
    "classify_gateway_failure",
]
