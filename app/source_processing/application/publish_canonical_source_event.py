"""Publication outbox de l'événement CanonicalSourcePublished M-004."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.event_envelope import EventEnvelope
from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import CanonicalSourceRef
from app.platform.event_bus.outbox import (
    OutboxEntry,
    ProducerStateMutation,
)
from app.source_processing.application.publish_canonical_source import PublishCanonicalSourceResult
from app.source_processing.domain.canonical_source import CanonicalSourceStatus


_PUBLISHED_EVENT_TYPE = "CanonicalSourcePublished"
_SUPERSEDED_EVENT_TYPE = "CanonicalSourceSuperseded"
_EVENT_VERSION = 1
_AGGREGATE_TYPE = "CanonicalSource"
_PRODUCER_CONTEXT = "SP"


class CanonicalPublicationOutbox(Protocol):
    """Port minimal requis pour inscrire les événements canoniques."""

    def has_event(self, event_id: str) -> bool:
        """Indique si un event_id existe déjà."""

    def entry_for(self, event_id: str) -> OutboxEntry:
        """Retourne l'entrée outbox existante."""

    def append_many_in_transaction(
        self,
        mutations_and_events: Iterable[tuple[ProducerStateMutation, EventEnvelope]],
    ) -> tuple[OutboxEntry, ...]:
        """Inscrit l'événement et sa mutation productrice atomiquement."""


@dataclass(frozen=True)
class PublishCanonicalSourceEventCommand:
    """Commande d'inscription outbox de CanonicalSourcePublished."""

    publication_result: PublishCanonicalSourceResult
    outbox: CanonicalPublicationOutbox
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        _ensure_publication_result(self.publication_result)
        if not _is_canonical_publication_outbox(self.outbox):
            raise ValueError("outbox invalide")
        _ensure_text(self.correlation_id, "correlation_id invalide")
        _ensure_text(self.causation_id, "causation_id invalide")


@dataclass(frozen=True)
class CanonicalSourcePublishedEventResult:
    """Résultat observable d'une inscription outbox CanonicalSourcePublished."""

    outbox_entry: OutboxEntry
    event: EventEnvelope
    created: bool
    superseded_entry: OutboxEntry | None = None
    superseded_event: EventEnvelope | None = None
    superseded_created: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.outbox_entry, OutboxEntry):
            raise ValueError("entrée outbox invalide")
        if not isinstance(self.event, EventEnvelope):
            raise ValueError("événement CanonicalSourcePublished invalide")
        if self.outbox_entry.event != self.event:
            raise ValueError("événement outbox incohérent")
        if not isinstance(self.created, bool):
            raise ValueError("indicateur created invalide")
        if self.superseded_entry is None:
            if self.superseded_event is not None or self.superseded_created:
                raise ValueError("événement CanonicalSourceSuperseded incohérent")
            return
        if not isinstance(self.superseded_entry, OutboxEntry):
            raise ValueError("entrée supersession outbox invalide")
        if not isinstance(self.superseded_event, EventEnvelope):
            raise ValueError("événement CanonicalSourceSuperseded invalide")
        if self.superseded_entry.event != self.superseded_event:
            raise ValueError("événement supersession outbox incohérent")
        if not isinstance(self.superseded_created, bool):
            raise ValueError("indicateur superseded_created invalide")


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
        superseded_event = _superseded_event_for(
            publication_result=publication_result,
            aggregate_version=aggregate_version,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
        )
        events = (event,) if superseded_event is None else (event, superseded_event)
        entries = _append_or_reuse_events(outbox=command.outbox, events=events)
        entry, created = entries[0]
        superseded_entry: OutboxEntry | None = None
        superseded_created = False
        if superseded_event is not None:
            superseded_entry, superseded_created = entries[1]
        return CanonicalSourcePublishedEventResult(
            outbox_entry=entry,
            event=entry.event,
            created=created,
            superseded_entry=superseded_entry,
            superseded_event=None if superseded_entry is None else superseded_entry.event,
            superseded_created=superseded_created,
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
            "event_type": _PUBLISHED_EVENT_TYPE,
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


def build_canonical_source_superseded_event(
    *,
    canonical_ref: CanonicalSourceRef,
    previous_canonical_version_id: str,
    aggregate_version: int,
    correlation_id: str,
    causation_id: str,
) -> EventEnvelope:
    """Construit l'événement de supersession sans exposer de contenu SP interne."""

    if not isinstance(canonical_ref, CanonicalSourceRef):
        raise ValueError("CanonicalSourceRef public obligatoire")
    previous_version_id = _ensure_canonical_version_id(previous_canonical_version_id)
    parsed_aggregate_version = _ensure_positive_integer(
        aggregate_version,
        "aggregate_version invalide",
    )
    return EventEnvelope.from_payload(
        {
            "event_id": canonical_source_superseded_event_id_for(
                canonical_ref.canonical_version_id
            ),
            "event_type": _SUPERSEDED_EVENT_TYPE,
            "event_version": _EVENT_VERSION,
            "occurred_at": canonical_ref.accepted_at,
            "aggregate_type": _AGGREGATE_TYPE,
            "aggregate_id": canonical_ref.canonical_source_id,
            "aggregate_version": parsed_aggregate_version,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "producer_context": _PRODUCER_CONTEXT,
            "payload": {
                "schema_version": "1.0",
                "canonical_source_id": canonical_ref.canonical_source_id,
                "previous_canonical_version_id": previous_version_id,
                "new_canonical_version_id": canonical_ref.canonical_version_id,
            },
        }
    )


def canonical_source_published_event_id_for(canonical_version_id: str) -> str:
    parsed_version_id = _ensure_canonical_version_id(canonical_version_id)
    return f"EVT-CANONICAL-SOURCE-PUBLISHED-{parsed_version_id}"


def canonical_source_superseded_event_id_for(canonical_version_id: str) -> str:
    parsed_version_id = _ensure_canonical_version_id(canonical_version_id)
    return f"EVT-CANONICAL-SOURCE-SUPERSEDED-{parsed_version_id}"


def _append_or_reuse_events(
    *,
    outbox: CanonicalPublicationOutbox,
    events: tuple[EventEnvelope, ...],
) -> tuple[tuple[OutboxEntry, bool], ...]:
    mutations_and_events = tuple((_state_mutation_for(event), event) for event in events)
    existing_entries = _existing_outbox_entries_for(
        outbox=outbox,
        mutations_and_events=mutations_and_events,
    )
    if existing_entries is not None:
        return tuple((entry, False) for entry in existing_entries)
    try:
        return tuple(
            (entry, True)
            for entry in outbox.append_many_in_transaction(mutations_and_events)
        )
    except ValueError:
        existing_entries = _existing_outbox_entries_for(
            outbox=outbox,
            mutations_and_events=mutations_and_events,
        )
        if existing_entries is not None:
            return tuple((entry, False) for entry in existing_entries)
        raise


def _existing_outbox_entries_for(
    *,
    outbox: CanonicalPublicationOutbox,
    mutations_and_events: tuple[tuple[ProducerStateMutation, EventEnvelope], ...],
) -> tuple[OutboxEntry, ...] | None:
    existing_flags = tuple(
        outbox.has_event(event.event_id)
        for _, event in mutations_and_events
    )
    if not any(existing_flags):
        return None
    if not all(existing_flags):
        raise ValueError("événements outbox incomplets pour version canonique")

    entries: list[OutboxEntry] = []
    for state_mutation, event in mutations_and_events:
        existing_entry = outbox.entry_for(event.event_id)
        if existing_entry.event != event or existing_entry.state_mutation != state_mutation:
            raise ValueError("événement outbox incohérent pour version canonique")
        entries.append(existing_entry)
    return tuple(entries)


def _superseded_event_for(
    *,
    publication_result: PublishCanonicalSourceResult,
    aggregate_version: int,
    correlation_id: str,
    causation_id: str,
) -> EventEnvelope | None:
    if aggregate_version == 1:
        return None
    previous_version = publication_result.canonical_source.versions[aggregate_version - 2]
    return build_canonical_source_superseded_event(
        canonical_ref=publication_result.canonical_ref,
        previous_canonical_version_id=previous_version.canonical_version_id,
        aggregate_version=aggregate_version,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


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
    if event.event_type == _SUPERSEDED_EVENT_TYPE:
        canonical_version_id = _ensure_canonical_version_id(
            event.payload["new_canonical_version_id"]
        )
        mutation_name = "CANONICAL-SOURCE-SUPERSEDED"
    else:
        canonical_version_id = _ensure_canonical_version_id(event.payload["canonical_version_id"])
        mutation_name = "CANONICAL-SOURCE-PUBLISHED"
    return ProducerStateMutation(
        mutation_id=f"MUT-SP-{mutation_name}-{canonical_version_id}",
        producer_context=event.producer_context,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        aggregate_version=event.aggregate_version,
    )


def _is_canonical_publication_outbox(value: Any) -> bool:
    return (
        callable(getattr(value, "has_event", None))
        and callable(getattr(value, "entry_for", None))
        and callable(getattr(value, "append_many_in_transaction", None))
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
    "CanonicalPublicationOutbox",
    "CanonicalSourcePublishedEventResult",
    "PublishCanonicalSourceEventCommand",
    "PublishCanonicalSourceEventHandler",
    "build_canonical_source_published_event",
    "build_canonical_source_superseded_event",
    "canonical_source_published_event_id_for",
    "canonical_source_superseded_event_id_for",
]
