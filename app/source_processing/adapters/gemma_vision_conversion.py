"""Adaptateur isolé de récupération Gemma Vision après un échec Granite tracé."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class GemmaVisionConversionError(RuntimeError):
    """Erreur stable de l'unique tentative Gemma autorisée par ADR-036."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or code.strip() == "" or code != code.strip():
            raise ValueError("code Gemma Vision invalide")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class GemmaVisionConversionRequest:
    document_id: str
    processing_run_id: str
    source_sha256: str
    source_pdf_path: Path
    page_number: int
    source_page_number: int
    route_name: str
    routing_policy_version: str
    gateway_endpoint_url: str
    gateway_timeout_seconds: int
    expected_model_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "processing_run_id",
            "source_sha256",
            "route_name",
            "routing_policy_version",
            "gateway_endpoint_url",
            "expected_model_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or value.strip() == "" or value != value.strip():
                raise ValueError(f"{field_name} invalide")
        if len(self.source_sha256) != 64 or any(character not in "0123456789abcdef" for character in self.source_sha256):
            raise ValueError("source_sha256 invalide")
        if not isinstance(self.source_pdf_path, Path):
            raise ValueError("source_pdf_path invalide")
        for field_name in ("page_number", "source_page_number", "gateway_timeout_seconds"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} invalide")
        if not self.gateway_endpoint_url.endswith("/v1/infer"):
            raise ValueError("gateway_endpoint_url invalide")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "source_sha256": self.source_sha256,
            "source_pdf_path": str(self.source_pdf_path.resolve()),
            "page_number": self.page_number,
            "source_page_number": self.source_page_number,
            "route_name": self.route_name,
            "routing_policy_version": self.routing_policy_version,
            "gateway_endpoint_url": self.gateway_endpoint_url,
            "gateway_timeout_seconds": self.gateway_timeout_seconds,
            "expected_model_id": self.expected_model_id,
        }


@dataclass(frozen=True)
class GemmaVisionPageItem:
    text: str
    bbox: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or self.text.strip() == "" or self.text != self.text.strip():
            raise ValueError("texte Gemma Vision invalide")
        if not isinstance(self.bbox, tuple) or len(self.bbox) != 4:
            raise ValueError("bbox Gemma Vision invalide")
        for coordinate in self.bbox:
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                raise ValueError("bbox Gemma Vision invalide")
            if coordinate < 0 or coordinate > 1000:
                raise ValueError("bbox Gemma Vision invalide")
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise ValueError("bbox Gemma Vision invalide")


@dataclass(frozen=True)
class GemmaVisionConversionResponse:
    tool_version: str
    items: tuple[GemmaVisionPageItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tool_version, str) or self.tool_version.strip() == "" or self.tool_version != self.tool_version.strip():
            raise ValueError("version Gemma Vision invalide")
        if not isinstance(self.items, tuple) or len(self.items) == 0:
            raise ValueError("items Gemma Vision requis")
        if any(not isinstance(item, GemmaVisionPageItem) for item in self.items):
            raise ValueError("item Gemma Vision invalide")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "GemmaVisionConversionResponse":
        if not isinstance(payload, Mapping) or set(payload) != {"tool_version", "items"}:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        tool_version = payload["tool_version"]
        raw_items = payload["items"]
        if not isinstance(tool_version, str) or not isinstance(raw_items, list):
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        try:
            items = tuple(
                GemmaVisionPageItem(
                    text=_required_text(item, "text"),
                    bbox=_bbox_from_payload(item),
                )
                for item in raw_items
            )
            return cls(tool_version=tool_version, items=items)
        except ValueError as error:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID") from error


class IsolatedGemmaVisionPageConverter:
    """Lance un rendu PDF et l'appel Gateway dans un processus Python isolé."""

    def __init__(self, *, timeout_seconds: int) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise ValueError("timeout Gemma Vision invalide")
        self._timeout_seconds = timeout_seconds

    def convert(self, request: GemmaVisionConversionRequest) -> GemmaVisionConversionResponse:
        if not isinstance(request, GemmaVisionConversionRequest):
            raise ValueError("requête Gemma Vision invalide")
        try:
            completed = subprocess.run(
                (sys.executable, "-B", "-m", "app.source_processing.adapters.gemma_vision_worker"),
                input=json.dumps(request.to_payload(), separators=(",", ":")).encode("utf-8"),
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise GemmaVisionConversionError("GEMMA_VISION_UNAVAILABLE") from error
        try:
            payload = json.loads(completed.stdout)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GemmaVisionConversionError("GEMMA_VISION_WORKER_PROTOCOL_INVALID") from error
        if not isinstance(payload, Mapping):
            raise GemmaVisionConversionError("GEMMA_VISION_WORKER_PROTOCOL_INVALID")
        if completed.returncode != 0:
            code = payload.get("error_code")
            raise GemmaVisionConversionError(
                code if isinstance(code, str) and code.strip() != "" else "GEMMA_VISION_WORKER_PROTOCOL_INVALID"
            )
        return GemmaVisionConversionResponse.from_payload(payload)


def _required_text(payload: Any, field_name: str) -> str:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} invalide")
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _bbox_from_payload(payload: Any) -> tuple[float, float, float, float]:
    if not isinstance(payload, Mapping):
        raise ValueError("bbox Gemma Vision invalide")
    raw_bbox = payload.get("bbox")
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise ValueError("bbox Gemma Vision invalide")
    if any(isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) for coordinate in raw_bbox):
        raise ValueError("bbox Gemma Vision invalide")
    return tuple(float(coordinate) for coordinate in raw_bbox)  # type: ignore[return-value]


__all__ = [
    "GemmaVisionConversionError",
    "GemmaVisionConversionRequest",
    "GemmaVisionConversionResponse",
    "GemmaVisionPageItem",
    "IsolatedGemmaVisionPageConverter",
]
