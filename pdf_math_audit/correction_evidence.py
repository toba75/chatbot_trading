from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from pdf_math_audit.gemma_proposal import Proposal, ProposalError


def evidence_key(region_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", region_id)


def record_success(
    archive: zipfile.ZipFile,
    checkpoint_root: Path | None,
    key: str,
    image: bytes,
    proposal: Proposal,
) -> None:
    files = {
        "crop.png": image,
        "request.json": _json_bytes(proposal.request),
        "response.json": _json_bytes(proposal.response),
    }
    _write(archive, checkpoint_root, key, files)


def record_failure(
    archive: zipfile.ZipFile,
    checkpoint_root: Path | None,
    key: str,
    image: bytes,
    error: ProposalError,
) -> None:
    files = {"crop.png": image, "request.json": _json_bytes(error.request)}
    if error.response is not None:
        files["response.bin"] = error.response
    _write(archive, checkpoint_root, key, files)


def checkpoint_record(path: Path | None, record: dict[str, Any]) -> None:
    if path is None:
        return
    with path.open("ab") as output:
        output.write(
            (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
                "utf-8"
            )
        )


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _write(
    archive: zipfile.ZipFile,
    checkpoint_root: Path | None,
    key: str,
    files: dict[str, bytes],
) -> None:
    for name, content in files.items():
        archive.writestr(f"{key}/{name}", content)
        if checkpoint_root is not None:
            destination = checkpoint_root / key / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
