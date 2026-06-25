from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from app.platform.local_compose import load_local_compose, validate_local_compose  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valide le Compose local M-002.")
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
        compose_path = Path(args.path).resolve()
        require_path_under_repository(compose_path, "compose local")
        compose = load_local_compose(compose_path)
        validate_local_compose(compose)
    except (OSError, ValueError) as exc:
        print(f"Compose local M-002 invalide: {exc}", file=sys.stderr)
        return 1

    print(
        "Compose local M-002 valide: "
        f"{len(compose.services)} service(s), "
        f"{len(compose.networks)} réseau(x), "
        f"{len(compose.secrets)} secret(s) contrôlé(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
