"""Cas d'usage M-004 de publication d'une version canonique immuable."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from app.contracts.source_references import CanonicalSourceRef
from app.source_processing.domain.canonical_source import (
    CanonicalArtifact,
    CanonicalArtifactKind,
    CanonicalSource,
    CanonicalSourceVersion,
    canonical_artifact_ref_for,
    canonical_source_id_for,
)
from app.source_processing.domain.page_conversion import (
    CanonicalQualityDecision,
    PagewiseDoclingDocument,
)
from app.source_processing.domain.source_document import SourceDocument


class CanonicalArtifactStore(Protocol):
    """Port de stockage du Docling JSON canonique."""

    def store_docling_json(self, request: "StoreCanonicalArtifactRequest") -> "StoredCanonicalArtifact":
        """Stocke l'artefact canonique exact et retourne sa référence persistée."""


@dataclass(frozen=True)
class StoreCanonicalArtifactRequest:
    """Requête stricte de stockage du Docling JSON canonique."""

    canonical_source_id: str
    canonical_version_id: str
    artifact_kind: CanonicalArtifactKind
    expected_artifact_ref: str
    artifact_sha256: str
    content_bytes: bytes

    def __post_init__(self) -> None:
        if self.artifact_kind is not CanonicalArtifactKind.DOCLING_JSON:
            raise ValueError("artefact dérivé non canonique")
        if not isinstance(self.content_bytes, bytes) or len(self.content_bytes) == 0:
            raise ValueError("contenu Docling JSON canonique invalide")
        CanonicalArtifact(
            artifact_ref=self.expected_artifact_ref,
            artifact_sha256=self.artifact_sha256,
            artifact_kind=self.artifact_kind,
        )
        if hashlib.sha256(self.content_bytes).hexdigest() != self.artifact_sha256:
            raise ValueError("hash d'artefact canonique incohérent")


@dataclass(frozen=True)
class StoredCanonicalArtifact:
    """Référence stockée du Docling JSON canonique."""

    artifact_ref: str
    artifact_sha256: str

    def to_canonical_artifact(self) -> CanonicalArtifact:
        return CanonicalArtifact(
            artifact_ref=self.artifact_ref,
            artifact_sha256=self.artifact_sha256,
            artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
        )


@dataclass(frozen=True)
class PublishCanonicalSourceCommand:
    """Commande applicative de publication canonique M-004."""

    source_document: SourceDocument
    docling_document: PagewiseDoclingDocument
    quality_decision: CanonicalQualityDecision
    accepted_at: str
    existing_canonical_source: CanonicalSource | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_document, SourceDocument):
            raise ValueError("source_document invalide")
        if not isinstance(self.docling_document, PagewiseDoclingDocument):
            raise ValueError("DoclingDocument canonique invalide")
        if not isinstance(self.quality_decision, CanonicalQualityDecision):
            raise ValueError("décision QA canonique invalide")
        if not isinstance(self.accepted_at, str):
            raise ValueError("accepted_at invalide")
        if self.existing_canonical_source is not None and not isinstance(
            self.existing_canonical_source,
            CanonicalSource,
        ):
            raise ValueError("CanonicalSource existante invalide")


@dataclass(frozen=True)
class PublishCanonicalSourceResult:
    """Résultat applicatif d'une publication canonique."""

    canonical_source: CanonicalSource
    published_version: CanonicalSourceVersion
    canonical_ref: CanonicalSourceRef
    stored_artifact_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_source, CanonicalSource):
            raise ValueError("CanonicalSource publiée invalide")
        if not isinstance(self.published_version, CanonicalSourceVersion):
            raise ValueError("version canonique publiée invalide")
        if not isinstance(self.canonical_ref, CanonicalSourceRef):
            raise ValueError("CanonicalSourceRef publiée invalide")
        if self.published_version.canonical_ref != self.canonical_ref:
            raise ValueError("CanonicalSourceRef incohérente")
        if self.published_version.canonical_artifact.artifact_ref != self.stored_artifact_ref:
            raise ValueError("référence d'artefact stocké incohérente")


class PublishCanonicalSourceHandler:
    """Publie une version canonique après QA GREEN."""

    def __init__(self, *, artifact_store: CanonicalArtifactStore) -> None:
        if not callable(getattr(artifact_store, "store_docling_json", None)):
            raise ValueError("artifact_store invalide")
        self._artifact_store = artifact_store

    def handle(self, command: PublishCanonicalSourceCommand) -> PublishCanonicalSourceResult:
        if not isinstance(command, PublishCanonicalSourceCommand):
            raise ValueError("commande PublishCanonicalSource invalide")

        command.source_document.ensure_documentary_publication_allowed()
        canonical_source_id = _canonical_source_id_for_command(command)
        canonical_version_id = command.docling_document.canonical_version_id
        serialized_docling_json = _serialize_docling_document(command.docling_document)
        artifact_sha256 = hashlib.sha256(serialized_docling_json).hexdigest()
        expected_artifact_ref = canonical_artifact_ref_for(
            canonical_source_id=canonical_source_id,
            canonical_version_id=canonical_version_id,
        )
        stored_artifact = self._artifact_store.store_docling_json(
            StoreCanonicalArtifactRequest(
                canonical_source_id=canonical_source_id,
                canonical_version_id=canonical_version_id,
                artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
                expected_artifact_ref=expected_artifact_ref,
                artifact_sha256=artifact_sha256,
                content_bytes=serialized_docling_json,
            )
        )
        if not isinstance(stored_artifact, StoredCanonicalArtifact):
            raise ValueError("artefact canonique stocké invalide")
        canonical_artifact = stored_artifact.to_canonical_artifact()

        if command.existing_canonical_source is None:
            canonical_source = CanonicalSource.publish_initial(
                source_document=command.source_document,
                docling_document=command.docling_document,
                quality_decision=command.quality_decision,
                canonical_artifact=canonical_artifact,
                accepted_at=command.accepted_at,
            )
        else:
            canonical_source = command.existing_canonical_source.publish_correction(
                docling_document=command.docling_document,
                quality_decision=command.quality_decision,
                canonical_artifact=canonical_artifact,
                accepted_at=command.accepted_at,
            )

        published_version = canonical_source.version_for(canonical_version_id)
        return PublishCanonicalSourceResult(
            canonical_source=canonical_source,
            published_version=published_version,
            canonical_ref=published_version.canonical_ref,
            stored_artifact_ref=canonical_artifact.artifact_ref,
        )


def _canonical_source_id_for_command(command: PublishCanonicalSourceCommand) -> str:
    candidate_source_id = canonical_source_id_for(command.source_document.document_id)
    if command.existing_canonical_source is None:
        return candidate_source_id
    if command.existing_canonical_source.canonical_source_id != candidate_source_id:
        raise ValueError("canonical_source_id incohérent")
    if command.existing_canonical_source.document_id != command.source_document.document_id:
        raise ValueError("document_id canonique incohérent")
    if command.existing_canonical_source.source_sha256 != command.source_document.fingerprint:
        raise ValueError("source_sha256 canonique incohérent")
    return command.existing_canonical_source.canonical_source_id


def _serialize_docling_document(docling_document: PagewiseDoclingDocument) -> bytes:
    payload = docling_document.to_payload()
    serialized = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return serialized.encode("utf-8")


__all__ = [
    "CanonicalArtifactStore",
    "PublishCanonicalSourceCommand",
    "PublishCanonicalSourceHandler",
    "PublishCanonicalSourceResult",
    "StoreCanonicalArtifactRequest",
    "StoredCanonicalArtifact",
]
