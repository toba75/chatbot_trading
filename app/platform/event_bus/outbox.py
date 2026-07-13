"""Outbox transactionnelle locale et consommation idempotente M-002."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.contracts.event_envelope import EventEnvelope
from app.contracts.outbox import OutboxEntry, OutboxMessageStatus, ProducerStateMutation


_EVENT_ID_PATTERN = re.compile(r"^EVT-[A-Z0-9][A-Z0-9-]*$")


@dataclass(frozen=True)
class EventConsumptionDecision:
    """Decision observable d'une consommation idempotente."""

    event_id: str
    applied: bool
    duplicate: bool

    def __post_init__(self) -> None:
        _ensure_event_id(self.event_id)
        if not isinstance(self.applied, bool):
            raise ValueError("applied non booleen")
        if not isinstance(self.duplicate, bool):
            raise ValueError("duplicate non booleen")
        if self.applied is self.duplicate:
            raise ValueError("decision de consommation incoherente")


class InMemoryTransactionalOutbox:
    """Double local explicite d'une outbox transactionnelle."""

    def __init__(
        self,
        entries: Iterable[OutboxEntry],
        state_mutations: Iterable[ProducerStateMutation] = (),
    ) -> None:
        if entries is None:
            raise ValueError("entries absent")
        if state_mutations is None:
            raise ValueError("state_mutations absent")

        self._entries_by_event_id: dict[str, OutboxEntry] = {}
        self._event_order: list[str] = []
        self._state_mutations: list[ProducerStateMutation] = []
        self._lock = threading.Lock()

        for state_mutation in state_mutations:
            self._state_mutations.append(_ensure_state_mutation(state_mutation))

        for entry in entries:
            if not isinstance(entry, OutboxEntry):
                raise ValueError("entry outbox invalide")
            event_id = entry.event.event_id
            if event_id in self._entries_by_event_id:
                raise ValueError(f"event_id outbox duplique: {event_id}")
            _ensure_event_matches_mutation(entry.state_mutation, entry.event)
            self._entries_by_event_id[event_id] = entry
            self._event_order.append(event_id)

    @classmethod
    def empty(cls) -> "InMemoryTransactionalOutbox":
        return cls(entries=(), state_mutations=())

    def append_in_transaction(
        self,
        state_mutation: ProducerStateMutation,
        event: EventEnvelope,
    ) -> OutboxEntry:
        return self.append_many_in_transaction(((state_mutation, event),))[0]

    def append_many_in_transaction(
        self,
        mutations_and_events: Iterable[tuple[ProducerStateMutation, EventEnvelope]],
    ) -> tuple[OutboxEntry, ...]:
        if mutations_and_events is None:
            raise ValueError("lot outbox absent")
        parsed_pairs: list[tuple[ProducerStateMutation, EventEnvelope]] = []
        batch_event_ids: set[str] = set()
        for pair in mutations_and_events:
            try:
                state_mutation, event = pair
            except (TypeError, ValueError) as exc:
                raise ValueError("lot outbox invalide") from exc
            mutation = _ensure_state_mutation(state_mutation)
            envelope = _ensure_event(event)
            _ensure_event_matches_mutation(mutation, envelope)
            if envelope.event_id in batch_event_ids:
                raise ValueError(f"event_id outbox duplique: {envelope.event_id}")
            batch_event_ids.add(envelope.event_id)
            parsed_pairs.append((mutation, envelope))
        if len(parsed_pairs) == 0:
            raise ValueError("lot outbox vide")

        with self._lock:
            for _, envelope in parsed_pairs:
                if envelope.event_id in self._entries_by_event_id:
                    raise ValueError(f"event_id outbox duplique: {envelope.event_id}")

            entries: list[OutboxEntry] = []
            for mutation, envelope in parsed_pairs:
                entry = OutboxEntry(
                    sequence=len(self._event_order) + 1,
                    state_mutation=mutation,
                    event=envelope,
                    status=OutboxMessageStatus.PENDING,
                    failure_reason=None,
                )
                self._entries_by_event_id[envelope.event_id] = entry
                self._event_order.append(envelope.event_id)
                self._state_mutations.append(mutation)
                entries.append(entry)
            return tuple(entries)

    def recorded_state_mutations(self) -> tuple[ProducerStateMutation, ...]:
        with self._lock:
            return tuple(self._state_mutations)

    def pending_events(self) -> tuple[OutboxEntry, ...]:
        with self._lock:
            entries = tuple(
                self._entries_by_event_id[event_id]
                for event_id in self._event_order
                if self._entries_by_event_id[event_id].status is OutboxMessageStatus.PENDING
            )
        return tuple(
            sorted(
                entries,
                key=lambda entry: (
                    entry.event.aggregate_type,
                    entry.event.aggregate_id,
                    entry.event.aggregate_version,
                    entry.sequence,
                ),
            )
        )

    def has_event(self, event_id: str) -> bool:
        parsed_event_id = _ensure_event_id(event_id)
        with self._lock:
            return parsed_event_id in self._entries_by_event_id

    def entry_for(self, event_id: str) -> OutboxEntry:
        parsed_event_id = _ensure_event_id(event_id)
        with self._lock:
            if parsed_event_id not in self._entries_by_event_id:
                raise ValueError(f"event outbox inconnu: {parsed_event_id}")
            return self._entries_by_event_id[parsed_event_id]

    def status_of(self, event_id: str) -> OutboxMessageStatus:
        return self.entry_for(event_id).status

    def mark_delivered(self, event_id: str) -> OutboxEntry:
        parsed_event_id = _ensure_event_id(event_id)
        with self._lock:
            if parsed_event_id not in self._entries_by_event_id:
                raise ValueError(f"event outbox inconnu: {parsed_event_id}")
            entry = self._entries_by_event_id[parsed_event_id]
            if entry.status is not OutboxMessageStatus.PENDING:
                raise ValueError(f"transition outbox invalide vers delivered: {entry.event.event_id}")
            delivered_entry = OutboxEntry(
                sequence=entry.sequence,
                state_mutation=entry.state_mutation,
                event=entry.event,
                status=OutboxMessageStatus.DELIVERED,
                failure_reason=None,
            )
            self._entries_by_event_id[entry.event.event_id] = delivered_entry
            return delivered_entry

    def mark_failed(self, event_id: str, failure_reason: str) -> OutboxEntry:
        reason = _ensure_text(failure_reason, "raison d'echec")
        parsed_event_id = _ensure_event_id(event_id)
        with self._lock:
            if parsed_event_id not in self._entries_by_event_id:
                raise ValueError(f"event outbox inconnu: {parsed_event_id}")
            entry = self._entries_by_event_id[parsed_event_id]
            if entry.status is not OutboxMessageStatus.PENDING:
                raise ValueError(f"transition outbox invalide vers failed: {entry.event.event_id}")
            failed_entry = OutboxEntry(
                sequence=entry.sequence,
                state_mutation=entry.state_mutation,
                event=entry.event,
                status=OutboxMessageStatus.FAILED,
                failure_reason=reason,
            )
            self._entries_by_event_id[entry.event.event_id] = failed_entry
            return failed_entry


class InMemoryProcessedEventRegistry:
    """Registre local explicite des event_id deja traites."""

    def __init__(
        self,
        processed_event_ids: Iterable[str],
        duplicate_event_ids: Iterable[str],
    ) -> None:
        if processed_event_ids is None:
            raise ValueError("processed_event_ids absent")
        if duplicate_event_ids is None:
            raise ValueError("duplicate_event_ids absent")

        self._processed_event_ids: list[str] = []
        self._processed_event_id_set: set[str] = set()
        self._duplicate_event_ids: list[str] = []

        for event_id in processed_event_ids:
            parsed_event_id = _ensure_event_id(event_id)
            if parsed_event_id in self._processed_event_id_set:
                raise ValueError(f"event_id traite duplique: {parsed_event_id}")
            self._processed_event_ids.append(parsed_event_id)
            self._processed_event_id_set.add(parsed_event_id)

        for event_id in duplicate_event_ids:
            parsed_event_id = _ensure_event_id(event_id)
            if parsed_event_id not in self._processed_event_id_set:
                raise ValueError(f"doublon sans event_id traite: {parsed_event_id}")
            self._duplicate_event_ids.append(parsed_event_id)

    @classmethod
    def empty(cls) -> "InMemoryProcessedEventRegistry":
        return cls(processed_event_ids=(), duplicate_event_ids=())

    @classmethod
    def from_processed_event_ids(
        cls,
        processed_event_ids: Iterable[str],
    ) -> "InMemoryProcessedEventRegistry":
        return cls(processed_event_ids=processed_event_ids, duplicate_event_ids=())

    def has_processed(self, event: EventEnvelope) -> bool:
        envelope = _ensure_event(event)
        return envelope.event_id in self._processed_event_id_set

    def record_processed(self, event: EventEnvelope) -> None:
        envelope = _ensure_event(event)
        if envelope.event_id in self._processed_event_id_set:
            raise ValueError(f"event_id deja traite: {envelope.event_id}")
        self._processed_event_ids.append(envelope.event_id)
        self._processed_event_id_set.add(envelope.event_id)

    def record_duplicate(self, event: EventEnvelope) -> None:
        envelope = _ensure_event(event)
        if envelope.event_id not in self._processed_event_id_set:
            raise ValueError(f"doublon sans event_id traite: {envelope.event_id}")
        self._duplicate_event_ids.append(envelope.event_id)

    def processed_event_ids(self) -> tuple[str, ...]:
        return tuple(self._processed_event_ids)

    def duplicate_event_ids(self) -> tuple[str, ...]:
        return tuple(self._duplicate_event_ids)


@dataclass(frozen=True)
class IdempotentEventConsumer:
    """Consommateur qui applique un evenement au plus une fois par event_id."""

    processed_events: InMemoryProcessedEventRegistry

    def __post_init__(self) -> None:
        if not isinstance(self.processed_events, InMemoryProcessedEventRegistry):
            raise ValueError("processed_events invalide")
        object.__setattr__(self, "_lock", threading.Lock())

    def consume(
        self,
        event: EventEnvelope,
        handler: Callable[[EventEnvelope], Any],
    ) -> EventConsumptionDecision:
        envelope = _ensure_event(event)
        if not callable(handler):
            raise ValueError("handler invalide")

        with self._lock:
            if self.processed_events.has_processed(envelope):
                self.processed_events.record_duplicate(envelope)
                return EventConsumptionDecision(
                    event_id=envelope.event_id,
                    applied=False,
                    duplicate=True,
                )

            handler(envelope)
            self.processed_events.record_processed(envelope)
            return EventConsumptionDecision(
                event_id=envelope.event_id,
                applied=True,
                duplicate=False,
            )


def _ensure_event_matches_mutation(
    state_mutation: ProducerStateMutation,
    event: EventEnvelope,
) -> None:
    if event.producer_context != state_mutation.producer_context:
        raise ValueError("producer_context incoherent avec mutation productrice")
    if event.aggregate_type != state_mutation.aggregate_type:
        raise ValueError("aggregate_type incoherent avec mutation productrice")
    if event.aggregate_id != state_mutation.aggregate_id:
        raise ValueError("aggregate_id incoherent avec mutation productrice")
    if event.aggregate_version != state_mutation.aggregate_version:
        raise ValueError("aggregate_version incoherente avec mutation productrice")


def _ensure_state_mutation(value: ProducerStateMutation) -> ProducerStateMutation:
    if not isinstance(value, ProducerStateMutation):
        raise ValueError("state_mutation invalide")
    return value


def _ensure_event(value: EventEnvelope) -> EventEnvelope:
    if not isinstance(value, EventEnvelope):
        raise ValueError("event invalide")
    return value


def _ensure_event_id(value: str) -> str:
    text_value = _ensure_text(value, "event_id")
    if _EVENT_ID_PATTERN.fullmatch(text_value) is None:
        raise ValueError("event_id invalide")
    return text_value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value
