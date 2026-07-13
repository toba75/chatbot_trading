"""DTO neutres d'une outbox transactionnelle locale."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.contracts.event_envelope import ALLOWED_EVENT_PRODUCER_CONTEXTS, EventEnvelope


class OutboxMessageStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass(frozen=True)
class ProducerStateMutation:
    mutation_id: str
    producer_context: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int

    def __post_init__(self) -> None:
        _required_text(self.mutation_id, "mutation_id")
        producer_context = _required_text(self.producer_context, "producer_context")
        if producer_context not in ALLOWED_EVENT_PRODUCER_CONTEXTS:
            raise ValueError(f"producer_context inconnu: {producer_context}")
        _required_text(self.aggregate_type, "aggregate_type")
        _required_text(self.aggregate_id, "aggregate_id")
        _positive_integer(self.aggregate_version, "aggregate_version")


@dataclass(frozen=True)
class OutboxEntry:
    sequence: int
    state_mutation: ProducerStateMutation
    event: EventEnvelope
    status: OutboxMessageStatus
    failure_reason: str | None

    def __post_init__(self) -> None:
        _positive_integer(self.sequence, "sequence")
        if not isinstance(self.state_mutation, ProducerStateMutation):
            raise ValueError("state_mutation invalide")
        if not isinstance(self.event, EventEnvelope):
            raise ValueError("event invalide")
        if not isinstance(self.status, OutboxMessageStatus):
            raise ValueError("status outbox invalide")
        if self.status is OutboxMessageStatus.FAILED:
            _required_text(self.failure_reason, "failure_reason")
        elif self.failure_reason is not None:
            raise ValueError("failure_reason interdit sans statut failed")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["OutboxEntry", "OutboxMessageStatus", "ProducerStateMutation"]
