"""Contrat strict du manifeste d'archive chiffrée V1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final


BACKUP_MANIFEST_CONTRACT_VERSION: Final = "M013-BackupManifest-1.1"
BACKUP_ARCHIVE_FORMAT: Final = "M013-AES256GCM-TAR-1.0"
MAX_MANIFEST_BYTES: Final = 2 * 1024 * 1024

_CONTEXTS = frozenset({"SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV", "platform"})
_KINDS = {
    "corpus_original": "SP",
    "canonical_versions": "SP",
    "qdrant_projection": "KA",
    "claim_registry": "EG",
    "verified_answers": "RA",
    "conversation_turns": "CV",
    "strategy_snapshots": "SD",
    "experiment_results": "EX",
    "evaluation_reports": "EV",
    "governance_artifacts": "platform",
}
_NEGATIVE_CONTEXTS = frozenset({"EG", "RA", "SD", "EX", "EV"})
_SENSITIVE = (
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "clé privée",
    "cle privee",
    "mot de passe",
    "password",
    "passphrase",
    "private key",
    "secret_interdit_m013",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLACEHOLDER = re.compile(r"^([0-9a-f])\1{63}$")
_ENTRY_ID = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class BackupManifest:
    path: Path
    manifest_id: str
    environment: str
    deployment_id: str
    archive_format: str
    ciphertext_sha256: str
    entries: tuple[dict[str, Any], ...]


def read_backup_manifest(path: Path, label: str) -> BackupManifest:
    """Lit un manifeste 1.1 complet, sans accepter un contrat historique."""

    serialized = read_backup_manifest_bytes(path, label=label)
    try:
        document = json.loads(serialized.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"MANIFEST_{label.upper()}_JSON_INVALID:{error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"MANIFEST_{label.upper()}_OBJECT_REQUIRED")
    _equal(
        _text(document, "contract_version"),
        BACKUP_MANIFEST_CONTRACT_VERSION,
        "MANIFEST_CONTRACT_VERSION_INVALID",
    )
    manifest_id = _text(document, "manifest_id")
    environment = _text(document, "environment")
    deployment_id = _text(document, "deployment_id")
    _text(document, "backup_command")
    _text(document, "restore_command")
    _equal(_text(document, "restore_target"), "local_isolated", "MANIFEST_RESTORE_TARGET_INVALID")
    _true(_bool(document, "complete"), "MANIFEST_INCOMPLETE")
    _true(_bool(document, "archive_encrypted"), "MANIFEST_ENCRYPTION_REQUIRED")
    _true(not _bool(document, "key_git_tracked"), "MANIFEST_GIT_KEY_FORBIDDEN")
    archive_format = _text(document, "archive_format")
    _equal(archive_format, BACKUP_ARCHIVE_FORMAT, "MANIFEST_ARCHIVE_FORMAT_INVALID")
    ciphertext_sha256 = _sha(document, "ciphertext_sha256")
    key_reference = _text(document, "key_reference")
    _assert_no_secret(key_reference)
    _true(
        key_reference.startswith("hors_depot://"),
        "MANIFEST_KEY_OUTSIDE_REPOSITORY_REQUIRED",
    )
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("MANIFEST_ENTRIES_REQUIRED")
    entries = tuple(_entry(raw_entry) for raw_entry in raw_entries)
    _validate_entry_set(entries)
    return BackupManifest(
        path=path.resolve(),
        manifest_id=manifest_id,
        environment=environment,
        deployment_id=deployment_id,
        archive_format=archive_format,
        ciphertext_sha256=ciphertext_sha256,
        entries=entries,
    )


def read_backup_manifest_bytes(path: Path, *, label: str) -> bytes:
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError(f"MANIFEST_{label.upper()}_REQUIRED:{path}")
    size = path.stat().st_size
    if size == 0 or size > MAX_MANIFEST_BYTES:
        raise ValueError(f"MANIFEST_{label.upper()}_SIZE_INVALID:{size}")
    with path.open("rb") as stream:
        document = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(document) != size or len(document) > MAX_MANIFEST_BYTES:
        raise ValueError(f"MANIFEST_{label.upper()}_SIZE_INVALID:{len(document)}")
    return document


def _entry(raw_entry: object) -> dict[str, Any]:
    if not isinstance(raw_entry, dict):
        raise ValueError("MANIFEST_ENTRY_OBJECT_REQUIRED")
    entry = dict(raw_entry)
    entry["entry_id"] = _text(entry, "entry_id")
    _true(_ENTRY_ID.fullmatch(entry["entry_id"]) is not None, "MANIFEST_ENTRY_ID_INVALID")
    entry["context"] = _text(entry, "context")
    _true(entry["context"] in _CONTEXTS, "MANIFEST_CONTEXT_INVALID")
    entry["artifact_kind"] = _text(entry, "artifact_kind")
    _true(entry["artifact_kind"] in _KINDS, "MANIFEST_ARTIFACT_KIND_INVALID")
    _equal(_KINDS[entry["artifact_kind"]], entry["context"], "MANIFEST_ARTIFACT_CONTEXT_INVALID")
    entry["stable_identifier"] = _text(entry, "stable_identifier")
    entry["archive_member"] = _archive_member(entry)
    _equal(_text(entry, "storage_host"), "docker-local", "MANIFEST_SPARK_STORAGE_FORBIDDEN")
    entry["authority"] = _bool(entry, "authority")
    entry["immutable"] = _bool(entry, "immutable")
    entry["regenerable_projection"] = _bool(entry, "regenerable_projection")
    entry["retained_negative_or_superseded"] = _bool(
        entry, "retained_negative_or_superseded"
    )
    for name, code in (
        ("contains_plain_secret", "MANIFEST_PLAIN_SECRET_FORBIDDEN"),
        ("git_tracked_key_material", "MANIFEST_GIT_KEY_FORBIDDEN"),
        ("spark_business_storage", "MANIFEST_SPARK_STORAGE_FORBIDDEN"),
        ("destructive_restore", "MANIFEST_DESTRUCTIVE_RESTORE_FORBIDDEN"),
    ):
        _true(not _bool(entry, name), code)
    entry["backup_sha256"] = _sha(entry, "backup_sha256")
    if entry["artifact_kind"] == "qdrant_projection":
        _true(entry["regenerable_projection"], "MANIFEST_REGENERABLE_PROJECTION_REQUIRED")
    if entry["regenerable_projection"]:
        _true(not entry["authority"], "MANIFEST_REGENERABLE_PROJECTION_AUTHORITY_FORBIDDEN")
    return entry


def _archive_member(entry: dict[str, Any]) -> str:
    member = _text(entry, "archive_member")
    parsed = PurePosixPath(member)
    expected = PurePosixPath("entries") / f"{entry['entry_id']}.json"
    _equal(parsed, expected, "MANIFEST_ARCHIVE_MEMBER_INVALID")
    return member


def _validate_entry_set(entries: tuple[dict[str, Any], ...]) -> None:
    _unique((entry["entry_id"] for entry in entries), "MANIFEST_ENTRY_DUPLICATE")
    _unique((entry["archive_member"] for entry in entries), "MANIFEST_ARCHIVE_MEMBER_DUPLICATE")
    _unique((entry["stable_identifier"] for entry in entries), "MANIFEST_STABLE_IDENTIFIER_DUPLICATE")
    contexts = {entry["context"] for entry in entries}
    kinds = {entry["artifact_kind"] for entry in entries}
    negatives = {entry["context"] for entry in entries if entry["retained_negative_or_superseded"]}
    _equal(contexts, _CONTEXTS, "MANIFEST_CONTEXT_COVERAGE_INVALID")
    _equal(kinds, set(_KINDS), "MANIFEST_ARTIFACT_COVERAGE_INVALID")
    _true(_NEGATIVE_CONTEXTS <= negatives, "MANIFEST_NEGATIVE_RETENTION_INVALID")
    _true(any(entry["regenerable_projection"] for entry in entries), "MANIFEST_REGENERABLE_PROJECTION_REQUIRED")


def _text(document: dict[str, Any], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"MANIFEST_TEXT_REQUIRED:{name}")
    return value


def _bool(document: dict[str, Any], name: str) -> bool:
    value = document.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"MANIFEST_BOOL_REQUIRED:{name}")
    return value


def _sha(document: dict[str, Any], name: str) -> str:
    value = _text(document, name)
    if not _SHA256.fullmatch(value) or _PLACEHOLDER.fullmatch(value):
        raise ValueError(f"MANIFEST_SHA256_INVALID:{name}")
    return value


def _assert_no_secret(value: str) -> None:
    if any(fragment in value.lower() for fragment in _SENSITIVE):
        raise ValueError("MANIFEST_PLAIN_SECRET_FORBIDDEN")


def _true(value: bool, code: str) -> None:
    if not value:
        raise ValueError(code)


def _equal(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise ValueError(code)


def _unique(values: object, code: str) -> None:
    sequence = tuple(values)  # type: ignore[arg-type]
    if len(sequence) != len(set(sequence)):
        raise ValueError(code)


__all__ = [
    "BACKUP_ARCHIVE_FORMAT",
    "BACKUP_MANIFEST_CONTRACT_VERSION",
    "MAX_MANIFEST_BYTES",
    "BackupManifest",
    "read_backup_manifest",
    "read_backup_manifest_bytes",
]
