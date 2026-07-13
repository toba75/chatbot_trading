"""Chargement strict du manifeste TOML de la gate."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

from ost_gate.errors import ManifestError
from ost_gate.models import GateManifest, GateNode

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]*$")
_KINDS = frozenset({"validator", "test"})
_REQUIRED_NODE_KEYS = frozenset(
    {
        "id",
        "path",
        "kind",
        "scope",
        "phase",
        "timeout_seconds",
        "serial_group",
        "depends_on",
        "live",
    }
)


def load_manifest(manifest_path: Path) -> GateManifest:
    """Charge et valide un manifeste sans interprétation permissive."""

    resolved_manifest = manifest_path.resolve(strict=False)
    if not resolved_manifest.is_file():
        raise ManifestError(f"GATE_MANIFEST_REQUIRED:{manifest_path}")
    repository_root = resolved_manifest.parent.resolve(strict=True)
    try:
        with resolved_manifest.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"GATE_MANIFEST_TOML_INVALID:{error}") from error
    if not isinstance(document, Mapping):
        raise ManifestError("GATE_MANIFEST_DOCUMENT_INVALID")
    if document.get("schema_version") != 1:
        raise ManifestError("GATE_MANIFEST_SCHEMA_VERSION_REQUIRED:1")
    raw_nodes = document.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ManifestError("GATE_MANIFEST_EMPTY")

    nodes: list[GateNode] = []
    identifiers: set[str] = set()
    paths: set[Path] = set()
    for index, raw_node in enumerate(raw_nodes, start=1):
        node = _parse_node(raw_node, index, repository_root)
        if node.identifier in identifiers:
            raise ManifestError(f"GATE_NODE_ID_DUPLICATE:{node.identifier}")
        if node.path in paths:
            raise ManifestError(f"GATE_NODE_PATH_DUPLICATE:{node.path.relative_to(repository_root).as_posix()}")
        identifiers.add(node.identifier)
        paths.add(node.path)
        nodes.append(node)
    for node in nodes:
        for dependency in node.depends_on:
            if dependency not in identifiers:
                raise ManifestError(f"GATE_NODE_DEPENDENCY_UNKNOWN:{node.identifier}:{dependency}")
    return GateManifest(
        repository_root=repository_root,
        source_path=resolved_manifest,
        nodes=tuple(nodes),
    )


def _parse_node(raw_node: object, index: int, repository_root: Path) -> GateNode:
    if not isinstance(raw_node, Mapping):
        raise ManifestError(f"GATE_NODE_INVALID:{index}")
    keys = frozenset(raw_node)
    missing = sorted(_REQUIRED_NODE_KEYS - keys)
    unexpected = sorted(keys - _REQUIRED_NODE_KEYS)
    if missing:
        raise ManifestError(f"GATE_NODE_FIELD_REQUIRED:{index}:{','.join(missing)}")
    if unexpected:
        raise ManifestError(f"GATE_NODE_FIELD_UNEXPECTED:{index}:{','.join(unexpected)}")
    identifier = _required_text(raw_node, "id", index)
    if not _IDENTIFIER.fullmatch(identifier):
        raise ManifestError(f"GATE_NODE_ID_INVALID:{identifier}")
    relative_path = _required_text(raw_node, "path", index)
    path = _resolve_repository_path(relative_path, repository_root, identifier)
    kind = _required_text(raw_node, "kind", index)
    if kind not in _KINDS:
        raise ManifestError(f"GATE_NODE_KIND_INVALID:{identifier}:{kind}")
    scope = _required_text(raw_node, "scope", index)
    phase = _required_text(raw_node, "phase", index)
    serial_group = _required_text(raw_node, "serial_group", index)
    timeout_seconds = raw_node["timeout_seconds"]
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ManifestError(f"GATE_NODE_TIMEOUT_INVALID:{identifier}")
    live = raw_node["live"]
    if not isinstance(live, bool):
        raise ManifestError(f"GATE_NODE_LIVE_INVALID:{identifier}")
    dependencies = raw_node["depends_on"]
    if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
        raise ManifestError(f"GATE_NODE_DEPENDENCIES_INVALID:{identifier}")
    depends_on = tuple(_dependency_text(value, identifier) for value in dependencies)
    if len(set(depends_on)) != len(depends_on):
        raise ManifestError(f"GATE_NODE_DEPENDENCY_DUPLICATE:{identifier}")
    if identifier in depends_on:
        raise ManifestError(f"GATE_NODE_SELF_DEPENDENCY:{identifier}")
    return GateNode(
        identifier=identifier,
        path=path,
        kind=kind,
        scope=scope,
        phase=phase,
        timeout_seconds=timeout_seconds,
        serial_group=serial_group,
        depends_on=depends_on,
        live=live,
    )


def _required_text(raw_node: Mapping[str, object], key: str, index: int) -> str:
    value = raw_node[key]
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"GATE_NODE_TEXT_REQUIRED:{index}:{key}")
    return value


def _dependency_text(value: object, identifier: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _IDENTIFIER.fullmatch(value):
        raise ManifestError(f"GATE_NODE_DEPENDENCY_INVALID:{identifier}")
    return value


def _resolve_repository_path(value: str, repository_root: Path, identifier: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ManifestError(f"GATE_NODE_PATH_OUTSIDE_REPOSITORY:{identifier}:{value}")
    resolved = (repository_root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(repository_root)
    except ValueError as error:
        raise ManifestError(f"GATE_NODE_PATH_OUTSIDE_REPOSITORY:{identifier}:{value}") from error
    if resolved.suffix != ".py" or not resolved.is_file():
        raise ManifestError(f"GATE_NODE_FILE_REQUIRED:{identifier}:{value}")
    return resolved
