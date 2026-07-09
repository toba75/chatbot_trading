"""Contrat technique du gateway LLM local M-002."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecodeError
from types import MappingProxyType
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from app.platform.observability import GatewayObservation, InMemoryObservabilityCollector, sha256_text


GATEWAY_CLIENT_ID = "llm-gateway"
SECRET_MASK = "<secret-masked>"
_FORBIDDEN_SAMPLING_KEYS = frozenset({"model", "messages", "response_format"})
_ALLOWED_SPARK_HOSTS = frozenset({"spark-inference", "spark-inference.test"})
_SPARK_API_PATH = "/v1"
_AUTH_MODE_NONE = "none"
_AUTH_MODE_API_KEY_FILE = "api_key_file"
_TLS_MODE_DISABLED = "disabled"
_TLS_MODE_CA_BUNDLE = "ca_bundle"
_MODEL_REVISION_HEADER = "x-model-revision"
_RUNTIME_VERSION_HEADER = "x-runtime-version"
_TTFT_HEADER = "x-ttft-ms"


class LLMGatewayContractError(ValueError):
    """Erreur technique explicite du contrat gateway LLM."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class SparkUnavailableError(ConnectionError):
    """Panne réseau ou indisponibilité du Spark avant le premier token."""


class SparkAuthenticationError(ConnectionError):
    """Refus d'authentification explicite du Spark."""


class SparkHTTPStatusError(ConnectionError):
    """Réponse HTTP Spark non nominale avant le premier token."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        if not isinstance(status_code, int) or status_code <= 0:
            raise LLMGatewayContractError(
                "LLM_SPARK_HTTP_STATUS_INVALID",
                "Le statut HTTP Spark doit être un entier strictement positif.",
            )
        self.status_code = status_code


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
    if isinstance(error, SparkAuthenticationError):
        return GatewayFailureClassification(
            code="LLM_AUTHENTICATION_FAILED",
            message="L'authentification du gateway LLM auprès du Spark est refusée.",
            retryable=False,
            before_first_token=True,
            publishable=False,
        )
    if isinstance(error, SparkHTTPStatusError):
        retryable = error.status_code == 429 or error.status_code >= 500
        return GatewayFailureClassification(
            code="LLM_SPARK_HTTP_ERROR",
            message=f"Le Spark retourne un statut HTTP non nominal: {error.status_code}.",
            retryable=retryable,
            before_first_token=True,
            publishable=False,
        )
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
    model_revision: str
    runtime_version: str
    auth_mode: str
    api_key: str | None
    tls_mode: str
    tls_ca_bundle_path: str | None
    timeout_seconds: int

    def __post_init__(self) -> None:
        _require_text(self.base_url, "base_url", "LLM_GATEWAY_BASE_URL_REQUIRED")
        _require_text(self.served_model, "served_model", "LLM_GATEWAY_MODEL_REQUIRED")
        _require_text(self.model_revision, "model_revision", "LLM_GATEWAY_MODEL_REVISION_REQUIRED")
        _require_text(self.runtime_version, "runtime_version", "LLM_GATEWAY_RUNTIME_VERSION_REQUIRED")
        _require_text(self.auth_mode, "auth_mode", "LLM_GATEWAY_AUTH_MODE_REQUIRED")
        _require_text(self.tls_mode, "tls_mode", "LLM_GATEWAY_TLS_MODE_REQUIRED")

        if self.auth_mode not in {_AUTH_MODE_NONE, _AUTH_MODE_API_KEY_FILE}:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_AUTH_MODE_REQUIRED",
                "Le mode d'authentification Spark du gateway LLM est invalide.",
            )
        if self.tls_mode not in {_TLS_MODE_DISABLED, _TLS_MODE_CA_BUNDLE}:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_MODE_REQUIRED",
                "Le mode TLS Spark du gateway LLM est invalide.",
            )
        if self.auth_mode == _AUTH_MODE_NONE and self.api_key is not None:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_API_KEY_FORBIDDEN",
                "La clé API Spark est interdite quand auth_mode vaut none.",
            )
        if self.auth_mode == _AUTH_MODE_API_KEY_FILE:
            _require_text(self.api_key, "api_key", "LLM_GATEWAY_API_KEY_REQUIRED")
        if self.tls_mode == _TLS_MODE_DISABLED and self.tls_ca_bundle_path is not None:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_CA_FORBIDDEN",
                "Le bundle CA Spark est interdit quand tls_mode vaut disabled.",
            )
        if self.tls_mode == _TLS_MODE_CA_BUNDLE:
            _require_text(self.tls_ca_bundle_path, "tls_ca_bundle_path", "LLM_GATEWAY_TLS_CA_REQUIRED")

        parsed_base_url = urlparse(self.base_url)
        if parsed_base_url.scheme not in {"http", "https"} or parsed_base_url.netloc == "":
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "Le gateway LLM exige une URL Spark explicite.",
            )
        if self.tls_mode == _TLS_MODE_DISABLED and parsed_base_url.scheme != "http":
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_MODE_REQUIRED",
                "Le mode TLS disabled exige une URL Spark HTTP explicite.",
            )
        if self.tls_mode == _TLS_MODE_CA_BUNDLE and parsed_base_url.scheme != "https":
            raise LLMGatewayContractError(
                "LLM_GATEWAY_TLS_REQUIRED",
                "Le mode TLS ca_bundle exige une URL Spark HTTPS explicite.",
            )
        if parsed_base_url.username is not None or parsed_base_url.password is not None:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "L'URL Spark du gateway LLM ne doit pas contenir d'identifiant.",
            )
        if parsed_base_url.path != _SPARK_API_PATH:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "Le gateway LLM doit cibler le chemin Spark /v1.",
            )
        if not _is_allowed_spark_host(parsed_base_url.hostname):
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "Le gateway LLM doit cibler explicitement spark-inference ou une adresse privée Spark.",
            )
        try:
            parsed_port = parsed_base_url.port
        except ValueError as exc:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "Le port Spark du gateway LLM est invalide.",
            ) from exc
        if parsed_port is None or parsed_port <= 0 or parsed_port > 65535:
            raise LLMGatewayContractError(
                "LLM_GATEWAY_SPARK_ENDPOINT_REQUIRED",
                "Le port Spark du gateway LLM est invalide.",
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
            "model_revision": self.model_revision,
            "runtime_version": self.runtime_version,
            "auth_mode": self.auth_mode,
            "api_key": SECRET_MASK if self.api_key is not None else None,
            "tls_mode": self.tls_mode,
            "tls_ca_bundle_path": self.tls_ca_bundle_path,
            "timeout_seconds": self.timeout_seconds,
        }

    def __repr__(self) -> str:
        return f"GatewayConfiguration({self.masked_for_logs()!r})"


def _is_allowed_spark_host(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname in _ALLOWED_SPARK_HOSTS:
        return True
    try:
        parsed_ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return parsed_ip.is_private


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
        object.__setattr__(self, "output_schema", _freeze_json_value(self.output_schema, "output_schema"))
        object.__setattr__(
            self,
            "sampling_parameters",
            _freeze_json_value(self.sampling_parameters, "sampling_parameters"),
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
    ttft_ms: float | None


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
        tls_ca_bundle_path: str | None,
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
        try:
            structured_output = _extract_structured_output(response.payload, request.output_schema)
            completed_at = _utc_now()
            provenance = _build_provenance(
                configuration=self._configuration,
                response=response,
                request=request,
                body=body,
                structured_output=structured_output,
                started_at=started_at,
                completed_at=completed_at,
            )
        except SparkStreamingInterruptedError as exc:
            classification = classify_gateway_failure(exc)
            self._failure_metric_recorder.record_gateway_observation(
                _build_gateway_observation(
                    configuration=self._configuration,
                    request=request,
                    body=body,
                    status=classification.code,
                    latency_ms=transport_success.latency_ms,
                    response_payload=response.payload,
                    model_revision=_optional_response_text(response, "model_revision"),
                    runtime_version=_optional_response_text(response, "runtime_version"),
                    ttft_ms=transport_success.ttft_ms,
                    retry_count=transport_success.attempt - 1,
                    circuit_open=False,
                    output_interrupted=True,
                    error_code=classification.code,
                )
            )
            raise LLMGatewayInferenceError(
                code=classification.code,
                message=classification.message,
                retryable=classification.retryable,
                retry_pending=False,
                publishable=classification.publishable,
                business_state_changed=False,
            ) from exc
        except LLMGatewayContractError as exc:
            self._failure_metric_recorder.record_gateway_observation(
                _build_gateway_observation(
                    configuration=self._configuration,
                    request=request,
                    body=body,
                    status=exc.code,
                    latency_ms=transport_success.latency_ms,
                    response_payload=response.payload,
                    model_revision=_optional_response_text(response, "model_revision"),
                    runtime_version=_optional_response_text(response, "runtime_version"),
                    ttft_ms=transport_success.ttft_ms,
                    retry_count=transport_success.attempt - 1,
                    circuit_open=False,
                    output_interrupted=False,
                    error_code=exc.code,
                )
            )
            raise LLMGatewayInferenceError(
                code=exc.code,
                message=exc.message,
                retryable=False,
                retry_pending=False,
                publishable=False,
                business_state_changed=False,
            ) from exc
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
                ttft_ms=transport_success.ttft_ms,
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
        circuit_refusal_started_ns = time.perf_counter_ns()
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
                    latency_ms=_elapsed_ms_since(circuit_refusal_started_ns),
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
                SparkAuthenticationError,
                SparkHTTPStatusError,
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
                        ttft_ms=None,
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
                ttft_ms=_ttft_ms_from_headers(response.headers),
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
        tls_ca_bundle_path: str | None,
    ) -> OpenAICompatibleResponse:
        url = f"{base_url.rstrip('/')}/chat/completions"
        request = urllib.request.Request(
            url=url,
            data=_canonical_json(body).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            if tls_ca_bundle_path is None:
                response_context = urllib.request.urlopen(request, timeout=timeout_seconds)
            else:
                context = ssl.create_default_context(cafile=tls_ca_bundle_path)
                response_context = urllib.request.urlopen(request, timeout=timeout_seconds, context=context)
            with response_context as response:
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
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise SparkAuthenticationError("Authentification Spark refusée.") from exc
            raise SparkHTTPStatusError("Statut HTTP Spark non nominal.", status_code=exc.code) from exc
        except ssl.SSLCertVerificationError as exc:
            raise SparkTLSCertificateInvalidError("Certificat TLS Spark invalide.") from exc
        except (FileNotFoundError, ssl.SSLError) as exc:
            raise SparkTLSCertificateInvalidError("Bundle CA Spark invalide.") from exc
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
                "schema": _thaw_json_value(request.output_schema),
                "strict": True,
            },
        },
    }
    payload.update(_thaw_json_value(request.sampling_parameters))
    return payload


def _build_headers(
    *,
    configuration: GatewayConfiguration,
    request: InferenceRequest,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-OST-Client": GATEWAY_CLIENT_ID,
        "X-Trace-Id": request.trace_id,
        "X-Request-Id": request.request_id,
        "Idempotency-Key": request.idempotency_key,
    }
    if configuration.auth_mode == _AUTH_MODE_API_KEY_FILE:
        headers["Authorization"] = f"Bearer {configuration.api_key}"
    return headers


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


def _extract_structured_output(payload: Mapping[str, Any], output_schema: Mapping[str, Any]) -> dict[str, Any]:
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

    finish_reason = first_choice.get("finish_reason")
    if finish_reason is not None and finish_reason != "stop":
        partial_output = "sortie partielle non journalisée"
        message = first_choice.get("message")
        if isinstance(message, Mapping) and isinstance(message.get("content"), str):
            partial_output = message["content"]
        raise SparkStreamingInterruptedError(
            "Le Spark a terminé la génération sans statut stop.",
            partial_output=partial_output,
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
    _validate_structured_output_schema(structured_output, output_schema)
    return structured_output


def _build_provenance(
    *,
    configuration: GatewayConfiguration,
    response: OpenAICompatibleResponse,
    request: InferenceRequest,
    body: Mapping[str, Any],
    structured_output: Mapping[str, Any],
    started_at: str,
    completed_at: str,
) -> ModelProvenance:
    model_id = _required_payload_text(response.payload, "model", "LLM_RESPONSE_PROVENANCE_MISSING")
    model_revision = _response_or_declared_text(
        response=response,
        field_name="model_revision",
        header_name=_MODEL_REVISION_HEADER,
        declared_value=configuration.model_revision,
    )
    runtime_version = _response_or_declared_text(
        response=response,
        field_name="runtime_version",
        header_name=_RUNTIME_VERSION_HEADER,
        declared_value=configuration.runtime_version,
    )

    return ModelProvenance(
        model_id=model_id,
        model_revision=model_revision,
        runtime_version=runtime_version,
        prompt_id=request.prompt_id,
        prompt_version=request.prompt_version,
        schema_version=request.schema_version,
        sampling_parameters=_thaw_json_value(request.sampling_parameters),
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


def _response_or_declared_text(
    *,
    response: OpenAICompatibleResponse,
    field_name: str,
    header_name: str,
    declared_value: str,
) -> str:
    if field_name in response.payload:
        return _required_provenance_text(response.payload[field_name], field_name)
    if header_name in response.headers:
        return _required_provenance_text(response.headers[header_name], field_name)
    return declared_value


def _required_provenance_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError("LLM_RESPONSE_PROVENANCE_MISSING", f"Champ de réponse requis absent: {field_name}")
    if value != value.strip():
        raise LLMGatewayContractError("LLM_RESPONSE_PROVENANCE_MISSING", f"Champ de réponse non normalisé: {field_name}")
    return value


def _optional_response_text(response: OpenAICompatibleResponse, field_name: str) -> str | None:
    value = response.payload.get(field_name)
    if value is None:
        header_name = _MODEL_REVISION_HEADER if field_name == "model_revision" else _RUNTIME_VERSION_HEADER
        value = response.headers.get(header_name)
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() == "":
        return None
    if value != value.strip():
        return None
    return value


def _require_text(value: object, field_name: str, code: str) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise LLMGatewayContractError(code, f"Champ requis absent: {field_name}")
    if value != value.strip():
        raise LLMGatewayContractError(code, f"Champ non normalisé: {field_name}")


def _require_mapping(value: object, field_name: str, code: str) -> None:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise LLMGatewayContractError(code, f"Objet requis absent: {field_name}")


def _validate_structured_output_schema(output: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if schema.get("type") != "object":
        raise LLMGatewayContractError(
            "LLM_RESPONSE_SCHEMA_INVALID",
            "Le schéma de sortie local doit être un objet JSON Schema.",
        )

    required = schema.get("required", ())
    if not isinstance(required, (list, tuple)):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_SCHEMA_INVALID",
            "Le champ required du schéma de sortie doit être une liste.",
        )
    for field_name in required:
        if not isinstance(field_name, str) or field_name.strip() == "":
            raise LLMGatewayContractError(
                "LLM_RESPONSE_SCHEMA_INVALID",
                "Le champ required du schéma de sortie contient une entrée invalide.",
            )
        if field_name not in output:
            raise LLMGatewayContractError(
                "LLM_RESPONSE_SCHEMA_INVALID",
                f"Champ de sortie requis absent: {field_name}",
            )

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_SCHEMA_INVALID",
            "Le champ properties du schéma de sortie doit être un objet.",
        )

    if schema.get("additionalProperties") is False:
        allowed_fields = set(properties)
        extra_fields = sorted(set(output).difference(allowed_fields))
        if len(extra_fields) > 0:
            raise LLMGatewayContractError(
                "LLM_RESPONSE_SCHEMA_INVALID",
                f"Champs de sortie non déclarés: {', '.join(extra_fields)}",
            )

    for field_name, property_schema in properties.items():
        if field_name not in output:
            continue
        if not isinstance(property_schema, Mapping):
            raise LLMGatewayContractError(
                "LLM_RESPONSE_SCHEMA_INVALID",
                f"Schéma de propriété invalide: {field_name}",
            )
        _validate_json_type(output[field_name], property_schema.get("type"), field_name)


def _validate_json_type(value: Any, expected_type: Any, field_name: str) -> None:
    if expected_type is None:
        return
    type_validators = {
        "string": lambda item: isinstance(item, str),
        "number": lambda item: (isinstance(item, (int, float)) and not isinstance(item, bool)),
        "integer": lambda item: (isinstance(item, int) and not isinstance(item, bool)),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, Mapping),
        "array": lambda item: isinstance(item, list),
    }
    validator = type_validators.get(expected_type)
    if validator is None:
        raise LLMGatewayContractError(
            "LLM_RESPONSE_SCHEMA_INVALID",
            f"Type JSON Schema non supporté: {expected_type}",
        )
    if not validator(value):
        raise LLMGatewayContractError(
            "LLM_RESPONSE_SCHEMA_INVALID",
            f"Type de sortie invalide pour {field_name}: {expected_type}",
        )


def _ttft_ms_from_headers(headers: Mapping[str, str]) -> float | None:
    raw_value = headers.get(_TTFT_HEADER)
    if raw_value is None:
        return None
    try:
        parsed_value = float(raw_value)
    except ValueError as exc:
        raise LLMGatewayContractError(
            "LLM_RESPONSE_TTFT_INVALID",
            "Le header TTFT Spark doit être numérique.",
        ) from exc
    if parsed_value < 0:
        raise LLMGatewayContractError(
            "LLM_RESPONSE_TTFT_INVALID",
            "Le header TTFT Spark doit être positif ou nul.",
        )
    return parsed_value


def _freeze_json_value(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        frozen_values = {}
        for key, item in value.items():
            if not isinstance(key, str) or key.strip() == "":
                raise LLMGatewayContractError(
                    "LLM_JSON_MAPPING_INVALID",
                    f"Clé JSON invalide pour {field_name}.",
                )
            frozen_values[key] = _freeze_json_value(item, f"{field_name}.{key}")
        return MappingProxyType(frozen_values)
    if isinstance(value, tuple):
        return tuple(_freeze_json_value(item, field_name) for item in value)
    if isinstance(value, list):
        return tuple(_freeze_json_value(item, field_name) for item in value)
    return value


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    if isinstance(value, list):
        return [_thaw_json_value(item) for item in value]
    return value


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
    "SparkAuthenticationError",
    "SparkFirstTokenTimeoutError",
    "SparkHTTPStatusError",
    "SparkStreamingInterruptedError",
    "SparkTLSCertificateInvalidError",
    "SparkUnavailableError",
    "SystemGatewayClock",
    "UrllibOpenAICompatibleTransport",
    "build_openai_chat_completion_request",
    "classify_gateway_failure",
]
