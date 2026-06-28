"""Événements KA de cycle de vie KnowledgeProjection publiés via outbox."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.contracts.event_envelope import EventEnvelope
from app.knowledge_access.domain.knowledge_projection import KnowledgeProjection
from app.platform.event_bus import (
    InMemoryTransactionalOutbox,
    OutboxEntry,
    ProducerStateMutation,
)


@dataclass(frozen=True)
class KnowledgeProjectionEventFactory:
    """Fabrique d'événements publics KA pour une transition de projection."""

    occurred_at: str
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", _ensure_text(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "correlation_id",
            _ensure_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "causation_id", _ensure_text(self.causation_id, "causation_id"))

    def built(self, *, projection: KnowledgeProjection, chunk_count: int) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        parsed_chunk_count = _ensure_positive_integer(chunk_count, "chunk_count")
        return self._event(
            event_type="KnowledgeProjectionBuilt",
            projection=parsed_projection,
            aggregate_version=2,
            payload={
                "projection_id": parsed_projection.projection_id,
                "canonical_version_id": parsed_projection.canonical_version_id,
                "build_fingerprint": parsed_projection.build_fingerprint.value,
                "chunk_count": parsed_chunk_count,
            },
        )

    def became_searchable(
        self,
        *,
        projection: KnowledgeProjection,
        index_generation: str,
        published_at: str,
    ) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        return self._event(
            event_type="KnowledgeProjectionBecameSearchable",
            projection=parsed_projection,
            aggregate_version=4,
            payload={
                "projection_id": parsed_projection.projection_id,
                "canonical_version_id": parsed_projection.canonical_version_id,
                "projection_profile_id": parsed_projection.projection_profile.projection_profile_id,
                "index_generation": _ensure_text(index_generation, "index_generation"),
                "published_at": _ensure_text(published_at, "published_at"),
            },
        )

    def failed(
        self,
        *,
        projection: KnowledgeProjection,
        failed_step: str,
        public_error_code: str,
        retry_allowed: bool,
    ) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        if not isinstance(retry_allowed, bool):
            raise ValueError("retry_allowed non booleen")
        return self._event(
            event_type="KnowledgeProjectionFailed",
            projection=parsed_projection,
            aggregate_version=5,
            payload={
                "projection_id": parsed_projection.projection_id,
                "failed_step": _ensure_text(failed_step, "failed_step"),
                "public_error_code": _ensure_text(public_error_code, "public_error_code"),
                "retry_allowed": retry_allowed,
            },
        )

    def became_stale(
        self,
        *,
        projection: KnowledgeProjection,
        stale_reason: str,
        superseding_input_ref: str,
    ) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        return self._event(
            event_type="KnowledgeProjectionBecameStale",
            projection=parsed_projection,
            aggregate_version=6,
            payload={
                "projection_id": parsed_projection.projection_id,
                "stale_reason": _ensure_text(stale_reason, "stale_reason"),
                "superseding_input_ref": _ensure_text(
                    superseding_input_ref,
                    "superseding_input_ref",
                ),
            },
        )

    def retired(
        self,
        *,
        projection: KnowledgeProjection,
        retired_reason: str,
    ) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        return self._event(
            event_type="KnowledgeProjectionRetired",
            projection=parsed_projection,
            aggregate_version=7,
            payload={
                "projection_id": parsed_projection.projection_id,
                "retired_reason": _ensure_text(retired_reason, "retired_reason"),
            },
        )

    def _event(
        self,
        *,
        event_type: str,
        projection: KnowledgeProjection,
        aggregate_version: int,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        parsed_projection = _ensure_projection(projection)
        return EventEnvelope.from_payload(
            {
                "event_id": _event_id_for(event_type, parsed_projection.projection_id),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": self.occurred_at,
                "aggregate_type": "KnowledgeProjection",
                "aggregate_id": parsed_projection.projection_id,
                "aggregate_version": aggregate_version,
                "correlation_id": self.correlation_id,
                "causation_id": self.causation_id,
                "producer_context": "KA",
                "payload": payload,
            }
        )


def append_projection_events_to_outbox(
    *,
    outbox: InMemoryTransactionalOutbox,
    events: Iterable[EventEnvelope],
) -> tuple[OutboxEntry, ...]:
    parsed_outbox = _ensure_outbox(outbox)
    parsed_events = _ensure_events(events)
    pairs: list[tuple[ProducerStateMutation, EventEnvelope]] = []
    for event in parsed_events:
        if parsed_outbox.has_event(event.event_id):
            continue
        pairs.append(
            (
                ProducerStateMutation(
                    mutation_id=f"MUT-{event.event_id}",
                    producer_context=event.producer_context,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    aggregate_version=event.aggregate_version,
                ),
                event,
            )
        )
    if len(pairs) == 0:
        return ()
    return parsed_outbox.append_many_in_transaction(tuple(pairs))


def _event_id_for(event_type: str, projection_id: str) -> str:
    parsed_event_type = _ensure_text(event_type, "event_type")
    parsed_projection_id = _ensure_text(projection_id, "projection_id")
    digest = hashlib.sha256(f"{parsed_event_type}:{parsed_projection_id}".encode("utf-8")).hexdigest()
    return f"EVT-KA-{parsed_event_type.upper()}-{digest[:24].upper()}"


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("projection invalide")
    return value


def _ensure_outbox(value: InMemoryTransactionalOutbox) -> InMemoryTransactionalOutbox:
    if not isinstance(value, InMemoryTransactionalOutbox):
        raise ValueError("outbox invalide")
    return value


def _ensure_events(value: Iterable[EventEnvelope]) -> tuple[EventEnvelope, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, EventEnvelope):
            raise ValueError("event invalide")
    return events


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "KnowledgeProjectionEventFactory",
    "append_projection_events_to_outbox",
]
