"""Adaptateur Granite-Docling isolé, scellé et strictement hors ligne."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.contracts.technical_jobs import (
    GraniteExecutionCapability,
    GraniteModelStillRunning,
    require_granite_execution_capability,
)
from app.source_processing.adapters.docling_native_conversion import (
    NativeDoclingConversionResponse,
)


_ASSET_MANIFEST_SCHEMA_VERSION = "1.0"
_DOCLING_VERSION = "2.111.0"
GRANITE_DOCLING_MODEL_REPOSITORY = "ibm-granite/granite-docling-258M"
GRANITE_DOCLING_MODEL_REVISION = "982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe"
_GRANITE_MODEL_DIRECTORY = "ibm-granite--granite-docling-258M"
_GRANITE_ROUTE_NAMES = frozenset(
    {
        "SCAN_GRANITE",
        "BAD_OCR_TO_GRANITE",
        "MIXED_PAGEWISE",
        "TARGETED_ENRICHMENT",
        "PREPROCESS_GRANITE",
    }
)


class GraniteDoclingAssetManifestError(RuntimeError):
    """Actifs Granite absents, altérés ou incompatibles avec le scellement."""

    def __init__(self, code: str = "CONVERSION_ASSET_MANIFEST_INVALID") -> None:
        super().__init__(code)


class GraniteDoclingConversionError(RuntimeError):
    """Échec terminal du seul chemin Granite-Docling autorisé."""

    def __init__(self, code: str = "GRANITE_DOCLING_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class GraniteDoclingAssetManifest:
    """Manifeste de tous les octets que Granite-Docling reçoit hors ligne."""

    assets_root: Path
    tool_version: str
    model_repository: str
    model_revision: str
    asset_hashes: Mapping[str, str]

    @classmethod
    def load(
        cls,
        *,
        manifest_path: Path,
        assets_root: Path,
    ) -> "GraniteDoclingAssetManifest":
        if not isinstance(manifest_path, Path) or not isinstance(assets_root, Path):
            raise GraniteDoclingAssetManifestError()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GraniteDoclingAssetManifestError() from error
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema_version",
            "tool",
            "tool_version",
            "model_repository",
            "model_revision",
            "assets",
        }:
            raise GraniteDoclingAssetManifestError()
        if (
            payload["schema_version"] != _ASSET_MANIFEST_SCHEMA_VERSION
            or payload["tool"] != "granite_docling"
            or payload["tool_version"] != _DOCLING_VERSION
            or payload["model_repository"] != GRANITE_DOCLING_MODEL_REPOSITORY
            or payload["model_revision"] != GRANITE_DOCLING_MODEL_REVISION
            or not isinstance(payload["assets"], list)
            or len(payload["assets"]) == 0
        ):
            raise GraniteDoclingAssetManifestError()
        resolved_root = assets_root.resolve()
        if (
            not resolved_root.is_dir()
            or not (resolved_root / _GRANITE_MODEL_DIRECTORY).is_dir()
        ):
            raise GraniteDoclingAssetManifestError()
        hashes: dict[str, str] = {}
        for asset in payload["assets"]:
            if not isinstance(asset, Mapping) or set(asset) != {
                "relative_path",
                "sha256",
            }:
                raise GraniteDoclingAssetManifestError()
            relative_path = asset["relative_path"]
            expected_hash = asset["sha256"]
            if (
                not isinstance(relative_path, str)
                or not isinstance(expected_hash, str)
                or relative_path.strip() == ""
                or Path(relative_path).is_absolute()
                or not _is_sha256(expected_hash)
                or relative_path in hashes
            ):
                raise GraniteDoclingAssetManifestError()
            resolved_asset = (resolved_root / relative_path).resolve()
            if (
                not resolved_asset.is_relative_to(resolved_root)
                or not resolved_asset.is_file()
            ):
                raise GraniteDoclingAssetManifestError()
            if hashlib.sha256(resolved_asset.read_bytes()).hexdigest() != expected_hash:
                raise GraniteDoclingAssetManifestError()
            hashes[relative_path] = expected_hash
        return cls(
            assets_root=resolved_root,
            tool_version=_DOCLING_VERSION,
            model_repository=GRANITE_DOCLING_MODEL_REPOSITORY,
            model_revision=GRANITE_DOCLING_MODEL_REVISION,
            asset_hashes=hashes,
        )


@dataclass(frozen=True)
class GraniteDoclingConversionRequest:
    """Entrée bornée de Granite-Docling pour une unique page explicitement routée."""

    document_id: str
    processing_run_id: str
    source_sha256: str
    source_pdf_path: Path
    page_number: int
    source_page_number: int
    route_name: str
    routing_policy_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "processing_run_id",
            "route_name",
            "routing_policy_version",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, str)
                or value.strip() == ""
                or value != value.strip()
            ):
                raise ValueError(f"{field_name} invalide")
        if self.route_name not in _GRANITE_ROUTE_NAMES:
            raise ValueError("route Granite invalide")
        if not _is_sha256(self.source_sha256):
            raise ValueError("source_sha256 invalide")
        if not isinstance(self.source_pdf_path, Path):
            raise ValueError("source_pdf_path invalide")
        for field_name in ("page_number", "source_page_number"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} invalide")

    def to_payload(self, *, assets_root: Path) -> dict[str, object]:
        return {
            "schema_version": _ASSET_MANIFEST_SCHEMA_VERSION,
            "document_id": self.document_id,
            "processing_run_id": self.processing_run_id,
            "source_sha256": self.source_sha256,
            "source_pdf_path": str(self.source_pdf_path.resolve()),
            "page_number": self.page_number,
            "source_page_number": self.source_page_number,
            "route_name": self.route_name,
            "routing_policy_version": self.routing_policy_version,
            "assets_root": str(assets_root),
            "model_repository": GRANITE_DOCLING_MODEL_REPOSITORY,
            "model_revision": GRANITE_DOCLING_MODEL_REVISION,
        }


class IsolatedGraniteDoclingConverter:
    """Démarre Granite-Docling seulement dans l'interpréteur courant de ``uv``."""

    def __init__(
        self, *, asset_manifest_path: Path, assets_root: Path, timeout_seconds: float
    ) -> None:
        if not isinstance(asset_manifest_path, Path) or not isinstance(
            assets_root, Path
        ):
            raise ValueError("configuration Granite-Docling invalide")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout Granite-Docling invalide")
        self._asset_manifest_path = asset_manifest_path
        self._assets_root = assets_root
        self._timeout_seconds = float(timeout_seconds)
        GraniteDoclingAssetManifest.load(
            manifest_path=self._asset_manifest_path,
            assets_root=self._assets_root,
        )

    def start(
        self,
        request: GraniteDoclingConversionRequest,
        *,
        capability: GraniteExecutionCapability,
    ) -> "RunningGraniteDoclingConversion":
        if not isinstance(request, GraniteDoclingConversionRequest):
            raise ValueError("requête Granite-Docling invalide")
        require_granite_execution_capability(capability)
        manifest = GraniteDoclingAssetManifest.load(
            manifest_path=self._asset_manifest_path,
            assets_root=self._assets_root,
        )
        if not request.source_pdf_path.is_file():
            raise GraniteDoclingConversionError()
        if (
            hashlib.sha256(request.source_pdf_path.read_bytes()).hexdigest()
            != request.source_sha256
        ):
            raise GraniteDoclingConversionError("SOURCE_FINGERPRINT_MISMATCH")
        environment = dict(os.environ)
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        environment["HF_HOME"] = str(manifest.assets_root)
        environment["PYTHONNOUSERSITE"] = "1"
        process = subprocess.Popen(
            (
                sys.executable,
                "-B",
                "-m",
                "app.source_processing.adapters.docling_granite_worker",
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            creationflags=_worker_process_creation_flags(),
        )
        return RunningGraniteDoclingConversion(
            process=process,
            request=request,
            input_payload=json.dumps(
                request.to_payload(assets_root=manifest.assets_root),
                separators=(",", ":"),
            ).encode("utf-8"),
            timeout_seconds=self._timeout_seconds,
        )


class RunningGraniteDoclingConversion:
    """Processus Granite observable et annulable par le contrôleur de capacité."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[bytes],
        request: GraniteDoclingConversionRequest,
        input_payload: bytes,
        timeout_seconds: float,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout Granite-Docling invalide")
        self._process = process
        self._request = request
        self._input_payload: bytes | None = input_payload
        self._deadline = time.monotonic() + float(timeout_seconds)
        self._terminated = False
        self._termination_lock = threading.Lock()

    def wait(self, *, timeout_seconds: float) -> NativeDoclingConversionResponse:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout Granite-Docling invalide")
        remaining_seconds = self._deadline - time.monotonic()
        if remaining_seconds <= 0:
            self._raise_timeout()
        input_payload = self._input_payload
        self._input_payload = None
        try:
            stdout, _stderr = self._process.communicate(
                input=input_payload,
                timeout=min(float(timeout_seconds), remaining_seconds),
            )
        except subprocess.TimeoutExpired as error:
            if time.monotonic() >= self._deadline:
                self._raise_timeout(cause=error)
            raise GraniteModelStillRunning() from error
        try:
            payload = json.loads(stdout)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GraniteDoclingConversionError() from error
        if self._process.returncode != 0:
            code = payload.get("error_code") if isinstance(payload, Mapping) else None
            raise GraniteDoclingConversionError(
                code
                if isinstance(code, str) and code != ""
                else "GRANITE_DOCLING_UNAVAILABLE"
            )
        native_request = _native_response_request(self._request)
        return NativeDoclingConversionResponse.from_payload(
            request=native_request,
            payload=payload,
        )

    def terminate(self) -> None:
        with self._termination_lock:
            if self._terminated:
                return
            if self._process.poll() is not None:
                self._terminated = True
                return
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5.0)
            self._terminated = True

    def _raise_timeout(self, *, cause: Exception | None = None) -> None:
        timeout_error = GraniteDoclingConversionError("GRANITE_DOCLING_TIMEOUT")
        try:
            self.terminate()
        except Exception as termination_error:
            raise ExceptionGroup(
                "GRANITE_TIMEOUT_AND_TERMINATION_FAILURE",
                [timeout_error, termination_error],
            ) from timeout_error
        if cause is not None:
            raise timeout_error from cause
        raise timeout_error


def _native_response_request(request: GraniteDoclingConversionRequest):
    """Réemploie le validateur strict de réponse Docling pagewise déjà livré en T-003."""

    from app.source_processing.adapters.docling_native_conversion import (
        NativeDoclingConversionRequest,
    )

    return NativeDoclingConversionRequest(
        document_id=request.document_id,
        processing_run_id=request.processing_run_id,
        source_sha256=request.source_sha256,
        source_pdf_path=request.source_pdf_path,
        expected_page_numbers=(request.page_number,),
        routing_policy_version=request.routing_policy_version,
    )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _worker_process_creation_flags() -> int:
    return int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))


__all__ = [
    "GRANITE_DOCLING_MODEL_REPOSITORY",
    "GRANITE_DOCLING_MODEL_REVISION",
    "GraniteDoclingAssetManifest",
    "GraniteDoclingAssetManifestError",
    "GraniteDoclingConversionError",
    "GraniteDoclingConversionRequest",
    "IsolatedGraniteDoclingConverter",
    "RunningGraniteDoclingConversion",
]
