"""Point d'entrée ``uv run api`` de l'API orchestratrice."""

from __future__ import annotations

import argparse
import os
import sys

from app.platform.configuration import ApplicationConfigurationError, load_application_configuration
from app.platform.orchestrator_asgi import serve_orchestrator_app
from app.platform.orchestrator_runtime import build_orchestrator_composition_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Serveur Uvicorn de orchestrator-api.")
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    try:
        configuration = load_application_configuration(
            config_path=arguments.config,
            environment_snapshot=dict(os.environ),
        )
    except ApplicationConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    serve_orchestrator_app(
        configuration=configuration,
        composition_root_factory=build_orchestrator_composition_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
