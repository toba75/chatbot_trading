"""Protocole explicite de relais entre une outbox productrice et la file platform."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID

from app.platform.job_runtime import JobIdempotenceKey, JobPriority, JobRequest


@dataclass(frozen=True, slots=True)
class RelayedJobMessage:
    """Message technique immutable publié par un contexte propriétaire."""

    message_id: str
    job_name: str
    priority: str
    input_hash: str
    configuration_hash: str
    code_version: str
    model_version: str
    payload: Mapping[str, Any]
    trace_id: str

    def __post_init__(self) -> None:
        _required_text(self.message_id, "message_id")
        _required_text(self.trace_id, "trace_id")
        request = self.as_job_request()
        object.__setattr__(self, "payload", request.payload)

    def as_job_request(self) -> JobRequest:
        try:
            priority = JobPriority(self.priority)
        except (TypeError, ValueError) as exc:
            raise ValueError("priority relais invalide") from exc
        return JobRequest(
            job_name=self.job_name,
            priority=priority,
            idempotence_key=JobIdempotenceKey(
                job_name=self.job_name,
                input_hash=self.input_hash,
                configuration_hash=self.configuration_hash,
                code_version=self.code_version,
                model_version=self.model_version,
            ),
            payload=self.payload,
        )

    @property
    def content_hash(self) -> str:
        canonical = {
            "configuration_hash": self.configuration_hash,
            "input_hash": self.input_hash,
            "job_name": self.job_name,
            "message_id": self.message_id,
            "model_version": self.model_version,
            "payload": _json_value(self.payload),
            "priority": self.priority,
            "trace_id": self.trace_id,
            "code_version": self.code_version,
        }
        serialized = json.dumps(
            canonical,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ClaimedRelayMessage:
    """Lease SP attachée à un message sans exposer sa transaction."""

    message: RelayedJobMessage
    owner_id: str
    claim_generation: int
    claim_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.message, RelayedJobMessage):
            raise ValueError("message relayé invalide")
        _required_text(self.owner_id, "owner_id")
        if (
            isinstance(self.claim_generation, bool)
            or not isinstance(self.claim_generation, int)
            or self.claim_generation < 1
        ):
            raise ValueError("génération claim relais invalide")
        try:
            token = UUID(_required_text(self.claim_token, "claim_token"))
        except ValueError as exc:
            raise ValueError("claim_token relais invalide") from exc
        if token.version != 4:
            raise ValueError("claim_token relais invalide")


class RelayOutbox(Protocol):
    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> ClaimedRelayMessage | None: ...

    def acknowledge(
        self,
        claim: ClaimedRelayMessage,
        *,
        platform_job_id: str,
    ) -> None: ...


class RelayConsumer(Protocol):
    def consume_relay_message(self, message: RelayedJobMessage) -> str: ...


class JobOutboxRelay:
    """Coordonne claim, consommation et ACK sans partager leur transaction."""

    def __init__(self, *, outbox: RelayOutbox, consumer: RelayConsumer) -> None:
        if not callable(getattr(outbox, "claim_next", None)):
            raise ValueError("outbox relais invalide")
        if not callable(getattr(outbox, "acknowledge", None)):
            raise ValueError("outbox sans ACK")
        if not callable(getattr(consumer, "consume_relay_message", None)):
            raise ValueError("consommateur relais invalide")
        self._outbox = outbox
        self._consumer = consumer

    def relay_pending(self, *, limit: int, owner_id: str, lease_seconds: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("relay limit invalide")
        _required_text(owner_id, "owner_id")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or lease_seconds < 1
        ):
            raise ValueError("relay lease_seconds invalide")
        relayed = 0
        for _ in range(limit):
            claim = self._outbox.claim_next(
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
            if claim is None:
                return relayed
            platform_job_id = self._consumer.consume_relay_message(claim.message)
            self._outbox.acknowledge(claim, platform_job_id=platform_job_id)
            relayed += 1
        return relayed


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_json_value(nested) for nested in value]
    return value


__all__ = [
    "ClaimedRelayMessage",
    "JobOutboxRelay",
    "RelayedJobMessage",
    "RelayConsumer",
    "RelayOutbox",
]
