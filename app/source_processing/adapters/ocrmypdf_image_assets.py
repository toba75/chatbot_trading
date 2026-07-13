"""Provisionnement explicite de l'image OCRmyPDF référencée par digest."""

from __future__ import annotations

import subprocess

from app.source_processing.adapters.ocrmypdf_container import OcrmyPdfImageManifest


def main() -> int:
    from pathlib import Path

    manifest_path = Path("config/ocrmypdf-image.json")
    manifest = OcrmyPdfImageManifest.load(
        manifest_path=manifest_path,
        require_local_image=False,
    )
    result = subprocess.run(("docker", "pull", manifest.image_reference), check=False)
    if result.returncode != 0:
        raise RuntimeError("OCRMYPDF_UNAVAILABLE")
    OcrmyPdfImageManifest.load(
        manifest_path=manifest_path,
        require_local_image=True,
    )
    print(manifest.image_reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
