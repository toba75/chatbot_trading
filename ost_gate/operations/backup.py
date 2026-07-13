"""Commande `uv run backup-v1`."""

from __future__ import annotations

import argparse
from pathlib import Path

from ost_gate.operations.backup_manifest import read_backup_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backup-v1")
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args(argv)
    manifest = read_backup_manifest(arguments.manifest, "backup")
    print(f"Manifeste de sauvegarde V1 vérifié: {manifest.path} ({len(manifest.entries)} entrée(s) restaurable(s))")
    return 0
