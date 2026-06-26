from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from app.platform.topology import load_platform_topology  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valide le registre de topologie M-002.")
    parser.add_argument("--path", required=True)
    return parser.parse_args()


def require_path_under_repository(path: Path, label: str) -> None:
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError(f"Chemin hors dépôt interdit ({label}): {path}") from exc


def main() -> int:
    try:
        args = parse_args()
        topology_path = Path(args.path).resolve()
        require_path_under_repository(topology_path, "topologie")
        topology = load_platform_topology(topology_path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Topologie M-002 invalide: {exc}", file=sys.stderr)
        return 1

    print(
        "Topologie M-002 valide: "
        f"{len(topology.hosts)} hôte(s), {len(topology.services)} service(s) contrôlé(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
