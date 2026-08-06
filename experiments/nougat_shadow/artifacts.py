from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json_bytes(path: Path) -> bytes:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as source:
            return source.read()
    return path.read_bytes()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_json_bytes(path))


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
