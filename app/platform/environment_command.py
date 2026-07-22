"""Commandes UV dédiées aux trois environnements d'exécution."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol

from app.platform.environment_compose import (
    start_environment_compose_stack,
    wait_environment_compose_stack,
)
from app.platform.local_runtime import HTTP_SERVICE_PORTS
from app.platform.production_e2e import (
    ProductionE2EError,
    run_production_environment_e2e,
)
from app.platform.test_e2e import TestE2EError, run_test_environment_e2e


ApplicationEnvironment = Literal["development", "test", "production"]
EnvironmentLifecycleState = Literal["starting", "ready", "failed", "stopped"]

_ENVIRONMENT_CONFIG_PATHS: Final = MappingProxyType(
    {
        "development": Path("config/environments/development.yaml"),
        "test": Path("config/environments/test.yaml"),
        "production": Path("config/environments/production.yaml"),
    }
)
_ARGUMENTS_FORBIDDEN = "UV_ENVIRONMENT_ARGUMENTS_FORBIDDEN"
_ENVIRONMENT_UNKNOWN = "CONFIG_ENVIRONMENT_UNKNOWN"


@dataclass(frozen=True, slots=True)
class EnvironmentLaunchConfiguration:
    """Identité explicite transmise à la pile locale supervisée."""

    environment: ApplicationEnvironment
    service_id: str
    port: int
    config_path: str

    def __post_init__(self) -> None:
        configuration_relative_path_for_environment(self.environment)
        if self.service_id != "ui":
            raise ValueError("ENVIRONMENT_LAUNCH_SERVICE_INVALID")
        if self.port != HTTP_SERVICE_PORTS["ui"]:
            raise ValueError("ENVIRONMENT_LAUNCH_PORT_INVALID")
        if not isinstance(self.config_path, str) or self.config_path.strip() == "":
            raise ValueError("ENVIRONMENT_LAUNCH_CONFIG_PATH_INVALID")


@dataclass(frozen=True, slots=True)
class EnvironmentLifecycleEvent:
    """État observable du cycle de vie de la pile sélectionnée."""

    environment: ApplicationEnvironment
    state: EnvironmentLifecycleState
    config_path: str
    error_code: str | None

    def __post_init__(self) -> None:
        configuration_relative_path_for_environment(self.environment)
        if self.state not in {"starting", "ready", "failed", "stopped"}:
            raise ValueError("ENVIRONMENT_LIFECYCLE_STATE_INVALID")
        if not isinstance(self.config_path, str) or self.config_path.strip() == "":
            raise ValueError("ENVIRONMENT_LIFECYCLE_CONFIG_PATH_INVALID")
        if self.state == "failed":
            if not isinstance(self.error_code, str) or self.error_code.strip() == "":
                raise ValueError("ENVIRONMENT_LIFECYCLE_ERROR_REQUIRED")
        elif self.error_code is not None:
            raise ValueError("ENVIRONMENT_LIFECYCLE_ERROR_FORBIDDEN")

    def to_mapping(self) -> dict[str, str | None]:
        return {
            "event_type": "environment_lifecycle",
            "environment": self.environment,
            "state": self.state,
            "config_path": self.config_path,
            "error_code": self.error_code,
        }


class ServeHttp(Protocol):
    def __call__(self, *, service_id: str, port: int, config_path: str) -> None:
        pass


LocalStack = Callable[
    [EnvironmentLaunchConfiguration],
    AbstractContextManager[EnvironmentLaunchConfiguration],
]
PublishState = Callable[[EnvironmentLifecycleEvent], None]


def configuration_relative_path_for_environment(environment: str) -> Path:
    """Retourne l'unique fichier associé au profil fermé."""

    if not isinstance(environment, str) or environment not in _ENVIRONMENT_CONFIG_PATHS:
        raise ValueError(f"{_ENVIRONMENT_UNKNOWN}: profil inconnu: {environment!r}")
    return _ENVIRONMENT_CONFIG_PATHS[environment]


def run_environment_command(
    *,
    environment: ApplicationEnvironment,
    argv: Sequence[str],
    repository_root: Path,
    serve_http: ServeHttp,
    local_stack: LocalStack,
    publish_state: PublishState,
) -> int:
    """Lance et supervise la pile correspondant à une commande dédiée."""

    relative_config_path = configuration_relative_path_for_environment(environment)
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise ValueError(f"{_ARGUMENTS_FORBIDDEN}: arguments invalides")
    parsed_argv = tuple(argv)
    if len(parsed_argv) != 0:
        raise ValueError(
            f"{_ARGUMENTS_FORBIDDEN}: uv run {environment} ne prend aucun argument"
        )
    root = _require_repository_root(repository_root)
    config_path = (root / relative_config_path).resolve()
    if not config_path.is_file():
        raise ValueError(
            f"CONFIG_FILE_UNREADABLE: configuration {environment} absente: {config_path}"
        )
    launch_configuration = EnvironmentLaunchConfiguration(
        environment=environment,
        service_id="ui",
        port=HTTP_SERVICE_PORTS["ui"],
        config_path=str(config_path),
    )
    active_configuration = launch_configuration
    publish_state(_lifecycle_event(active_configuration, state="starting"))
    try:
        with local_stack(launch_configuration) as runtime_configuration:
            active_configuration = _require_runtime_configuration(
                runtime_configuration,
                expected_environment=environment,
            )
            publish_state(_lifecycle_event(active_configuration, state="ready"))
            serve_http(
                service_id=active_configuration.service_id,
                port=active_configuration.port,
                config_path=active_configuration.config_path,
            )
    except ValueError as exc:
        publish_state(
            _lifecycle_event(
                active_configuration,
                state="failed",
                error_code=_error_code(exc),
            )
        )
        raise
    except KeyboardInterrupt:
        publish_state(_lifecycle_event(active_configuration, state="stopped"))
        return 0
    publish_state(_lifecycle_event(active_configuration, state="stopped"))
    return 0


def development() -> int:
    return _run_entrypoint("development")


def test() -> int:
    try:
        return _run_test_qualification(
            argv=tuple(sys.argv[1:]),
            repository_root=Path.cwd(),
            pdf_path=(
                Path.cwd()
                / "data"
                / "corpus"
                / "the-original-turtle-trading-rules.pdf"
            ),
            runner=run_test_environment_e2e,
            publish_report=_publish_test_report,
        )
    except TestE2EError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def production() -> int:
    try:
        return _run_production_qualification(
            argv=tuple(sys.argv[1:]),
            repository_root=Path.cwd(),
            pdf_path=(
                Path.cwd()
                / "data"
                / "corpus"
                / "the-original-turtle-trading-rules.pdf"
            ),
            runner=run_production_environment_e2e,
            publish_report=_publish_production_report,
        )
    except ProductionE2EError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _run_test_qualification(
    *,
    argv: Sequence[str],
    repository_root: Path,
    pdf_path: Path,
    runner: Callable[..., Any],
    publish_report: Callable[[Any], None],
) -> int:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise ValueError(f"{_ARGUMENTS_FORBIDDEN}: arguments invalides")
    if tuple(argv) != ():
        raise ValueError(
            f"{_ARGUMENTS_FORBIDDEN}: uv run test ne prend aucun argument"
        )
    if not callable(runner) or not callable(publish_report):
        raise ValueError("TEST_E2E_RUNNER_INVALID")
    report = runner(repository_root=repository_root, pdf_path=pdf_path)
    publish_report(report)
    return 0


def _publish_test_report(report: Any) -> None:
    to_mapping = getattr(report, "to_mapping", None)
    if not callable(to_mapping):
        raise ValueError("TEST_E2E_REPORT_INVALID")
    payload = to_mapping()
    if not isinstance(payload, Mapping):
        raise ValueError("TEST_E2E_REPORT_INVALID")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _run_production_qualification(
    *,
    argv: Sequence[str],
    repository_root: Path,
    pdf_path: Path,
    runner: Callable[..., Any],
    publish_report: Callable[[Any], None],
) -> int:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise ValueError(f"{_ARGUMENTS_FORBIDDEN}: arguments invalides")
    if tuple(argv) != ():
        raise ValueError(
            f"{_ARGUMENTS_FORBIDDEN}: uv run production ne prend aucun argument"
        )
    if not callable(runner) or not callable(publish_report):
        raise ValueError("PRODUCTION_E2E_RUNNER_INVALID")
    report = runner(repository_root=repository_root, pdf_path=pdf_path)
    publish_report(report)
    return 0


def _publish_production_report(report: Any) -> None:
    to_mapping = getattr(report, "to_mapping", None)
    if not callable(to_mapping):
        raise ValueError("PRODUCTION_E2E_REPORT_INVALID")
    payload = to_mapping()
    if not isinstance(payload, Mapping):
        raise ValueError("PRODUCTION_E2E_REPORT_INVALID")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _run_entrypoint(environment: ApplicationEnvironment) -> int:
    try:
        return run_environment_command(
            environment=environment,
            argv=tuple(sys.argv[1:]),
            repository_root=Path.cwd(),
            serve_http=wait_environment_compose_stack,
            local_stack=start_environment_compose_stack,
            publish_state=_publish_state,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("UV_ENVIRONMENT_REPOSITORY_ROOT_INVALID")
    root = value.resolve()
    if not root.is_dir():
        raise ValueError(f"UV_ENVIRONMENT_REPOSITORY_ROOT_INVALID: dépôt absent: {root}")
    return root


def _require_runtime_configuration(
    value: Any,
    *,
    expected_environment: ApplicationEnvironment,
) -> EnvironmentLaunchConfiguration:
    if not isinstance(value, EnvironmentLaunchConfiguration):
        raise ValueError("ENVIRONMENT_RUNTIME_CONFIGURATION_INVALID")
    if value.environment != expected_environment:
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: profil runtime divergent")
    if value.service_id != "ui" or value.port != HTTP_SERVICE_PORTS["ui"]:
        raise ValueError("ENVIRONMENT_RUNTIME_CONFIGURATION_INVALID")
    if not Path(value.config_path).is_file():
        raise ValueError(
            f"CONFIG_FILE_UNREADABLE: configuration runtime absente: {value.config_path}"
        )
    return value


def _lifecycle_event(
    configuration: EnvironmentLaunchConfiguration,
    *,
    state: EnvironmentLifecycleState,
    error_code: str | None = None,
) -> EnvironmentLifecycleEvent:
    return EnvironmentLifecycleEvent(
        environment=configuration.environment,
        state=state,
        config_path=configuration.config_path,
        error_code=error_code,
    )


def _error_code(error: ValueError) -> str:
    message = str(error)
    code = message.split(":", 1)[0]
    if code.strip() == "":
        raise ValueError("ENVIRONMENT_TERMINAL_ERROR_CODE_INVALID")
    return code


def _publish_state(event: EnvironmentLifecycleEvent) -> None:
    if not isinstance(event, EnvironmentLifecycleEvent):
        raise ValueError("ENVIRONMENT_LIFECYCLE_EVENT_INVALID")
    print(json.dumps(event.to_mapping(), ensure_ascii=False, sort_keys=True), flush=True)


__all__ = [
    "ApplicationEnvironment",
    "EnvironmentLaunchConfiguration",
    "EnvironmentLifecycleEvent",
    "configuration_relative_path_for_environment",
    "development",
    "production",
    "run_environment_command",
    "test",
]
