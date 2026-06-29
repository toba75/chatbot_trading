"""Cas d'usage KA de chunking depuis une version canonique publiée."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.application.request_projection import CanonicalSourceReader
from app.knowledge_access.domain.chunking import (
    ChunkingProfile,
    HierarchicalChunkProjection,
    HierarchicalChunkProjector,
)


class ChunkingSourceNotFoundError(ValueError):
    """Erreur métier stable quand la version canonique n'est pas lisible par KA."""

    def __init__(self, canonical_version_id: str) -> None:
        self.canonical_version_id = _ensure_canonical_version_id(canonical_version_id)
        super().__init__(f"source canonique introuvable: {self.canonical_version_id}")


@dataclass(frozen=True)
class ProjectCanonicalChunksCommand:
    """Commande KA de projection des chunks d'une version canonique."""

    canonical_version_id: str
    chunking_profile: ChunkingProfile

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_id(self.canonical_version_id),
        )
        if not isinstance(self.chunking_profile, ChunkingProfile):
            raise ValueError("chunking_profile invalide")


class ProjectCanonicalChunksHandler:
    """Construit la projection de chunks via le port canonique publié."""

    def __init__(self, *, canonical_source_reader: CanonicalSourceReader) -> None:
        if not callable(getattr(canonical_source_reader, "find_chunking_source_by_version_id", None)):
            raise ValueError("canonical_source_reader sans lecture de chunking")
        self._canonical_source_reader = canonical_source_reader
        self._projector = HierarchicalChunkProjector()

    def project_from_canonical_version(
        self,
        command: ProjectCanonicalChunksCommand,
    ) -> HierarchicalChunkProjection:
        parsed_command = _ensure_command(command)
        canonical_document = self._canonical_source_reader.find_chunking_source_by_version_id(
            parsed_command.canonical_version_id
        )
        if canonical_document is None:
            raise ChunkingSourceNotFoundError(parsed_command.canonical_version_id)
        return self._projector.project(
            canonical_document=canonical_document,
            chunking_profile=parsed_command.chunking_profile,
        )


def _ensure_command(value: ProjectCanonicalChunksCommand) -> ProjectCanonicalChunksCommand:
    if not isinstance(value, ProjectCanonicalChunksCommand):
        raise ValueError("commande ProjectCanonicalChunks invalide")
    return value


def _ensure_canonical_version_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical_version_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "CVER"))
    except ValueError as exc:
        raise ValueError(f"canonical_version_id invalide: {exc}") from exc


__all__ = [
    "ChunkingSourceNotFoundError",
    "ProjectCanonicalChunksCommand",
    "ProjectCanonicalChunksHandler",
]
