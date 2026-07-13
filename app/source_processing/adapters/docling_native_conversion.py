"""Adaptateur Docling natif isolé et stockage canonique immuable (ADR-032)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.source_processing.application.publish_canonical_source import (
    StoreCanonicalArtifactRequest,
    StoredCanonicalArtifact,
)


_ASSET_MANIFEST_SCHEMA_VERSION = "1.0"
_DOCLING_VERSION = "2.111.0"
_CANONICAL_ARTIFACT_PREFIX = "artifact:source_processing.canonical_sources/"


class DoclingAssetManifestError(RuntimeError):
    """Actifs Docling absents, altérés ou non conformes."""

    def __init__(self, code: str = "CONVERSION_ASSET_MANIFEST_INVALID") -> None:
        super().__init__(code)


class DoclingNativeConversionError(RuntimeError):
    """Échec stable du chemin Docling standard, sans route de remplacement."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or code.strip() == "" or code != code.strip():
            raise ValueError("code Docling invalide")
        self.code = code
        super().__init__(code)


class CanonicalArtifactStoreError(RuntimeError):
    """Erreur stable du stockage canonique durable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)


@dataclass(frozen=True)
class DoclingAssetManifest:
    """Manifeste scellé des fichiers nécessaires au runtime Docling standard."""

    assets_root: Path
    tool_version: str
    asset_hashes: Mapping[str, str]

    @classmethod
    def load(cls, *, manifest_path: Path, assets_root: Path) -> "DoclingAssetManifest":
        if not isinstance(manifest_path, Path) or not manifest_path.is_file():
            raise DoclingAssetManifestError()
        if not isinstance(assets_root, Path) or not assets_root.is_dir():
            raise DoclingAssetManifestError()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DoclingAssetManifestError() from error
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema_version",
            "tool",
            "tool_version",
            "assets",
        }:
            raise DoclingAssetManifestError()
        if payload["schema_version"] != _ASSET_MANIFEST_SCHEMA_VERSION:
            raise DoclingAssetManifestError()
        if payload["tool"] != "docling" or payload["tool_version"] != _DOCLING_VERSION:
            raise DoclingAssetManifestError()
        assets = payload["assets"]
        if not isinstance(assets, list) or len(assets) == 0:
            raise DoclingAssetManifestError()
        resolved_root = assets_root.resolve()
        hashes: dict[str, str] = {}
        for asset in assets:
            if not isinstance(asset, Mapping) or set(asset) != {"relative_path", "sha256"}:
                raise DoclingAssetManifestError()
            relative_path = asset["relative_path"]
            expected_hash = asset["sha256"]
            if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
                raise DoclingAssetManifestError()
            if relative_path.strip() == "" or Path(relative_path).is_absolute():
                raise DoclingAssetManifestError()
            if not _is_sha256(expected_hash) or relative_path in hashes:
                raise DoclingAssetManifestError()
            resolved_asset = (resolved_root / relative_path).resolve()
            if not resolved_asset.is_relative_to(resolved_root) or not resolved_asset.is_file():
                raise DoclingAssetManifestError()
            actual_hash = hashlib.sha256(resolved_asset.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise DoclingAssetManifestError()
            hashes[relative_path] = expected_hash
        return cls(assets_root=resolved_root, tool_version=_DOCLING_VERSION, asset_hashes=hashes)


@dataclass(frozen=True)
class NativeDoclingConversionRequest:
    """Entrée bornée et versionnée du processus Docling isolé."""

    document_id: str
    processing_run_id: str
    source_sha256: str
    source_pdf_path: Path
    expected_page_numbers: tuple[int, ...]
    routing_policy_version: str

    def __post_init__(self) -> None:
        for field_name in ("document_id", "processing_run_id", "routing_policy_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or value.strip() == "" or value != value.strip():
                raise ValueError(f"{field_name} invalide")
        if not _is_sha256(self.source_sha256):
            raise ValueError("source_sha256 invalide")
        if not isinstance(self.source_pdf_path, Path):
            raise ValueError("source_pdf_path invalide")
        pages = tuple(self.expected_page_numbers)
        if len(pages) == 0 or any(isinstance(page, bool) or not isinstance(page, int) or page < 1 for page in pages):
            raise ValueError("expected_page_numbers invalide")
        if pages != tuple(sorted(set(pages))):
            raise ValueError("expected_page_numbers invalide")
        object.__setattr__(self, "expected_page_numbers", pages)

    def to_payload(self, *, assets_root: Path) -> dict[str, object]:
        return {
            "schema_version": _ASSET_MANIFEST_SCHEMA_VERSION,
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "source_sha256": self.source_sha256,
            "source_pdf_path": str(self.source_pdf_path.resolve()),
            "expected_page_numbers": list(self.expected_page_numbers),
            "routing_policy_version": self.routing_policy_version,
            "assets_root": str(assets_root),
        }


@dataclass(frozen=True)
class NativeDoclingPageItem:
    text: str
    bbox: tuple[float, float, float, float]
    provenance: Mapping[str, object]


@dataclass(frozen=True)
class NativeDoclingPage:
    page_number: int
    items: tuple[NativeDoclingPageItem, ...]


@dataclass(frozen=True)
class NativeDoclingConversionResponse:
    """Sortie contrôlée de Docling, avant sa traduction vers le domaine SP."""

    tool_version: str
    pages: tuple[NativeDoclingPage, ...]

    @classmethod
    def from_payload(
        cls,
        *,
        request: NativeDoclingConversionRequest,
        payload: Any,
    ) -> "NativeDoclingConversionResponse":
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema_version",
            "tool_version",
            "pages",
        }:
            raise DoclingNativeConversionError("DOCLING_STANDARD_UNAVAILABLE")
        if payload["schema_version"] != _ASSET_MANIFEST_SCHEMA_VERSION or payload["tool_version"] != _DOCLING_VERSION:
            raise DoclingNativeConversionError("DOCLING_STANDARD_UNAVAILABLE")
        raw_pages = payload["pages"]
        if not isinstance(raw_pages, list):
            raise DoclingNativeConversionError("DOCLING_PAGE_MANIFEST_MISMATCH")
        raw_page_values: list[tuple[int, list[Any]]] = []
        for raw_page in raw_pages:
            if not isinstance(raw_page, Mapping) or set(raw_page) != {"page_number", "items"}:
                raise DoclingNativeConversionError("DOCLING_PAGE_MANIFEST_MISMATCH")
            page_number = raw_page["page_number"]
            raw_items = raw_page["items"]
            if isinstance(page_number, bool) or not isinstance(page_number, int) or not isinstance(raw_items, list) or len(raw_items) == 0:
                raise DoclingNativeConversionError("DOCLING_PAGE_MANIFEST_MISMATCH")
            raw_page_values.append((page_number, raw_items))
        if tuple(page_number for page_number, _ in raw_page_values) != request.expected_page_numbers:
            raise DoclingNativeConversionError("DOCLING_PAGE_MANIFEST_MISMATCH")
        parsed_pages = tuple(
            NativeDoclingPage(
                page_number=page_number,
                items=tuple(
                    _parse_page_item(raw_item, page_number=page_number)
                    for raw_item in raw_items
                ),
            )
            for page_number, raw_items in raw_page_values
        )
        return cls(tool_version=_DOCLING_VERSION, pages=parsed_pages)


class IsolatedNativeDoclingConverter:
    """Lance Docling exclusivement dans l'interpréteur courant de l'environnement uv."""

    def __init__(self, *, asset_manifest_path: Path, assets_root: Path, timeout_seconds: float) -> None:
        if not isinstance(asset_manifest_path, Path) or not isinstance(assets_root, Path):
            raise ValueError("configuration Docling invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int | float) or timeout_seconds <= 0:
            raise ValueError("timeout Docling invalide")
        self._asset_manifest_path = asset_manifest_path
        self._assets_root = assets_root
        self._timeout_seconds = float(timeout_seconds)
        DoclingAssetManifest.load(
            manifest_path=self._asset_manifest_path,
            assets_root=self._assets_root,
        )

    def convert(self, request: NativeDoclingConversionRequest) -> NativeDoclingConversionResponse:
        if not isinstance(request, NativeDoclingConversionRequest):
            raise ValueError("requête Docling invalide")
        manifest = DoclingAssetManifest.load(
            manifest_path=self._asset_manifest_path,
            assets_root=self._assets_root,
        )
        if not request.source_pdf_path.is_file():
            raise DoclingNativeConversionError("DOCLING_STANDARD_UNAVAILABLE")
        if hashlib.sha256(request.source_pdf_path.read_bytes()).hexdigest() != request.source_sha256:
            raise DoclingNativeConversionError("SOURCE_FINGERPRINT_MISMATCH")
        environment = dict(os.environ)
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        environment["HF_HOME"] = str(manifest.assets_root)
        environment["PYTHONNOUSERSITE"] = "1"
        try:
            completed = subprocess.run(
                (sys.executable, "-B", "-m", "app.source_processing.adapters.docling_native_worker"),
                input=json.dumps(request.to_payload(assets_root=manifest.assets_root), separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DoclingNativeConversionError("DOCLING_STANDARD_UNAVAILABLE") from error
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise DoclingNativeConversionError("DOCLING_STANDARD_UNAVAILABLE") from error
        if completed.returncode != 0:
            code = payload.get("error_code") if isinstance(payload, Mapping) else None
            raise DoclingNativeConversionError(
                code if isinstance(code, str) and code != "" else "DOCLING_STANDARD_UNAVAILABLE"
            )
        return NativeDoclingConversionResponse.from_payload(request=request, payload=payload)


class CanonicalArtifactFileStore:
    """Stocke un Docling JSON une seule fois sous ``canonical_sources_root``."""

    def __init__(self, *, root: Path) -> None:
        if not isinstance(root, Path):
            raise ValueError("racine artefacts canoniques invalide")
        self._root = root.resolve()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE") from error
        if not self._root.is_dir():
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE")

    def store_docling_json(self, request: StoreCanonicalArtifactRequest) -> StoredCanonicalArtifact:
        if not isinstance(request, StoreCanonicalArtifactRequest):
            raise ValueError("requête artefact canonique invalide")
        path = self._path_for(request.expected_artifact_ref)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                existing = path.read_bytes()
                if hashlib.sha256(existing).hexdigest() != request.artifact_sha256 or existing != request.content_bytes:
                    raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_IMMUTABILITY_VIOLATION")
                return StoredCanonicalArtifact(
                    artifact_ref=request.expected_artifact_ref,
                    artifact_sha256=request.artifact_sha256,
                )
            with path.open("xb") as stream:
                stream.write(request.content_bytes)
        except CanonicalArtifactStoreError:
            raise
        except OSError as error:
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE") from error
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != request.artifact_sha256:
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE")
        return StoredCanonicalArtifact(
            artifact_ref=request.expected_artifact_ref,
            artifact_sha256=request.artifact_sha256,
        )

    def _path_for(self, artifact_ref: str) -> Path:
        if not isinstance(artifact_ref, str) or not artifact_ref.startswith(_CANONICAL_ARTIFACT_PREFIX):
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE")
        relative = artifact_ref.removeprefix(_CANONICAL_ARTIFACT_PREFIX)
        candidate = (self._root / relative).resolve()
        if not candidate.is_relative_to(self._root) or candidate.name != "docling.json":
            raise CanonicalArtifactStoreError("CANONICAL_ARTIFACT_STORE_UNAVAILABLE")
        return candidate


def _parse_page_item(value: Any, *, page_number: int) -> NativeDoclingPageItem:
    if not isinstance(value, Mapping) or set(value) != {"text", "bbox", "provenance"}:
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    text = value["text"]
    bbox = value["bbox"]
    provenance = value["provenance"]
    if not isinstance(text, str) or text.strip() == "" or text != text.strip():
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    parsed_bbox = tuple(_finite_coordinate(coordinate) for coordinate in bbox)
    if parsed_bbox[0] >= parsed_bbox[2] or parsed_bbox[1] >= parsed_bbox[3]:
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    if not isinstance(provenance, Mapping) or provenance.get("page_number") != page_number:
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    return NativeDoclingPageItem(text=text, bbox=parsed_bbox, provenance=dict(provenance))


def _finite_coordinate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DoclingNativeConversionError("DOCLING_PROVENANCE_MISSING")
    return float(value)


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = [
    "CanonicalArtifactFileStore",
    "CanonicalArtifactStoreError",
    "DoclingAssetManifest",
    "DoclingAssetManifestError",
    "DoclingNativeConversionError",
    "IsolatedNativeDoclingConverter",
    "NativeDoclingConversionRequest",
    "NativeDoclingConversionResponse",
    "NativeDoclingPage",
    "NativeDoclingPageItem",
]
