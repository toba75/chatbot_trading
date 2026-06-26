"""Composant technique event_bus."""

from app.platform.event_bus.outbox import (
    EventConsumptionDecision,
    IdempotentEventConsumer,
    InMemoryProcessedEventRegistry,
    InMemoryTransactionalOutbox,
    OutboxEntry,
    OutboxMessageStatus,
    ProducerStateMutation,
)

__all__ = [
    "EventConsumptionDecision",
    "IdempotentEventConsumer",
    "InMemoryProcessedEventRegistry",
    "InMemoryTransactionalOutbox",
    "OutboxEntry",
    "OutboxMessageStatus",
    "ProducerStateMutation",
]
