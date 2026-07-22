"""Transport binaire borné des matériels d'archive vers le conteneur administratif."""

from __future__ import annotations

import os
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from typing import BinaryIO, Final

from ost_gate.operations.backup_manifest import MAX_MANIFEST_BYTES
from ost_gate.operations.encrypted_archive import KEY_BYTES, MAX_ARCHIVE_BYTES


TRANSPORT_MAGIC: Final = b"M013ADM1"
COMPOSE_ERROR_EXIT_CODES: Final = {
    "ARCHIVE_CIPHERTEXT_HASH_MISMATCH": 41,
    "ARCHIVE_DECRYPTION_FAILED": 42,
}
_HEADER = struct.Struct(">8sQQQ")


def encode_compose_payload(*, manifest: bytes, archive: bytes, key: bytes) -> bytes:
    _require_payload_size(manifest, maximum=MAX_MANIFEST_BYTES, code="MANIFEST_TRANSPORT_SIZE_INVALID")
    _require_payload_size(archive, maximum=MAX_ARCHIVE_BYTES, code="ARCHIVE_TRANSPORT_SIZE_INVALID")
    if not isinstance(key, bytes) or len(key) != KEY_BYTES:
        raise ValueError("ARCHIVE_KEY_SIZE_INVALID")
    return _HEADER.pack(TRANSPORT_MAGIC, len(manifest), len(archive), len(key)) + manifest + archive + key


def decode_compose_payload(stream: BinaryIO) -> tuple[bytes, bytes, bytes]:
    header = _read_exact(stream, _HEADER.size, code="ADMINISTRATIVE_TRANSPORT_HEADER_INVALID")
    magic, manifest_size, archive_size, key_size = _HEADER.unpack(header)
    if magic != TRANSPORT_MAGIC:
        raise ValueError("ADMINISTRATIVE_TRANSPORT_MAGIC_INVALID")
    if manifest_size == 0 or manifest_size > MAX_MANIFEST_BYTES:
        raise ValueError("MANIFEST_TRANSPORT_SIZE_INVALID")
    if archive_size == 0 or archive_size > MAX_ARCHIVE_BYTES:
        raise ValueError("ARCHIVE_TRANSPORT_SIZE_INVALID")
    if key_size != KEY_BYTES:
        raise ValueError("ARCHIVE_KEY_SIZE_INVALID")
    manifest = _read_exact(stream, manifest_size, code="MANIFEST_TRANSPORT_TRUNCATED")
    archive = _read_exact(stream, archive_size, code="ARCHIVE_TRANSPORT_TRUNCATED")
    key = _read_exact(stream, key_size, code="ARCHIVE_KEY_TRANSPORT_TRUNCATED")
    if stream.read(1) != b"":
        raise ValueError("ADMINISTRATIVE_TRANSPORT_TRAILING_BYTES")
    return manifest, archive, key


def run_streamed_compose_operation(
    *,
    operation: str,
    config_path: str,
    target_path: str | None,
) -> int:
    if operation not in {"backup", "restore"}:
        raise ValueError("ADMINISTRATIVE_OPERATION_UNKNOWN")
    if operation == "backup" and target_path is not None:
        raise ValueError("BACKUP_TARGET_FORBIDDEN")
    if operation == "restore" and target_path is None:
        raise ValueError("RESTORE_TARGET_REQUIRED")
    manifest, archive, key = decode_compose_payload(sys.stdin.buffer)
    with TemporaryDirectory(prefix=f"ostrading-{operation}-", dir="/tmp") as directory:
        root = Path(directory)
        manifest_path = root / "manifest.json"
        archive_path = root / "archive.m013.aesgcm"
        key_path = root / "archive.key"
        _write_private_file(manifest_path, manifest)
        _write_private_file(archive_path, archive)
        _write_private_file(key_path, key)
        arguments = [
            "--manifest",
            str(manifest_path),
            "--archive",
            str(archive_path),
            "--key-file",
            str(key_path),
            "--config",
            config_path,
            "--inside-compose",
        ]
        if target_path is not None:
            arguments.extend(("--target", target_path))
        module = __import__(f"ost_gate.operations.{operation}", fromlist=["main"])
        try:
            return module.main(arguments)
        except ValueError as error:
            exit_code = COMPOSE_ERROR_EXIT_CODES.get(str(error))
            if exit_code is None:
                raise
            print(str(error), file=sys.stderr, flush=True)
            return exit_code


def _read_exact(stream: BinaryIO, size: int, *, code: str) -> bytes:
    document = stream.read(size)
    if len(document) != size:
        raise ValueError(code)
    return document


def _require_payload_size(document: bytes, *, maximum: int, code: str) -> None:
    if not isinstance(document, bytes) or len(document) == 0 or len(document) > maximum:
        raise ValueError(code)


def _write_private_file(path: Path, document: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(document)


__all__ = [
    "COMPOSE_ERROR_EXIT_CODES",
    "MAX_MANIFEST_BYTES",
    "decode_compose_payload",
    "encode_compose_payload",
    "run_streamed_compose_operation",
]
