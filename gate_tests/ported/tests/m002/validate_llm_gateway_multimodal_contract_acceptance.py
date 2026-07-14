from __future__ import annotations

from base64 import b64encode
from hashlib import sha256

from app.platform import local_runtime
from app.platform.llm_gateway import (
    GatewayCircuitBreaker,
    GatewayCircuitBreakerPolicy,
    GatewayConfiguration,
    GatewayFailureMetricRecorder,
    GatewayRetryPolicy,
    InferenceImage,
    InferenceImageMessage,
    OpenAICompatibleLocalLanguageModelGateway,
    OpenAICompatibleResponse,
    build_openai_chat_completion_request,
)
from app.platform.observability import InMemoryObservabilityCollector


class ManualClock:
    def monotonic_seconds(self) -> float:
        return 0.0


class ControlledOpenAITransport:
    def __init__(self) -> None:
        self.body: dict[str, object] | None = None

    def post_chat_completion(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        body: dict[str, object],
        timeout_seconds: int,
        tls_ca_bundle_path: str | None,
    ) -> OpenAICompatibleResponse:
        del base_url, headers, timeout_seconds, tls_ca_bundle_path
        self.body = body
        return OpenAICompatibleResponse(
            payload={
                "id": "chatcmpl-vision-contract",
                "model": "gemma-vision",
                "model_revision": "gemma-4-vision-revision",
                "runtime_version": "vllm-vision-runtime",
                "choices": [{"message": {"content": '{"text":"Trading on Momentum"}'}}],
            },
            headers={},
        )


def test_validate_llm_gateway_multimodal_contract_acceptance() -> None:
    """Given une page PNG hachée, When elle transite par le gateway, Then le Spark reçoit une requête image OpenAI compatible."""

    image_bytes = b"\x89PNG\r\n\x1a\nvisible-page"
    image = InferenceImage(
        media_type="image/png",
        data_base64=b64encode(image_bytes).decode("ascii"),
        sha256=sha256(image_bytes).hexdigest(),
    )
    request = local_runtime._build_inference_request(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extraire exclusivement le texte visible."},
                        {
                            "type": "image",
                            "media_type": image.media_type,
                            "data_base64": image.data_base64,
                            "sha256": image.sha256,
                        },
                    ],
                }
            ],
            "output_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
                "additionalProperties": False,
            },
            "schema_name": "page_text_extraction",
            "schema_version": "page_text_extraction.v1",
            "trace_id": "trace-multimodal-contract",
            "request_id": "request-multimodal-contract",
            "idempotency_key": "idem-multimodal-contract",
            "prompt_id": "prompt-page-text-extraction",
            "prompt_version": "1",
            "sampling_parameters": {"temperature": 0, "top_p": 1},
        }
    )

    message = request.messages[0]
    assert isinstance(message, InferenceImageMessage)
    assert message.images == (image,)

    configuration = GatewayConfiguration(
        base_url="http://spark-inference.test:8000/v1",
        served_model="gemma-vision",
        model_revision="gemma-4-vision-declared-revision",
        runtime_version="vllm-vision-declared-runtime",
        configuration_hash="c" * 64,
        auth_mode="none",
        api_key=None,
        tls_mode="disabled",
        tls_ca_bundle_path=None,
        timeout_seconds=7,
    )
    payload = build_openai_chat_completion_request(
        configuration=configuration,
        request=request,
    )
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extraire exclusivement le texte visible."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image.data_base64}",
                    },
                },
            ],
        }
    ]

    transport = ControlledOpenAITransport()
    gateway = OpenAICompatibleLocalLanguageModelGateway(
        configuration=configuration,
        transport=transport,
        retry_policy=GatewayRetryPolicy(max_retries_before_first_token=0),
        circuit_breaker=GatewayCircuitBreaker(
            policy=GatewayCircuitBreakerPolicy(failure_threshold=3, open_seconds=30),
            clock=ManualClock(),
        ),
        failure_metric_recorder=GatewayFailureMetricRecorder(
            observability_collector=InMemoryObservabilityCollector(),
        ),
    )

    result = gateway.infer(request)
    assert result.structured_output == {"text": "Trading on Momentum"}
    assert transport.body == payload
