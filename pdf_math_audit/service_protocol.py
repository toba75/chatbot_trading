from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def ndjson_line(event: dict[str, Any]) -> bytes:
    return (
        json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def artifact_events(
    name: str, path: Path, chunk_bytes: int
) -> Iterator[dict[str, Any]]:
    with path.open("rb") as artifact:
        for sequence, chunk in enumerate(iter(lambda: artifact.read(chunk_bytes), b"")):
            yield {
                "type": "artifact",
                "name": name,
                "sequence": sequence,
                "content_base64": base64.b64encode(chunk).decode("ascii"),
            }


def artifact_metadata(path: Path, chunks: int) -> dict[str, Any]:
    with path.open("rb") as artifact:
        digest = hashlib.file_digest(artifact, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest, "chunks": chunks}
