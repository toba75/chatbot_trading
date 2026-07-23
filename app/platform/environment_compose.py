"""Orchestration Compose stricte des trois piles d'environnement."""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from types import MappingProxyType
from typing import Any, Final, Literal
from urllib.request import urlopen
from uuid import UUID, uuid4

from cryptography import x509

from app.platform.administrative_operations import (
    AdministrativeOperationEvidence,
    AdministrativeOperationRequest,
    execute_administrative_operation,
)
from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.configured_datastore_identity import (
    APPLICATION_FILE_ROOT_NAMES,
    build_configured_datastore_preflight,
    configured_datastore_identity,
)
from app.platform.datastore_identity import DatastoreIdentity
from app.platform.worker_environment import (
    build_worker_environment_binding,
    read_worker_health_file,
)


ApplicationEnvironment = Literal["development", "test", "production"]
ENVIRONMENTS: Final = ("development", "test", "production")
REQUIRED_SERVICE_IDS: Final = (
    "edge-gateway",
    "ui",
    "orchestrator-api",
    "llm-gateway",
    "postgres",
    "qdrant",
    "granite-docling",
    "embedding-service",
    "reranker-service",
    "ocr-runtime",
    "worker-documents",
    "worker-projection",
)
EXPECTED_SERVICE_REPLICAS: Final = MappingProxyType(
    {
        service_id: (
            2 if service_id in {"worker-documents", "worker-projection"} else 1
        )
        for service_id in REQUIRED_SERVICE_IDS
    }
)
APPLICATION_SERVICE_IDS: Final = tuple(
    service_id
    for service_id in REQUIRED_SERVICE_IDS
    if service_id not in {"edge-gateway", "postgres", "qdrant", "ocr-runtime"}
)
_TECHNICAL_ENVIRONMENT_KEYS: Final = frozenset(
    {"OSTRADING_IMAGE_REVISION", "OSTRADING_POSTGRES_SCHEMA_VERSION"}
)
_SECRET_FILE_NAMES: Final = (
    "postgres_password",
    "qdrant_api_key",
    "llm_gateway_api_key",
    "tls_ca_certificate.pem",
    "local_api_token",
)
_EXPECTED_SERVICE_SECRETS: Final = MappingProxyType(
    {
        "edge-gateway": frozenset(),
        "ui": frozenset(("local_api_token",)),
        "orchestrator-api": frozenset(
            ("postgres_password", "qdrant_api_key", "local_api_token")
        ),
        "llm-gateway": frozenset(),
        "postgres": frozenset(("postgres_password",)),
        "qdrant": frozenset(("qdrant_api_key",)),
        "granite-docling": frozenset(),
        "embedding-service": frozenset(),
        "reranker-service": frozenset(),
        "ocr-runtime": frozenset(),
        "worker-documents": frozenset(("postgres_password",)),
        "worker-projection": frozenset(("postgres_password", "qdrant_api_key")),
    }
)
_STACK_COORDINATES: Final = MappingProxyType(
    {
        "development": (18443, 8080, 8090),
        "test": (19443, 8081, 8091),
        "production": (20443, 8082, 8092),
    }
)
_CONFIG_CONTAINER_PATH = "/workspace/config/application.yaml"
_SCHEMA_CONTAINER_PATH = "/workspace/config/application.schema.json"
_SPARK_ENDPOINT = "http://192.168.1.120:8000/v1"


@dataclass(frozen=True, slots=True)
class EnvironmentStackDefinition:
    environment: ApplicationEnvironment
    repository_root: Path
    project_name: str
    base_compose_path: Path
    compose_path: Path
    configuration_path: Path
    caddyfile_path: Path
    secrets_path: Path
    edge_port: int
    api_port: int
    llm_gateway_port: int

    def __post_init__(self) -> None:
        _require_environment(self.environment)
        if (
            not isinstance(self.repository_root, Path)
            or not self.repository_root.is_absolute()
        ):
            raise ValueError("ENVIRONMENT_STACK_REPOSITORY_ROOT_INVALID")
        if self.project_name != f"ostrading-{self.environment}":
            raise ValueError("ENVIRONMENT_STACK_PROJECT_MISMATCH")
        for path in (
            self.base_compose_path,
            self.compose_path,
            self.configuration_path,
            self.caddyfile_path,
            self.secrets_path,
        ):
            if not isinstance(path, Path) or not path.is_absolute():
                raise ValueError("ENVIRONMENT_STACK_PATH_INVALID")
            _require_path_under(path, root=self.repository_root)
        for port in (self.edge_port, self.api_port, self.llm_gateway_port):
            if (
                isinstance(port, bool)
                or not isinstance(port, int)
                or not 1 <= port <= 65_535
            ):
                raise ValueError("ENVIRONMENT_STACK_PORT_INVALID")


@dataclass(frozen=True, slots=True)
class EnvironmentContainerState:
    service: str
    container_name: str
    state: str
    health: str

    def __post_init__(self) -> None:
        for value in (self.service, self.container_name, self.state, self.health):
            if (
                not isinstance(value, str)
                or value.strip() == ""
                or value != value.strip()
            ):
                raise ValueError("ENVIRONMENT_CONTAINER_STATE_INVALID")


@dataclass(frozen=True, slots=True)
class EnvironmentStackReadiness:
    environment: ApplicationEnvironment
    project_name: str
    is_ready: bool
    ready_services: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_environment(self.environment)
        if self.project_name != f"ostrading-{self.environment}":
            raise ValueError("ENVIRONMENT_STACK_PROJECT_MISMATCH")
        if self.is_ready is not True:
            raise ValueError("ENVIRONMENT_STACK_NOT_READY")
        if self.ready_services != REQUIRED_SERVICE_IDS:
            raise ValueError("ENVIRONMENT_STACK_READINESS_INCOMPLETE")


def environment_stack_definition(
    environment: str,
    *,
    repository_root: Path,
) -> EnvironmentStackDefinition:
    """Résout sans fallback les artefacts et ports du profil demandé."""

    selected = _require_environment(environment)
    root = _require_repository_root(repository_root)
    edge_port, api_port, llm_gateway_port = _STACK_COORDINATES[selected]
    deploy_root = root / "deploy" / "environments"
    return EnvironmentStackDefinition(
        environment=selected,
        repository_root=root,
        project_name=f"ostrading-{selected}",
        base_compose_path=(deploy_root / "compose.base.yaml").resolve(),
        compose_path=(deploy_root / f"{selected}.compose.yaml").resolve(),
        configuration_path=(
            root / "config" / "environments" / f"{selected}.yaml"
        ).resolve(),
        caddyfile_path=(deploy_root / f"Caddyfile.{selected}").resolve(),
        secrets_path=(root / "config" / "secrets" / selected).resolve(),
        edge_port=edge_port,
        api_port=api_port,
        llm_gateway_port=llm_gateway_port,
    )


def render_environment_compose(
    definition: EnvironmentStackDefinition,
    *,
    technical_environment: Mapping[str, str],
) -> Mapping[str, Any]:
    """Retourne le JSON réellement rendu par Docker Compose."""

    _require_definition_files(definition, require_secrets=False)
    result = _run_compose(
        definition,
        ("config", "--format", "json"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ENVIRONMENT_COMPOSE_RENDER_INVALID") from exc
    if not isinstance(document, Mapping):
        raise ValueError("ENVIRONMENT_COMPOSE_RENDER_INVALID")
    return document


def validate_environment_compose_matrix(
    rendered: Mapping[str, Mapping[str, Any]],
    *,
    definitions: Mapping[str, EnvironmentStackDefinition],
) -> Mapping[str, Mapping[str, Any]]:
    """Valide l'étanchéité structurelle des trois rendus effectifs."""

    if tuple(rendered) != ENVIRONMENTS or tuple(definitions) != ENVIRONMENTS:
        raise ValueError("ENVIRONMENT_COMPOSE_THREE_PROFILES_REQUIRED")
    resource_owners: dict[str, str] = {}
    edge_ports: dict[int, str] = {}
    validated: dict[str, Mapping[str, Any]] = {}
    for environment in ENVIRONMENTS:
        definition = definitions[environment]
        if definition.environment != environment:
            raise ValueError("ENVIRONMENT_STACK_DEFINITION_MISMATCH")
        document = rendered[environment]
        _validate_environment_compose_document(document, definition=definition)
        for resource_kind in ("volumes", "networks"):
            resources = _required_mapping(document, resource_kind)
            for payload in resources.values():
                resource = _required_mapping_value(payload, "ressource Compose")
                name = _required_text(resource, "name", "ressource Compose")
                if environment not in name:
                    raise ValueError("ENVIRONMENT_COMPOSE_RESOURCE_PROFILE_MISMATCH")
                previous = resource_owners.get(name)
                if previous is not None:
                    raise ValueError(
                        f"ENVIRONMENT_COMPOSE_MUTABLE_RESOURCE_SHARED: {previous}/{environment}: {name}"
                    )
                resource_owners[name] = environment
        previous_port_owner = edge_ports.get(definition.edge_port)
        if previous_port_owner is not None:
            raise ValueError("ENVIRONMENT_COMPOSE_HOST_PORT_COLLISION")
        edge_ports[definition.edge_port] = environment
        validated[environment] = document
    return MappingProxyType(validated)


def aggregate_environment_readiness(
    definition: EnvironmentStackDefinition,
    *,
    container_states: Sequence[EnvironmentContainerState],
) -> EnvironmentStackReadiness:
    """Exige tous les services et toutes leurs réplicas running/healthy."""

    if not isinstance(container_states, Sequence) or isinstance(
        container_states, (str, bytes)
    ):
        raise ValueError("ENVIRONMENT_STACK_STATES_INVALID")
    by_service: dict[str, list[EnvironmentContainerState]] = {}
    prefix = f"{definition.project_name}-"
    for container_state in container_states:
        if not isinstance(container_state, EnvironmentContainerState):
            raise ValueError("ENVIRONMENT_CONTAINER_STATE_INVALID")
        if not container_state.container_name.startswith(prefix):
            raise ValueError("ENVIRONMENT_STACK_CONTAINER_MISMATCH")
        if container_state.service not in REQUIRED_SERVICE_IDS:
            raise ValueError(
                f"ENVIRONMENT_STACK_SERVICE_UNEXPECTED: {container_state.service}"
            )
        by_service.setdefault(container_state.service, []).append(container_state)
    missing = tuple(
        service_id
        for service_id in REQUIRED_SERVICE_IDS
        if service_id not in by_service
    )
    if missing:
        raise ValueError(f"ENVIRONMENT_STACK_SERVICE_MISSING: {','.join(missing)}")
    for service_id in REQUIRED_SERVICE_IDS:
        expected_replicas = EXPECTED_SERVICE_REPLICAS[service_id]
        if len(by_service[service_id]) != expected_replicas:
            raise ValueError(
                "ENVIRONMENT_STACK_REPLICA_COUNT_INVALID: "
                f"{service_id}: expected={expected_replicas}, observed={len(by_service[service_id])}"
            )
        for state in by_service[service_id]:
            if state.state != "running" or state.health != "healthy":
                raise ValueError(
                    "ENVIRONMENT_STACK_NOT_READY: "
                    f"{service_id}: state={state.state}, health={state.health}"
                )
    return EnvironmentStackReadiness(
        environment=definition.environment,
        project_name=definition.project_name,
        is_ready=True,
        ready_services=REQUIRED_SERVICE_IDS,
    )


def inspect_environment_readiness(
    definition: EnvironmentStackDefinition,
    *,
    technical_environment: Mapping[str, str],
) -> EnvironmentStackReadiness:
    result = _run_compose(
        definition,
        ("ps", "--all", "--format", "json"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    states = _parse_compose_ps(result.stdout)
    return aggregate_environment_readiness(definition, container_states=states)


@contextmanager
def start_environment_compose_stack(launch_configuration: Any) -> Iterator[Any]:
    """Démarre la pile complète et ne la publie qu'après readiness agrégée."""

    environment = getattr(launch_configuration, "environment", None)
    config_path_text = getattr(launch_configuration, "config_path", None)
    if not isinstance(environment, str) or not isinstance(config_path_text, str):
        raise ValueError("ENVIRONMENT_LAUNCH_CONFIGURATION_INVALID")
    configuration_path = Path(config_path_text).resolve()
    repository_root = _repository_root_from_configuration(configuration_path)
    definition = environment_stack_definition(
        environment,
        repository_root=repository_root,
    )
    if configuration_path != definition.configuration_path:
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: fichier de pile divergent")
    configuration = load_application_configuration(
        config_path=configuration_path,
        environment_snapshot=dict(os.environ),
    )
    _require_launch_profile_identity(
        environment=environment,
        configuration_path=configuration_path,
        definition=definition,
        configuration=configuration,
    )
    _provision_environment_secrets(definition)
    technical_environment = _technical_environment_from_repository(repository_root)
    document = render_environment_compose(
        definition,
        technical_environment=technical_environment,
    )
    _validate_environment_compose_document(document, definition=definition)
    started = False
    lifecycle_owner_recorded = False
    lifecycle_id = str(uuid4())
    try:
        started = True
        _run_compose(
            definition,
            ("up", "--build", "--detach", "--wait", "--wait-timeout", "600"),
            technical_environment=technical_environment,
            capture_output=False,
        )
        inspect_environment_readiness(
            definition,
            technical_environment=technical_environment,
        )
        if definition.environment == "test":
            _record_test_lifecycle_owner(
                definition=definition,
                technical_environment=technical_environment,
                lifecycle_id=lifecycle_id,
            )
            lifecycle_owner_recorded = True
        yield launch_configuration
    finally:
        if started:
            if definition.environment == "test" and lifecycle_owner_recorded:
                _finalize_test_environment_stack(
                    definition=definition,
                    configuration=configuration,
                    technical_environment=technical_environment,
                    lifecycle_id=lifecycle_id,
                )
            else:
                _stop_environment_stack(
                    definition=definition,
                    technical_environment=technical_environment,
                )


def _finalize_test_environment_stack(
    *,
    definition: EnvironmentStackDefinition,
    configuration: ApplicationConfiguration,
    technical_environment: Mapping[str, str],
    lifecycle_id: str,
) -> None:
    cleanup_completed = False
    try:
        _cleanup_test_environment_stack(
            definition=definition,
            configuration=configuration,
            technical_environment=technical_environment,
            lifecycle_id=lifecycle_id,
        )
        cleanup_completed = True
    finally:
        if not cleanup_completed:
            _stop_environment_stack(
                definition=definition,
                technical_environment=technical_environment,
            )


def _cleanup_test_environment_stack(
    *,
    definition: EnvironmentStackDefinition,
    configuration: ApplicationConfiguration,
    technical_environment: Mapping[str, str],
    lifecycle_id: str,
) -> None:
    """Supprime uniquement les ressources test après préflight d'identité."""

    if definition.environment != "test":
        raise ValueError("ADMINISTRATIVE_OPERATION_FORBIDDEN")
    expected_identity = configured_datastore_identity(configuration)
    persistent_owner_id = _observed_test_lifecycle_owner(
        definition=definition,
        technical_environment=technical_environment,
    )
    execute_administrative_operation(
        request=AdministrativeOperationRequest(
            operation="test_cleanup",
            target_identity=expected_identity,
            automatic=True,
            lifecycle_id=lifecycle_id,
            lifecycle_owner_id=persistent_owner_id,
            backup_manifest=None,
        ),
        observe_identity=lambda: _observed_stack_identity(
            definition=definition,
            technical_environment=technical_environment,
        ),
        mutate=lambda: _run_compose(
            definition,
            ("down", "--volumes", "--remove-orphans"),
            technical_environment=technical_environment,
            capture_output=False,
        ),
        record_audit=_publish_administrative_evidence,
    )


def _stop_environment_stack(
    *,
    definition: EnvironmentStackDefinition,
    technical_environment: Mapping[str, str],
) -> None:
    _run_compose(
        definition,
        ("down", "--remove-orphans"),
        technical_environment=technical_environment,
        capture_output=False,
    )


def _record_test_lifecycle_owner(
    *,
    definition: EnvironmentStackDefinition,
    technical_environment: Mapping[str, str],
    lifecycle_id: str,
) -> None:
    _run_compose(
        definition,
        (
            "exec",
            "--no-TTY",
            "orchestrator-api",
            "python",
            "-m",
            "app.platform.environment_compose",
            "record-test-lifecycle-owner",
            "--config",
            _CONFIG_CONTAINER_PATH,
            "--lifecycle-id",
            lifecycle_id,
        ),
        technical_environment=technical_environment,
        capture_output=True,
    )


def _observed_test_lifecycle_owner(
    *,
    definition: EnvironmentStackDefinition,
    technical_environment: Mapping[str, str],
) -> str:
    result = _run_compose(
        definition,
        (
            "exec",
            "--no-TTY",
            "orchestrator-api",
            "python",
            "-m",
            "app.platform.environment_compose",
            "read-test-lifecycle-owner",
            "--config",
            _CONFIG_CONTAINER_PATH,
        ),
        technical_environment=technical_environment,
        capture_output=True,
    )
    owner_id = result.stdout.strip()
    try:
        parsed = UUID(owner_id)
    except ValueError as exc:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID") from exc
    if parsed.version != 4:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID")
    return owner_id


def _observed_stack_identity(
    *,
    definition: EnvironmentStackDefinition,
    technical_environment: Mapping[str, str],
) -> DatastoreIdentity:
    result = _run_compose(
        definition,
        (
            "exec",
            "--no-TTY",
            "orchestrator-api",
            "python",
            "-m",
            "app.platform.environment_compose",
            "check-administrative-identity",
            "--config",
            _CONFIG_CONTAINER_PATH,
        ),
        technical_environment=technical_environment,
        capture_output=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ADMINISTRATIVE_IDENTITY_OUTPUT_INVALID") from exc
    return DatastoreIdentity.from_mapping(payload)


def _publish_administrative_evidence(evidence: AdministrativeOperationEvidence) -> None:
    print(
        json.dumps(evidence.to_mapping(), ensure_ascii=False, sort_keys=True),
        flush=True,
    )


def wait_environment_compose_stack(
    *, service_id: str, port: int, config_path: str
) -> None:
    """Bloque la commande UV tant que la pile sélectionnée reste en exécution."""

    if service_id != "ui" or port != 8081:
        raise ValueError("ENVIRONMENT_STACK_WAIT_TARGET_INVALID")
    path = Path(config_path).resolve()
    repository_root = _repository_root_from_configuration(path)
    configuration = load_application_configuration(
        config_path=path,
        environment_snapshot=dict(os.environ),
    )
    definition = environment_stack_definition(
        configuration.application.environment,
        repository_root=repository_root,
    )
    if definition.configuration_path != path:
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: attente de pile divergente")
    technical_environment = _technical_environment_from_repository(repository_root)
    _wait_for_first_environment_service_exit(
        definition,
        technical_environment=technical_environment,
    )


def _wait_for_first_environment_service_exit(
    definition: EnvironmentStackDefinition,
    *,
    technical_environment: Mapping[str, str],
) -> None:
    while True:
        result = _run_compose(
            definition,
            ("ps", "--all", "--format", "json"),
            technical_environment=technical_environment,
            capture_output=True,
        )
        if _first_environment_service_has_stopped(
            result.stdout,
            project_name=definition.project_name,
        ):
            return
        time.sleep(1)


def _first_environment_service_has_stopped(document: str, *, project_name: str) -> bool:
    if not isinstance(document, str) or document.strip() == "":
        raise ValueError("ENVIRONMENT_COMPOSE_PS_INVALID")
    if not isinstance(project_name, str) or project_name.strip() == "":
        raise ValueError("ENVIRONMENT_COMPOSE_PROJECT_INVALID")
    rows_by_service: dict[str, list[Mapping[str, Any]]] = {
        service_id: [] for service_id in REQUIRED_SERVICE_IDS
    }
    for line in document.splitlines():
        if line.strip() == "":
            continue
        try:
            row = _required_mapping_value(json.loads(line), "supervision conteneur")
        except json.JSONDecodeError as exc:
            raise ValueError("ENVIRONMENT_COMPOSE_PS_INVALID") from exc
        service = _required_text(row, "Service", "supervision conteneur")
        name = _required_text(row, "Name", "supervision conteneur")
        if service not in rows_by_service:
            raise ValueError(f"ENVIRONMENT_STACK_SERVICE_UNEXPECTED: {service}")
        if not name.startswith(f"{project_name}-"):
            raise ValueError(f"ENVIRONMENT_STACK_CONTAINER_MISMATCH: {name}")
        rows_by_service[service].append(row)
    missing = tuple(
        service_id for service_id, rows in rows_by_service.items() if len(rows) == 0
    )
    if missing:
        raise ValueError(f"ENVIRONMENT_STACK_SERVICE_MISSING: {','.join(missing)}")
    for service_id in REQUIRED_SERVICE_IDS:
        for row in rows_by_service[service_id]:
            state = _required_text(row, "State", "supervision conteneur").lower()
            health_value = row.get("Health")
            health = health_value.lower() if isinstance(health_value, str) else ""
            if state == "running" and health == "healthy":
                continue
            exit_code = row.get("ExitCode")
            if state == "exited" and service_id == "edge-gateway" and exit_code == 0:
                return True
            if state == "exited":
                raise ValueError(
                    "ENVIRONMENT_STACK_SERVICE_EXITED: "
                    f"{service_id}: code={exit_code!r}"
                )
            raise ValueError(
                "ENVIRONMENT_STACK_NOT_READY: "
                f"{service_id}: state={state}, health={health}"
            )
    return False


def configured_http_healthcheck(*, service: str, path: str, config_path: Path) -> None:
    configuration = load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )
    if service == "orchestrator-api":
        port = configuration.services.api.port
    elif service == "llm-gateway":
        port = configuration.services.llm_gateway.port
    else:
        raise ValueError("ENVIRONMENT_HEALTHCHECK_SERVICE_UNKNOWN")
    if not isinstance(path, str) or not path.startswith("/") or "//" in path:
        raise ValueError("ENVIRONMENT_HEALTHCHECK_PATH_INVALID")
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=8) as response:
        if response.status != 200:
            raise ValueError("ENVIRONMENT_HEALTHCHECK_HTTP_FAILED")


def configured_worker_healthcheck(
    *,
    worker_id: str,
    config_path: Path,
    health_path: Path,
) -> Mapping[str, object]:
    configuration = load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )
    binding = build_worker_environment_binding(configuration, worker_id=worker_id)
    health = read_worker_health_file(
        path=health_path,
        expected_identity=binding.identity,
        expected_worker_id=worker_id,
        maximum_age_seconds=30.0,
    )
    serialized_health = {
        "service": health["service"],
        "status": health["status"],
        "environment": health["environment"],
        "deployment_id": health["deployment_id"],
        "configuration_hash": health["configuration_hash"],
        "updated_at_epoch": health["updated_at_epoch"],
    }
    print(json.dumps(serialized_health, ensure_ascii=False, sort_keys=True), flush=True)
    return health


def configured_administrative_identity(config_path: Path) -> Mapping[str, str]:
    """Observe les autorités de stockage avant un nettoyage de test."""

    configuration = load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )
    expected = configured_datastore_identity(configuration)
    observed = build_configured_datastore_preflight(
        configuration,
        include_postgres=True,
        include_qdrant=True,
        file_root_names=APPLICATION_FILE_ROOT_NAMES,
    ).run(initialize_if_empty=False)
    if len(observed) != 2 + len(APPLICATION_FILE_ROOT_NAMES) or any(
        identity != expected for identity in observed
    ):
        raise ValueError("ADMINISTRATIVE_PREFLIGHT_INCOMPLETE")
    payload = expected.to_mapping()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
    return payload


def record_test_lifecycle_owner(config_path: Path, lifecycle_id: str) -> str:
    configuration = load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )
    if configuration.application.environment != "test":
        raise ValueError("ADMINISTRATIVE_OPERATION_FORBIDDEN")
    try:
        owner = UUID(lifecycle_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID") from exc
    if owner.version != 4:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID")
    owner_path = Path(configuration.paths.data_root) / ".test-lifecycle-owner"
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    with owner_path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(str(owner))
    print(str(owner), flush=True)
    return str(owner)


def read_test_lifecycle_owner(config_path: Path) -> str:
    configuration = load_application_configuration(
        config_path=config_path,
        environment_snapshot=dict(os.environ),
    )
    if configuration.application.environment != "test":
        raise ValueError("ADMINISTRATIVE_OPERATION_FORBIDDEN")
    owner_path = Path(configuration.paths.data_root) / ".test-lifecycle-owner"
    try:
        owner_text = owner_path.read_text(encoding="ascii").strip()
        owner = UUID(owner_text)
    except (OSError, ValueError) as exc:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID") from exc
    if owner.version != 4:
        raise ValueError("TEST_LIFECYCLE_OWNER_INVALID")
    print(str(owner), flush=True)
    return str(owner)


def export_environment_caddy_ca(
    *,
    environment: str,
    repository_root: Path,
    destination_path: Path,
    technical_environment: Mapping[str, str],
) -> Path:
    """Exporte la CA Caddy du profil sans modifier le magasin de confiance hôte."""

    root = _require_repository_root(repository_root)
    definition = environment_stack_definition(environment, repository_root=root)
    if not isinstance(destination_path, Path):
        raise ValueError("ENVIRONMENT_CADDY_CA_DESTINATION_INVALID")
    destination = destination_path.resolve()
    if not destination.parent.is_dir():
        raise ValueError("ENVIRONMENT_CADDY_CA_DESTINATION_PARENT_MISSING")
    _run_compose(
        definition,
        (
            "cp",
            "edge-gateway:/data/caddy/pki/authorities/local/root.crt",
            str(destination),
        ),
        technical_environment=technical_environment,
        capture_output=True,
    )
    try:
        certificate_bytes = destination.read_bytes()
        x509.load_pem_x509_certificate(certificate_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError("ENVIRONMENT_CADDY_CA_INVALID") from exc
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Healthchecks des piles d'environnement."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    config_parser = subparsers.add_parser("check-config")
    config_parser.add_argument("--config", required=True)
    http_parser = subparsers.add_parser("check-http")
    http_parser.add_argument("--service", required=True)
    http_parser.add_argument("--path", required=True)
    http_parser.add_argument("--config", required=True)
    worker_parser = subparsers.add_parser("check-worker")
    worker_parser.add_argument("--worker-id", required=True)
    worker_parser.add_argument("--config", required=True)
    worker_parser.add_argument("--health-path", required=True, type=Path)
    administrative_parser = subparsers.add_parser("check-administrative-identity")
    administrative_parser.add_argument("--config", required=True)
    owner_record_parser = subparsers.add_parser("record-test-lifecycle-owner")
    owner_record_parser.add_argument("--config", required=True)
    owner_record_parser.add_argument("--lifecycle-id", required=True)
    owner_read_parser = subparsers.add_parser("read-test-lifecycle-owner")
    owner_read_parser.add_argument("--config", required=True)
    export_ca_parser = subparsers.add_parser("export-ca")
    export_ca_parser.add_argument("--environment", required=True, choices=ENVIRONMENTS)
    export_ca_parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == "check-config":
        load_application_configuration(
            config_path=arguments.config,
            environment_snapshot=dict(os.environ),
        )
        return 0
    if arguments.command == "check-worker":
        configured_worker_healthcheck(
            worker_id=arguments.worker_id,
            config_path=Path(arguments.config),
            health_path=arguments.health_path,
        )
        return 0
    if arguments.command == "check-administrative-identity":
        configured_administrative_identity(Path(arguments.config))
        return 0
    if arguments.command == "record-test-lifecycle-owner":
        record_test_lifecycle_owner(Path(arguments.config), arguments.lifecycle_id)
        return 0
    if arguments.command == "read-test-lifecycle-owner":
        read_test_lifecycle_owner(Path(arguments.config))
        return 0
    if arguments.command == "export-ca":
        root = _require_repository_root(Path.cwd())
        export_environment_caddy_ca(
            environment=arguments.environment,
            repository_root=root,
            destination_path=arguments.output,
            technical_environment=_technical_environment_from_repository(root),
        )
        return 0
    configured_http_healthcheck(
        service=arguments.service,
        path=arguments.path,
        config_path=Path(arguments.config),
    )
    return 0


def _validate_environment_compose_document(
    document: Mapping[str, Any],
    *,
    definition: EnvironmentStackDefinition,
) -> None:
    if document.get("name") != definition.project_name:
        raise ValueError("ENVIRONMENT_COMPOSE_PROJECT_MISMATCH")
    services = _required_mapping(document, "services")
    if set(services) != set(REQUIRED_SERVICE_IDS):
        raise ValueError("ENVIRONMENT_COMPOSE_SERVICE_MATRIX_MISMATCH")
    expected_config = definition.configuration_path.resolve()
    expected_schema = (
        definition.repository_root / "config" / "application.schema.json"
    ).resolve()
    for service_id in APPLICATION_SERVICE_IDS:
        service = _required_mapping_value(services[service_id], f"service {service_id}")
        if "environment" in service or "env_file" in service:
            raise ValueError(
                f"ENVIRONMENT_COMPOSE_APPLICATION_ENV_FORBIDDEN: {service_id}"
            )
        command = service.get("command")
        if not isinstance(command, list) or "--config" not in command:
            raise ValueError(
                f"ENVIRONMENT_COMPOSE_CONFIG_ARGUMENT_MISSING: {service_id}"
            )
        config_index = command.index("--config")
        if (
            config_index + 1 >= len(command)
            or command[config_index + 1] != _CONFIG_CONTAINER_PATH
        ):
            raise ValueError(
                f"ENVIRONMENT_COMPOSE_CONFIG_ARGUMENT_INVALID: {service_id}"
            )
        mounts = _mounts_by_target(service, service_id=service_id)
        _require_read_only_bind(
            mounts, _CONFIG_CONTAINER_PATH, expected_config, service_id
        )
        _require_read_only_bind(
            mounts, _SCHEMA_CONTAINER_PATH, expected_schema, service_id
        )
        if any(target.startswith("/workspace/config/secrets/") for target in mounts):
            raise ValueError(
                f"ENVIRONMENT_COMPOSE_SECRET_DIRECTORY_FORBIDDEN: {service_id}"
            )
    postgres = _required_mapping_value(services["postgres"], "service postgres")
    postgres_environment = _required_mapping(postgres, "environment")
    if set(postgres_environment) != {
        "POSTGRES_DB",
        "POSTGRES_PASSWORD_FILE",
        "POSTGRES_USER",
    }:
        raise ValueError("ENVIRONMENT_COMPOSE_TECHNICAL_ENVIRONMENT_INVALID")
    if (
        postgres_environment["POSTGRES_PASSWORD_FILE"]
        != "/run/secrets/postgres_password"
    ):
        raise ValueError("ENVIRONMENT_COMPOSE_POSTGRES_SECRET_INVALID")
    for service_id, service_payload in services.items():
        service = _required_mapping_value(service_payload, f"service {service_id}")
        if "env_file" in service:
            raise ValueError(f"ENVIRONMENT_COMPOSE_ENV_FILE_FORBIDDEN: {service_id}")
        healthcheck = service.get("healthcheck")
        if not isinstance(healthcheck, Mapping) or not healthcheck.get("test"):
            raise ValueError(f"ENVIRONMENT_COMPOSE_HEALTHCHECK_MISSING: {service_id}")
        mounted_secrets = _service_secret_targets(service, service_id=service_id)
        if frozenset(mounted_secrets) != _EXPECTED_SERVICE_SECRETS[service_id]:
            raise ValueError(f"ENVIRONMENT_COMPOSE_SECRET_SCOPE_INVALID: {service_id}")
        for secret_id, target in mounted_secrets.items():
            expected_target = (
                f"/run/secrets/{secret_id}"
                if service_id in {"postgres", "qdrant"}
                else f"/workspace/config/secrets/{definition.environment}/{secret_id}"
            )
            if target != expected_target:
                raise ValueError(
                    f"ENVIRONMENT_COMPOSE_SECRET_TARGET_INVALID: {service_id}"
                )
    edge = _required_mapping_value(services["edge-gateway"], "service edge-gateway")
    ports = edge.get("ports")
    if not isinstance(ports, list) or len(ports) != 1:
        raise ValueError("ENVIRONMENT_COMPOSE_EDGE_PORT_INVALID")
    port = _required_mapping_value(ports[0], "port edge-gateway")
    if (
        port.get("host_ip") != "127.0.0.1"
        or port.get("target") != 8443
        or str(port.get("published")) != str(definition.edge_port)
    ):
        raise ValueError("ENVIRONMENT_COMPOSE_EDGE_PORT_INVALID")
    secrets_payload = _required_mapping(document, "secrets")
    if set(secrets_payload) != {
        "postgres_password",
        "qdrant_api_key",
        "local_api_token",
    }:
        raise ValueError("ENVIRONMENT_COMPOSE_SECRETS_INVALID")
    for secret_id, secret_payload in secrets_payload.items():
        secret = _required_mapping_value(secret_payload, f"secret {secret_id}")
        secret_file = Path(
            _required_text(secret, "file", f"secret {secret_id}")
        ).resolve()
        _require_path_under(secret_file, root=definition.secrets_path)
    qdrant_service = _required_mapping_value(services["qdrant"], "service qdrant")
    qdrant_command = qdrant_service.get("command")
    if (
        not isinstance(qdrant_command, list)
        or len(qdrant_command) != 1
        or "QDRANT__SERVICE__API_KEY" not in qdrant_command[0]
        or "/run/secrets/qdrant_api_key" not in qdrant_command[0]
    ):
        raise ValueError("ENVIRONMENT_COMPOSE_QDRANT_AUTH_MISSING")
    ocr_runtime = _required_mapping_value(
        services["ocr-runtime"], "service ocr-runtime"
    )
    if "2375" in json.dumps(ocr_runtime, sort_keys=True):
        raise ValueError("ENVIRONMENT_COMPOSE_OCR_TCP_FORBIDDEN")
    ocr_environment = _required_mapping(ocr_runtime, "environment")
    if ocr_environment != {"DOCKER_HOST": "unix:///var/run/ocr-docker/docker.sock"}:
        raise ValueError("ENVIRONMENT_COMPOSE_OCR_SOCKET_INVALID")
    for service_id in ("ocr-runtime", "worker-documents"):
        socket_mount = _mounts_by_target(
            _required_mapping_value(services[service_id], f"service {service_id}"),
            service_id=service_id,
        ).get("/var/run/ocr-docker")
        if socket_mount is None or socket_mount.get("source") != "ocr-runtime-socket":
            raise ValueError(f"ENVIRONMENT_COMPOSE_OCR_SOCKET_INVALID: {service_id}")
    gateway = _required_mapping_value(services["llm-gateway"], "service llm-gateway")
    labels = _required_mapping(gateway, "labels")
    if labels.get("org.ostrading.environment") != definition.environment:
        raise ValueError("ENVIRONMENT_COMPOSE_GATEWAY_PROFILE_MISMATCH")
    if labels.get("org.ostrading.spark-endpoint") != _SPARK_ENDPOINT:
        raise ValueError("ENVIRONMENT_COMPOSE_SPARK_ENDPOINT_MISMATCH")
    configuration = load_application_configuration(
        config_path=definition.configuration_path,
        environment_snapshot=dict(os.environ),
    )
    if configuration.application.environment != definition.environment:
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: pile/configuration")
    if configuration.services.api.port != definition.api_port:
        raise ValueError("ENVIRONMENT_COMPOSE_ORCHESTRATOR_PORT_MISMATCH")
    if configuration.services.llm_gateway.port != definition.llm_gateway_port:
        raise ValueError("ENVIRONMENT_COMPOSE_GATEWAY_PORT_MISMATCH")
    if configuration.services.llm_gateway.spark_endpoint_url != _SPARK_ENDPOINT:
        raise ValueError("ENVIRONMENT_COMPOSE_SPARK_ENDPOINT_MISMATCH")
    _validate_local_document_distribution(
        _required_mapping_value(
            services["worker-documents"],
            "service worker-documents",
        ),
        configuration=configuration,
    )
    volumes = _required_mapping(document, "volumes")
    postgres_volume = _required_mapping_value(
        volumes["postgres-data"], "volume postgres-data"
    )
    if postgres_volume.get("name") != configuration.services.postgres.data_volume:
        raise ValueError("ENVIRONMENT_COMPOSE_POSTGRES_VOLUME_MISMATCH")
    qdrant_volume = _required_mapping_value(
        volumes["qdrant-data"], "volume qdrant-data"
    )
    if qdrant_volume.get("name") != configuration.services.qdrant.storage_volume:
        raise ValueError("ENVIRONMENT_COMPOSE_QDRANT_VOLUME_MISMATCH")


def _validate_local_document_distribution(
    worker: Mapping[str, Any],
    *,
    configuration: ApplicationConfiguration,
) -> None:
    distribution = configuration.services.workers.local_distribution
    deploy = _required_mapping(worker, "deploy")
    if deploy.get("replicas") != distribution.replicas:
        raise ValueError("ENVIRONMENT_COMPOSE_DOCUMENT_REPLICAS_MISMATCH")
    resources = _required_mapping(deploy, "resources")
    limits = _required_mapping(resources, "limits")
    if limits.get("memory") != str(distribution.memory_bytes):
        raise ValueError("ENVIRONMENT_COMPOSE_DOCUMENT_MEMORY_MISMATCH")
    if limits.get("cpus") != distribution.cpus:
        raise ValueError("ENVIRONMENT_COMPOSE_DOCUMENT_CPUS_MISMATCH")
    reservations = _required_mapping(resources, "reservations")
    if reservations.get("devices") != [
        {
            "capabilities": ["gpu"],
            "device_ids": ["0"],
            "driver": "nvidia",
        }
    ]:
        raise ValueError("ENVIRONMENT_COMPOSE_DOCUMENT_GPU_ZERO_REQUIRED")
    if (
        distribution.granite_device != "cuda:0"
        or distribution.granite_slots_global != 2
        or distribution.granite_slots_per_worker != 1
    ):
        raise ValueError("ENVIRONMENT_COMPOSE_GRANITE_CAPACITY_MISMATCH")


def _mounts_by_target(
    service: Mapping[str, Any], *, service_id: str
) -> Mapping[str, Mapping[str, Any]]:
    raw_mounts = service.get("volumes")
    if not isinstance(raw_mounts, list):
        raise ValueError(f"ENVIRONMENT_COMPOSE_VOLUMES_MISSING: {service_id}")
    mounts: dict[str, Mapping[str, Any]] = {}
    for raw_mount in raw_mounts:
        mount = _required_mapping_value(raw_mount, f"volume {service_id}")
        target = _required_text(mount, "target", f"volume {service_id}")
        if target in mounts:
            raise ValueError(
                f"ENVIRONMENT_COMPOSE_VOLUME_TARGET_DUPLICATE: {service_id}: {target}"
            )
        mounts[target] = mount
    return MappingProxyType(mounts)


def _service_secret_targets(
    service: Mapping[str, Any],
    *,
    service_id: str,
) -> Mapping[str, str]:
    raw_secrets = service.get("secrets", [])
    if not isinstance(raw_secrets, list):
        raise ValueError(f"ENVIRONMENT_COMPOSE_SECRETS_INVALID: {service_id}")
    mounted: dict[str, str] = {}
    for raw_secret in raw_secrets:
        secret = _required_mapping_value(raw_secret, f"secret service {service_id}")
        source = _required_text(secret, "source", f"secret service {service_id}")
        target = _required_text(secret, "target", f"secret service {service_id}")
        if source in mounted:
            raise ValueError(f"ENVIRONMENT_COMPOSE_SECRET_DUPLICATE: {service_id}")
        mounted[source] = target
    return MappingProxyType(mounted)


def _require_read_only_bind(
    mounts: Mapping[str, Mapping[str, Any]],
    target: str,
    expected_source: Path,
    service_id: str,
) -> None:
    mount = mounts.get(target)
    if mount is None:
        raise ValueError(f"ENVIRONMENT_COMPOSE_BIND_MISSING: {service_id}: {target}")
    source = mount.get("source")
    if mount.get("type") != "bind" or not isinstance(source, str):
        raise ValueError(f"ENVIRONMENT_COMPOSE_BIND_INVALID: {service_id}: {target}")
    if Path(source).resolve() != expected_source or mount.get("read_only") is not True:
        raise ValueError(f"ENVIRONMENT_COMPOSE_BIND_INVALID: {service_id}: {target}")


def _parse_compose_ps(document: str) -> tuple[EnvironmentContainerState, ...]:
    if not isinstance(document, str) or document.strip() == "":
        raise ValueError("ENVIRONMENT_COMPOSE_PS_INVALID")
    payload = []
    for line in document.splitlines():
        if line.strip() == "":
            continue
        try:
            payload.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("ENVIRONMENT_COMPOSE_PS_INVALID") from exc
    states = []
    for item in payload:
        row = _required_mapping_value(item, "état conteneur")
        states.append(
            EnvironmentContainerState(
                service=_required_text(row, "Service", "état conteneur"),
                container_name=_required_text(row, "Name", "état conteneur"),
                state=_required_text(row, "State", "état conteneur").lower(),
                health=_required_text(row, "Health", "état conteneur").lower(),
            )
        )
    return tuple(states)


def _provision_environment_secrets(definition: EnvironmentStackDefinition) -> None:
    """Valide les secrets fournis explicitement, sans jamais les créer."""

    _require_definition_files(definition, require_secrets=True)


def _require_launch_profile_identity(
    *,
    environment: str,
    configuration_path: Path,
    definition: EnvironmentStackDefinition,
    configuration: Any,
) -> Any:
    selected = _require_environment(environment)
    application = getattr(configuration, "application", None)
    if application is None:
        raise ValueError("ENVIRONMENT_LAUNCH_CONFIGURATION_INVALID")
    if (
        definition.environment != selected
        or configuration_path != definition.configuration_path
        or getattr(application, "environment", None) != selected
    ):
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: commande/fichier/profil")
    return configuration


def _require_secret_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"ENVIRONMENT_SECRET_UNREADABLE: {path}")
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"ENVIRONMENT_SECRET_UNREADABLE: {path}") from exc
    if len(value.encode("utf-8")) < 32:
        raise ValueError(f"ENVIRONMENT_SECRET_INVALID: {path}")


def _technical_environment_from_repository(repository_root: Path) -> Mapping[str, str]:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("ENVIRONMENT_GIT_UNAVAILABLE")
    revision_result = subprocess.run(
        (git_executable, "rev-parse", "HEAD"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    revision = revision_result.stdout.strip()
    if (
        revision_result.returncode != 0
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise ValueError("ENVIRONMENT_GIT_REVISION_INVALID")
    migration_names = sorted(
        path.name
        for path in (repository_root / "deploy" / "postgres" / "migrations").glob(
            "*.sql"
        )
        if re.match(r"^[0-9]{3}_", path.name)
    )
    if not migration_names:
        raise ValueError("ENVIRONMENT_POSTGRES_SCHEMA_VERSION_MISSING")
    schema_version = migration_names[-1].split("_", 1)[0]
    return MappingProxyType(
        {
            "OSTRADING_IMAGE_REVISION": revision,
            "OSTRADING_POSTGRES_SCHEMA_VERSION": schema_version,
        }
    )


def _run_compose(
    definition: EnvironmentStackDefinition,
    arguments: Sequence[str],
    *,
    technical_environment: Mapping[str, str],
    capture_output: bool,
    allowed_returncodes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    environment = _compose_process_environment(technical_environment)
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise ValueError("ENVIRONMENT_DOCKER_UNAVAILABLE")
    command = (
        docker_executable,
        "compose",
        "--project-name",
        definition.project_name,
        "--file",
        str(definition.base_compose_path),
        "--file",
        str(definition.compose_path),
        *arguments,
    )
    result = subprocess.run(
        command,
        cwd=definition.repository_root,
        check=False,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if result.returncode not in allowed_returncodes:
        stderr = result.stderr.strip() if isinstance(result.stderr, str) else ""
        raise ValueError(
            f"ENVIRONMENT_COMPOSE_COMMAND_FAILED: {definition.environment}: "
            f"code={result.returncode}: {stderr}"
        )
    return result


def _compose_process_environment(
    technical_environment: Mapping[str, str],
) -> Mapping[str, str]:
    if (
        not isinstance(technical_environment, Mapping)
        or set(technical_environment) != _TECHNICAL_ENVIRONMENT_KEYS
    ):
        raise ValueError("ENVIRONMENT_COMPOSE_TECHNICAL_ENVIRONMENT_INVALID")
    revision = technical_environment["OSTRADING_IMAGE_REVISION"]
    schema_version = technical_environment["OSTRADING_POSTGRES_SCHEMA_VERSION"]
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("ENVIRONMENT_GIT_REVISION_INVALID")
    if re.fullmatch(r"[0-9]{3}", schema_version) is None:
        raise ValueError("ENVIRONMENT_POSTGRES_SCHEMA_VERSION_INVALID")
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise ValueError("ENVIRONMENT_DOCKER_UNAVAILABLE")
    process_environment = dict(os.environ)
    process_environment.update(technical_environment)
    return MappingProxyType(process_environment)


def _require_definition_files(
    definition: EnvironmentStackDefinition,
    *,
    require_secrets: bool,
) -> None:
    if not isinstance(definition, EnvironmentStackDefinition):
        raise ValueError("ENVIRONMENT_STACK_DEFINITION_INVALID")
    for path in (
        definition.base_compose_path,
        definition.compose_path,
        definition.configuration_path,
        definition.caddyfile_path,
    ):
        if not path.is_file():
            raise ValueError(f"ENVIRONMENT_STACK_FILE_MISSING: {path}")
    if require_secrets:
        for file_name in _SECRET_FILE_NAMES:
            _require_secret_file(definition.secrets_path / file_name)


def _repository_root_from_configuration(configuration_path: Path) -> Path:
    path = configuration_path.resolve()
    if path.parent.name != "environments" or path.parent.parent.name != "config":
        raise ValueError("ENVIRONMENT_CONFIGURATION_PATH_INVALID")
    return _require_repository_root(path.parents[2])


def _require_repository_root(repository_root: Path) -> Path:
    if not isinstance(repository_root, Path):
        raise ValueError("ENVIRONMENT_STACK_REPOSITORY_ROOT_INVALID")
    root = repository_root.resolve()
    if not root.is_dir():
        raise ValueError("ENVIRONMENT_STACK_REPOSITORY_ROOT_INVALID")
    return root


def _require_environment(environment: str) -> ApplicationEnvironment:
    if not isinstance(environment, str) or environment not in ENVIRONMENTS:
        raise ValueError(f"CONFIG_ENVIRONMENT_UNKNOWN: profil inconnu: {environment!r}")
    return environment  # type: ignore[return-value]


def _require_path_under(path: Path, *, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("ENVIRONMENT_STACK_PATH_OUTSIDE_REPOSITORY") from exc


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"ENVIRONMENT_COMPOSE_MAPPING_REQUIRED: {key}")
    return value


def _required_mapping_value(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"ENVIRONMENT_COMPOSE_MAPPING_REQUIRED: {context}")
    return value


def _required_text(payload: Mapping[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"ENVIRONMENT_COMPOSE_TEXT_REQUIRED: {context}: {key}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "APPLICATION_SERVICE_IDS",
    "ENVIRONMENTS",
    "REQUIRED_SERVICE_IDS",
    "EnvironmentContainerState",
    "EnvironmentStackDefinition",
    "EnvironmentStackReadiness",
    "aggregate_environment_readiness",
    "configured_http_healthcheck",
    "configured_administrative_identity",
    "configured_worker_healthcheck",
    "environment_stack_definition",
    "export_environment_caddy_ca",
    "inspect_environment_readiness",
    "render_environment_compose",
    "start_environment_compose_stack",
    "validate_environment_compose_matrix",
    "wait_environment_compose_stack",
]
