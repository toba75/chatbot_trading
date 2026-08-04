from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ProposalError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        request: dict[str, Any],
        response: bytes | None = None,
    ) -> None:
        self.request = request
        self.response = response
        super().__init__(message)


@dataclass(frozen=True)
class Proposal:
    latex: str
    request: dict[str, Any]
    response: dict[str, Any]


def propose_formula(
    *,
    endpoint: str,
    model: str,
    prompt: str,
    image: bytes,
    timeout_seconds: int,
    max_response_bytes: int,
) -> Proposal:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(image).decode("ascii")
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 512,
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(max_response_bytes + 1)
    except urllib.error.HTTPError as error:
        raw = error.read(max_response_bytes + 1)
        raise ProposalError(
            f"Appel Gemma refusé : HTTP {error.code}", request=payload, response=raw
        ) from error
    except OSError as error:
        raise ProposalError(
            f"Appel Gemma impossible : {error}", request=payload
        ) from error
    if len(raw) > max_response_bytes:
        raise ProposalError(
            "La réponse Gemma dépasse la taille autorisée",
            request=payload,
            response=raw,
        )
    try:
        response_payload = json.loads(raw)
        content = response_payload["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise ProposalError(
            "La réponse Gemma ne respecte pas le contrat attendu",
            request=payload,
            response=raw,
        ) from error
    if not isinstance(content, str) or not content.strip():
        raise ProposalError(
            "La proposition Gemma est vide", request=payload, response=raw
        )
    return Proposal(content.strip(), payload, response_payload)
