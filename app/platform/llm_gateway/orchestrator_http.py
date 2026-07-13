"""Adaptateur HTTP du port d'inférence utilisé par l'orchestrateur."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from app.contracts.llm_inference import (
    LlmInferenceRequest,
    LlmInferenceResponse,
)


class UrllibLlmInferenceGateway:
    def __init__(self, *, endpoint_url: str, timeout_seconds: int) -> None:
        if (
            not isinstance(endpoint_url, str)
            or endpoint_url.strip() == ""
            or endpoint_url != endpoint_url.strip()
            or not endpoint_url.endswith("/v1/infer")
        ):
            raise ValueError("endpoint LLM gateway invalide")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or timeout_seconds < 1
        ):
            raise ValueError("timeout LLM gateway invalide")
        self._endpoint_url = endpoint_url
        self._timeout_seconds = timeout_seconds

    def infer(self, request: LlmInferenceRequest) -> LlmInferenceResponse:
        if not isinstance(request, LlmInferenceRequest):
            raise TypeError("requête d'inférence invalide")
        http_request = urllib.request.Request(
            self._endpoint_url,
            data=json.dumps(
                request.to_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Trace-ID": request.trace_id,
            },
            method="POST",
        )
        started_ns = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                try:
                    payload = _json_object(response.read())
                except ValueError:
                    return LlmInferenceResponse(
                        status_code=502,
                        payload={"error_code": "LLM_GATEWAY_RESPONSE_INVALID"},
                        latency_ms=_elapsed_ms(started_ns),
                    )
                return LlmInferenceResponse(
                    status_code=response.status,
                    payload=payload,
                    latency_ms=_elapsed_ms(started_ns),
                )
        except urllib.error.HTTPError as error:
            try:
                payload = _json_object(error.read())
            except ValueError:
                payload = {
                    "error_code": "LLM_GATEWAY_HTTP_ERROR",
                    "status_code": error.code,
                }
            return LlmInferenceResponse(
                status_code=error.code,
                payload=payload,
                latency_ms=_elapsed_ms(started_ns),
            )
        except (TimeoutError, urllib.error.URLError, OSError):
            return LlmInferenceResponse(
                status_code=502,
                payload={"error_code": "LLM_GATEWAY_UNAVAILABLE"},
                latency_ms=_elapsed_ms(started_ns),
            )


def _json_object(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("LLM_GATEWAY_RESPONSE_INVALID") from error
    if not isinstance(payload, dict):
        raise ValueError("LLM_GATEWAY_RESPONSE_INVALID")
    return payload


def _elapsed_ms(started_ns: int) -> float:
    elapsed = time.perf_counter_ns() - started_ns
    if elapsed < 0:
        raise RuntimeError("LLM_GATEWAY_MONOTONIC_CLOCK_INVALID")
    return elapsed / 1_000_000


__all__ = ["UrllibLlmInferenceGateway"]
