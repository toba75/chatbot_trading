"""Archive TAR authentifiée AES-256-GCM et vérification des entrées extraites."""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import tarfile
from typing import Any, Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ost_gate.operations.backup_manifest import BackupManifest


ARCHIVE_MAGIC: Final = b"M013AESGCM1"
ARCHIVE_AAD: Final = b"M013-BackupArchive-1.0"
MAX_ARCHIVE_BYTES: Final = 256 * 1024 * 1024
MAX_DECRYPTED_BYTES: Final = 384 * 1024 * 1024
MAX_ENTRY_BYTES: Final = 64 * 1024 * 1024
MAX_ENTRY_COUNT: Final = 1024
KEY_BYTES: Final = 32
NONCE_BYTES: Final = 12

_ENTRY_DOCUMENT_KEYS = frozenset(
    {
        "schema_version",
        "entry_id",
        "context",
        "artifact_kind",
        "stable_identifier",
        "authority",
        "immutable",
        "regenerable_projection",
        "retained_negative_or_superseded",
        "payload_base64",
    }
)
_ENTRY_ID = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class BackupArchiveEntry:
    entry_id: str
    context: str
    artifact_kind: str
    stable_identifier: str
    authority: bool
    immutable: bool
    regenerable_projection: bool
    retained_negative_or_superseded: bool
    payload: bytes

    def __post_init__(self) -> None:
        for value, name in (
            (self.entry_id, "entry_id"),
            (self.context, "context"),
            (self.artifact_kind, "artifact_kind"),
            (self.stable_identifier, "stable_identifier"),
        ):
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"ARCHIVE_ENTRY_TEXT_REQUIRED:{name}")
        if _ENTRY_ID.fullmatch(self.entry_id) is None:
            raise ValueError("ARCHIVE_ENTRY_ID_INVALID")
        for value, name in (
            (self.authority, "authority"),
            (self.immutable, "immutable"),
            (self.regenerable_projection, "regenerable_projection"),
            (self.retained_negative_or_superseded, "retained_negative_or_superseded"),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"ARCHIVE_ENTRY_BOOL_REQUIRED:{name}")
        if not isinstance(self.payload, bytes) or len(self.payload) > MAX_ENTRY_BYTES:
            raise ValueError("ARCHIVE_ENTRY_PAYLOAD_INVALID")


@dataclass(frozen=True, slots=True)
class ArchiveMaterial:
    ciphertext: bytes
    encryption_key: bytes


@dataclass(frozen=True, slots=True)
class VerifiedArchiveEntry:
    entry_id: str
    stable_identifier: str
    archive_member: str
    sha256: str
    serialized_entry: bytes
    payload: bytes


@dataclass(frozen=True, slots=True)
class VerifiedArchive:
    ciphertext_sha256: str
    entries: tuple[VerifiedArchiveEntry, ...]


def archive_entry_sha256(entry: BackupArchiveEntry) -> str:
    return sha256(_entry_document_bytes(entry)).hexdigest()


def build_encrypted_archive(
    *,
    entries: tuple[BackupArchiveEntry, ...],
    encryption_key: bytes,
    nonce: bytes,
) -> bytes:
    """Produit le format contractuel; l'exploitation reste responsable de sa conservation."""

    _require_key(encryption_key)
    if not isinstance(nonce, bytes) or len(nonce) != NONCE_BYTES:
        raise ValueError("ARCHIVE_NONCE_INVALID")
    if not isinstance(entries, tuple) or not entries or len(entries) > MAX_ENTRY_COUNT:
        raise ValueError("ARCHIVE_ENTRY_COUNT_INVALID")
    if len({entry.entry_id for entry in entries}) != len(entries):
        raise ValueError("ARCHIVE_ENTRY_DUPLICATE")
    plaintext = BytesIO()
    with tarfile.open(fileobj=plaintext, mode="w:") as archive:
        for entry in entries:
            document = _entry_document_bytes(entry)
            member = tarfile.TarInfo(name=f"entries/{entry.entry_id}.json")
            member.size = len(document)
            member.mtime = 0
            member.mode = 0o600
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            archive.addfile(member, BytesIO(document))
    plaintext_bytes = plaintext.getvalue()
    if len(plaintext_bytes) > MAX_DECRYPTED_BYTES:
        raise ValueError("ARCHIVE_PLAINTEXT_TOO_LARGE")
    ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext_bytes, ARCHIVE_AAD)
    result = ARCHIVE_MAGIC + nonce + ciphertext
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("ARCHIVE_TOO_LARGE")
    return result


def load_archive_material(*, archive_path: Path, key_path: Path) -> ArchiveMaterial:
    ciphertext = _read_bounded_file(
        archive_path,
        missing_code="ARCHIVE_REQUIRED",
        maximum_bytes=MAX_ARCHIVE_BYTES,
    )
    encryption_key = _read_bounded_file(
        key_path,
        missing_code="ARCHIVE_KEY_REQUIRED",
        maximum_bytes=KEY_BYTES,
    )
    _require_key(encryption_key)
    return ArchiveMaterial(ciphertext=ciphertext, encryption_key=encryption_key)


def verify_encrypted_archive(
    *,
    manifest: BackupManifest,
    material: ArchiveMaterial,
) -> VerifiedArchive:
    if not isinstance(manifest, BackupManifest) or not isinstance(material, ArchiveMaterial):
        raise TypeError("ARCHIVE_VERIFICATION_INPUT_INVALID")
    actual_ciphertext_hash = sha256(material.ciphertext).hexdigest()
    if actual_ciphertext_hash != manifest.ciphertext_sha256:
        raise ValueError("ARCHIVE_CIPHERTEXT_HASH_MISMATCH")
    _require_key(material.encryption_key)
    prefix_size = len(ARCHIVE_MAGIC) + NONCE_BYTES
    if len(material.ciphertext) <= prefix_size or not material.ciphertext.startswith(ARCHIVE_MAGIC):
        raise ValueError("ARCHIVE_FORMAT_INVALID")
    nonce = material.ciphertext[len(ARCHIVE_MAGIC):prefix_size]
    encrypted_payload = material.ciphertext[prefix_size:]
    try:
        plaintext = AESGCM(material.encryption_key).decrypt(
            nonce,
            encrypted_payload,
            ARCHIVE_AAD,
        )
    except (InvalidTag, ValueError) as error:
        raise ValueError("ARCHIVE_DECRYPTION_FAILED") from error
    if len(plaintext) > MAX_DECRYPTED_BYTES:
        raise ValueError("ARCHIVE_PLAINTEXT_TOO_LARGE")
    verified_entries = _verify_tar_entries(plaintext=plaintext, manifest=manifest)
    return VerifiedArchive(
        ciphertext_sha256=actual_ciphertext_hash,
        entries=verified_entries,
    )


def _verify_tar_entries(
    *,
    plaintext: bytes,
    manifest: BackupManifest,
) -> tuple[VerifiedArchiveEntry, ...]:
    expected_by_member = {entry["archive_member"]: entry for entry in manifest.entries}
    try:
        with tarfile.open(fileobj=BytesIO(plaintext), mode="r:") as archive:
            members = archive.getmembers()
            if len(members) > MAX_ENTRY_COUNT or len({member.name for member in members}) != len(members):
                raise ValueError("ARCHIVE_MEMBER_SET_INVALID")
            if any(not member.isfile() for member in members):
                raise ValueError("ARCHIVE_MEMBER_TYPE_INVALID")
            if {member.name for member in members} != set(expected_by_member):
                raise ValueError("ARCHIVE_MEMBER_SET_INVALID")
            verified = []
            for member_name, expected in expected_by_member.items():
                member = archive.getmember(member_name)
                if member.size > MAX_ENTRY_BYTES:
                    raise ValueError("ARCHIVE_ENTRY_TOO_LARGE")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("ARCHIVE_ENTRY_UNREADABLE")
                serialized = stream.read(MAX_ENTRY_BYTES + 1)
                if len(serialized) != member.size or len(serialized) > MAX_ENTRY_BYTES:
                    raise ValueError("ARCHIVE_ENTRY_SIZE_INVALID")
                actual_hash = sha256(serialized).hexdigest()
                if actual_hash != expected["backup_sha256"]:
                    raise ValueError("ARCHIVE_ENTRY_HASH_MISMATCH")
                entry = _read_entry_document(serialized)
                _require_entry_matches_manifest(entry=entry, expected=expected)
                verified.append(
                    VerifiedArchiveEntry(
                        entry_id=entry["entry_id"],
                        stable_identifier=entry["stable_identifier"],
                        archive_member=member_name,
                        sha256=actual_hash,
                        serialized_entry=serialized,
                        payload=entry["payload"],
                    )
                )
    except tarfile.TarError as error:
        raise ValueError("ARCHIVE_TAR_INVALID") from error
    return tuple(verified)


def _read_entry_document(serialized: bytes) -> dict[str, Any]:
    try:
        document = json.loads(serialized.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("ARCHIVE_ENTRY_DOCUMENT_INVALID") from error
    if not isinstance(document, dict) or frozenset(document) != _ENTRY_DOCUMENT_KEYS:
        raise ValueError("ARCHIVE_ENTRY_DOCUMENT_INVALID")
    if document["schema_version"] != "M013-BackupEntry-1.0":
        raise ValueError("ARCHIVE_ENTRY_SCHEMA_INVALID")
    for name in (
        "authority",
        "immutable",
        "regenerable_projection",
        "retained_negative_or_superseded",
    ):
        if not isinstance(document[name], bool):
            raise ValueError(f"ARCHIVE_ENTRY_BOOL_INVALID:{name}")
    try:
        payload = b64decode(document["payload_base64"], validate=True)
    except (TypeError, ValueError) as error:
        raise ValueError("ARCHIVE_ENTRY_PAYLOAD_INVALID") from error
    if len(payload) > MAX_ENTRY_BYTES:
        raise ValueError("ARCHIVE_ENTRY_PAYLOAD_INVALID")
    return {**document, "payload": payload}


def _require_entry_matches_manifest(
    *,
    entry: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    comparisons = (
        ("entry_id", "ARCHIVE_ENTRY_ID_MISMATCH"),
        ("context", "ARCHIVE_CONTEXT_MISMATCH"),
        ("artifact_kind", "ARCHIVE_ARTIFACT_KIND_MISMATCH"),
        ("stable_identifier", "ARCHIVE_STABLE_IDENTIFIER_MISMATCH"),
        ("authority", "ARCHIVE_AUTHORITY_MISMATCH"),
        ("immutable", "ARCHIVE_IMMUTABILITY_MISMATCH"),
        ("regenerable_projection", "ARCHIVE_PROJECTION_POLICY_MISMATCH"),
        ("retained_negative_or_superseded", "ARCHIVE_RETENTION_MISMATCH"),
    )
    for name, code in comparisons:
        if entry.get(name) != expected[name]:
            raise ValueError(code)


def _entry_document_bytes(entry: BackupArchiveEntry) -> bytes:
    document = {
        "schema_version": "M013-BackupEntry-1.0",
        "entry_id": entry.entry_id,
        "context": entry.context,
        "artifact_kind": entry.artifact_kind,
        "stable_identifier": entry.stable_identifier,
        "authority": entry.authority,
        "immutable": entry.immutable,
        "regenerable_projection": entry.regenerable_projection,
        "retained_negative_or_superseded": entry.retained_negative_or_superseded,
        "payload_base64": b64encode(entry.payload).decode("ascii"),
    }
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _read_bounded_file(path: Path, *, missing_code: str, maximum_bytes: int) -> bytes:
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError(f"{missing_code}:{path}")
    size = path.stat().st_size
    if size == 0 or size > maximum_bytes:
        raise ValueError(f"{missing_code}_SIZE_INVALID:{size}")
    with path.open("rb") as stream:
        document = stream.read(maximum_bytes + 1)
    if len(document) != size or len(document) > maximum_bytes:
        raise ValueError(f"{missing_code}_SIZE_INVALID:{len(document)}")
    return document


def _require_key(encryption_key: bytes) -> None:
    if not isinstance(encryption_key, bytes) or len(encryption_key) != KEY_BYTES:
        raise ValueError("ARCHIVE_KEY_SIZE_INVALID")


__all__ = [
    "KEY_BYTES",
    "MAX_ARCHIVE_BYTES",
    "ArchiveMaterial",
    "BackupArchiveEntry",
    "VerifiedArchive",
    "VerifiedArchiveEntry",
    "archive_entry_sha256",
    "build_encrypted_archive",
    "load_archive_material",
    "verify_encrypted_archive",
]
