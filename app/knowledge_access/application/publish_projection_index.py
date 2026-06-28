"""Cas d'usage KA de publication d'une projection dans un index vectoriel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.knowledge_access.application.projection_events import (
    KnowledgeProjectionEventFactory,
    ProjectionOutbox,
    append_projection_events_to_outbox,
)
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionStatus,
)
from app.knowledge_access.domain.projection_encoding import ProjectionEncodingResult
from app.knowledge_access.domain.projection_index import (
    PartialVectorIndexError,
    VectorIndexDeletion,
    VectorIndexError,
    VectorIndexPoint,
    VectorIndexPublication,
    VectorIndexPublishRequest,
    VectorIndexSchema,
    VectorIndexUnavailableError,
    index_generation_for,
)
from app.knowledge_access.domain.time import ensure_utc_instant


class ProjectionStateRepository(Protocol):
    """Port de persistance d'état KnowledgeProjection pour l'indexation."""

    def projection_for_id(self, projection_id: str) -> KnowledgeProjection:
        """Retourne une projection existante."""

    def save_transition(self, projection: KnowledgeProjection) -> KnowledgeProjection:
        """Persiste une transition de projection existante."""


class VectorIndex(Protocol):
    """Port stable qui masque la projection technique Qdrant."""

    def publish_generation(self, request: VectorIndexPublishRequest) -> VectorIndexPublication:
        """Publie atomiquement une génération d'index."""

    def delete_generation(self, *, collection_name: str, index_generation: str) -> VectorIndexDeletion:
        """Supprime une génération technique sans toucher la source canonique."""

    def generation_exists(self, *, collection_name: str, index_generation: str) -> bool:
        """Indique si une génération technique existe sans la créer."""


@dataclass(frozen=True)
class PublishProjectionIndexCommand:
    """Commande KA de publication d'index technique régénérable."""

    projection_id: str
    encoded_projection: ProjectionEncodingResult
    index_schema: VectorIndexSchema
    occurred_at: str
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        if not isinstance(self.encoded_projection, ProjectionEncodingResult):
            raise ValueError("encoded_projection invalide")
        if self.encoded_projection.projection_id != self.projection_id:
            raise ValueError("projection_id encodage incoherent")
        if not isinstance(self.index_schema, VectorIndexSchema):
            raise ValueError("index_schema invalide")
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "correlation_id",
            _ensure_correlation_id(self.correlation_id),
        )
        object.__setattr__(self, "causation_id", _ensure_causation_id(self.causation_id))


@dataclass(frozen=True)
class MarkProjectionStaleCommand:
    """Commande KA marquant une projection obsolète."""

    projection_id: str
    stale_reason: str
    superseding_input_ref: str
    occurred_at: str
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        object.__setattr__(self, "stale_reason", _ensure_text(self.stale_reason, "stale_reason"))
        object.__setattr__(
            self,
            "superseding_input_ref",
            _ensure_text(self.superseding_input_ref, "superseding_input_ref"),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "correlation_id",
            _ensure_correlation_id(self.correlation_id),
        )
        object.__setattr__(self, "causation_id", _ensure_causation_id(self.causation_id))


@dataclass(frozen=True)
class RetireProjectionIndexCommand:
    """Commande KA de retrait d'une projection indexée."""

    projection_id: str
    collection_name: str
    index_generation: str
    retired_reason: str
    occurred_at: str
    correlation_id: str
    causation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        object.__setattr__(self, "collection_name", _ensure_text(self.collection_name, "collection_name"))
        object.__setattr__(
            self,
            "index_generation",
            _ensure_text(self.index_generation, "index_generation"),
        )
        object.__setattr__(
            self,
            "retired_reason",
            _ensure_text(self.retired_reason, "retired_reason"),
        )
        object.__setattr__(self, "occurred_at", ensure_utc_instant(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "correlation_id",
            _ensure_correlation_id(self.correlation_id),
        )
        object.__setattr__(self, "causation_id", _ensure_causation_id(self.causation_id))


@dataclass(frozen=True)
class PublishProjectionIndexResult:
    """Résultat observable de publication d'index."""

    projection: KnowledgeProjection
    index_generation: str
    published_point_count: int
    idempotent: bool
    public_error_code: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.projection, KnowledgeProjection):
            raise ValueError("projection invalide")
        object.__setattr__(self, "index_generation", _ensure_text(self.index_generation, "index_generation"))
        if isinstance(self.published_point_count, bool) or not isinstance(self.published_point_count, int):
            raise ValueError("published_point_count invalide")
        if self.published_point_count < 0:
            raise ValueError("published_point_count invalide")
        if not isinstance(self.idempotent, bool):
            raise ValueError("idempotent non booleen")
        if self.public_error_code is not None:
            object.__setattr__(
                self,
                "public_error_code",
                _ensure_text(self.public_error_code, "public_error_code"),
            )


@dataclass(frozen=True)
class ProjectionLifecycleResult:
    """Résultat observable d'une transition STALE ou RETIRED."""

    projection: KnowledgeProjection

    def __post_init__(self) -> None:
        if not isinstance(self.projection, KnowledgeProjection):
            raise ValueError("projection invalide")


class PublishProjectionIndexHandler:
    """Orchestre la publication atomique d'une projection KA dans VectorIndex."""

    def __init__(
        self,
        *,
        projection_repository: ProjectionStateRepository,
        vector_index: VectorIndex,
        outbox: ProjectionOutbox,
    ) -> None:
        if not callable(getattr(projection_repository, "projection_for_id", None)):
            raise ValueError("projection_repository sans projection_for_id")
        if not callable(getattr(projection_repository, "save_transition", None)):
            raise ValueError("projection_repository sans save_transition")
        if not callable(getattr(vector_index, "publish_generation", None)):
            raise ValueError("vector_index sans publish_generation")
        if not callable(getattr(vector_index, "delete_generation", None)):
            raise ValueError("vector_index sans delete_generation")
        if not callable(getattr(vector_index, "generation_exists", None)):
            raise ValueError("vector_index sans generation_exists")
        if not callable(getattr(outbox, "has_event", None)):
            raise ValueError("outbox invalide")
        if not callable(getattr(outbox, "append_many_in_transaction", None)):
            raise ValueError("outbox invalide")
        self._projection_repository = projection_repository
        self._vector_index = vector_index
        self._outbox = outbox

    def publish(self, command: PublishProjectionIndexCommand) -> PublishProjectionIndexResult:
        parsed_command = _ensure_publish_command(command)
        projection = self._projection_repository.projection_for_id(parsed_command.projection_id)
        index_generation = index_generation_for(
            projection=projection,
            encoded_projection=parsed_command.encoded_projection,
            index_schema=parsed_command.index_schema,
        )
        request = self._publish_request_for(
            projection=projection,
            encoded_projection=parsed_command.encoded_projection,
            index_schema=parsed_command.index_schema,
            index_generation=index_generation,
        )
        factory = _event_factory_for(parsed_command)

        if projection.status is ProjectionStatus.SEARCHABLE:
            if not self._vector_index.generation_exists(
                collection_name=request.collection_name,
                index_generation=request.index_generation,
            ):
                raise VectorIndexUnavailableError("generation SEARCHABLE absente")
            publication = self._vector_index.publish_generation(request)
            return PublishProjectionIndexResult(
                projection=projection,
                index_generation=index_generation,
                published_point_count=publication.published_point_count,
                idempotent=True,
                public_error_code=None,
            )

        built_event = None
        if projection.status is ProjectionStatus.REQUESTED:
            built_projection = projection.start_build().mark_built()
            built_event = factory.built(
                projection=built_projection,
                chunk_count=len(parsed_command.encoded_projection.encoded_chunks),
            )
            indexing_projection = built_projection.start_indexing()
        elif projection.status is ProjectionStatus.BUILDING:
            built_projection = projection.mark_built()
            built_event = factory.built(
                projection=built_projection,
                chunk_count=len(parsed_command.encoded_projection.encoded_chunks),
            )
            indexing_projection = built_projection.start_indexing()
        elif projection.status is ProjectionStatus.BUILT:
            indexing_projection = projection.start_indexing()
        elif projection.status is ProjectionStatus.INDEXING:
            indexing_projection = projection
        else:
            raise ValueError(f"projection non publiable: {projection.status.value}")

        try:
            publication = self._vector_index.publish_generation(request)
        except VectorIndexError as exc:
            failed_projection = indexing_projection.mark_failed()
            self._projection_repository.save_transition(failed_projection)
            failed_event = factory.failed(
                projection=failed_projection,
                failed_step="INDEXING",
                public_error_code=exc.error_code,
                retry_allowed=True,
            )
            events = (failed_event,) if built_event is None else (built_event, failed_event)
            append_projection_events_to_outbox(outbox=self._outbox, events=events)
            return PublishProjectionIndexResult(
                projection=failed_projection,
                index_generation=index_generation,
                published_point_count=0,
                idempotent=False,
                public_error_code=exc.error_code,
            )

        searchable_projection = indexing_projection.mark_searchable()
        self._projection_repository.save_transition(searchable_projection)
        searchable_event = factory.became_searchable(
            projection=searchable_projection,
            index_generation=index_generation,
            published_at=parsed_command.occurred_at,
        )
        events = (searchable_event,) if built_event is None else (built_event, searchable_event)
        append_projection_events_to_outbox(outbox=self._outbox, events=events)
        return PublishProjectionIndexResult(
            projection=searchable_projection,
            index_generation=index_generation,
            published_point_count=publication.published_point_count,
            idempotent=publication.idempotent,
            public_error_code=None,
        )

    def mark_stale(self, command: MarkProjectionStaleCommand) -> ProjectionLifecycleResult:
        parsed_command = _ensure_stale_command(command)
        projection = self._projection_repository.projection_for_id(parsed_command.projection_id)
        stale_projection = projection.mark_stale()
        self._projection_repository.save_transition(stale_projection)
        factory = KnowledgeProjectionEventFactory(
            occurred_at=parsed_command.occurred_at,
            correlation_id=parsed_command.correlation_id,
            causation_id=parsed_command.causation_id,
        )
        append_projection_events_to_outbox(
            outbox=self._outbox,
            events=(
                factory.became_stale(
                    projection=stale_projection,
                    stale_reason=parsed_command.stale_reason,
                    superseding_input_ref=parsed_command.superseding_input_ref,
                ),
            ),
        )
        return ProjectionLifecycleResult(projection=stale_projection)

    def retire(self, command: RetireProjectionIndexCommand) -> ProjectionLifecycleResult:
        parsed_command = _ensure_retire_command(command)
        projection = self._projection_repository.projection_for_id(parsed_command.projection_id)
        deletion = self._vector_index.delete_generation(
            collection_name=parsed_command.collection_name,
            index_generation=parsed_command.index_generation,
        )
        if not deletion.deleted:
            raise ValueError("index_generation absente pour retrait")
        retired_projection = projection.retire()
        self._projection_repository.save_transition(retired_projection)
        factory = KnowledgeProjectionEventFactory(
            occurred_at=parsed_command.occurred_at,
            correlation_id=parsed_command.correlation_id,
            causation_id=parsed_command.causation_id,
        )
        append_projection_events_to_outbox(
            outbox=self._outbox,
            events=(
                factory.retired(
                    projection=retired_projection,
                    retired_reason=parsed_command.retired_reason,
                ),
            ),
        )
        return ProjectionLifecycleResult(projection=retired_projection)

    def _publish_request_for(
        self,
        *,
        projection: KnowledgeProjection,
        encoded_projection: ProjectionEncodingResult,
        index_schema: VectorIndexSchema,
        index_generation: str,
    ) -> VectorIndexPublishRequest:
        points = tuple(
            VectorIndexPoint.from_encoded_chunk(
                projection=projection,
                encoded_chunk=chunk,
                index_schema=index_schema,
            )
            for chunk in encoded_projection.encoded_chunks
        )
        return VectorIndexPublishRequest(
            collection_name=index_schema.collection_name,
            index_generation=index_generation,
            schema=index_schema,
            build_fingerprint=encoded_projection.build_fingerprint,
            points=points,
            expected_point_count=len(encoded_projection.encoded_chunks),
        )


def _event_factory_for(command: PublishProjectionIndexCommand) -> KnowledgeProjectionEventFactory:
    return KnowledgeProjectionEventFactory(
        occurred_at=command.occurred_at,
        correlation_id=command.correlation_id,
        causation_id=command.causation_id,
    )


def _ensure_publish_command(value: PublishProjectionIndexCommand) -> PublishProjectionIndexCommand:
    if not isinstance(value, PublishProjectionIndexCommand):
        raise ValueError("commande PublishProjectionIndex invalide")
    return value


def _ensure_stale_command(value: MarkProjectionStaleCommand) -> MarkProjectionStaleCommand:
    if not isinstance(value, MarkProjectionStaleCommand):
        raise ValueError("commande MarkProjectionStale invalide")
    return value


def _ensure_retire_command(value: RetireProjectionIndexCommand) -> RetireProjectionIndexCommand:
    if not isinstance(value, RetireProjectionIndexCommand):
        raise ValueError("commande RetireProjectionIndex invalide")
    return value


def _ensure_projection_id(value: Any) -> str:
    text = _ensure_text(value, "projection_id")
    if not text.startswith("PROJ-"):
        raise ValueError("projection_id invalide")
    return text


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_correlation_id(value: Any) -> str:
    text = _ensure_text(value, "correlation_id")
    if not text.startswith("CORR-"):
        raise ValueError("correlation_id invalide")
    return text


def _ensure_causation_id(value: Any) -> str:
    text = _ensure_text(value, "causation_id")
    if not (text.startswith("CMD-") or text.startswith("EVT-")):
        raise ValueError("causation_id invalide")
    return text


__all__ = [
    "MarkProjectionStaleCommand",
    "ProjectionLifecycleResult",
    "ProjectionStateRepository",
    "PublishProjectionIndexCommand",
    "PublishProjectionIndexHandler",
    "PublishProjectionIndexResult",
    "RetireProjectionIndexCommand",
    "VectorIndex",
]
