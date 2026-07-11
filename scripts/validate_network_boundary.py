from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from app.platform.configuration import load_application_configuration  # noqa: E402
from app.platform.local_compose import load_local_compose  # noqa: E402
from app.platform.security.network_boundary import (  # noqa: E402
    load_spark_firewall_policy,
    validate_network_boundary,
)
from app.platform.topology import load_platform_topology  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valide la frontière réseau locale M-002.")
    parser.add_argument("--compose-path", required=True)
    parser.add_argument("--topology-path", required=True)
    parser.add_argument("--spark-firewall-path", required=True)
    parser.add_argument("--application-config-path", required=True)
    return parser.parse_args()


def require_path_under_repository(path: Path, label: str) -> None:
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError(f"Chemin hors dépôt interdit ({label}): {path}") from exc


def main() -> int:
    try:
        args = parse_args()
        compose_path = Path(args.compose_path).resolve()
        topology_path = Path(args.topology_path).resolve()
        spark_firewall_path = Path(args.spark_firewall_path).resolve()
        application_config_path = Path(args.application_config_path).resolve()

        require_path_under_repository(compose_path, "compose local")
        require_path_under_repository(topology_path, "topologie M-002")
        require_path_under_repository(spark_firewall_path, "pare-feu Spark")
        require_path_under_repository(application_config_path, "configuration applicative")

        compose = load_local_compose(compose_path)
        topology = load_platform_topology(topology_path)
        spark_firewall = load_spark_firewall_policy(spark_firewall_path)
        application_configuration = load_application_configuration(
            config_path=application_config_path,
            environment_snapshot={},
        )
        validate_network_boundary(
            compose=compose,
            topology=topology,
            spark_firewall=spark_firewall,
            application_configuration=application_configuration,
        )
    except (OSError, ValueError) as exc:
        print(f"Frontière réseau M-002 invalide: {exc}", file=sys.stderr)
        return 1

    print(
        "Frontière réseau M-002 valide: "
        f"{len(compose.services)} service(s) Compose, "
        f"{len(spark_firewall.allowed_ingress)} règle(s) Spark, "
        "transport Spark et egress contrôlés."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
