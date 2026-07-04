"""Store memoire append-only des snapshots SD et de leur outbox."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.contracts.event_envelope import EventEnvelope
from app.contracts.strategy_experiments import StrategySnapshot
from app.strategy_design.domain.strategy_candidate import StrategySnapshotPublication


@dataclass(frozen=True)
class StoredStrategySnapshot:
    snapshot_id: str
    snapshot_hash: str
    snapshot: StrategySnapshot

    def __post_init__(self) -> None:
        _ensure_text(self.snapshot_id, "snapshot_id")
        _ensure_text(self.snapshot_hash, "snapshot_hash")
        if not isinstance(self.snapshot, StrategySnapshot):
            raise ValueError("StrategySnapshot attendu")
        if self.snapshot.strategy_version_id != self.snapshot_id:
            raise ValueError("snapshot_id incoherent")
        if self.snapshot.spec_hash != self.snapshot_hash:
            raise ValueError("snapshot_hash incoherent")


class InMemoryStrategySnapshotStore:
    def __init__(
        self,
        *,
        snapshots: tuple[StoredStrategySnapshot, ...],
        outbox_events: tuple[EventEnvelope, ...],
        supersedes_by_snapshot_id: dict[str, str],
    ) -> None:
        self._lock = threading.Lock()
        self._snapshots_by_id: dict[str, StoredStrategySnapshot] = {}
        self._snapshot_order: list[str] = []
        self._outbox_events_by_id: dict[str, EventEnvelope] = {}
        self._outbox_order: list[str] = []
        self._supersedes_by_snapshot_id = dict(supersedes_by_snapshot_id)
        self._superseded_by_snapshot_id = {
            superseded_id: snapshot_id
            for snapshot_id, superseded_id in self._supersedes_by_snapshot_id.items()
        }

        for snapshot in snapshots:
            self._append_snapshot_record(snapshot)
        for event in outbox_events:
            self._append_outbox_event(event)

    @classmethod
    def empty(cls) -> "InMemoryStrategySnapshotStore":
        return cls(
            snapshots=(),
            outbox_events=(),
            supersedes_by_snapshot_id={},
        )

    def append_publication(
        self,
        publication: StrategySnapshotPublication,
    ) -> StoredStrategySnapshot:
        if not isinstance(publication, StrategySnapshotPublication):
            raise ValueError("StrategySnapshotPublication attendue")

        with self._lock:
            if publication.snapshot_id in self._snapshots_by_id:
                existing = self._snapshots_by_id[publication.snapshot_id]
                if existing.snapshot_hash != publication.snapshot_hash:
                    raise ValueError("snapshot append-only viole")
                if publication.created_event.event_id not in self._outbox_events_by_id:
                    raise ValueError("transaction snapshot outbox incoherente")
                return existing

            if publication.supersedes_snapshot_id is not None:
                if publication.supersedes_snapshot_id not in self._snapshots_by_id:
                    raise ValueError("snapshot supersede absent")
                if publication.supersedes_snapshot_id in self._superseded_by_snapshot_id:
                    raise ValueError("snapshot deja supersede")
                if publication.superseded_event is None:
                    raise ValueError("event StrategyVersionSuperseded absent")
            elif publication.superseded_event is not None:
                raise ValueError("event StrategyVersionSuperseded sans relation")

            if publication.created_event.event_id in self._outbox_events_by_id:
                raise ValueError("event_id outbox duplique")
            if (
                publication.superseded_event is not None
                and publication.superseded_event.event_id in self._outbox_events_by_id
            ):
                raise ValueError("event_id outbox duplique")

            stored = StoredStrategySnapshot(
                snapshot_id=publication.snapshot_id,
                snapshot_hash=publication.snapshot_hash,
                snapshot=publication.snapshot,
            )
            self._append_snapshot_record(stored)
            self._append_outbox_event(publication.created_event)

            if publication.supersedes_snapshot_id is not None:
                self._supersedes_by_snapshot_id[publication.snapshot_id] = (
                    publication.supersedes_snapshot_id
                )
                self._superseded_by_snapshot_id[publication.supersedes_snapshot_id] = (
                    publication.snapshot_id
                )
                self._append_outbox_event(publication.superseded_event)

            return stored

    def get(self, snapshot_id: str) -> StoredStrategySnapshot:
        parsed_snapshot_id = _ensure_text(snapshot_id, "snapshot_id")
        with self._lock:
            if parsed_snapshot_id not in self._snapshots_by_id:
                raise ValueError(f"snapshot absent: {parsed_snapshot_id}")
            return self._snapshots_by_id[parsed_snapshot_id]

    def snapshots(self) -> tuple[StoredStrategySnapshot, ...]:
        with self._lock:
            return tuple(self._snapshots_by_id[snapshot_id] for snapshot_id in self._snapshot_order)

    def outbox_events(self) -> tuple[EventEnvelope, ...]:
        with self._lock:
            return tuple(self._outbox_events_by_id[event_id] for event_id in self._outbox_order)

    def supersedes(self, snapshot_id: str) -> str | None:
        parsed_snapshot_id = _ensure_text(snapshot_id, "snapshot_id")
        with self._lock:
            return self._supersedes_by_snapshot_id.get(parsed_snapshot_id)

    def superseded_by(self, snapshot_id: str) -> str | None:
        parsed_snapshot_id = _ensure_text(snapshot_id, "snapshot_id")
        with self._lock:
            return self._superseded_by_snapshot_id.get(parsed_snapshot_id)

    def _append_snapshot_record(self, snapshot: StoredStrategySnapshot) -> None:
        if not isinstance(snapshot, StoredStrategySnapshot):
            raise ValueError("StoredStrategySnapshot attendu")
        if snapshot.snapshot_id in self._snapshots_by_id:
            raise ValueError("snapshot_id duplique")
        self._snapshots_by_id[snapshot.snapshot_id] = snapshot
        self._snapshot_order.append(snapshot.snapshot_id)

    def _append_outbox_event(self, event: EventEnvelope) -> None:
        if not isinstance(event, EventEnvelope):
            raise ValueError("EventEnvelope attendu")
        if event.event_id in self._outbox_events_by_id:
            raise ValueError("event_id outbox duplique")
        self._outbox_events_by_id[event.event_id] = event
        self._outbox_order.append(event.event_id)


def _ensure_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value
