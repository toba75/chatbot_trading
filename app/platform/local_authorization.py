"""Autorisation explicite des mutations persistantes de la stack locale."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any


_MINIMUM_TOKEN_BYTES = 32


class LocalMutationAuthorizer:
    """Valide un secret backend sans considérer le loopback comme une identité."""

    def __init__(self, *, secret: bytes) -> None:
        if not isinstance(secret, bytes):
            raise TypeError("LOCAL_API_TOKEN_INVALID")
        if len(secret) < _MINIMUM_TOKEN_BYTES:
            raise ValueError("LOCAL_API_TOKEN_TOO_SHORT")
        if any(byte in b"\r\n\0" for byte in secret):
            raise ValueError("LOCAL_API_TOKEN_INVALID")
        self._secret = secret

    @classmethod
    def from_file(cls, path: Path) -> "LocalMutationAuthorizer":
        if not isinstance(path, Path):
            raise TypeError("LOCAL_API_TOKEN_PATH_INVALID")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError("LOCAL_API_TOKEN_UNREADABLE") from exc
        if raw.endswith(b"\r\n"):
            raw = raw[:-2]
        elif raw.endswith(b"\n"):
            raw = raw[:-1]
        return cls(secret=raw)

    def authorization_header(self) -> str:
        try:
            token = self._secret.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("LOCAL_API_TOKEN_INVALID") from exc
        return f"Bearer {token}"

    def authorize(
        self,
        *,
        method: str,
        path: str,
        authorization_header: str | None,
    ) -> tuple[int, str] | None:
        if method != "POST" or not _is_persistent_document_mutation(path):
            return None
        if authorization_header is None:
            return 401, "LOCAL_API_TOKEN_REQUIRED"
        prefix = "Bearer "
        if not authorization_header.startswith(prefix):
            return 403, "LOCAL_API_TOKEN_INVALID"
        supplied = authorization_header.removeprefix(prefix).encode("utf-8")
        if not hmac.compare_digest(supplied, self._secret):
            return 403, "LOCAL_API_TOKEN_INVALID"
        return None


def _is_persistent_document_mutation(path: Any) -> bool:
    return isinstance(path, str) and (
        path == "/v1/documents"
        or (
            path.startswith("/v1/documents/")
            and (path.endswith("/diagnose") or path.endswith("/index"))
        )
    )


__all__ = ["LocalMutationAuthorizer"]
