"""Read-model public de la projection courante détenu par KA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import SourceLocator
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionStatus,
)
from app.knowledge_access.domain.time import ensure_utc_instant


_FRESHNESS_BY_PROJECTION_STATUS = {
    ProjectionStatus.REQUESTED: "PENDING",
    ProjectionStatus.BUILDING: "PENDING",
    ProjectionStatus.BUILT: "PENDING",
    ProjectionStatus.INDEXING: "PENDING",
    ProjectionStatus.SEARCHABLE: "CURRENT",
    ProjectionStatus.STALE: "STALE",
    ProjectionStatus.FAILED: "UNAVAILABLE",
    ProjectionStatus.RETIRED: "UNAVAILABLE",
}
_FRESHNESS_STATUSES = frozenset(_FRESHNESS_BY_PROJECTION_STATUS.values())


class ProjectionReadRepository(Protocol):
    """Port KA qui lit l'agrégat courant et ses sorties inspectables bornées."""

    def current_projection_for_document_id(
        self,
        document_id: str,
        sample_limit: int,
    ) -> "ProjectionReadRecord | None":
        """Retourne l'état réel KA sans exposer son stockage technique."""


@dataclass(frozen=True, slots=True)
class ProjectionReadRecord:
    """État KA lu depuis la source de vérité de projection."""

    projection: KnowledgeProjection
    chunk_count: int
    chunk_samples: tuple[KnowledgeChunk, ...]
    state_observed_at: str

    def __post_init__(self) -> None:
        projection = _ensure_projection(self.projection)
        chunk_count = _ensure_non_negative_integer(self.chunk_count, "chunk_count")
        chunk_samples = _ensure_chunk_samples(self.chunk_samples)
        if len(chunk_samples) > chunk_count:
            raise ValueError("échantillons de chunks incohérents avec chunk_count")
        for sample in chunk_samples:
            if sample.document_id != projection.document_id:
                raise ValueError("chunk documentaire incohérent avec la projection")
            if sample.canonical_version_id != projection.canonical_version_id:
                raise ValueError("version canonique du chunk incohérente")
        object.__setattr__(self, "chunk_count", chunk_count)
        object.__setattr__(self, "chunk_samples", chunk_samples)
        object.__setattr__(
            self,
            "state_observed_at",
            ensure_utc_instant(self.state_observed_at, "state_observed_at"),
        )


@dataclass(frozen=True, slots=True)
class ProjectionNotRequestedView:
    """Absence réelle de projection KA pour un document."""

    document_id: str
    projection_status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        if self.projection_status != "PROJECTION_NOT_REQUESTED":
            raise ValueError("projection_status d'absence invalide")


@dataclass(frozen=True, slots=True)
class ProjectionProfileView:
    """Paramètres publics du profil de projection."""

    projection_profile_id: str
    chunking_profile: str
    embedding_model: str
    sparse_profile: str
    index_schema: str

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            _ensure_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class ProjectionFreshnessView:
    """Fraîcheur interprétée exclusivement depuis l'état de l'agrégat KA."""

    status: str
    observed_at: str

    def __post_init__(self) -> None:
        if self.status not in _FRESHNESS_STATUSES:
            raise ValueError("fraîcheur de projection inconnue")
        object.__setattr__(
            self,
            "observed_at",
            ensure_utc_instant(self.observed_at, "observed_at"),
        )


@dataclass(frozen=True, slots=True)
class SourceLocatorView:
    """Localisateur public conservant la traçabilité canonique du chunk."""

    schema_version: str
    canonical_version_id: str
    document_id: str
    page_pdf: int
    item_id: str
    bbox: tuple[float, float, float, float]
    content_hash: str

    @classmethod
    def from_locator(cls, locator: SourceLocator) -> "SourceLocatorView":
        parsed_locator = _ensure_source_locator(locator)
        return cls(
            schema_version=parsed_locator.schema_version,
            canonical_version_id=parsed_locator.canonical_version_id,
            document_id=parsed_locator.document_id,
            page_pdf=parsed_locator.page_pdf,
            item_id=parsed_locator.item_id,
            bbox=parsed_locator.bbox,
            content_hash=parsed_locator.content_hash,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.schema_version, "schema_version")
        _ensure_domain_id(self.canonical_version_id, "CVER")
        _ensure_document_id(self.document_id)
        if isinstance(self.page_pdf, bool) or not isinstance(self.page_pdf, int) or self.page_pdf < 1:
            raise ValueError("page_pdf invalide")
        _ensure_text(self.item_id, "item_id")
        if not isinstance(self.bbox, tuple) or len(self.bbox) != 4:
            raise ValueError("bbox invalide")
        _ensure_text(self.content_hash, "content_hash")


@dataclass(frozen=True, slots=True)
class ProjectionChunkSampleView:
    """Aperçu de chunk borné, sans identifiant de point technique."""

    chunk_level: str
    text_preview: str
    text_preview_truncated: bool
    content_hash: str
    source_locators: tuple[SourceLocatorView, ...]

    def __post_init__(self) -> None:
        _ensure_text(self.chunk_level, "chunk_level")
        _ensure_text(self.text_preview, "text_preview")
        if not isinstance(self.text_preview_truncated, bool):
            raise ValueError("text_preview_truncated invalide")
        _ensure_text(self.content_hash, "content_hash")
        locators = tuple(self.source_locators)
        if len(locators) == 0:
            raise ValueError("SourceLocator absent de l'échantillon")
        for locator in locators:
            if not isinstance(locator, SourceLocatorView):
                raise ValueError("SourceLocator public invalide")
        object.__setattr__(self, "source_locators", locators)


@dataclass(frozen=True, slots=True)
class KnowledgeProjectionView:
    """Projection KA publique, inspectable et indépendante de Qdrant."""

    document_id: str
    projection_id: str
    canonical_version_id: str
    projection_status: str
    profile: ProjectionProfileView
    freshness: ProjectionFreshnessView
    chunk_count: int
    chunk_samples: tuple[ProjectionChunkSampleView, ...]

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        _ensure_domain_id(self.projection_id, "PROJ")
        _ensure_domain_id(self.canonical_version_id, "CVER")
        ProjectionStatus.from_value(self.projection_status)
        if not isinstance(self.profile, ProjectionProfileView):
            raise ValueError("profil public invalide")
        if not isinstance(self.freshness, ProjectionFreshnessView):
            raise ValueError("fraîcheur publique invalide")
        _ensure_non_negative_integer(self.chunk_count, "chunk_count")
        samples = tuple(self.chunk_samples)
        if len(samples) > self.chunk_count:
            raise ValueError("échantillons publics incohérents avec chunk_count")
        for sample in samples:
            if not isinstance(sample, ProjectionChunkSampleView):
                raise ValueError("échantillon public invalide")
        object.__setattr__(self, "chunk_samples", samples)


ProjectionView = ProjectionNotRequestedView | KnowledgeProjectionView


class ProjectionQueryService:
    """Interprète l'état KA et produit un read-model public strict."""

    def __init__(
        self,
        *,
        projection_read_repository: ProjectionReadRepository,
        chunk_sample_limit: int,
        text_preview_character_limit: int,
        source_locator_limit: int,
    ) -> None:
        if not callable(
            getattr(
                projection_read_repository,
                "current_projection_for_document_id",
                None,
            )
        ):
            raise ValueError("projection_read_repository sans lecture documentaire")
        self._projection_read_repository = projection_read_repository
        self._chunk_sample_limit = _ensure_positive_integer(
            chunk_sample_limit,
            "chunk_sample_limit",
        )
        self._text_preview_character_limit = _ensure_positive_integer(
            text_preview_character_limit,
            "text_preview_character_limit",
        )
        self._source_locator_limit = _ensure_positive_integer(
            source_locator_limit,
            "source_locator_limit",
        )

    def read_projection(self, document_id: str) -> ProjectionView:
        parsed_document_id = _ensure_document_id(document_id)
        record = self._projection_read_repository.current_projection_for_document_id(
            parsed_document_id,
            self._chunk_sample_limit,
        )
        if record is None:
            return ProjectionNotRequestedView(
                document_id=parsed_document_id,
                projection_status="PROJECTION_NOT_REQUESTED",
            )
        parsed_record = _ensure_projection_read_record(record)
        projection = parsed_record.projection
        if projection.document_id != parsed_document_id:
            raise ValueError("projection retournée pour un autre document")
        if len(parsed_record.chunk_samples) > self._chunk_sample_limit:
            raise ValueError("port de lecture retourne des échantillons non bornés")

        profile = projection.projection_profile
        return KnowledgeProjectionView(
            document_id=projection.document_id,
            projection_id=projection.projection_id,
            canonical_version_id=projection.canonical_version_id,
            projection_status=projection.status.value,
            profile=ProjectionProfileView(
                projection_profile_id=profile.projection_profile_id,
                chunking_profile=profile.chunking_profile,
                embedding_model=profile.embedding_model,
                sparse_profile=profile.sparse_profile,
                index_schema=profile.index_schema,
            ),
            freshness=ProjectionFreshnessView(
                status=_FRESHNESS_BY_PROJECTION_STATUS[projection.status],
                observed_at=parsed_record.state_observed_at,
            ),
            chunk_count=parsed_record.chunk_count,
            chunk_samples=tuple(
                self._sample_view(sample)
                for sample in parsed_record.chunk_samples
            ),
        )

    def _sample_view(self, chunk: KnowledgeChunk) -> ProjectionChunkSampleView:
        parsed_chunk = _ensure_chunk(chunk)
        preview = parsed_chunk.text[: self._text_preview_character_limit]
        locators = parsed_chunk.source_locators[: self._source_locator_limit]
        if len(locators) == 0:
            raise ValueError("SourceLocator absent du chunk public")
        return ProjectionChunkSampleView(
            chunk_level=parsed_chunk.chunk_level,
            text_preview=preview,
            text_preview_truncated=len(parsed_chunk.text) > len(preview),
            content_hash=parsed_chunk.content_hash,
            source_locators=tuple(
                SourceLocatorView.from_locator(locator) for locator in locators
            ),
        )


def _ensure_projection_read_record(value: Any) -> ProjectionReadRecord:
    if not isinstance(value, ProjectionReadRecord):
        raise ValueError("enregistrement de lecture projection invalide")
    return value


def _ensure_projection(value: Any) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("KnowledgeProjection invalide")
    return value


def _ensure_chunk_samples(value: Sequence[KnowledgeChunk]) -> tuple[KnowledgeChunk, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("échantillons de chunks invalides")
    samples = tuple(value)
    for sample in samples:
        _ensure_chunk(sample)
    return samples


def _ensure_chunk(value: Any) -> KnowledgeChunk:
    if not isinstance(value, KnowledgeChunk):
        raise ValueError("chunk KA invalide")
    return value


def _ensure_source_locator(value: Any) -> SourceLocator:
    if not isinstance(value, SourceLocator):
        raise ValueError("SourceLocator invalide")
    return value


def _ensure_document_id(value: Any) -> str:
    return _ensure_domain_id(value, "DOC")


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identifiant de domaine invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"identifiant {expected_prefix} invalide: {exc}") from exc


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = [
    "KnowledgeProjectionView",
    "ProjectionChunkSampleView",
    "ProjectionFreshnessView",
    "ProjectionNotRequestedView",
    "ProjectionProfileView",
    "ProjectionQueryService",
    "ProjectionReadRecord",
    "ProjectionReadRepository",
    "ProjectionView",
    "SourceLocatorView",
]
