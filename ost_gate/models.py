"""Modèles immuables de la gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GateNode:
    """Une preuve atomique et exécutable du manifeste."""

    identifier: str
    path: Path
    kind: str
    scope: str
    phase: str
    timeout_seconds: int
    serial_group: str
    depends_on: tuple[str, ...]
    live: bool


@dataclass(frozen=True, slots=True)
class GateManifest:
    """Le manifeste complet, résolu depuis la racine du dépôt."""

    repository_root: Path
    source_path: Path
    nodes: tuple[GateNode, ...]


@dataclass(frozen=True, slots=True)
class GatePlan:
    """Un ordre topologique déterministe, découpé en niveaux dépendants."""

    repository_root: Path
    nodes: tuple[GateNode, ...]
    levels: tuple[tuple[GateNode, ...], ...]
    partial: bool
    scope: str | None
    offline: bool


@dataclass(frozen=True, slots=True)
class NodeResult:
    """Résultat observable d’un nœud exécuté une fois."""

    identifier: str
    scope: str
    phase: str
    status: str
    duration_seconds: float
    executions: int
    detail: str | None
