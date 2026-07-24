"""Stockage local SP des artefacts de page, borné par environnement."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
        self._verified_sources: set[tuple[str, str, int]] = set()

    def materialize_verified_source(
        self,
        *,
        source_path: Path,
        identity: LocalArtifactIdentity,
        sha256: str,
    ) -> LocalArtifactDescriptor:
        if not isinstance(source_path, Path) or not source_path.is_file():
            raise ArtifactContractError("ARTIFACT_NOT_FOUND")
        if not isinstance(identity, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        digest, size = _hash_file(source_path)
        if digest != sha256:
            raise ArtifactContractError("ARTIFACT_HASH_MISMATCH")
        target = identity.resolve_under(self._profile_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing_hash, existing_size = _hash_file(target)
            if (existing_hash, existing_size) != (digest, size):
                raise ArtifactContractError("PAGE_SOURCE_ARTIFACT_DIVERGENT")
        else:
            temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
            try:
                with source_path.open("rb") as source, temporary.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    pass
            finally:
                temporary.unlink(missing_ok=True)
            existing_hash, existing_size = _hash_file(target)
            if (existing_hash, existing_size) != (digest, size):
                raise ArtifactContractError("PAGE_SOURCE_ARTIFACT_DIVERGENT")
        descriptor = LocalArtifactDescriptor(
            identity=identity,
            sha256=digest,
            size_bytes=size,
        )
        self._verified_sources.add((identity.artifact_ref, digest, size))
        return descriptor

    def resolve_verified_path(self, descriptor: LocalArtifactDescriptor) -> Path:
        if not isinstance(descriptor, LocalArtifactDescriptor):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        path = descriptor.identity.resolve_under(self._profile_root)
        if not path.is_file():
            raise ArtifactContractError("ARTIFACT_NOT_FOUND")
        identity = (
            descriptor.identity.artifact_ref,
            descriptor.sha256,
            descriptor.size_bytes,
        )
        if identity not in self._verified_sources:
            digest, size = _hash_file(path)
            if (digest, size) != (descriptor.sha256, descriptor.size_bytes):
                raise ArtifactContractError("ARTIFACT_HASH_MISMATCH")
            self._verified_sources.add(identity)
        return path

    def read(self, descriptor: LocalArtifactDescriptor) -> bytes:
        if not isinstance(descriptor, LocalArtifactDescriptor):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        path = self.resolve_verified_path(descriptor)
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
        lease_expires_at: datetime,
    ) -> LocalArtifactDescriptor:
        if not isinstance(identity, LocalArtifactIdentity):
            raise ArtifactContractError("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(content, bytes) or len(content) == 0:
            raise ArtifactContractError("ARTIFACT_CONTENT_INVALID")
        if not isinstance(lease_expires_at, datetime) or lease_expires_at.tzinfo is None:
            raise ArtifactContractError("JOB_LEASE_DEADLINE_INVALID")
        path = identity.resolve_under(self._profile_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if datetime.now(UTC) >= lease_expires_at.astimezone(UTC):
                raise ArtifactContractError("JOB_LEASE_LOST")
            try:
                os.link(temporary, path)
            except FileExistsError:
                existing = path.read_bytes()
                if existing != content:
                    raise ArtifactContractError("PAGE_RESULT_ARTIFACT_DIVERGENT") from None
        finally:
            temporary.unlink(missing_ok=True)
        return LocalArtifactDescriptor(
            identity=identity,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    if size < 1:
        raise ArtifactContractError("ARTIFACT_HASH_MISMATCH")
    return digest.hexdigest(), size


__all__ = ["LocalPageArtifactStore"]
