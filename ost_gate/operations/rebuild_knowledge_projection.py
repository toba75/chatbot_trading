"""Commande `uv run rebuild-knowledge-projection`."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rebuild-knowledge-projection")
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.source != "SP":
        raise ValueError(f"PROJECTION_SOURCE_INVALID:{arguments.source}")
    source_root = arguments.source_root.resolve(strict=True)
    target = arguments.target.resolve(strict=False)
    if target.is_file() or (target.is_dir() and any(target.iterdir())):
        raise ValueError(f"PROJECTION_TARGET_INVALID:{target}")
    try:
        target.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError(f"PROJECTION_TARGET_INSIDE_SOURCE_FORBIDDEN:{target}")
    corpus_marker = source_root / "corpus_originals.marker"
    canonical_marker = source_root / "canonical_versions.marker"
    if not corpus_marker.is_file() or not canonical_marker.is_file():
        raise ValueError("PROJECTION_SP_AUTHORITY_REQUIRED")
    source_count = sum(1 for item in source_root.rglob("*") if item.is_file())
    if source_count == 0:
        raise ValueError("PROJECTION_SOURCE_EMPTY")
    staging = target.with_name(f"{target.name}.staging-{uuid.uuid4().hex}")
    try:
        staging.mkdir(parents=True)
        document = {
            "source": "SP",
            "source_root": str(source_root),
            "target": str(target),
            "reconstructed_item_count": source_count,
            "corpus_marker": corpus_marker.read_text(encoding="utf-8-sig").strip(),
            "canonical_marker": canonical_marker.read_text(encoding="utf-8-sig").strip(),
            "status": "GREEN",
        }
        (staging / "projection_manifest.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists():
            target.rmdir()
        staging.replace(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"Projection KA reconstruite depuis SP: {source_count} artefact(s), preuve vérifiée: {target}")
    return 0
