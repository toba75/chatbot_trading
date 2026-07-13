"""Provisionnement explicite et scellement des actifs Granite-Docling."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.source_processing.adapters.docling_granite_conversion import (
    GRANITE_DOCLING_MODEL_REPOSITORY,
    GRANITE_DOCLING_MODEL_REVISION,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Précharge et scelle les actifs Granite-Docling hors ligne."
    )
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--replace-manifest", action="store_true")
    arguments = parser.parse_args()
    assets_root = Path(arguments.assets_root).resolve()
    manifest_path = Path(arguments.manifest_path).resolve()
    if manifest_path.exists() and not arguments.replace_manifest:
        raise RuntimeError("GRANITE_DOCLING_ASSET_MANIFEST_ALREADY_EXISTS")
    from huggingface_hub import snapshot_download

    model_directory = assets_root / "ibm-granite--granite-docling-258M"
    snapshot_download(
        repo_id=GRANITE_DOCLING_MODEL_REPOSITORY,
        revision=GRANITE_DOCLING_MODEL_REVISION,
        local_dir=model_directory,
        local_dir_use_symlinks=False,
    )
    assets = [
        {
            "relative_path": path.relative_to(assets_root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(assets_root.rglob("*"))
        if path.is_file() and ".cache" not in path.parts
    ]
    if len(assets) == 0:
        raise RuntimeError("CONVERSION_ASSET_MANIFEST_INVALID")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "granite_docling",
                "tool_version": "2.111.0",
                "model_repository": GRANITE_DOCLING_MODEL_REPOSITORY,
                "model_revision": GRANITE_DOCLING_MODEL_REVISION,
                "assets": assets,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(manifest_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
