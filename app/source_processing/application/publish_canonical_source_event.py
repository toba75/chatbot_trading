"""Publication outbox de l'événement CanonicalSourcePublished M-004."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.event_envelope import EventEnvelope
from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import CanonicalSourceRef
from app.platform.event_bus.outbox import (
    InMemoryTransactionalOutbox,
    OutboxEntry,
    ProducerStateMutation,
)
from app.source_processing.application.publish_canonical_source import PublishCanonicalSourceResult
from app.source_processing.domain.canonical_source import CanonicalSourceStatus


_EVENT_TYPE = "CanonicalSourcePublished"
_EVENT_VERSION = 1
_AGGREGATE_TYPE = "CanonicalSource"
_PRODUCER_CONTEXT = "SP"


@dataclass(frozen=True)
class PublishCanonicalSourceEventCommand:
    """Commande d'inscription outbox de CanonicalSourcePublished."""

    publication_result: PublishCanonicalSourceResult
    outbox: InMemoryTransactionalOutbox
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        _ensure_publication_result(self.publication_result)
        if not isinstance(self.outbox, InMemoryTransactionalOutbox):
            raise ValueError("outbox invalide")
        _ensure_text(self.correlation_id, "correlation_id invalide")
        _ensure_text(self.causation_id, "causation_id invalide")


@dataclass(frozen=True)
class CanonicalSourcePublishedEventResult:
    """Résultat observable d'une inscription outbox CanonicalSourcePublished."""

    outbox_entry: OutboxEntry
    event: EventEnvelope
    created: bool

    def __post_init__(self) -> None:
        if not isinstance(self.outbox_entry, OutboxEntry):
            raise ValueError("entrée outbox invalide")
        if not isinstance(self.event, EventEnvelope):
            raise ValueError("événement CanonicalSourcePublished invalide")
        if self.outbox_entry.event != self.event:
            raise ValueError("événement outbox incohérent")
        if not isinstance(self.created, bool):
            raise ValueError("indicateur created invalide")


class PublishCanonicalSourceEventHandler:
    """Inscrit CanonicalSourcePublished dans l'outbox M-002 après publication acceptée."""

    def handle(
        self,
        command: PublishCanonicalSourceEventCommand,
    ) -> CanonicalSourcePublishedEventResult:
        if not isinstance(command, PublishCanonicalSourceEventCommand):
            raise ValueError("commande CanonicalSourcePublished invalide")

        publication_result = _ensure_publication_result(command.publication_result)
        aggregate_version = _aggregate_version_for(publication_result)
        event = build_canonical_source_published_event(
            canonical_ref=publication_result.canonical_ref,
            aggregate_version=aggregate_version,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
        )
        state_mutation = _state_mutation_for(event)

        if command.outbox.has_event(event.event_id):
            existing_entry = command.outbox.entry_for(event.event_id)
            if existing_entry.event != event or existing_entry.state_mutation != state_mutation:
                raise ValueError("événement outbox incohérent pour version canonique")
            return CanonicalSourcePublishedEventResult(
                outbox_entry=existing_entry,
                event=existing_entry.event,
                created=False,
            )

        entry = command.outbox.append_in_transaction(
            state_mutation=state_mutation,
            event=event,
        )
        return CanonicalSourcePublishedEventResult(
            outbox_entry=entry,
            event=entry.event,
            created=True,
        )


def build_canonical_source_published_event(
    *,
    canonical_ref: CanonicalSourceRef,
    aggregate_version: int,
    correlation_id: str,
    causation_id: str,
) -> EventEnvelope:
    """Construit l'enveloppe publique depuis le seul CanonicalSourceRef contractuel."""

    if not isinstance(canonical_ref, CanonicalSourceRef):
        raise ValueError("CanonicalSourceRef public obligatoire")
    parsed_aggregate_version = _ensure_positive_integer(
        aggregate_version,
        "aggregate_version invalide",
    )

    return EventEnvelope.from_payload(
        {
            "event_id": canonical_source_published_event_id_for(
                canonical_ref.canonical_version_id
            ),
            "event_type": _EVENT_TYPE,
            "event_version": _EVENT_VERSION,
            "occurred_at": canonical_ref.accepted_at,
            "aggregate_type": _AGGREGATE_TYPE,
            "aggregate_id": canonical_ref.canonical_source_id,
            "aggregate_version": parsed_aggregate_version,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "producer_context": _PRODUCER_CONTEXT,
            "payload": canonical_ref.to_payload(),
        }
    )


def canonical_source_published_event_id_for(canonical_version_id: str) -> str:
    parsed_version_id = _ensure_canonical_version_id(canonical_version_id)
    return f"EVT-CANONICAL-SOURCE-PUBLISHED-{parsed_version_id}"


def _ensure_publication_result(
    value: Any,
) -> PublishCanonicalSourceResult:
    if not isinstance(value, PublishCanonicalSourceResult):
        raise ValueError("publication acceptée obligatoire")
    if value.canonical_source.status is not CanonicalSourceStatus.PUBLISHED:
        raise ValueError("publication acceptée obligatoire")
    if value.published_version.canonical_ref != value.canonical_ref:
        raise ValueError("CanonicalSourceRef publiée incohérente")
    if not value.canonical_source.has_version(value.published_version.canonical_version_id):
        raise ValueError("version publiée absente")
    return value


def _aggregate_version_for(publication_result: PublishCanonicalSourceResult) -> int:
    for index, version in enumerate(publication_result.canonical_source.versions, start=1):
        if version.canonical_version_id == publication_result.published_version.canonical_version_id:
            return index
    raise ValueError("version publiée absente")


def _state_mutation_for(event: EventEnvelope) -> ProducerStateMutation:
    canonical_version_id = _ensure_canonical_version_id(event.payload["canonical_version_id"])
    return ProducerStateMutation(
        mutation_id=f"MUT-SP-CANONICAL-SOURCE-PUBLISHED-{canonical_version_id}",
        producer_context=event.producer_context,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        aggregate_version=event.aggregate_version,
    )


def _ensure_canonical_version_id(value: str) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "CVER"))
    except ValueError as exc:
        raise ValueError(f"canonical_version_id invalide: {exc}") from exc


def _ensure_text(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    if value.strip() == "":
        raise ValueError(message)
    if value != value.strip():
        raise ValueError(message)
    return value


def _ensure_positive_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


__all__ = [
    "CanonicalSourcePublishedEventResult",
    "PublishCanonicalSourceEventCommand",
    "PublishCanonicalSourceEventHandler",
    "build_canonical_source_published_event",
    "canonical_source_published_event_id_for",
]
