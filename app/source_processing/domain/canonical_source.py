"""Agrégat de publication canonique immuable M-004."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import CanonicalSourceRef
from app.source_processing.domain.page_conversion import (
    CanonicalQualityDecision,
    PagewiseDoclingFusionService,
    PagewiseDoclingDocument,
    QualityDecisionStatus,
    TextAuthorityManifest,
)
from app.source_processing.domain.source_document import (
    DocumentId,
    SourceDocument,
    SourceFingerprint,
)


_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_CANONICAL_ARTIFACT_PREFIX = "artifact:source_processing.canonical_sources/"
_REGENERABLE_EXPORT_PREFIX = "artifact:source_processing.canonical_exports/"
_CANONICAL_SCHEMA_VERSION = "1.0"


class CanonicalArtifactKind(str, Enum):
    """Nature explicite d'un artefact documentaire M-004."""

    DOCLING_JSON = "DOCLING_JSON"
    MARKDOWN = "MARKDOWN"
    HTML = "HTML"

    @classmethod
    def from_value(cls, value: "CanonicalArtifactKind | str") -> "CanonicalArtifactKind":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("type d'artefact canonique inconnu")
        for artifact_kind in cls:
            if artifact_kind.value == value:
                return artifact_kind
        raise ValueError("type d'artefact canonique inconnu")


class CanonicalSourceStatus(str, Enum):
    """État métier de l'agrégat CanonicalSource."""

    PUBLISHED = "PUBLISHED"


@dataclass(frozen=True)
class CanonicalArtifact:
    """Artefact Docling JSON qui fait autorité pour une version canonique."""

    artifact_ref: str
    artifact_sha256: str
    artifact_kind: CanonicalArtifactKind

    def __post_init__(self) -> None:
        artifact_kind = CanonicalArtifactKind.from_value(self.artifact_kind)
        if artifact_kind is not CanonicalArtifactKind.DOCLING_JSON:
            raise ValueError("artefact dérivé non canonique")
        object.__setattr__(self, "artifact_kind", artifact_kind)
        object.__setattr__(
            self,
            "artifact_ref",
            _ensure_canonical_artifact_ref(self.artifact_ref),
        )
        object.__setattr__(
            self,
            "artifact_sha256",
            _ensure_sha256(self.artifact_sha256, "hash d'artefact canonique invalide"),
        )


@dataclass(frozen=True)
class RegenerableExport:
    """Export dérivé et régénérable, jamais source de vérité canonique."""

    export_ref: str
    export_sha256: str
    export_kind: CanonicalArtifactKind

    def __post_init__(self) -> None:
        export_kind = CanonicalArtifactKind.from_value(self.export_kind)
        if export_kind is CanonicalArtifactKind.DOCLING_JSON:
            raise ValueError("export régénérable invalide")
        object.__setattr__(self, "export_kind", export_kind)
        object.__setattr__(
            self,
            "export_ref",
            _ensure_regenerable_export_ref(self.export_ref, export_kind),
        )
        object.__setattr__(
            self,
            "export_sha256",
            _ensure_sha256(self.export_sha256, "hash d'export régénérable invalide"),
        )

    @property
    def is_canonical(self) -> bool:
        return False


@dataclass(frozen=True)
class CanonicalSourceVersion:
    """Version canonique publiée, immuable et résoluble."""

    canonical_source_id: str
    document_id: DocumentId
    canonical_version_id: str
    source_sha256: SourceFingerprint
    canonical_artifact: CanonicalArtifact
    page_count: int
    accepted_at: str
    quality_policy_version: str
    exports: tuple[RegenerableExport, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_source_id",
            _ensure_domain_identifier(self.canonical_source_id, "canonical_source_id", "CSRC"),
        )
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_identifier(self.canonical_version_id, "canonical_version_id", "CVER"),
        )
        _ensure_source_fingerprint(self.source_sha256)
        if not isinstance(self.canonical_artifact, CanonicalArtifact):
            raise ValueError("artefact canonique invalide")
        _ensure_artifact_matches_version(
            canonical_source_id=self.canonical_source_id,
            canonical_version_id=self.canonical_version_id,
            artifact_ref=self.canonical_artifact.artifact_ref,
        )
        object.__setattr__(self, "page_count", _ensure_positive_integer(self.page_count, "page_count invalide"))
        object.__setattr__(self, "quality_policy_version", _ensure_text(self.quality_policy_version, "version de politique QA obligatoire"))
        object.__setattr__(self, "exports", _ensure_exports(self.exports))
        CanonicalSourceRef.from_payload(self._canonical_ref_payload())

    @property
    def canonical_ref(self) -> CanonicalSourceRef:
        return CanonicalSourceRef.from_payload(self._canonical_ref_payload())

    def with_regenerable_export(self, export: RegenerableExport) -> "CanonicalSourceVersion":
        if not isinstance(export, RegenerableExport):
            raise ValueError("export régénérable invalide")
        if any(existing.export_ref == export.export_ref for existing in self.exports):
            raise ValueError("export régénérable dupliqué")
        return CanonicalSourceVersion(
            canonical_source_id=self.canonical_source_id,
            document_id=self.document_id,
            canonical_version_id=self.canonical_version_id,
            source_sha256=self.source_sha256,
            canonical_artifact=self.canonical_artifact,
            page_count=self.page_count,
            accepted_at=self.accepted_at,
            quality_policy_version=self.quality_policy_version,
            exports=self.exports + (export,),
        )

    def _canonical_ref_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _CANONICAL_SCHEMA_VERSION,
            "canonical_source_id": self.canonical_source_id,
            "document_id": self.document_id.value,
            "canonical_version_id": self.canonical_version_id,
            "source_sha256": self.source_sha256.value,
            "canonical_artifact_sha256": self.canonical_artifact.artifact_sha256,
            "page_count": self.page_count,
            "accepted_at": self.accepted_at,
            "quality_policy_version": self.quality_policy_version,
        }


@dataclass(frozen=True)
class CanonicalSource:
    """Agrégat SP qui possède les versions canoniques publiées d'une source."""

    canonical_source_id: str
    document_id: DocumentId
    source_sha256: SourceFingerprint
    status: CanonicalSourceStatus
    current_version_id: str
    versions: tuple[CanonicalSourceVersion, ...]

    @classmethod
    def publish_initial(
        cls,
        *,
        source_document: SourceDocument,
        docling_document: PagewiseDoclingDocument,
        text_authority_manifest: TextAuthorityManifest,
        quality_decision: CanonicalQualityDecision,
        canonical_artifact: CanonicalArtifact,
        accepted_at: str,
    ) -> "CanonicalSource":
        parsed_source_document = _ensure_source_document(source_document)
        parsed_source_document.ensure_documentary_publication_allowed()
        parsed_docling_document = _ensure_docling_document(docling_document)
        _ensure_docling_document_matches_source(
            source_document=parsed_source_document,
            docling_document=parsed_docling_document,
        )
        _ensure_docling_document_has_text_authority(
            docling_document=parsed_docling_document,
            text_authority_manifest=text_authority_manifest,
        )
        _ensure_green_quality_decision(quality_decision)
        canonical_source_id = canonical_source_id_for(parsed_source_document.document_id)
        version = _build_version(
            canonical_source_id=canonical_source_id,
            source_document=parsed_source_document,
            docling_document=parsed_docling_document,
            quality_decision=quality_decision,
            canonical_artifact=canonical_artifact,
            accepted_at=accepted_at,
        )
        return cls(
            canonical_source_id=canonical_source_id,
            document_id=parsed_source_document.document_id,
            source_sha256=parsed_source_document.fingerprint,
            status=CanonicalSourceStatus.PUBLISHED,
            current_version_id=version.canonical_version_id,
            versions=(version,),
        )

    def publish_correction(
        self,
        *,
        docling_document: PagewiseDoclingDocument,
        text_authority_manifest: TextAuthorityManifest,
        quality_decision: CanonicalQualityDecision,
        canonical_artifact: CanonicalArtifact,
        accepted_at: str,
    ) -> "CanonicalSource":
        parsed_docling_document = _ensure_docling_document(docling_document)
        if parsed_docling_document.document_id != self.document_id:
            raise ValueError("document_id canonique incohérent")
        if parsed_docling_document.source_sha256 != self.source_sha256:
            raise ValueError("source_sha256 canonique incohérent")
        if self.has_version(parsed_docling_document.canonical_version_id):
            raise ValueError("mutation en place interdite")
        _ensure_docling_document_has_text_authority(
            docling_document=parsed_docling_document,
            text_authority_manifest=text_authority_manifest,
        )
        _ensure_green_quality_decision(quality_decision)

        version = CanonicalSourceVersion(
            canonical_source_id=self.canonical_source_id,
            document_id=self.document_id,
            canonical_version_id=parsed_docling_document.canonical_version_id,
            source_sha256=self.source_sha256,
            canonical_artifact=canonical_artifact,
            page_count=len(parsed_docling_document.pages),
            accepted_at=accepted_at,
            quality_policy_version=quality_decision.policy_version,
            exports=(),
        )
        return CanonicalSource(
            canonical_source_id=self.canonical_source_id,
            document_id=self.document_id,
            source_sha256=self.source_sha256,
            status=CanonicalSourceStatus.PUBLISHED,
            current_version_id=version.canonical_version_id,
            versions=self.versions + (version,),
        )

    def with_regenerable_export(
        self,
        *,
        canonical_version_id: str,
        export: RegenerableExport,
    ) -> "CanonicalSource":
        parsed_version_id = _ensure_domain_identifier(
            canonical_version_id,
            "canonical_version_id",
            "CVER",
        )
        updated_versions: list[CanonicalSourceVersion] = []
        version_found = False
        for version in self.versions:
            if version.canonical_version_id == parsed_version_id:
                updated_versions.append(version.with_regenerable_export(export))
                version_found = True
            else:
                updated_versions.append(version)
        if not version_found:
            raise ValueError("version canonique absente")
        return CanonicalSource(
            canonical_source_id=self.canonical_source_id,
            document_id=self.document_id,
            source_sha256=self.source_sha256,
            status=self.status,
            current_version_id=self.current_version_id,
            versions=tuple(updated_versions),
        )

    def version_for(self, canonical_version_id: str) -> CanonicalSourceVersion:
        parsed_version_id = _ensure_domain_identifier(
            canonical_version_id,
            "canonical_version_id",
            "CVER",
        )
        for version in self.versions:
            if version.canonical_version_id == parsed_version_id:
                return version
        raise ValueError("version canonique absente")

    def has_version(self, canonical_version_id: str) -> bool:
        parsed_version_id = _ensure_domain_identifier(
            canonical_version_id,
            "canonical_version_id",
            "CVER",
        )
        return any(version.canonical_version_id == parsed_version_id for version in self.versions)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "canonical_source_id",
            _ensure_domain_identifier(self.canonical_source_id, "canonical_source_id", "CSRC"),
        )
        _ensure_document_id(self.document_id)
        _ensure_source_fingerprint(self.source_sha256)
        if not isinstance(self.status, CanonicalSourceStatus):
            raise ValueError("statut CanonicalSource invalide")
        object.__setattr__(
            self,
            "current_version_id",
            _ensure_domain_identifier(self.current_version_id, "current_version_id", "CVER"),
        )
        versions = _ensure_versions(self.versions)
        object.__setattr__(self, "versions", versions)
        version_ids = tuple(version.canonical_version_id for version in versions)
        if self.current_version_id not in version_ids:
            raise ValueError("version courante absente")
        if self.current_version_id != versions[-1].canonical_version_id:
            raise ValueError("version courante incohérente")
        for version in versions:
            if version.canonical_source_id != self.canonical_source_id:
                raise ValueError("canonical_source_id incohérent")
            if version.document_id != self.document_id:
                raise ValueError("document_id canonique incohérent")
            if version.source_sha256 != self.source_sha256:
                raise ValueError("source_sha256 canonique incohérent")


def canonical_source_id_for(document_id: DocumentId) -> str:
    parsed_document_id = _ensure_document_id(document_id)
    source_id = f"CSRC-{parsed_document_id.value.removeprefix('DOC-')}"
    return _ensure_domain_identifier(source_id, "canonical_source_id", "CSRC")


def canonical_artifact_ref_for(*, canonical_source_id: str, canonical_version_id: str) -> str:
    parsed_source_id = _ensure_domain_identifier(
        canonical_source_id,
        "canonical_source_id",
        "CSRC",
    )
    parsed_version_id = _ensure_domain_identifier(
        canonical_version_id,
        "canonical_version_id",
        "CVER",
    )
    return f"{_CANONICAL_ARTIFACT_PREFIX}{parsed_source_id}/{parsed_version_id}/docling.json"


def _build_version(
    *,
    canonical_source_id: str,
    source_document: SourceDocument,
    docling_document: PagewiseDoclingDocument,
    quality_decision: CanonicalQualityDecision,
    canonical_artifact: CanonicalArtifact,
    accepted_at: str,
) -> CanonicalSourceVersion:
    return CanonicalSourceVersion(
        canonical_source_id=canonical_source_id,
        document_id=source_document.document_id,
        canonical_version_id=docling_document.canonical_version_id,
        source_sha256=source_document.fingerprint,
        canonical_artifact=canonical_artifact,
        page_count=len(docling_document.pages),
        accepted_at=accepted_at,
        quality_policy_version=quality_decision.policy_version,
        exports=(),
    )


def _ensure_green_quality_decision(value: CanonicalQualityDecision) -> CanonicalQualityDecision:
    if not isinstance(value, CanonicalQualityDecision):
        raise ValueError("décision QA canonique invalide")
    if not value.publication_allowed:
        raise ValueError("QA GREEN obligatoire")
    if value.status not in {QualityDecisionStatus.PASS, QualityDecisionStatus.PASS_WITH_WARNINGS}:
        raise ValueError("QA GREEN obligatoire")
    return value


def _ensure_docling_document_matches_source(
    *,
    source_document: SourceDocument,
    docling_document: PagewiseDoclingDocument,
) -> None:
    if docling_document.document_id != source_document.document_id:
        raise ValueError("document_id canonique incohérent")
    if docling_document.source_sha256 != source_document.fingerprint:
        raise ValueError("source_sha256 canonique incohérent")
    if docling_document.original_storage_ref != source_document.original_storage_ref:
        raise ValueError("original_storage_ref canonique incohérent")


def _ensure_docling_document_has_text_authority(
    *,
    docling_document: PagewiseDoclingDocument,
    text_authority_manifest: TextAuthorityManifest,
) -> None:
    if not isinstance(text_authority_manifest, TextAuthorityManifest):
        raise ValueError("autorité textuelle obligatoire")
    authorized_document = PagewiseDoclingFusionService().merge_authorized(
        document_id=docling_document.document_id,
        canonical_version_id=docling_document.canonical_version_id,
        source_sha256=docling_document.source_sha256,
        original_storage_ref=docling_document.original_storage_ref,
        page_manifest=text_authority_manifest.page_manifest,
        text_authority_manifest=text_authority_manifest,
    )
    if authorized_document.to_payload() != docling_document.to_payload():
        raise ValueError("autorité textuelle obligatoire")


def _ensure_versions(value: Sequence[CanonicalSourceVersion]) -> tuple[CanonicalSourceVersion, ...]:
    if value is None:
        raise ValueError("versions canoniques absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("versions canoniques invalides")
    versions = tuple(value)
    if len(versions) == 0:
        raise ValueError("versions canoniques vides")
    version_ids: list[str] = []
    for version in versions:
        if not isinstance(version, CanonicalSourceVersion):
            raise ValueError("version canonique invalide")
        version_ids.append(version.canonical_version_id)
    if len(version_ids) != len(set(version_ids)):
        raise ValueError("version canonique dupliquée")
    return versions


def _ensure_exports(value: Sequence[RegenerableExport]) -> tuple[RegenerableExport, ...]:
    if value is None:
        raise ValueError("exports régénérables absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("exports régénérables invalides")
    exports = tuple(value)
    export_refs: list[str] = []
    for export in exports:
        if not isinstance(export, RegenerableExport):
            raise ValueError("export régénérable invalide")
        export_refs.append(export.export_ref)
    if len(export_refs) != len(set(export_refs)):
        raise ValueError("export régénérable dupliqué")
    return exports


def _ensure_canonical_artifact_ref(value: Any) -> str:
    text = _ensure_text(value, "référence d'artefact canonique invalide")
    if not text.startswith(_CANONICAL_ARTIFACT_PREFIX):
        raise ValueError("référence d'artefact canonique invalide")
    if not text.endswith("/docling.json"):
        raise ValueError("artefact dérivé non canonique")
    return text


def _ensure_regenerable_export_ref(value: Any, export_kind: CanonicalArtifactKind) -> str:
    text = _ensure_text(value, "référence d'export régénérable invalide")
    if not text.startswith(_REGENERABLE_EXPORT_PREFIX):
        raise ValueError("référence d'export régénérable invalide")
    if export_kind is CanonicalArtifactKind.MARKDOWN and not text.endswith(".md"):
        raise ValueError("référence d'export régénérable invalide")
    if export_kind is CanonicalArtifactKind.HTML and not text.endswith(".html"):
        raise ValueError("référence d'export régénérable invalide")
    return text


def _ensure_artifact_matches_version(
    *,
    canonical_source_id: str,
    canonical_version_id: str,
    artifact_ref: str,
) -> None:
    expected_ref = canonical_artifact_ref_for(
        canonical_source_id=canonical_source_id,
        canonical_version_id=canonical_version_id,
    )
    if artifact_ref != expected_ref:
        raise ValueError("artefact canonique incohérent")


def _ensure_sha256(value: Any, message: str) -> str:
    text = _ensure_text(value, message)
    if _HASH_PATTERN.fullmatch(text) is None:
        raise ValueError(message)
    return text.lower()


def _ensure_domain_identifier(value: Any, field_name: str, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


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


def _ensure_document_id(value: Any) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_source_fingerprint(value: Any) -> SourceFingerprint:
    if not isinstance(value, SourceFingerprint):
        raise ValueError("source_sha256 invalide")
    return value


def _ensure_source_document(value: Any) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


def _ensure_docling_document(value: Any) -> PagewiseDoclingDocument:
    if not isinstance(value, PagewiseDoclingDocument):
        raise ValueError("DoclingDocument canonique invalide")
    return value


__all__ = [
    "CanonicalArtifact",
    "CanonicalArtifactKind",
    "CanonicalSource",
    "CanonicalSourceStatus",
    "CanonicalSourceVersion",
    "RegenerableExport",
    "canonical_artifact_ref_for",
    "canonical_source_id_for",
]
