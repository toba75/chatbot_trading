"""Protocole explicite de relais entre une outbox productrice et la file platform."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID

from app.platform.job_runtime import JobIdempotenceKey, JobPriority, JobRequest
from app.platform.worker_environment import WorkerEnvironmentMismatchError


@dataclass(frozen=True, slots=True)
class RelayedJobMessage:
    """Message technique immutable publié par un contexte propriétaire."""

    message_id: str
    environment: str
    deployment_id: str
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

    @classmethod
    def from_job_request(
        cls,
        *,
        message_id: str,
        request: JobRequest,
        trace_id: str,
    ) -> "RelayedJobMessage":
        if not isinstance(request, JobRequest):
            raise ValueError("request relais invalide")
        return cls(
            message_id=message_id,
            environment=request.environment,
            deployment_id=request.deployment_id,
            job_name=request.job_name,
            priority=request.priority.value,
            input_hash=request.idempotence_key.input_hash,
            configuration_hash=request.idempotence_key.configuration_hash,
            code_version=request.idempotence_key.code_version,
            model_version=request.idempotence_key.model_version,
            payload=request.payload,
            trace_id=trace_id,
        )

    def as_job_request(self) -> JobRequest:
        try:
            priority = JobPriority(self.priority)
        except (TypeError, ValueError) as exc:
            raise ValueError("priority relais invalide") from exc
        return JobRequest(
            environment=self.environment,
            deployment_id=self.deployment_id,
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
            "deployment_id": self.deployment_id,
            "environment": self.environment,
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

    def reject_environment_mismatch(
        self,
        claim: ClaimedRelayMessage,
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
            started_ns = time.perf_counter_ns()
            try:
                platform_job_id = self._consumer.consume_relay_message(claim.message)
                self._outbox.acknowledge(claim, platform_job_id=platform_job_id)
            except WorkerEnvironmentMismatchError:
                reject = getattr(self._outbox, "reject_environment_mismatch", None)
                if not callable(reject):
                    raise ValueError("outbox sans refus environnement")
                reject(claim)
                _print_relay_observation(
                    claim=claim,
                    relayed_count=relayed,
                    started_ns=started_ns,
                    error_code=WorkerEnvironmentMismatchError.code,
                    succeeded=False,
                )
                continue
            except Exception as exception:
                _print_relay_observation(
                    claim=claim,
                    relayed_count=relayed,
                    started_ns=started_ns,
                    error_code=_safe_relay_error_code(exception),
                    succeeded=False,
                )
                raise
            relayed += 1
            _print_relay_observation(
                claim=claim,
                relayed_count=relayed,
                started_ns=started_ns,
                error_code=None,
                succeeded=True,
            )
        return relayed


def _print_relay_observation(
    *,
    claim: ClaimedRelayMessage,
    relayed_count: int,
    started_ns: int,
    error_code: str | None,
    succeeded: bool,
) -> None:
    print(
        json.dumps(
            {
                "configuration_hash": claim.message.configuration_hash,
                "duration_ms": round(
                    (time.perf_counter_ns() - started_ns) / 1_000_000,
                    3,
                ),
                "error_code": error_code,
                "error_count": 0 if succeeded else 1,
                "event_type": "job_outbox_relay",
                "message_id": claim.message.message_id,
                "relayed_count": relayed_count,
                "success_count": 1 if succeeded else 0,
                "trace_id": claim.message.trace_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _safe_relay_error_code(exception: Exception) -> str:
    candidate = getattr(exception, "code", None)
    if not isinstance(candidate, str):
        candidate = str(exception)
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", candidate):
        return candidate
    return "JOB_OUTBOX_RELAY_FAILED"


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
