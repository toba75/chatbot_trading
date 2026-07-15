"""OCRmyPDF isolé dans une image Docker immuable et sans réseau (ADR-003/032)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.source_processing.application.convert_routed_pages import PagePreprocessingRequest
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PreprocessedPageArtifact,
)


_SCHEMA_VERSION = "1.0"
_OCRMYPDF_IMAGE_DIGEST = "sha256:88d50f2ce7c054e5aacfc48794eca50dbb8af9a6ef1d2a540456dcd9a4687e42"
_OCRMYPDF_IMAGE_REFERENCE = f"jbarlow83/ocrmypdf@{_OCRMYPDF_IMAGE_DIGEST}"
_OCRMYPDF_VERSION = "17.8.0"


class OcrmyPdfImageManifestError(RuntimeError):
    """Image OCRmyPDF absente ou non scellée."""

    def __init__(self, code: str = "CONVERSION_ASSET_MANIFEST_INVALID") -> None:
        super().__init__(code)


class OcrmyPdfContainerError(RuntimeError):
    """Échec stable de l'unique runtime OCRmyPDF autorisé."""

    def __init__(self, code: str = "OCRMYPDF_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class OcrmyPdfImageManifest:
    """Référence Docker exclusivement par digest, validée avant toute action."""

    image_reference: str
    tool_version: str

    @classmethod
    def load(
        cls,
        *,
        manifest_path: Path,
        require_local_image: bool,
        docker_inspect: Callable[[str], bool] | None = None,
    ) -> "OcrmyPdfImageManifest":
        if not isinstance(manifest_path, Path) or not isinstance(require_local_image, bool):
            raise OcrmyPdfImageManifestError()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OcrmyPdfImageManifestError() from error
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema_version",
            "tool",
            "tool_version",
            "image_reference",
        }:
            raise OcrmyPdfImageManifestError()
        image_reference = payload["image_reference"]
        if (
            payload["schema_version"] != _SCHEMA_VERSION
            or payload["tool"] != "ocrmypdf"
            or payload["tool_version"] != _OCRMYPDF_VERSION
            or image_reference != _OCRMYPDF_IMAGE_REFERENCE
        ):
            raise OcrmyPdfImageManifestError()
        manifest = cls(image_reference=image_reference, tool_version=_OCRMYPDF_VERSION)
        if require_local_image:
            inspector = docker_inspect if docker_inspect is not None else _docker_image_exists
            if not inspector(manifest.image_reference):
                raise OcrmyPdfImageManifestError("OCRMYPDF_UNAVAILABLE")
        return manifest


class OcrmyPdfPagePreprocessor:
    """Prétraite uniquement PREPROCESS_GRANITE, sans modifier l'original."""

    def __init__(
        self,
        *,
        image_manifest_path: Path,
        audit_root: Path,
        source_path_resolver: Callable[[str], Path],
        timeout_seconds: float,
    ) -> None:
        if not isinstance(audit_root, Path) or not callable(source_path_resolver):
            raise ValueError("configuration OCRmyPDF invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int | float) or timeout_seconds <= 0:
            raise ValueError("timeout OCRmyPDF invalide")
        self._manifest_path = image_manifest_path
        self._audit_root = audit_root.resolve()
        self._source_path_resolver = source_path_resolver
        self._timeout_seconds = float(timeout_seconds)
        OcrmyPdfImageManifest.load(
            manifest_path=self._manifest_path,
            require_local_image=True,
        )
        try:
            self._audit_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OcrmyPdfContainerError() from error

    def preprocess_page(self, request: PagePreprocessingRequest) -> PreprocessedPageArtifact:
        if not isinstance(request, PagePreprocessingRequest):
            raise ValueError("requête OCRmyPDF invalide")
        if request.route_name.value != "PREPROCESS_GRANITE":
            raise ValueError("OCRmyPDF hors route PREPROCESS_GRANITE")
        manifest = OcrmyPdfImageManifest.load(
            manifest_path=self._manifest_path,
            require_local_image=True,
        )
        try:
            source_path = self._source_path_resolver(request.source_artifact_ref).resolve()
        except (OSError, ValueError) as error:
            raise OcrmyPdfContainerError() from error
        if not source_path.is_file():
            raise OcrmyPdfContainerError()
        output_path = self._path_for(request)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OcrmyPdfContainerError() from error
        command = build_ocrmypdf_container_command(
            image_reference=manifest.image_reference,
            source_path=source_path,
            output_path=output_path,
            page_number=request.page_number.value,
        )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout_seconds,
                check=False,
                creationflags=_worker_process_creation_flags(),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            _remove_if_present(output_path)
            raise OcrmyPdfContainerError() from error
        if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            _remove_if_present(output_path)
            raise OcrmyPdfContainerError()
        return PreprocessedPageArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.OCRMYPDF,
            tool_version=manifest.tool_version,
            artifact_hash=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            artifact_ref=request.expected_output_artifact_ref,
        )

    def path_for_artifact_ref(self, artifact_ref: str) -> Path:
        if not isinstance(artifact_ref, str) or not artifact_ref.startswith(
            "artifact:source_processing.page_conversion/"
        ):
            raise ValueError("référence OCRmyPDF invalide")
        relative = artifact_ref.removeprefix("artifact:source_processing.page_conversion/")
        candidate = (self._audit_root / relative).resolve()
        if not candidate.is_relative_to(self._audit_root) or candidate.suffix.lower() != ".pdf":
            raise ValueError("référence OCRmyPDF invalide")
        return candidate

    def _path_for(self, request: PagePreprocessingRequest) -> Path:
        path = self.path_for_artifact_ref(request.expected_output_artifact_ref)
        if path.exists():
            _remove_if_present(path)
        return path


def build_ocrmypdf_container_command(
    *,
    image_reference: str,
    source_path: Path,
    output_path: Path,
    page_number: int,
) -> tuple[str, ...]:
    """Construit le seul appel Docker permis : digest, original RO, sortie dédiée et réseau absent."""

    if image_reference != _OCRMYPDF_IMAGE_REFERENCE:
        raise ValueError("image OCRmyPDF non scellée")
    if not isinstance(source_path, Path) or not isinstance(output_path, Path):
        raise ValueError("chemin OCRmyPDF invalide")
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        raise ValueError("page OCRmyPDF invalide")
    source = source_path.resolve()
    output = output_path.resolve()
    if source.parent == output.parent:
        raise ValueError("montages OCRmyPDF incohérents")
    return (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        "--mount",
        f"type=bind,source={source.parent},target=/input,readonly",
        "--mount",
        f"type=bind,source={output.parent},target=/output",
        image_reference,
        "--pages",
        str(page_number),
        "--rotate-pages",
        "--redo-ocr",
        "--output-type",
        "pdf",
        f"/input/{source.name}",
        f"/output/{output.name}",
    )


def _docker_image_exists(image_reference: str) -> bool:
    result = subprocess.run(
        ("docker", "image", "inspect", image_reference),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.returncode == 0


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _worker_process_creation_flags() -> int:
    return int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))


__all__ = [
    "OcrmyPdfContainerError",
    "OcrmyPdfImageManifest",
    "OcrmyPdfImageManifestError",
    "OcrmyPdfPagePreprocessor",
    "build_ocrmypdf_container_command",
]
