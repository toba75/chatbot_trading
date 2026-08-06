from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


CONTRACT_VERSION = "2.1"
CAPABILITY_PROFILE = "pdf-docling-semantic-correction-v3"
ANALYZER_VERSION = "0.8.0"
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def sha256_argument(value: str) -> str:
    if not _SHA256_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "une empreinte SHA-256 sur 64 caractères est requise"
        )
    return value.lower()


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def require_fingerprint(
    parser: argparse.ArgumentParser,
    *,
    label: str,
    actual: str,
    announced: str,
) -> None:
    if actual != announced:
        parser.error(f"l’empreinte SHA-256 annoncée pour {label} ne correspond pas")
