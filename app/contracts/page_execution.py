"""DTO neutres de l'exécution fenced et de la complétion d'une page."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from app.contracts.technical_jobs import ClaimedJob


class GraniteCapacityConfigurationError(ValueError):
    """Le contrat partagé de capacité Granite est invalide."""

    code = "GRANITE_CAPACITY_CONFIGURATION_INVALID"

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or reason.strip() == "":
            raise ValueError("motif Granite invalide")
        self.reason = reason
        super().__init__(f"{self.code}:{reason}")


class GranitePageTerminalStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class GranitePageTerminalEnvelope:
    """Enveloppe technique immutable produite sous le double fencing actif."""

    completion_id: str
    status: GranitePageTerminalStatus
    payload: Mapping[str, Any]
    payload_fingerprint: str
    failure_reason: str | None

    def __post_init__(self) -> None:
        completion_id = _text(self.completion_id, "completion_id")
        if not isinstance(self.status, GranitePageTerminalStatus):
            raise GraniteCapacityConfigurationError("TERMINAL_STATUS_INVALID")
        payload = _freeze_json_mapping(self.payload)
        canonical_payload = _canonical_json(payload)
        fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        if self.payload_fingerprint != fingerprint:
            raise GraniteCapacityConfigurationError("TERMINAL_FINGERPRINT_MISMATCH")
        if self.status is GranitePageTerminalStatus.SUCCEEDED:
            if self.failure_reason is not None:
                raise GraniteCapacityConfigurationError("TERMINAL_FAILURE_FORBIDDEN")
        else:
            _text(self.failure_reason, "failure_reason")
        object.__setattr__(self, "completion_id", completion_id)
        object.__setattr__(self, "payload", payload)

    @classmethod
    def from_payload(
        cls,
        *,
        completion_id: str,
        status: GranitePageTerminalStatus,
        payload: Mapping[str, Any],
        failure_reason: str | None,
    ) -> "GranitePageTerminalEnvelope":
        parsed_payload = _freeze_json_mapping(payload)
        serialized = _canonical_json(parsed_payload)
        return cls(
            completion_id=completion_id,
            status=status,
            payload=parsed_payload,
            payload_fingerprint=hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest(),
            failure_reason=failure_reason,
        )

    def canonical_payload_json(self) -> str:
        """Revalide le hash immédiatement avant toute persistance."""

        serialized = _canonical_json(self.payload)
        if (
            hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            != self.payload_fingerprint
        ):
            raise GraniteCapacityConfigurationError("TERMINAL_FINGERPRINT_MISMATCH")
        return serialized


@dataclass(frozen=True, slots=True)
class GraniteSlotLease:
    """Couple claim-slot immutable transporté entre contextes techniques."""

    claimed_job: ClaimedJob
    slot_ordinal: int
    slot_generation: int
    slot_token: str
    lease_until: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.claimed_job, ClaimedJob):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if (
            isinstance(self.slot_ordinal, bool)
            or not isinstance(self.slot_ordinal, int)
            or self.slot_ordinal not in (1, 2)
        ):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if (
            isinstance(self.slot_generation, bool)
            or not isinstance(self.slot_generation, int)
            or self.slot_generation < 1
        ):
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        try:
            token = UUID(_text(self.slot_token, "slot_token"))
        except (TypeError, ValueError) as error:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID") from error
        if token.version != 4:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if not isinstance(self.lease_until, datetime) or self.lease_until.tzinfo is None:
            raise ValueError("GRANITE_SLOT_IDENTITY_INVALID")
        if self.lease_until != self.claimed_job.lease_expires_at:
            raise ValueError("GRANITE_SLOT_LEASE_DEADLINE_MISMATCH")
        object.__setattr__(self, "slot_token", str(token))


@dataclass(frozen=True, slots=True)
class PageCompletionMessage:
    """Fait platform immutable consommable sans dépendance vers platform."""

    completion_id: str
    environment: str
    deployment_id: str
    configuration_hash: str
    job_id: str
    claim_generation: int
    claim_token: str
    worker_instance_id: str
    slot_ordinal: int | None
    slot_generation: int | None
    slot_token: str | None
    payload: Mapping[str, Any]
    payload_fingerprint: str
    terminal_status: str
    failure_reason: str | None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.completion_id, "completion_id"),
            (self.environment, "environment"),
            (self.deployment_id, "deployment_id"),
            (self.job_id, "job_id"),
            (self.claim_token, "claim_token"),
            (self.worker_instance_id, "worker_instance_id"),
            (self.payload_fingerprint, "payload_fingerprint"),
            (self.terminal_status, "terminal_status"),
        ):
            _text(value, field_name)
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("environment invalide")
        _sha256(self.configuration_hash, "configuration_hash")
        if (
            isinstance(self.claim_generation, bool)
            or not isinstance(self.claim_generation, int)
            or self.claim_generation < 1
        ):
            raise ValueError("claim_generation invalide")
        _uuid4(self.claim_token, "claim_token")
        _validate_slot_identity(
            ordinal=self.slot_ordinal,
            generation=self.slot_generation,
            token=self.slot_token,
        )
        if not isinstance(self.payload, Mapping) or len(self.payload) == 0:
            raise ValueError("payload invalide")
        fingerprint = hashlib.sha256(
            _canonical_json(self.payload).encode("utf-8")
        ).hexdigest()
        if fingerprint != self.payload_fingerprint:
            raise ValueError("payload_fingerprint invalide")
        if self.terminal_status == "succeeded":
            if self.failure_reason is not None:
                raise ValueError("failure_reason interdit")
        elif self.terminal_status in {"failed", "abandoned"}:
            _text(self.failure_reason, "failure_reason")
        else:
            raise ValueError("terminal_status invalide")
        object.__setattr__(self, "payload", _freeze_json_mapping(self.payload))

    @classmethod
    def from_execution(
        cls,
        *,
        claimed_job: ClaimedJob,
        granite_lease: GraniteSlotLease | None,
        envelope: GranitePageTerminalEnvelope,
    ) -> "PageCompletionMessage":
        if not isinstance(claimed_job, ClaimedJob):
            raise ValueError("claimed_job invalide")
        if not isinstance(envelope, GranitePageTerminalEnvelope):
            raise ValueError("envelope invalide")
        if granite_lease is not None and granite_lease.claimed_job != claimed_job:
            raise ValueError("granite_lease divergente")
        request = claimed_job.job.request
        return cls(
            completion_id=envelope.completion_id,
            environment=request.environment,
            deployment_id=request.deployment_id,
            configuration_hash=request.idempotence_key.configuration_hash,
            job_id=claimed_job.job.job_id,
            claim_generation=claimed_job.claim_generation,
            claim_token=claimed_job.claim_token,
            worker_instance_id=claimed_job.lease_owner,
            slot_ordinal=None if granite_lease is None else granite_lease.slot_ordinal,
            slot_generation=(
                None if granite_lease is None else granite_lease.slot_generation
            ),
            slot_token=None if granite_lease is None else granite_lease.slot_token,
            payload=envelope.payload,
            payload_fingerprint=envelope.payload_fingerprint,
            terminal_status=envelope.status.value,
            failure_reason=envelope.failure_reason,
        )


def _validate_slot_identity(
    *,
    ordinal: int | None,
    generation: int | None,
    token: str | None,
) -> None:
    if ordinal is None and generation is None and token is None:
        return
    if (
        ordinal not in {1, 2}
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or token is None
    ):
        raise ValueError("slot identity invalide")
    _uuid4(token, "slot_token")


def _freeze_json_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
    frozen = _freeze_json_value(value)
    if not isinstance(frozen, Mapping):
        raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
    return frozen


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")
            frozen[key] = _freeze_json_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_FINITE")
        return value
    raise GraniteCapacityConfigurationError("TERMINAL_PAYLOAD_NON_JSON")


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    return value


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_compatible(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _uuid4(value: Any, field_name: str) -> str:
    try:
        parsed = UUID(_text(value, field_name))
    except ValueError as error:
        raise ValueError(f"{field_name} invalide") from error
    if parsed.version != 4:
        raise ValueError(f"{field_name} invalide")
    return str(parsed)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _sha256(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "GraniteCapacityConfigurationError",
    "GranitePageTerminalEnvelope",
    "GranitePageTerminalStatus",
    "GraniteSlotLease",
    "PageCompletionMessage",
]
