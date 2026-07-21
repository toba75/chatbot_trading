"""Sous-processus borné : rendu d'une page puis appel exclusif au llm-gateway."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from app.contracts.llm_inference import (
    LlmInferenceImage,
    LlmInferenceImageMessage,
    LlmInferenceRequest,
)
from app.platform.llm_gateway.orchestrator_http import UrllibLlmInferenceGateway
from app.source_processing.adapters.gemma_vision_conversion import (
    GEMMA_DENSE_RENDER_SEGMENT_COUNT,
    GemmaVisionConversionError,
)


_MAX_RENDERED_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_GEMMA_PAGE_ITEMS = 16
_GATEWAY_GEMMA_OUTPUT_ERROR_CODES = frozenset(
    {
        "LLM_RESPONSE_INVALID_JSON",
        "LLM_RESPONSE_SCHEMA_INVALID",
    }
)
_GATEWAY_GEMMA_TRUNCATED_ERROR_CODES = frozenset({"LLM_PARTIAL_OUTPUT"})
_PAGE_TRANSCRIPTION_PROMPT = (
    "Transcris uniquement le texte documentaire visible de cette page PDF. "
    "Regroupe les éléments adjacents en régions de lecture complètes. "
    "Pour un tableau dense, retourne toutes ses cellules dans un seul item texte, "
    "séparées par la séquence ASCII espace-barre-espace ( | ). "
    "N'utilise aucun caractère de contrôle U+0000 à U+001F dans les valeurs "
    "textuelles JSON. N’omets aucun texte lisible. "
    "Retourne au plus 16 items, chacun avec bbox=[left,top,right,bottom] "
    "en coordonnées entières normalisées de 0 à 1000. "
    "Ne fabrique aucun texte et ne retourne ni Markdown ni commentaire."
)


def main() -> int:
    try:
        payload = _required_payload(json.loads(sys.stdin.read()))
        response = _convert(payload)
    except GemmaVisionConversionError as error:
        _write({"error_code": error.code})
        return 1
    except Exception:
        _write({"error_code": "GEMMA_VISION_WORKER_UNEXPECTED"})
        return 1
    _write(response)
    return 0


def _convert(payload: Mapping[str, Any]) -> dict[str, object]:
    source_path = Path(_required_text(payload, "source_pdf_path"))
    source_sha256 = _required_text(payload, "source_sha256")
    if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source_sha256:
        raise GemmaVisionConversionError("GEMMA_VISION_SOURCE_INVALID")
    render_rotation_degrees = _required_render_rotation_degrees(payload)
    render_segment_index, render_segment_count = _required_render_segment(payload)
    image_bytes = _render_page_png(
        source_path=source_path,
        source_page_number=_required_positive_int(payload, "source_page_number"),
        render_rotation_degrees=render_rotation_degrees,
        render_segment_index=render_segment_index,
        render_segment_count=render_segment_count,
    )
    image = LlmInferenceImage(
        media_type="image/png",
        data_base64=base64.b64encode(image_bytes).decode("ascii"),
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )
    document_id = _required_text(payload, "document_id")
    processing_run_id = _required_text(payload, "processing_run_id")
    page_number = _required_positive_int(payload, "page_number")
    identity_suffix = _request_identity_suffix(
        render_rotation_degrees=render_rotation_degrees,
        render_segment_index=render_segment_index,
        render_segment_count=render_segment_count,
    )
    request = LlmInferenceRequest(
        messages=(
            LlmInferenceImageMessage(
                role="user",
                content=_transcription_prompt(
                    render_segment_index=render_segment_index,
                    render_segment_count=render_segment_count,
                ),
                images=(image,),
            ),
        ),
        output_schema=_output_schema(),
        schema_name="source_processing_page_conversion",
        schema_version="1.2",
        trace_id=(
            f"TRACE-M004-GEMMA-{document_id.removeprefix('DOC-')}-"
            f"P{page_number:03d}-{identity_suffix}"
        ),
        request_id=f"REQ-M004-GEMMA-{processing_run_id}-P{page_number:03d}-{identity_suffix}",
        idempotency_key=(
            f"IDEMP-M004-GEMMA-{processing_run_id}-P{page_number:03d}-{identity_suffix}"
        ),
        prompt_id="m004-gemma-vision-page-conversion",
        prompt_version="1.3",
        sampling_parameters={
            "temperature": 0.0,
            "max_tokens": _required_positive_int(payload, "max_output_tokens"),
        },
    )
    response = UrllibLlmInferenceGateway(
        endpoint_url=_required_text(payload, "gateway_endpoint_url"),
        timeout_seconds=_required_positive_int(payload, "gateway_timeout_seconds"),
    ).infer(request)
    if response.status_code != 200:
        gateway_error_code = response.payload.get("error_code")
        if gateway_error_code in _GATEWAY_GEMMA_OUTPUT_ERROR_CODES:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        if gateway_error_code in _GATEWAY_GEMMA_TRUNCATED_ERROR_CODES:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_TRUNCATED")
        raise GemmaVisionConversionError("GEMMA_VISION_UNAVAILABLE")
    structured_output = response.payload.get("structured_output")
    provenance = response.payload.get("provenance")
    if not isinstance(structured_output, Mapping) or not isinstance(provenance, Mapping):
        raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
    model_id = _required_text(provenance, "model_id")
    if model_id != _required_text(payload, "expected_model_id"):
        raise GemmaVisionConversionError("GEMMA_VISION_MODEL_MISMATCH")
    model_revision = _required_text(provenance, "model_revision")
    runtime_version = _required_text(provenance, "runtime_version")
    items = _structured_items(
        structured_output,
        render_rotation_degrees=render_rotation_degrees,
        render_segment_index=render_segment_index,
        render_segment_count=render_segment_count,
    )
    return {
        "tool_version": _tool_version(
            model_id=model_id,
            model_revision=model_revision,
            runtime_version=runtime_version,
            render_rotation_degrees=render_rotation_degrees,
            render_segment_index=render_segment_index,
            render_segment_count=render_segment_count,
        ),
        "items": items,
    }


def _render_page_png(
    *,
    source_path: Path,
    source_page_number: int,
    render_rotation_degrees: int,
    render_segment_index: int | None,
    render_segment_count: int | None,
) -> bytes:
    try:
        import pypdfium2

        document = pypdfium2.PdfDocument(str(source_path))
        if source_page_number > len(document):
            raise GemmaVisionConversionError("GEMMA_VISION_PAGE_MISSING")
        page = document[source_page_number - 1]
        bitmap = page.render(scale=1.5, rotation=render_rotation_degrees)
        image = bitmap.to_pil()
        if render_segment_index is not None and render_segment_count is not None:
            image = image.crop(
                _segment_crop_box(
                    image_width=image.width,
                    image_height=image.height,
                    render_rotation_degrees=render_rotation_degrees,
                    render_segment_index=render_segment_index,
                    render_segment_count=render_segment_count,
                )
            )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        rendered = buffer.getvalue()
        if len(rendered) == 0 or len(rendered) > _MAX_RENDERED_IMAGE_BYTES:
            raise GemmaVisionConversionError("GEMMA_VISION_IMAGE_TOO_LARGE")
        return rendered
    except GemmaVisionConversionError:
        raise
    except Exception as error:
        raise GemmaVisionConversionError("GEMMA_VISION_RENDERING_FAILED") from error


def _structured_items(
    structured_output: Mapping[str, Any],
    *,
    render_rotation_degrees: int,
    render_segment_index: int | None = None,
    render_segment_count: int | None = None,
) -> list[dict[str, object]]:
    if set(structured_output) != {"items"} or not isinstance(structured_output["items"], list):
        raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
    items: list[dict[str, object]] = []
    for item in structured_output["items"]:
        if not isinstance(item, Mapping) or set(item) != {"text", "bbox"}:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        text = _required_text(item, "text")
        bbox = item["bbox"]
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bbox)
            or any(value < 0 or value > 1000 for value in bbox)
        ):
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        left, top, right, bottom = bbox
        normalized_bbox = [min(left, right), min(top, bottom), max(left, right), max(top, bottom)]
        if normalized_bbox[0] == normalized_bbox[2] or normalized_bbox[1] == normalized_bbox[3]:
            raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
        bbox_dans_rendu_complet = _bbox_dans_rendu_complet(
            normalized_bbox,
            render_rotation_degrees=render_rotation_degrees,
            render_segment_index=render_segment_index,
            render_segment_count=render_segment_count,
        )
        items.append(
            {
                "text": text,
                "bbox": _bbox_dans_repere_source(
                    bbox_dans_rendu_complet,
                    render_rotation_degrees=render_rotation_degrees,
                ),
            }
        )
    if len(items) == 0:
        raise GemmaVisionConversionError("GEMMA_VISION_OUTPUT_INVALID")
    return items


def _bbox_dans_rendu_complet(
    bbox: list[int | float],
    *,
    render_rotation_degrees: int,
    render_segment_index: int | None,
    render_segment_count: int | None,
) -> list[int | float]:
    if render_segment_index is None and render_segment_count is None:
        return list(bbox)
    if (
        render_segment_index not in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
        or render_segment_count != GEMMA_DENSE_RENDER_SEGMENT_COUNT
    ):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    if render_rotation_degrees != 90:
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    left, top, right, bottom = bbox
    segment_offset = (
        1000 * (render_segment_count - render_segment_index) / render_segment_count
    )
    return [
        segment_offset + left / render_segment_count,
        top,
        segment_offset + right / render_segment_count,
        bottom,
    ]


def _segment_crop_box(
    *,
    image_width: int,
    image_height: int,
    render_rotation_degrees: int,
    render_segment_index: int,
    render_segment_count: int,
) -> tuple[int, int, int, int]:
    if (
        isinstance(image_width, bool)
        or not isinstance(image_width, int)
        or image_width < 1
        or isinstance(image_height, bool)
        or not isinstance(image_height, int)
        or image_height < 1
        or render_rotation_degrees != 90
        or render_segment_index
        not in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
        or render_segment_count != GEMMA_DENSE_RENDER_SEGMENT_COUNT
    ):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    left = image_width * (render_segment_count - render_segment_index) // render_segment_count
    right = image_width * (render_segment_count - render_segment_index + 1) // render_segment_count
    return left, 0, right, image_height


def _bbox_dans_repere_source(
    bbox: list[int | float],
    *,
    render_rotation_degrees: int,
) -> list[int | float]:
    if render_rotation_degrees == 0:
        return list(bbox)
    if render_rotation_degrees == 90:
        left, top, right, bottom = bbox
        return [top, 1000 - right, bottom, 1000 - left]
    raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")


def _tool_version(
    *,
    model_id: str,
    model_revision: str,
    runtime_version: str,
    render_rotation_degrees: int,
    render_segment_index: int | None,
    render_segment_count: int | None,
) -> str:
    version = (
        f"{model_revision};{runtime_version}"
        if model_revision.startswith(f"{model_id}@")
        else f"{model_id}@{model_revision};{runtime_version}"
    )
    if render_rotation_degrees != 0:
        version = f"{version};render-rotation-{render_rotation_degrees:03d}"
    if render_segment_index is not None and render_segment_count is not None:
        version = (
            f"{version};render-segment-{render_segment_index:02d}-"
            f"of-{render_segment_count:02d}"
        )
    return version


def _request_identity_suffix(
    *,
    render_rotation_degrees: int,
    render_segment_index: int | None,
    render_segment_count: int | None,
) -> str:
    suffix = f"R{render_rotation_degrees:03d}"
    if render_segment_index is None and render_segment_count is None:
        return f"{suffix}-FULL"
    if (
        render_segment_index not in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
        or render_segment_count != GEMMA_DENSE_RENDER_SEGMENT_COUNT
    ):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return f"{suffix}-S{render_segment_index:02d}OF{render_segment_count:02d}"


def _transcription_prompt(
    *,
    render_segment_index: int | None,
    render_segment_count: int | None,
) -> str:
    if render_segment_index is None and render_segment_count is None:
        return _PAGE_TRANSCRIPTION_PROMPT
    if (
        render_segment_index not in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
        or render_segment_count != GEMMA_DENSE_RENDER_SEGMENT_COUNT
    ):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return (
        f"{_PAGE_TRANSCRIPTION_PROMPT} Cette image est le segment vertical "
        f"{render_segment_index} sur {render_segment_count} de la page tournée. "
        "Transcris uniquement ce segment et conserve son ordre de lecture."
    )


def _output_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": _MAX_GEMMA_PAGE_ITEMS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text", "bbox"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1},
                        "bbox": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {"type": "number", "minimum": 0, "maximum": 1000},
                        },
                    },
                },
            }
        },
    }


def _required_payload(payload: Any) -> Mapping[str, Any]:
    expected = {
        "schema_version", "document_id", "processing_run_id", "source_sha256", "source_pdf_path",
        "page_number", "source_page_number", "route_name", "routing_policy_version",
        "gateway_endpoint_url", "gateway_timeout_seconds", "max_output_tokens",
        "expected_model_id", "render_rotation_degrees", "render_segment_index",
        "render_segment_count",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected or payload["schema_version"] != "1.2":
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    _required_render_segment(payload)
    return payload


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return value


def _required_positive_int(payload: Mapping[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return value


def _required_render_rotation_degrees(payload: Mapping[str, Any]) -> int:
    value = payload.get("render_rotation_degrees")
    if value not in (0, 90) or isinstance(value, bool):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return value


def _required_render_segment(payload: Mapping[str, Any]) -> tuple[int | None, int | None]:
    segment_index = payload.get("render_segment_index")
    segment_count = payload.get("render_segment_count")
    if segment_index is None and segment_count is None:
        return None, None
    if (
        isinstance(segment_index, bool)
        or isinstance(segment_count, bool)
        or segment_index not in range(1, GEMMA_DENSE_RENDER_SEGMENT_COUNT + 1)
        or segment_count != GEMMA_DENSE_RENDER_SEGMENT_COUNT
        or _required_render_rotation_degrees(payload) != 90
    ):
        raise GemmaVisionConversionError("GEMMA_VISION_REQUEST_INVALID")
    return segment_index, segment_count


def _write(payload: Mapping[str, object]) -> None:
    sys.stdout.buffer.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
