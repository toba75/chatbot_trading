"""Adaptateur de readiness HTTP du LLM gateway."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.platform.orchestrator_composition import DependencyReadiness


@dataclass(slots=True)
class HttpHealthOrchestratorDependency:
    """Dépendance HTTP stricte dont la panne reste exprimée par un code sûr."""

    name: str
    health_url: str
    timeout_seconds: int
    not_ready_error_code: str
    api_key: str | None
    expected_identity: JobEnvironmentIdentity | None
    _opened: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if self.name not in {"llm-gateway", "qdrant"}:
            raise ValueError("nom de dépendance HTTP non supporté")
        if not self.health_url.startswith(("http://", "https://")):
            raise ValueError("URL health HTTP explicite obligatoire")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, int)
            or self.timeout_seconds < 1
        ):
            raise ValueError("timeout health HTTP invalide")
        if self.not_ready_error_code not in {"LLM_GATEWAY_NOT_READY", "QDRANT_NOT_READY"}:
            raise ValueError("code readiness HTTP non supporté")
        if self.name == "qdrant":
            if not isinstance(self.api_key, str) or len(self.api_key.encode("utf-8")) < 32:
                raise ValueError("clé API readiness Qdrant invalide")
            if self.expected_identity is not None:
                raise ValueError("identité applicative interdite pour Qdrant")
        elif self.api_key is not None:
            raise ValueError("clé API interdite pour la readiness LLM locale")
        elif not isinstance(self.expected_identity, JobEnvironmentIdentity):
            raise ValueError("identité applicative LLM invalide")

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("dépendance HTTP déjà ouverte")
        if not await asyncio.to_thread(self._is_ready):
            raise RuntimeError(self.not_ready_error_code)
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("dépendance HTTP non ouverte")
        self._opened = False

    def readiness(self) -> DependencyReadiness:
        status = "ready" if self._opened and self._is_ready() else "unavailable"
        return DependencyReadiness(
            name=self.name,
            status=status,
            error_code=None if status == "ready" else self.not_ready_error_code,
        )

    def _is_ready(self) -> bool:
        headers = {"Accept": "application/json"}
        if self.api_key is not None:
            headers["api-key"] = self.api_key
        request = Request(
            self.health_url,
            method="GET",
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    return False
                if self.name == "qdrant":
                    return True
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        return payload == {
            "service": "llm-gateway",
            "status": "ready",
            **self.expected_identity.to_mapping(),
        }


__all__ = ["HttpHealthOrchestratorDependency"]
