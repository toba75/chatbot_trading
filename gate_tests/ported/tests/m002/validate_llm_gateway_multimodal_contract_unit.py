from __future__ import annotations

from base64 import b64encode
from hashlib import sha256

from app.platform.llm_gateway import InferenceImage, LLMGatewayContractError


def _image_payload(raw_bytes: bytes) -> dict[str, str]:
    return {
        "media_type": "image/png",
        "data_base64": b64encode(raw_bytes).decode("ascii"),
        "sha256": sha256(raw_bytes).hexdigest(),
    }


def _assert_error_code(expected_code: str, callback: object) -> None:
    try:
        callback()
    except LLMGatewayContractError as exc:
        assert exc.code == expected_code
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_code}")


def test_validate_llm_gateway_multimodal_contract_unit() -> None:
    """Given une image de page, When sa frontière est validée, Then seuls les octets hachés et admissibles peuvent atteindre le Spark."""

    raw_bytes = b"\x89PNG\r\n\x1a\npage-image"
    payload = _image_payload(raw_bytes)
    image = InferenceImage(**payload)
    assert image.byte_size == len(raw_bytes)

    _assert_error_code(
        "LLM_IMAGE_HASH_INVALID",
        lambda: InferenceImage(**{**payload, "sha256": "0" * 64}),
    )
    _assert_error_code(
        "LLM_IMAGE_MEDIA_TYPE_INVALID",
        lambda: InferenceImage(**{**payload, "media_type": "application/pdf"}),
    )
    _assert_error_code(
        "LLM_IMAGE_PAYLOAD_INVALID",
        lambda: InferenceImage(**{**payload, "data_base64": "not canonical base64"}),
    )
