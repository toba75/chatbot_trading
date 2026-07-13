"""Provisionnement explicite et scellage des actifs Docling natifs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Précharge et scelle les actifs Docling du chemin NATIVE_STANDARD."
    )
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--replace-manifest", action="store_true")
    arguments = parser.parse_args()
    assets_root = Path(arguments.assets_root).resolve()
    manifest_path = Path(arguments.manifest_path).resolve()
    if manifest_path.exists() and not arguments.replace_manifest:
        raise RuntimeError("DOCLING_ASSET_MANIFEST_ALREADY_EXISTS")

    from docling.utils.model_downloader import download_models

    download_models(
        output_dir=assets_root,
        force=False,
        progress=True,
        with_layout=True,
        with_tableformer=False,
        with_tableformer_v2=False,
        with_code_formula=False,
        with_picture_classifier=False,
        with_smolvlm=False,
        with_granitedocling=False,
        with_granitedocling_mlx=False,
        with_granitedocling_2stage=False,
        with_smoldocling=False,
        with_smoldocling_mlx=False,
        with_granite_vision=False,
        with_granite_chart_extraction=False,
        with_granite_chart_extraction_v4=False,
        with_rapidocr=False,
        with_easyocr=False,
        with_nemotron_ocr=False,
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
                "tool": "docling",
                "tool_version": "2.111.0",
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
