"""DTO neutres du protocole de jobs techniques partagé entre contextes."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import UUID


_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_JOB_ID_PATTERN = re.compile(r"^JOB-M002-[0-9]{6}$")


class JobPriority(str, Enum):
    """Priorité technique explicite d'un job local."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"

    @property
    def rank(self) -> int:
        return int(self.value[1])


class JobStatus(str, Enum):
    """Statut explicite d'un job local."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class JobIdempotenceKey:
    job_name: str
    input_hash: str
    configuration_hash: str
    code_version: str
    model_version: str

    def __post_init__(self) -> None:
        _ensure_text(self.job_name, "job_name")
        _ensure_hash(self.input_hash, "input_hash")
        _ensure_hash(self.configuration_hash, "configuration_hash")
        _ensure_text(self.code_version, "code_version")
        _ensure_text(self.model_version, "model_version")

    def identity_tuple(self) -> tuple[str, str, str, str, str]:
        return (self.job_name, self.input_hash, self.configuration_hash, self.code_version, self.model_version)


@dataclass(frozen=True)
class JobRequest:
    job_name: str
    priority: JobPriority
    idempotence_key: JobIdempotenceKey
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        job_name = _ensure_text(self.job_name, "job_name")
        if not isinstance(self.priority, JobPriority):
            raise ValueError("priority invalide")
        if not isinstance(self.idempotence_key, JobIdempotenceKey):
            raise ValueError("idempotence_key invalide")
        if self.idempotence_key.job_name != job_name:
            raise ValueError("idempotence_key incohérente avec job_name")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))


@dataclass(frozen=True)
class JobRecord:
    sequence: int
    job_id: str
    request: JobRequest
    status: JobStatus
    result: Mapping[str, Any] | None
    failure_reason: str | None

    def __post_init__(self) -> None:
        _ensure_positive_integer(self.sequence, "sequence")
        _ensure_job_id(self.job_id)
        if not isinstance(self.request, JobRequest):
            raise ValueError("request invalide")
        if not isinstance(self.status, JobStatus):
            raise ValueError("status invalide")
        if self.status is JobStatus.SUCCEEDED:
            if self.result is None:
                raise ValueError("result absent")
            object.__setattr__(self, "result", _freeze_mapping(self.result, "result"))
        elif self.result is not None:
            raise ValueError("result interdit sans statut succeeded")
        if self.status is JobStatus.FAILED:
            _ensure_text(self.failure_reason, "failure_reason")
        elif self.failure_reason is not None:
            raise ValueError("failure_reason interdit sans statut failed")


@dataclass(frozen=True)
class JobSubmissionDecision:
    job: JobRecord
    created: bool
    recalculation_refused: bool

    def __post_init__(self) -> None:
        if not isinstance(self.job, JobRecord):
            raise ValueError("job invalide")
        if not isinstance(self.created, bool) or not isinstance(self.recalculation_refused, bool):
            raise ValueError("décision de soumission invalide")
        if self.created and self.recalculation_refused:
            raise ValueError("décision de soumission incohérente")


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    """Claim fenced complet; toute mutation doit présenter ces deux identités."""

    job: JobRecord
    trace_id: str
    lease_owner: str
    lease_expires_at: datetime
    claim_generation: int
    claim_token: str
    execution_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.job, JobRecord) or self.job.status is not JobStatus.RUNNING:
            raise ValueError("job running requis")
        _ensure_text(self.trace_id, "trace_id")
        _ensure_text(self.lease_owner, "lease_owner")
        if not isinstance(self.lease_expires_at, datetime) or self.lease_expires_at.tzinfo is None:
            raise ValueError("lease_expires_at invalide")
        _ensure_positive_integer(self.claim_generation, "claim_generation")
        _ensure_positive_integer(self.execution_attempts, "execution_attempts")
        if self.claim_generation != self.execution_attempts:
            raise ValueError("claim_generation incohérente avec execution_attempts")
        try:
            parsed_token = UUID(_ensure_text(self.claim_token, "claim_token"))
        except ValueError as exc:
            raise ValueError("claim_token invalide") from exc
        if parsed_token.version != 4:
            raise ValueError("claim_token invalide")


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_hash(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _HASH_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_job_id(value: Any) -> str:
    text = _ensure_text(value, "job_id")
    if _JOB_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("job_id invalide")
    return text


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _freeze_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or len(value) == 0:
        raise ValueError(f"{field_name} invalide")
    return MappingProxyType({_ensure_text(key, f"{field_name}.clé"): _freeze_payload_value(item, f"{field_name}.{key}") for key, item in value.items()})


def _freeze_payload_value(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_freeze_payload_value(item, f"{field_name}[]") for item in value)
    raise ValueError(f"{field_name} invalide")


__all__ = ["ClaimedJob", "JobIdempotenceKey", "JobPriority", "JobRecord", "JobRequest", "JobStatus", "JobSubmissionDecision"]
