"""Metadonnees filtrables de projection KA."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import ProjectionStatus


_SUPPORTED_FILTER_FIELDS = frozenset(
    {
        "author",
        "published_on_or_after",
        "published_on_or_before",
        "content_type",
        "canonical_quality",
        "chunk_level",
    }
)
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_CHUNK_LEVELS = frozenset({"PARENT", "CHILD"})
_DIVERSIFICATION_MODES = frozenset({"NONE", "PER_DOCUMENT"})


class ProjectionMetadataError(ValueError):
    """Erreur metier stable des metadonnees KA."""


class SearchFilterNotSupportedError(ProjectionMetadataError):
    """Erreur produite quand une dimension de filtre n'est pas supportee."""

    def __init__(self, dimension: str) -> None:
        self.dimension = _ensure_text(dimension, "dimension filtre invalide")
        super().__init__(f"FILTER_NOT_SUPPORTED: {self.dimension}")


class ProjectionStaleError(ProjectionMetadataError):
    """Erreur produite quand une projection STALE serait utilisee silencieusement."""

    def __init__(self, reason: str) -> None:
        self.reason = _ensure_text(reason, "projection_stale_reason")
        super().__init__(f"PROJECTION_STALE: {self.reason}")


@dataclass(frozen=True)
class ProjectionMetadata:
    """Metadonnees strictes associees a un chunk projetable."""

    projection_id: str
    chunk_id: str
    canonical_version_id: str
    document_id: str
    author: str
    published_on: date | str
    content_type: str
    canonical_quality: str
    chunk_level: str
    content_hash: str

    @classmethod
    def from_chunk(
        cls,
        *,
        projection_id: str,
        chunk: KnowledgeChunk,
        author: str,
        published_on: date | str,
        content_type: str,
        canonical_quality: str,
    ) -> "ProjectionMetadata":
        parsed_chunk = _ensure_chunk(chunk)
        return cls(
            projection_id=projection_id,
            chunk_id=parsed_chunk.chunk_id,
            canonical_version_id=parsed_chunk.canonical_version_id,
            document_id=parsed_chunk.document_id,
            author=author,
            published_on=published_on,
            content_type=content_type,
            canonical_quality=canonical_quality,
            chunk_level=parsed_chunk.chunk_level,
            content_hash=parsed_chunk.content_hash,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_domain_id(self.projection_id, "PROJ"))
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_id(self.canonical_version_id, "CVER"),
        )
        object.__setattr__(self, "document_id", _ensure_domain_id(self.document_id, "DOC"))
        object.__setattr__(self, "author", _ensure_text(self.author, "author"))
        object.__setattr__(self, "published_on", _ensure_date(self.published_on, "published_on"))
        object.__setattr__(
            self,
            "content_type",
            _ensure_text(self.content_type, "content_type"),
        )
        object.__setattr__(
            self,
            "canonical_quality",
            _ensure_text(self.canonical_quality, "canonical_quality"),
        )
        chunk_level = _ensure_text(self.chunk_level, "chunk_level")
        if chunk_level not in _CHUNK_LEVELS:
            raise ValueError("chunk_level inconnu")
        object.__setattr__(self, "chunk_level", chunk_level)
        object.__setattr__(self, "content_hash", _ensure_sha256(self.content_hash, "content_hash"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "chunk_id": self.chunk_id,
            "canonical_version_id": self.canonical_version_id,
            "document_id": self.document_id,
            "author": self.author,
            "published_on": self.published_on.isoformat(),
            "content_type": self.content_type,
            "canonical_quality": self.canonical_quality,
            "chunk_level": self.chunk_level,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class AppliedFilterTrace:
    """Trace l'application observable d'une dimension de filtre."""

    dimension: str
    operator: str
    requested_value: Any
    eligible_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", _ensure_text(self.dimension, "dimension"))
        object.__setattr__(self, "operator", _ensure_text(self.operator, "operator"))
        object.__setattr__(
            self,
            "eligible_count",
            _ensure_non_negative_integer(self.eligible_count, "eligible_count invalide"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "operator": self.operator,
            "requested_value": self.requested_value,
            "eligible_count": self.eligible_count,
        }


@dataclass(frozen=True)
class ProjectionFreshnessDecision:
    """Decision de fraicheur explicite pour une recherche KA."""

    status: ProjectionStatus
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ProjectionStatus.from_value(self.status))
        object.__setattr__(self, "warnings", _ensure_warning_tuple(self.warnings))

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ProjectionFreshnessPolicy:
    """Refuse l'usage silencieux d'une projection obsolete."""

    require_current: bool

    def __post_init__(self) -> None:
        if not isinstance(self.require_current, bool):
            raise ValueError("require_current non booleen")

    def evaluate(
        self,
        projection_status: ProjectionStatus | str,
        *,
        contractual_warning: str | None = None,
    ) -> ProjectionFreshnessDecision:
        status = ProjectionStatus.from_value(projection_status)
        if status == ProjectionStatus.STALE:
            if self.require_current:
                raise ProjectionStaleError("projection courante requise")
            warning = _ensure_optional_text(contractual_warning, "contractual_warning")
            if warning is None:
                raise ProjectionStaleError("avertissement contractuel absent")
            return ProjectionFreshnessDecision(status=status, warnings=(warning,))
        if status != ProjectionStatus.SEARCHABLE:
            raise ValueError(f"projection_status non searchable: {status.value}")
        if contractual_warning is not None:
            warning = _ensure_text(contractual_warning, "contractual_warning")
            return ProjectionFreshnessDecision(status=status, warnings=(warning,))
        return ProjectionFreshnessDecision(status=status, warnings=())


@dataclass(frozen=True)
class SearchFilter:
    """Filtre de recherche KA compose uniquement de dimensions supportees."""

    author: tuple[str, ...] | None
    published_on_or_after: date | None
    published_on_or_before: date | None
    content_type: tuple[str, ...] | None
    canonical_quality: tuple[str, ...] | None
    chunk_level: tuple[str, ...] | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SearchFilter":
        parsed_payload = _ensure_mapping(payload, "search_filter non objet")
        actual_fields = frozenset(parsed_payload.keys())
        unexpected_fields = actual_fields - _SUPPORTED_FILTER_FIELDS
        if len(unexpected_fields) > 0:
            raise SearchFilterNotSupportedError(sorted(unexpected_fields)[0])
        published_on_or_after = _optional_date(
            parsed_payload.get("published_on_or_after"),
            "published_on_or_after",
        )
        published_on_or_before = _optional_date(
            parsed_payload.get("published_on_or_before"),
            "published_on_or_before",
        )
        if (
            published_on_or_after is not None
            and published_on_or_before is not None
            and published_on_or_after > published_on_or_before
        ):
            raise ValueError("periode incoherente")
        return cls(
            author=_optional_text_tuple(parsed_payload.get("author"), "author"),
            published_on_or_after=published_on_or_after,
            published_on_or_before=published_on_or_before,
            content_type=_optional_text_tuple(parsed_payload.get("content_type"), "content_type"),
            canonical_quality=_optional_text_tuple(
                parsed_payload.get("canonical_quality"),
                "canonical_quality",
            ),
            chunk_level=_optional_text_tuple(parsed_payload.get("chunk_level"), "chunk_level"),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "author", _optional_text_tuple(self.author, "author"))
        object.__setattr__(
            self,
            "published_on_or_after",
            _optional_date(self.published_on_or_after, "published_on_or_after"),
        )
        object.__setattr__(
            self,
            "published_on_or_before",
            _optional_date(self.published_on_or_before, "published_on_or_before"),
        )
        if (
            self.published_on_or_after is not None
            and self.published_on_or_before is not None
            and self.published_on_or_after > self.published_on_or_before
        ):
            raise ValueError("periode incoherente")
        object.__setattr__(
            self,
            "content_type",
            _optional_text_tuple(self.content_type, "content_type"),
        )
        object.__setattr__(
            self,
            "canonical_quality",
            _optional_text_tuple(self.canonical_quality, "canonical_quality"),
        )
        chunk_level = _optional_text_tuple(self.chunk_level, "chunk_level")
        if chunk_level is not None:
            for level in chunk_level:
                if level not in _CHUNK_LEVELS:
                    raise ValueError("chunk_level inconnu")
        object.__setattr__(self, "chunk_level", chunk_level)

    def matches(self, metadata: ProjectionMetadata) -> bool:
        parsed_metadata = _ensure_metadata(metadata)
        if self.author is not None and parsed_metadata.author not in self.author:
            return False
        if (
            self.published_on_or_after is not None
            and parsed_metadata.published_on < self.published_on_or_after
        ):
            return False
        if (
            self.published_on_or_before is not None
            and parsed_metadata.published_on > self.published_on_or_before
        ):
            return False
        if self.content_type is not None and parsed_metadata.content_type not in self.content_type:
            return False
        if (
            self.canonical_quality is not None
            and parsed_metadata.canonical_quality not in self.canonical_quality
        ):
            return False
        if self.chunk_level is not None and parsed_metadata.chunk_level not in self.chunk_level:
            return False
        return True

    def apply(
        self,
        metadata: Sequence[ProjectionMetadata],
    ) -> tuple[tuple[ProjectionMetadata, ...], tuple[AppliedFilterTrace, ...]]:
        candidates = _ensure_metadata_tuple(metadata)
        filtered = candidates
        traces: list[AppliedFilterTrace] = []
        if self.author is not None:
            filtered = tuple(item for item in filtered if item.author in self.author)
            traces.append(
                AppliedFilterTrace(
                    dimension="author",
                    operator="IN",
                    requested_value=self.author,
                    eligible_count=len(filtered),
                )
            )
        if self.published_on_or_after is not None or self.published_on_or_before is not None:
            filtered = tuple(item for item in filtered if self._date_matches(item))
            traces.append(
                AppliedFilterTrace(
                    dimension="published_on",
                    operator=_period_operator(self),
                    requested_value=_period_payload(self),
                    eligible_count=len(filtered),
                )
            )
        if self.content_type is not None:
            filtered = tuple(item for item in filtered if item.content_type in self.content_type)
            traces.append(
                AppliedFilterTrace(
                    dimension="content_type",
                    operator="IN",
                    requested_value=self.content_type,
                    eligible_count=len(filtered),
                )
            )
        if self.canonical_quality is not None:
            filtered = tuple(
                item for item in filtered if item.canonical_quality in self.canonical_quality
            )
            traces.append(
                AppliedFilterTrace(
                    dimension="canonical_quality",
                    operator="IN",
                    requested_value=self.canonical_quality,
                    eligible_count=len(filtered),
                )
            )
        if self.chunk_level is not None:
            filtered = tuple(item for item in filtered if item.chunk_level in self.chunk_level)
            traces.append(
                AppliedFilterTrace(
                    dimension="chunk_level",
                    operator="IN",
                    requested_value=self.chunk_level,
                    eligible_count=len(filtered),
                )
            )
        return filtered, tuple(traces)

    def _date_matches(self, metadata: ProjectionMetadata) -> bool:
        parsed_metadata = _ensure_metadata(metadata)
        if (
            self.published_on_or_after is not None
            and parsed_metadata.published_on < self.published_on_or_after
        ):
            return False
        if (
            self.published_on_or_before is not None
            and parsed_metadata.published_on > self.published_on_or_before
        ):
            return False
        return True


@dataclass(frozen=True)
class DiversificationTrace:
    """Trace l'effet de la diversification des preuves candidates."""

    mode: str
    max_per_document: int | None
    input_count: int
    output_count: int

    def __post_init__(self) -> None:
        mode = _ensure_text(self.mode, "diversification_mode")
        if mode not in _DIVERSIFICATION_MODES:
            raise ValueError("diversification_mode inconnu")
        object.__setattr__(self, "mode", mode)
        if mode == "PER_DOCUMENT":
            object.__setattr__(
                self,
                "max_per_document",
                _ensure_positive_integer(self.max_per_document, "max_per_document invalide"),
            )
        elif self.max_per_document is not None:
            raise ValueError("max_per_document interdit sans diversification")
        object.__setattr__(
            self,
            "input_count",
            _ensure_non_negative_integer(self.input_count, "input_count invalide"),
        )
        object.__setattr__(
            self,
            "output_count",
            _ensure_non_negative_integer(self.output_count, "output_count invalide"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "max_per_document": self.max_per_document,
            "input_count": self.input_count,
            "output_count": self.output_count,
        }


@dataclass(frozen=True)
class EvidenceDiversificationPolicy:
    """Politique explicite de diversification des preuves candidates."""

    mode: str
    max_per_document: int | None

    @classmethod
    def none(cls) -> "EvidenceDiversificationPolicy":
        return cls(mode="NONE", max_per_document=None)

    @classmethod
    def per_document(cls, *, max_per_document: int) -> "EvidenceDiversificationPolicy":
        return cls(mode="PER_DOCUMENT", max_per_document=max_per_document)

    def __post_init__(self) -> None:
        mode = _ensure_text(self.mode, "diversification_mode")
        if mode not in _DIVERSIFICATION_MODES:
            raise ValueError("diversification_mode inconnu")
        object.__setattr__(self, "mode", mode)
        if mode == "PER_DOCUMENT":
            object.__setattr__(
                self,
                "max_per_document",
                _ensure_positive_integer(self.max_per_document, "max_per_document invalide"),
            )
        elif self.max_per_document is not None:
            raise ValueError("max_per_document interdit sans diversification")

    def apply(
        self,
        metadata: Sequence[ProjectionMetadata],
    ) -> tuple[tuple[ProjectionMetadata, ...], DiversificationTrace]:
        candidates = _ensure_metadata_tuple(metadata)
        if self.mode == "NONE":
            return candidates, DiversificationTrace(
                mode="NONE",
                max_per_document=None,
                input_count=len(candidates),
                output_count=len(candidates),
            )

        selected: list[ProjectionMetadata] = []
        counts_by_document: dict[str, int] = {}
        assert self.max_per_document is not None
        for item in candidates:
            current_count = counts_by_document.get(item.document_id, 0)
            if current_count >= self.max_per_document:
                continue
            selected.append(item)
            counts_by_document[item.document_id] = current_count + 1
        diversified = tuple(selected)
        return diversified, DiversificationTrace(
            mode="PER_DOCUMENT",
            max_per_document=self.max_per_document,
            input_count=len(candidates),
            output_count=len(diversified),
        )


@dataclass(frozen=True)
class ProjectionFilterTrace:
    """Trace complete de filtrage, fraicheur et diversification."""

    candidate_count: int
    eligible_count: int
    applied_filters: tuple[AppliedFilterTrace, ...]
    freshness: ProjectionFreshnessDecision
    diversification: DiversificationTrace

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_count",
            _ensure_non_negative_integer(self.candidate_count, "candidate_count invalide"),
        )
        object.__setattr__(
            self,
            "eligible_count",
            _ensure_non_negative_integer(self.eligible_count, "eligible_count invalide"),
        )
        object.__setattr__(
            self,
            "applied_filters",
            _ensure_applied_filter_traces(self.applied_filters),
        )
        if not isinstance(self.freshness, ProjectionFreshnessDecision):
            raise ValueError("freshness invalide")
        if not isinstance(self.diversification, DiversificationTrace):
            raise ValueError("diversification invalide")

    def to_payload(self) -> dict[str, Any]:
        return {
            "candidate_count": self.candidate_count,
            "eligible_count": self.eligible_count,
            "applied_filters": tuple(trace.to_payload() for trace in self.applied_filters),
            "freshness": self.freshness.to_payload(),
            "diversification": self.diversification.to_payload(),
            "warnings": self.freshness.warnings,
        }


@dataclass(frozen=True)
class ProjectionMetadataSelection:
    """Resultat de selection de metadonnees filtrables."""

    metadata: tuple[ProjectionMetadata, ...]
    trace: ProjectionFilterTrace

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _ensure_metadata_tuple(self.metadata))
        if not isinstance(self.trace, ProjectionFilterTrace):
            raise ValueError("trace invalide")


class ProjectionMetadataSelector:
    """Selectionne les chunks eligibles selon filtre, fraicheur et diversification."""

    def select(
        self,
        *,
        projection_status: ProjectionStatus | str,
        metadata: Sequence[ProjectionMetadata],
        search_filter: SearchFilter,
        freshness_policy: ProjectionFreshnessPolicy,
        diversification_policy: EvidenceDiversificationPolicy,
        contractual_stale_warning: str | None = None,
    ) -> ProjectionMetadataSelection:
        candidates = _ensure_metadata_tuple(metadata)
        parsed_filter = _ensure_search_filter(search_filter)
        parsed_freshness_policy = _ensure_freshness_policy(freshness_policy)
        parsed_diversification_policy = _ensure_diversification_policy(diversification_policy)
        freshness_decision = parsed_freshness_policy.evaluate(
            projection_status,
            contractual_warning=contractual_stale_warning,
        )
        filtered, filter_traces = parsed_filter.apply(candidates)
        diversified, diversification_trace = parsed_diversification_policy.apply(filtered)
        return ProjectionMetadataSelection(
            metadata=diversified,
            trace=ProjectionFilterTrace(
                candidate_count=len(candidates),
                eligible_count=len(diversified),
                applied_filters=filter_traces,
                freshness=freshness_decision,
                diversification=diversification_trace,
            ),
        )


def _ensure_chunk(value: KnowledgeChunk) -> KnowledgeChunk:
    if not isinstance(value, KnowledgeChunk):
        raise ValueError("chunk invalide")
    return value


def _ensure_metadata(value: ProjectionMetadata) -> ProjectionMetadata:
    if not isinstance(value, ProjectionMetadata):
        raise ValueError("metadata invalide")
    return value


def _ensure_search_filter(value: SearchFilter) -> SearchFilter:
    if not isinstance(value, SearchFilter):
        raise ValueError("search_filter invalide")
    return value


def _ensure_freshness_policy(value: ProjectionFreshnessPolicy) -> ProjectionFreshnessPolicy:
    if not isinstance(value, ProjectionFreshnessPolicy):
        raise ValueError("freshness_policy invalide")
    return value


def _ensure_diversification_policy(
    value: EvidenceDiversificationPolicy,
) -> EvidenceDiversificationPolicy:
    if not isinstance(value, EvidenceDiversificationPolicy):
        raise ValueError("diversification_policy invalide")
    return value


def _ensure_metadata_tuple(value: Sequence[ProjectionMetadata]) -> tuple[ProjectionMetadata, ...]:
    if value is None:
        raise ValueError("metadata absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("metadata invalides")
    metadata = tuple(value)
    if len(metadata) == 0:
        raise ValueError("metadata absentes")
    for item in metadata:
        _ensure_metadata(item)
    chunk_ids = tuple(item.chunk_id for item in metadata)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("chunk_id metadata duplique")
    return metadata


def _ensure_applied_filter_traces(
    value: Sequence[AppliedFilterTrace],
) -> tuple[AppliedFilterTrace, ...]:
    if value is None:
        raise ValueError("applied_filters absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("applied_filters invalides")
    traces = tuple(value)
    for trace in traces:
        if not isinstance(trace, AppliedFilterTrace):
            raise ValueError("applied_filter invalide")
    return traces


def _ensure_mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(message)
    return dict(value)


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identifiant de domaine invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"identifiant {expected_prefix} invalide: {exc}") from exc


def _ensure_chunk_id(value: Any) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
    return text


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _ensure_text(value, field_name)


def _ensure_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} invalide")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc


def _optional_date(value: Any, field_name: str) -> date | None:
    if value is None:
        return None
    return _ensure_date(value, field_name)


def _optional_text_tuple(value: Any, field_name: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return (_ensure_text(value, field_name),)
    if not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    items = tuple(value)
    if len(items) == 0:
        raise ValueError(f"{field_name} vide")
    parsed_items = tuple(_ensure_text(item, field_name) for item in items)
    if len(parsed_items) != len(set(parsed_items)):
        raise ValueError(f"{field_name} duplique")
    return parsed_items


def _ensure_warning_tuple(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("warnings absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("warnings invalides")
    warnings = tuple(_ensure_text(warning, "warning") for warning in value)
    if len(warnings) != len(set(warnings)):
        raise ValueError("warning duplique")
    return warnings


def _ensure_positive_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _ensure_non_negative_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(message)
    return value


def _ensure_sha256(value: Any, field_name: str) -> str:
    text_value = _ensure_text(value, field_name)
    if len(text_value) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text_value:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text_value


def _period_operator(search_filter: SearchFilter) -> str:
    if (
        search_filter.published_on_or_after is not None
        and search_filter.published_on_or_before is not None
    ):
        return "BETWEEN"
    if search_filter.published_on_or_after is not None:
        return "ON_OR_AFTER"
    return "ON_OR_BEFORE"


def _period_payload(search_filter: SearchFilter) -> dict[str, str | None]:
    return {
        "published_on_or_after": (
            search_filter.published_on_or_after.isoformat()
            if search_filter.published_on_or_after is not None
            else None
        ),
        "published_on_or_before": (
            search_filter.published_on_or_before.isoformat()
            if search_filter.published_on_or_before is not None
            else None
        ),
    }


__all__ = [
    "AppliedFilterTrace",
    "DiversificationTrace",
    "EvidenceDiversificationPolicy",
    "ProjectionFilterTrace",
    "ProjectionFreshnessDecision",
    "ProjectionFreshnessPolicy",
    "ProjectionMetadata",
    "ProjectionMetadataError",
    "ProjectionMetadataSelection",
    "ProjectionMetadataSelector",
    "ProjectionStaleError",
    "SearchFilter",
    "SearchFilterNotSupportedError",
]
