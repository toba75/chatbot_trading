"""Repository KA en mémoire pour les projections de connaissance."""

from __future__ import annotations

from app.contracts.event_envelope import EventEnvelope
from app.knowledge_access.application.request_projection import (
    ProjectionAlreadyRequestedError,
    ProjectionPersistenceDecision,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
)


class InMemoryKnowledgeProjectionRepository:
    """Repository strict et idempotent pour les tests applicatifs KA."""

    def __init__(self, projections: tuple[KnowledgeProjection, ...]) -> None:
        if projections is None:
            raise ValueError("projections absentes")
        self._projections_by_id: dict[str, KnowledgeProjection] = {}
        self._projection_id_by_fingerprint: dict[str, str] = {}
        for projection in projections:
            self._store_initial_projection(projection)

    @classmethod
    def empty(cls) -> "InMemoryKnowledgeProjectionRepository":
        return cls(projections=())

    def save_if_absent(
        self,
        projection: KnowledgeProjection,
    ) -> ProjectionPersistenceDecision:
        parsed_projection = _ensure_projection(projection)
        fingerprint_value = parsed_projection.build_fingerprint.value
        existing_projection_id = self._projection_id_by_fingerprint.get(fingerprint_value)
        if existing_projection_id is not None:
            return ProjectionPersistenceDecision(
                projection=self._projections_by_id[existing_projection_id],
                created=False,
            )
        if parsed_projection.projection_id in self._projections_by_id:
            raise ValueError(f"projection_id duplique: {parsed_projection.projection_id}")
        self._projections_by_id[parsed_projection.projection_id] = parsed_projection
        self._projection_id_by_fingerprint[fingerprint_value] = parsed_projection.projection_id
        return ProjectionPersistenceDecision(projection=parsed_projection, created=True)

    def require_absent_build_fingerprint(self, build_fingerprint: BuildFingerprint) -> None:
        parsed_fingerprint = _ensure_build_fingerprint(build_fingerprint)
        projection = self.projection_for_build_fingerprint(parsed_fingerprint)
        if projection is not None:
            raise ProjectionAlreadyRequestedError(
                projection_id=projection.projection_id,
                build_fingerprint=parsed_fingerprint,
            )

    def projection_for_build_fingerprint(
        self,
        build_fingerprint: BuildFingerprint,
    ) -> KnowledgeProjection | None:
        parsed_fingerprint = _ensure_build_fingerprint(build_fingerprint)
        projection_id = self._projection_id_by_fingerprint.get(parsed_fingerprint.value)
        if projection_id is None:
            return None
        return self._projections_by_id[projection_id]

    def projection_for_id(self, projection_id: str) -> KnowledgeProjection:
        if not isinstance(projection_id, str):
            raise ValueError("projection_id invalide")
        if projection_id not in self._projections_by_id:
            raise ValueError(f"projection inconnue: {projection_id}")
        return self._projections_by_id[projection_id]

    def save_transition(self, projection: KnowledgeProjection) -> KnowledgeProjection:
        parsed_projection = _ensure_projection(projection)
        if parsed_projection.projection_id not in self._projections_by_id:
            raise ValueError(f"projection inconnue: {parsed_projection.projection_id}")
        existing_projection = self._projections_by_id[parsed_projection.projection_id]
        if existing_projection.build_fingerprint != parsed_projection.build_fingerprint:
            raise ValueError("build_fingerprint transition incoherent")
        self._projections_by_id[parsed_projection.projection_id] = parsed_projection
        self._projection_id_by_fingerprint[
            parsed_projection.build_fingerprint.value
        ] = parsed_projection.projection_id
        return parsed_projection

    def projection_count(self) -> int:
        return len(self._projections_by_id)

    def _store_initial_projection(self, projection: KnowledgeProjection) -> None:
        parsed_projection = _ensure_projection(projection)
        fingerprint_value = parsed_projection.build_fingerprint.value
        if parsed_projection.projection_id in self._projections_by_id:
            raise ValueError(f"projection_id duplique: {parsed_projection.projection_id}")
        if fingerprint_value in self._projection_id_by_fingerprint:
            raise ValueError(f"build_fingerprint duplique: {fingerprint_value}")
        self._projections_by_id[parsed_projection.projection_id] = parsed_projection
        self._projection_id_by_fingerprint[fingerprint_value] = parsed_projection.projection_id


class InMemoryProjectionEventRegistry:
    """Registre local des événements CanonicalSourcePublished déjà traités par KA."""

    def __init__(
        self,
        *,
        processed_event_ids: tuple[str, ...],
        duplicate_event_ids: tuple[str, ...],
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
    def empty(cls) -> "InMemoryProjectionEventRegistry":
        return cls(processed_event_ids=(), duplicate_event_ids=())

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


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("projection invalide")
    return value


def _ensure_build_fingerprint(value: BuildFingerprint) -> BuildFingerprint:
    if not isinstance(value, BuildFingerprint):
        raise ValueError("build_fingerprint invalide")
    return value


def _ensure_event(value: EventEnvelope) -> EventEnvelope:
    if not isinstance(value, EventEnvelope):
        raise ValueError("event invalide")
    return value


def _ensure_event_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("event_id invalide")
    if value.strip() == "":
        raise ValueError("event_id vide")
    if value != value.strip():
        raise ValueError("event_id non normalise")
    if not value.startswith("EVT-"):
        raise ValueError("event_id invalide")
    return value


__all__ = [
    "InMemoryKnowledgeProjectionRepository",
    "InMemoryProjectionEventRegistry",
]
