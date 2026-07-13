"""Vérification stricte des seules références historiques autorisées."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class HistoricalReferenceError(ValueError):
    """Signale une référence retirée présente hors de la liste fermée."""


_ALLOWLIST_PATH = Path("docs/governance/historical_reference_allowlist.json")
_SOURCE_SUFFIXES = frozenset(
    {
        ".css",
        ".html",
        ".json",
        ".js",
        ".lock",
        ".md",
        ".py",
        ".sql",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".tmp",
        ".venv",
        ".venv-agent",
        ".venv-review3-api",
        "__pycache__",
        "chatbot_trading.egg-info",
        "node_modules",
    }
)
_REFERENCE_MARKERS = ("power" + "shell", "pw" + "sh", "." + "ps" + "1")


def validate_historical_references(repository_root: Path) -> None:
    """Refuse toute référence active et toute allowlist imprécise."""

    root = repository_root.resolve(strict=True)
    allowlist_path = (root / _ALLOWLIST_PATH).resolve(strict=False)
    if not allowlist_path.is_file():
        raise HistoricalReferenceError("GATE_HISTORICAL_ALLOWLIST_REQUIRED")
    allowed = _load_allowlist(root, allowlist_path)
    found: set[str] = set()
    for path in _source_files(root):
        relative_path = path.relative_to(root).as_posix()
        if relative_path == _ALLOWLIST_PATH.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_SOURCE_UTF8_REQUIRED:{relative_path}"
            ) from error
        if not _contains_reference(text):
            continue
        if relative_path not in allowed:
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_REFERENCE_ACTIVE:{relative_path}"
            )
        found.add(relative_path)
    stale = sorted(set(allowed) - found)
    if stale:
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_STALE:{','.join(stale)}"
        )


def _load_allowlist(root: Path, allowlist_path: Path) -> dict[str, str]:
    try:
        document = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_INVALID:{error}"
        ) from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise HistoricalReferenceError("GATE_HISTORICAL_ALLOWLIST_SCHEMA_REQUIRED")
    records = document.get("allowed_paths")
    if not isinstance(records, list) or not records:
        raise HistoricalReferenceError("GATE_HISTORICAL_ALLOWLIST_EMPTY")
    allowed: dict[str, str] = {}
    for index, record in enumerate(records, start=1):
        path, digest = _allowlist_record(record, index)
        if path in allowed:
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_ALLOWLIST_DUPLICATE:{path}"
            )
        candidate = (root / path).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_ALLOWLIST_OUTSIDE_REPOSITORY:{path}"
            ) from error
        if not candidate.is_file():
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_ALLOWLIST_FILE_REQUIRED:{path}"
            )
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != digest:
            raise HistoricalReferenceError(
                f"GATE_HISTORICAL_ALLOWLIST_HASH_MISMATCH:{path}"
            )
        allowed[path] = digest
    return allowed


def _allowlist_record(record: Any, index: int) -> tuple[str, str]:
    if not isinstance(record, dict) or set(record) != {"path", "reason", "sha256"}:
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_RECORD_INVALID:{index}"
        )
    path = record["path"]
    digest = record["sha256"]
    reason = record["reason"]
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_PATH_INVALID:{index}"
        )
    if not isinstance(reason, str) or not reason.strip():
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_REASON_REQUIRED:{path}"
        )
    if not isinstance(digest, str) or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise HistoricalReferenceError(
            f"GATE_HISTORICAL_ALLOWLIST_HASH_INVALID:{path}"
        )
    return path, digest


def _source_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _IGNORED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() in _SOURCE_SUFFIXES or path.name == "AGENTS.md":
            files.append(path)
    return sorted(files)


def _contains_reference(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in _REFERENCE_MARKERS)
