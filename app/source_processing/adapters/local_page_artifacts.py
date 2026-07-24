"""Stockage local SP des artefacts de page, borné par environnement."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.source_processing.domain.distribution_contracts import (
    ArtifactContractError,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
)


class LocalPageArtifactStore:
    """Lit après vérification et écrit sans jamais remplacer un artefact."""

    def __init__(self, *, profile_root: Path) -> None:
        if not isinstance(profile_root, Path) or not profile_root.is_absolute():
            raise ValueError("ARTIFACT_ROOT_INVALID")
        self._profile_root = profile_root.resolve()

    def read(self, descriptor: LocalArtifactDescriptor) -> bytes:
        if not isinstance(descriptor, LocalArtifactDescriptor):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        path = descriptor.identity.resolve_under(self._profile_root)
        if not path.is_file():
            raise ArtifactContractError("ARTIFACT_NOT_FOUND")
        content = path.read_bytes()
        if len(content) != descriptor.size_bytes:
            raise ArtifactContractError("ARTIFACT_HASH_MISMATCH")
        descriptor.verify_content(content)
        return content

    def write_immutable(
        self,
        *,
        identity: LocalArtifactIdentity,
        content: bytes,
    ) -> LocalArtifactDescriptor:
        if not isinstance(identity, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(content, bytes) or len(content) == 0:
            raise ArtifactContractError("ARTIFACT_CONTENT_INVALID")
        path = identity.resolve_under(self._profile_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            existing = path.read_bytes()
            if existing != content:
                raise ArtifactContractError("PAGE_RESULT_ARTIFACT_DIVERGENT") from None
        return LocalArtifactDescriptor(
            identity=identity,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )


__all__ = ["LocalPageArtifactStore"]
