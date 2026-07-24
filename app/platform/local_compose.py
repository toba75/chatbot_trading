"""Validation statique du Compose local M-002."""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


REQUIRED_SERVICE_IDS = (
    "edge-gateway",
    "ui",
    "orchestrator-api",
    "llm-gateway",
    "postgres",
    "qdrant",
    "granite-docling",
    "embedding-service",
    "reranker-service",
    "worker-documents",
    "worker-research",
    "worker-backtest",
    "backtest-engine",
)

EXPECTED_EXPOSED_PORTS = {
    "ui": ("8081",),
    "orchestrator-api": ("8080",),
    "llm-gateway": ("8090",),
    "postgres": ("5432",),
    "qdrant": ("6333",),
    "granite-docling": ("8001",),
    "embedding-service": ("8101",),
    "reranker-service": ("8102",),
    "backtest-engine": ("8200",),
}

WORKER_SERVICE_IDS = frozenset(
    {
        "worker-documents",
        "worker-research",
        "worker-backtest",
    }
)

REQUIRED_NETWORK_IDS = ("edge", "core", "spark-egress")
REQUIRED_COMPOSE_SECRETS = ("postgres_password",)
SPARK_API_KEY_SECRET = "gemma_api_key"
SPARK_CA_SECRET = "spark_ca"
FORBIDDEN_MODEL_SERVICE_PATTERN = re.compile(r"(^|[-_])(gemma|vllm)([-_]|$)")
REQUIRED_ENVIRONMENT_PATTERN = re.compile(r"^\$\{[A-Z][A-Z0-9_]*\?[^}]+\}$")
SECRET_ENVIRONMENT_MARKERS = ("PASSWORD", "TOKEN", "SECRET", "API_KEY")
INTERNAL_IMAGE_PREFIX = "ostrading/"
APPLICATION_CONFIG_CONTAINER_PATH = "/workspace/config/application.yaml"
APPLICATION_CONFIG_VOLUME = (
    f"./application.compose.yaml:{APPLICATION_CONFIG_CONTAINER_PATH}:ro"
)
APPLICATION_SCHEMA_CONTAINER_PATH = "/workspace/config/application.schema.json"
APPLICATION_SCHEMA_VOLUME = (
    f"../../config/application.schema.json:{APPLICATION_SCHEMA_CONTAINER_PATH}:ro"
)
LLM_GATEWAY_LOCAL_SECRETS_VOLUME = (
    "../../config/secrets/local:/workspace/config/secrets/local:ro"
)
APPLICATION_CONFIG_ARGUMENTS = ("--config", APPLICATION_CONFIG_CONTAINER_PATH)
FORBIDDEN_APPLICATION_ENVIRONMENT_KEYS = frozenset(
    (
        "API_PORT",
        "BACKTEST_ENGINE_URL",
        "BACKTEST_WORKDIR",
        "DATABASE_URL",
        "EMBEDDING_MODEL_PATH",
        "EMBEDDING_SERVICE_URL",
        "GRANITE_MODEL_PATH",
        "GRANITE_URL",
        "LLM_GATEWAY_PORT",
        "LLM_GATEWAY_URL",
        "QDRANT_URL",
        "RERANKER_MODEL_PATH",
        "RERANKER_SERVICE_URL",
        "SPARK_ALLOWED_CLIENT_CIDRS",
        "UI_API_URL",
    )
)
FORBIDDEN_APPLICATION_ENVIRONMENT_PREFIXES = ("GEMMA_", "VLLM_")
ALLOWED_TECHNICAL_ENVIRONMENT_BY_SERVICE = {
    "edge-gateway": frozenset(("CADDY_ADMIN",)),
    "postgres": frozenset(("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD_FILE")),
}
HISTORICAL_GATEWAY_ENVIRONMENT_KEYS = (
    "GEMMA_BASE_URL",
    "GEMMA_MODEL",
    "GEMMA_MODEL_REVISION",
    "GEMMA_RUNTIME_VERSION",
    "GEMMA_AUTH_MODE",
    "GEMMA_TLS_MODE",
    "GEMMA_TIMEOUT_SECONDS",
    "GEMMA_RETRY_BEFORE_FIRST_TOKEN",
    "GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    "GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS",
)


def _runtime_command(*arguments: str) -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "app.platform.local_runtime",
        *arguments,
        *APPLICATION_CONFIG_ARGUMENTS,
    )


EXPECTED_SERVICE_COMMANDS = {
    "ui": _runtime_command("serve-http", "ui", "8081"),
    "orchestrator-api": APPLICATION_CONFIG_ARGUMENTS,
    "llm-gateway": _runtime_command("serve-http", "llm-gateway", "8090"),
    "granite-docling": _runtime_command("serve-http", "granite-docling", "8001"),
    "embedding-service": _runtime_command("serve-http", "embedding-service", "8101"),
    "reranker-service": _runtime_command("serve-http", "reranker-service", "8102"),
    "worker-documents": (
        "--worker-id",
        "worker-documents",
        "--lease-seconds",
        "120",
        "--poll-seconds",
        "0.5",
        *APPLICATION_CONFIG_ARGUMENTS,
    ),
    "worker-research": _runtime_command(
        "run-worker", "worker-research", "--worker-id", "worker-research"
    ),
    "worker-backtest": _runtime_command(
        "run-worker", "worker-backtest", "--worker-id", "worker-backtest"
    ),
    "backtest-engine": _runtime_command("serve-http", "backtest-engine", "8200"),
}
APPLICATION_SERVICE_IDS = frozenset(EXPECTED_SERVICE_COMMANDS)


@dataclass(frozen=True)
class ComposeService:
    id: str
    image: str
    command: tuple[str, ...]
    ports: tuple[str, ...]
    expose: tuple[str, ...]
    profiles: tuple[str, ...]
    networks: tuple[str, ...]
    volumes: tuple[str, ...]
    secrets: tuple[str, ...]
    env_file: tuple[str, ...]
    tmpfs: tuple[str, ...]
    environment: Mapping[str, str]
    healthcheck: Mapping[str, Any]
    read_only: bool


@dataclass(frozen=True)
class LocalCompose:
    source: str
    name: str
    services: tuple[ComposeService, ...]
    networks: Mapping[str, Any]
    secrets: Mapping[str, Mapping[str, Any]]

    def service(self, service_id: str) -> ComposeService:
        for service in self.services:
            if service.id == service_id:
                return service
        raise ValueError(f"Service Compose absent: {service_id}")


@dataclass(frozen=True)
class _YamlLine:
    number: int
    indent: int
    text: str


def load_local_compose(path: str | Path) -> LocalCompose:
    compose_path = Path(path)
    return parse_local_compose_document(
        compose_path.read_text(encoding="utf-8-sig"),
        source=str(compose_path),
    )


def parse_local_compose_document(document: str, source: str) -> LocalCompose:
    payload = _parse_yaml_subset(document, source)
    if not isinstance(payload, Mapping):
        raise ValueError("Document Compose non objet.")

    name = _required_text(payload, "name", "Compose local")
    services_payload = _required_mapping(payload, "services", "Compose local")
    networks = _required_mapping(payload, "networks", "Compose local")
    secrets_payload = _required_mapping(payload, "secrets", "Compose local")

    services: list[ComposeService] = []
    seen_service_ids: set[str] = set()
    for service_id, service_payload in services_payload.items():
        if not isinstance(service_id, str) or service_id.strip() == "":
            raise ValueError("Identifiant de service Compose invalide.")
        if service_id != service_id.strip():
            raise ValueError(
                f"Identifiant de service Compose non normalisé: {service_id}"
            )
        if service_id in seen_service_ids:
            raise ValueError(f"Service Compose dupliqué: {service_id}")
        if not isinstance(service_payload, Mapping):
            raise ValueError(f"Service Compose non objet: {service_id}")

        services.append(_parse_service(service_id, service_payload))
        seen_service_ids.add(service_id)

    secrets: dict[str, Mapping[str, Any]] = {}
    for secret_id, secret_payload in secrets_payload.items():
        if not isinstance(secret_id, str) or secret_id.strip() == "":
            raise ValueError("Identifiant de secret Compose invalide.")
        if not isinstance(secret_payload, Mapping):
            raise ValueError(f"Secret Compose non objet: {secret_id}")
        secrets[secret_id] = secret_payload

    return LocalCompose(
        source=source,
        name=name,
        services=tuple(services),
        networks=networks,
        secrets=secrets,
    )


def validate_local_compose(compose: LocalCompose) -> None:
    _validate_services(compose)
    _validate_networks(compose)
    _validate_secrets(compose)

    for service in compose.services:
        _validate_service_image(service)
        _validate_service_ports(service)
        _validate_service_exposure(service)
        _validate_service_tmpfs(service)
        _validate_service_healthcheck(service)
        _validate_service_application_configuration(service)
        _validate_service_command(service)
        _validate_service_networks(service, compose.networks)
        _validate_service_secrets(service, compose.secrets)
        _validate_service_environment(service)


def _parse_service(service_id: str, payload: Mapping[str, Any]) -> ComposeService:
    environment_payload = _optional_mapping(
        payload, "environment", f"service {service_id}"
    )
    environment: dict[str, str] = {}
    for key, value in environment_payload.items():
        if not isinstance(key, str) or key.strip() == "":
            raise ValueError(
                f"Variable d'environnement invalide pour service {service_id}."
            )
        if not isinstance(value, str):
            raise ValueError(
                f"Variable d'environnement non textuelle pour service {service_id}: {key}"
            )
        if value.strip() == "":
            raise ValueError(
                f"Variable d'environnement vide pour service {service_id}: {key}"
            )
        if value != value.strip():
            raise ValueError(
                f"Variable d'environnement non normalisée pour service {service_id}: {key}"
            )
        environment[key] = value

    healthcheck_payload = _optional_mapping(
        payload, "healthcheck", f"service {service_id}"
    )

    return ComposeService(
        id=service_id,
        image=_required_text(payload, "image", f"service {service_id}"),
        command=_optional_text_list(payload, "command", f"service {service_id}"),
        ports=_optional_text_list(payload, "ports", f"service {service_id}"),
        expose=_optional_text_list(payload, "expose", f"service {service_id}"),
        profiles=_optional_text_list(payload, "profiles", f"service {service_id}"),
        networks=_optional_text_list(payload, "networks", f"service {service_id}"),
        volumes=_optional_text_list(payload, "volumes", f"service {service_id}"),
        secrets=_optional_text_list(payload, "secrets", f"service {service_id}"),
        env_file=_optional_env_file_list(payload, "env_file", f"service {service_id}"),
        tmpfs=_optional_text_list(payload, "tmpfs", f"service {service_id}"),
        environment=environment,
        healthcheck=healthcheck_payload,
        read_only=_optional_bool(payload, "read_only", f"service {service_id}"),
    )


def _validate_services(compose: LocalCompose) -> None:
    services_by_id = {service.id: service for service in compose.services}

    for service in compose.services:
        if FORBIDDEN_MODEL_SERVICE_PATTERN.search(service.id):
            raise ValueError(
                f"Service Gemma/vLLM principal interdit dans Compose local: {service.id}"
            )
        if service.id not in REQUIRED_SERVICE_IDS:
            raise ValueError(f"Service Compose non prévu par M-002: {service.id}")

    for service_id in REQUIRED_SERVICE_IDS:
        if service_id not in services_by_id:
            raise ValueError(f"Service Compose requis absent: {service_id}")


def _validate_networks(compose: LocalCompose) -> None:
    for network_id in REQUIRED_NETWORK_IDS:
        if network_id not in compose.networks:
            raise ValueError(f"Réseau Compose absent: {network_id}")

    core_network = compose.networks["core"]
    if not isinstance(core_network, Mapping):
        raise ValueError("Réseau core non objet.")
    if core_network.get("internal") is not True:
        raise ValueError("Réseau core non interne.")


def _validate_secrets(compose: LocalCompose) -> None:
    for secret_id in REQUIRED_COMPOSE_SECRETS:
        if secret_id not in compose.secrets:
            raise ValueError(f"Secret Compose absent: {secret_id}")

        secret_payload = compose.secrets[secret_id]
        secret_file = _required_text(secret_payload, "file", f"secret {secret_id}")
        if not secret_file.startswith("./secrets/"):
            raise ValueError(f"Chemin de secret hors répertoire secrets: {secret_id}")
        if ".." in Path(secret_file).parts:
            raise ValueError(f"Chemin de secret parent interdit: {secret_id}")


def _validate_service_image(service: ComposeService) -> None:
    if (
        not service.image.startswith(INTERNAL_IMAGE_PREFIX)
        and "@sha256:" not in service.image
    ):
        raise ValueError(
            f"Image tierce sans digest pour service {service.id}: {service.image}"
        )
    if not _is_pinned_image(service.image):
        raise ValueError(
            f"Image non épinglée pour service {service.id}: {service.image}"
        )


def _validate_service_ports(service: ComposeService) -> None:
    if service.id == "edge-gateway":
        if len(service.ports) == 0:
            raise ValueError("Port utilisateur absent pour edge-gateway.")
        for port in service.ports:
            if not port.startswith("127.0.0.1:"):
                raise ValueError(
                    f"Port utilisateur non lié à 127.0.0.1 pour edge-gateway: {port}"
                )
        return

    if len(service.ports) > 0:
        raise ValueError(f"Port publié interdit pour service interne: {service.id}")


def _validate_service_exposure(service: ComposeService) -> None:
    if service.id in EXPECTED_EXPOSED_PORTS:
        expected_ports = EXPECTED_EXPOSED_PORTS[service.id]
        if service.expose != expected_ports:
            raise ValueError(
                f"Ports exposés internes invalides pour {service.id}. "
                f"Attendu: {', '.join(expected_ports)}"
            )
        return

    if service.id in WORKER_SERVICE_IDS and len(service.expose) > 0:
        raise ValueError(f"Port exposé interdit pour worker: {service.id}")


def _validate_service_tmpfs(service: ComposeService) -> None:
    if service.id == "edge-gateway":
        if service.tmpfs != ("/tmp",):
            raise ValueError("tmpfs /tmp requis pour edge-gateway")
        return

    if service.id == "orchestrator-api":
        if service.tmpfs != ("/tmp:size=128m,mode=1777",):
            raise ValueError(
                "ORCHESTRATOR_TMPFS_BOUNDED_REQUIRED: "
                "tmpfs /tmp borné requis pour orchestrator-api: "
                f"{service.tmpfs}"
            )
        return

    if service.id == "worker-documents":
        if service.tmpfs not in (
            (),
            ("/tmp:size=128m,mode=1777",),
            (
                "/tmp:size=128m,mode=1777",
                "/triton-cache:rw,exec,nosuid,nodev,size=128m,mode=0770,gid=31000",
            ),
        ):
            raise ValueError("tmpfs /tmp worker-documents invalide")
        return

    if len(service.tmpfs) > 0:
        raise ValueError(f"tmpfs non prévu pour service: {service.id}")


def _validate_service_healthcheck(service: ComposeService) -> None:
    if len(service.healthcheck) == 0:
        raise ValueError(f"Healthcheck absent pour service: {service.id}")

    test = service.healthcheck.get("test")
    if not isinstance(test, list) or len(test) == 0:
        raise ValueError(f"Healthcheck sans test pour service: {service.id}")

    for field_name in ("interval", "timeout", "retries", "start_period"):
        if field_name not in service.healthcheck:
            raise ValueError(
                f"Healthcheck incomplet pour service {service.id}: {field_name}"
            )

    command_text = " ".join(str(item) for item in test)
    if service.read_only and ("touch " in command_text or ">" in command_text):
        raise ValueError(
            f"Healthcheck mutant interdit pour service read_only: {service.id}"
        )


def _validate_service_application_configuration(service: ComposeService) -> None:
    if len(service.env_file) > 0:
        raise ValueError(f"env_file interdit pour service {service.id}")

    if service.id not in APPLICATION_SERVICE_IDS:
        return

    if "--config" not in service.command:
        raise ValueError(
            f"Argument --config absent pour service applicatif: {service.id}"
        )

    config_index = service.command.index("--config")
    if config_index + 1 >= len(service.command):
        raise ValueError(
            f"Chemin --config absent pour service applicatif: {service.id}"
        )
    if service.command[config_index + 1] != APPLICATION_CONFIG_CONTAINER_PATH:
        raise ValueError(
            f"Chemin --config invalide pour service applicatif: {service.id}"
        )

    if APPLICATION_CONFIG_VOLUME not in service.volumes:
        raise ValueError(
            f"Montage config/application.yaml read-only absent pour service applicatif: {service.id}"
        )
    if APPLICATION_SCHEMA_VOLUME not in service.volumes:
        raise ValueError(
            f"Montage config/application.schema.json read-only absent pour service applicatif: {service.id}"
        )
    if (
        service.id == "llm-gateway"
        and LLM_GATEWAY_LOCAL_SECRETS_VOLUME not in service.volumes
    ):
        raise ValueError(
            "Montage config/secrets/local read-only absent pour service llm-gateway"
        )


def _validate_service_command(service: ComposeService) -> None:
    expected_command = EXPECTED_SERVICE_COMMANDS.get(service.id)
    if expected_command is None:
        if len(service.command) > 0:
            raise ValueError(f"Commande Compose non prévue pour service {service.id}")
        return

    if service.command != expected_command:
        if service.id == "orchestrator-api" and service.command[0:1] == ("api",):
            raise ValueError("Commande Compose Uvicorn orchestrator-api invalide")
        if (
            len(service.command) >= 3
            and service.command[0] == "python"
            and service.command[1] == "-m"
        ):
            module_name = service.command[2]
            if importlib.util.find_spec(module_name) is None:
                raise ValueError(
                    f"Commande Compose non exécutable pour service {service.id}: {module_name}"
                )
        raise ValueError(f"Commande Compose invalide pour service {service.id}")
    if service.id in {"orchestrator-api", "worker-documents"}:
        return
    if (
        len(service.command) >= 3
        and service.command[0] == "python"
        and service.command[1] == "-m"
    ):
        module_name = service.command[2]
        if importlib.util.find_spec(module_name) is None:
            raise ValueError(
                f"Commande Compose non exécutable pour service {service.id}: {module_name}"
            )
        return
    raise ValueError(f"Commande Compose non exécutable pour service {service.id}")


def _validate_service_networks(
    service: ComposeService, networks: Mapping[str, Any]
) -> None:
    if len(service.networks) == 0:
        raise ValueError(f"Réseau absent pour service: {service.id}")

    for network_id in service.networks:
        if network_id not in networks:
            raise ValueError(f"Réseau inconnu pour service {service.id}: {network_id}")

    if service.id == "edge-gateway":
        if service.networks != ("edge", "core"):
            raise ValueError("Réseaux edge-gateway invalides: edge et core requis.")
    elif "core" not in service.networks:
        raise ValueError(f"Réseau core absent pour service: {service.id}")

    if service.id == "llm-gateway":
        if "spark-egress" not in service.networks:
            raise ValueError("Réseau spark-egress absent pour llm-gateway.")
    elif "spark-egress" in service.networks:
        raise ValueError(f"Réseau spark-egress interdit pour service: {service.id}")


def _validate_service_secrets(
    service: ComposeService, secrets: Mapping[str, Mapping[str, Any]]
) -> None:
    for secret_id in service.secrets:
        if secret_id not in secrets:
            raise ValueError(
                f"Secret référencé absent pour service {service.id}: {secret_id}"
            )

    if service.id == "llm-gateway":
        if SPARK_API_KEY_SECRET in service.secrets:
            raise ValueError(
                f"Secret Spark interdit pour llm-gateway: {SPARK_API_KEY_SECRET}"
            )
        if SPARK_CA_SECRET in service.secrets:
            raise ValueError(
                f"Secret Spark interdit pour llm-gateway: {SPARK_CA_SECRET}"
            )

    if service.id == "postgres" and "postgres_password" not in service.secrets:
        raise ValueError("Secret PostgreSQL absent pour postgres: postgres_password")


def _validate_service_environment(service: ComposeService) -> None:
    for key, value in service.environment.items():
        if _is_application_environment_key(key):
            raise ValueError(
                f"Variable applicative interdite pour service {service.id}: {key}"
            )
        if service.id in APPLICATION_SERVICE_IDS:
            raise ValueError(
                f"Variable applicative interdite pour service {service.id}: {key}"
            )

        allowed_keys = ALLOWED_TECHNICAL_ENVIRONMENT_BY_SERVICE.get(
            service.id, frozenset()
        )
        if key not in allowed_keys:
            raise ValueError(
                f"Variable non allowlistée pour service {service.id}: {key}"
            )

        key_upper = key.upper()
        is_secret_file_reference = key_upper.endswith("_FILE") or key_upper.endswith(
            "_BUNDLE"
        )
        contains_secret_marker = any(
            marker in key_upper for marker in SECRET_ENVIRONMENT_MARKERS
        )

        if contains_secret_marker and not is_secret_file_reference:
            raise ValueError(
                f"Secret en clair interdit pour service {service.id}: {key}"
            )

        if key_upper.endswith("_FILE") and not value.startswith("/run/secrets/"):
            raise ValueError(
                f"Fichier secret invalide pour service {service.id}: {key}"
            )

        if value.startswith("/run/secrets/"):
            continue

        if (
            service.id == "postgres"
            and key in {"POSTGRES_DB", "POSTGRES_USER"}
            and value == "ostrading"
        ):
            continue

        if not REQUIRED_ENVIRONMENT_PATTERN.match(value):
            raise ValueError(
                f"Variable non injectée explicitement pour service {service.id}: {key}"
            )

        if ":-" in value or "-" in value.split("?", 1)[0]:
            raise ValueError(
                f"Valeur par défaut interdite pour service {service.id}: {key}"
            )


def _is_application_environment_key(key: str) -> bool:
    if key in FORBIDDEN_APPLICATION_ENVIRONMENT_KEYS:
        return True
    if key in HISTORICAL_GATEWAY_ENVIRONMENT_KEYS:
        return True
    return any(
        key.startswith(prefix) for prefix in FORBIDDEN_APPLICATION_ENVIRONMENT_PREFIXES
    )


def _is_pinned_image(image: str) -> bool:
    if "${" in image:
        return bool(
            re.fullmatch(
                r"ostrading/(?:orchestrator-api|worker-documents):"
                r"0\.1\.0-m013-fastapi-schema-"
                r"\$\{OSTRADING_POSTGRES_SCHEMA_VERSION\?[^}]+\}-"
                r"\$\{OSTRADING_IMAGE_REVISION\?[^}]+\}",
                image,
            )
        )

    if "@sha256:" in image:
        digest = image.rsplit("@sha256:", 1)[1]
        return bool(re.fullmatch(r"[a-fA-F0-9]{64}", digest))
    if not image.startswith(INTERNAL_IMAGE_PREFIX):
        return False

    last_segment = image.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return False

    tag = last_segment.rsplit(":", 1)[1]
    if tag == "" or tag.lower() == "latest":
        return False

    return any(character.isdigit() for character in tag)


def _parse_yaml_subset(document: str, source: str) -> Any:
    lines = _prepare_yaml_lines(document, source)
    if len(lines) == 0:
        raise ValueError(f"Document YAML vide: {source}")

    value, next_index = _parse_block(lines, 0, lines[0].indent, source)
    if next_index != len(lines):
        line = lines[next_index]
        raise ValueError(f"Ligne YAML inattendue {source}:{line.number}")
    return value


def _prepare_yaml_lines(document: str, source: str) -> tuple[_YamlLine, ...]:
    prepared: list[_YamlLine] = []
    for index, raw_line in enumerate(document.splitlines(), start=1):
        if "\t" in raw_line:
            raise ValueError(f"Tabulation YAML interdite {source}:{index}")

        line = raw_line.rstrip()
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Indentation YAML impaire {source}:{index}")

        prepared.append(_YamlLine(number=index, indent=indent, text=line[indent:]))

    return tuple(prepared)


def _parse_block(
    lines: tuple[_YamlLine, ...],
    index: int,
    indent: int,
    source: str,
) -> tuple[Any, int]:
    if index >= len(lines):
        raise ValueError(f"Bloc YAML absent: {source}")

    line = lines[index]
    if line.indent != indent:
        raise ValueError(f"Indentation YAML inattendue {source}:{line.number}")

    if line.text.startswith("- "):
        return _parse_sequence(lines, index, indent, source)
    return _parse_mapping(lines, index, indent, source)


def _parse_mapping(
    lines: tuple[_YamlLine, ...],
    index: int,
    indent: int,
    source: str,
) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}

    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"Indentation YAML inattendue {source}:{line.number}")
        if line.text.startswith("- "):
            break

        key, raw_value = _split_yaml_key_value(line, source)
        if key in mapping:
            raise ValueError(f"Clé YAML dupliquée {source}:{line.number}: {key}")

        if raw_value == "":
            next_index = index + 1
            if next_index >= len(lines) or lines[next_index].indent <= indent:
                raise ValueError(f"Valeur YAML absente {source}:{line.number}: {key}")
            value, index = _parse_block(lines, next_index, indent + 2, source)
        else:
            mapping[key] = _parse_scalar(raw_value, source, line.number)
            index += 1
            continue

        mapping[key] = value

    return mapping, index


def _parse_sequence(
    lines: tuple[_YamlLine, ...],
    index: int,
    indent: int,
    source: str,
) -> tuple[list[Any], int]:
    sequence: list[Any] = []

    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"Indentation YAML inattendue {source}:{line.number}")
        if not line.text.startswith("- "):
            break

        raw_value = line.text[2:].strip()
        if raw_value == "":
            next_index = index + 1
            if next_index >= len(lines) or lines[next_index].indent <= indent:
                raise ValueError(f"Valeur de liste YAML absente {source}:{line.number}")
            value, index = _parse_block(lines, next_index, indent + 2, source)
            sequence.append(value)
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:(?:\s|$)", raw_value):
            item_end = index + 1
            while item_end < len(lines) and lines[item_end].indent > indent:
                item_end += 1
            item_lines = (
                _YamlLine(
                    number=line.number,
                    indent=indent + 2,
                    text=raw_value,
                ),
                *lines[index + 1 : item_end],
            )
            value, parsed_end = _parse_mapping(
                item_lines,
                0,
                indent + 2,
                source,
            )
            if parsed_end != len(item_lines):
                unexpected = item_lines[parsed_end]
                raise ValueError(f"Ligne YAML inattendue {source}:{unexpected.number}")
            sequence.append(value)
            index = item_end
        else:
            sequence.append(_parse_scalar(raw_value, source, line.number))
            index += 1

    return sequence, index


def _split_yaml_key_value(line: _YamlLine, source: str) -> tuple[str, str]:
    if ":" not in line.text:
        raise ValueError(f"Clé YAML sans séparateur {source}:{line.number}")

    key, raw_value = line.text.split(":", 1)
    key = key.strip()
    if key == "":
        raise ValueError(f"Clé YAML vide {source}:{line.number}")
    if key != key.strip():
        raise ValueError(f"Clé YAML non normalisée {source}:{line.number}")

    return key, raw_value.strip()


def _parse_scalar(raw_value: str, source: str, line_number: int) -> Any:
    value = raw_value.strip()
    if value == "{}":
        return {}
    if value == "[]":
        return []
    if value in ("true", "false"):
        return value == "true"
    if value in ("null", "~"):
        return None

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    if value.startswith(('"', "'")) or value.endswith(('"', "'")):
        raise ValueError(f"Chaîne YAML mal fermée {source}:{line_number}")

    return value


def _required_text(payload: Mapping[str, Any], field_name: str, context: str) -> str:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")

    value = payload[field_name]
    if not isinstance(value, str):
        raise ValueError(f"Champ {field_name} non textuel pour {context}.")
    if value.strip() == "":
        raise ValueError(f"Champ {field_name} vide pour {context}.")
    if value != value.strip():
        raise ValueError(f"Champ {field_name} non normalisé pour {context}.")
    return value


def _required_mapping(
    payload: Mapping[str, Any], field_name: str, context: str
) -> Mapping[str, Any]:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")

    value = payload[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"Champ {field_name} non objet pour {context}.")
    if len(value) == 0:
        raise ValueError(f"Champ {field_name} vide pour {context}.")
    return value


def _optional_mapping(
    payload: Mapping[str, Any], field_name: str, context: str
) -> Mapping[str, Any]:
    if field_name not in payload:
        return {}

    value = payload[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"Champ {field_name} non objet pour {context}.")
    return value


def _optional_text_list(
    payload: Mapping[str, Any], field_name: str, context: str
) -> tuple[str, ...]:
    if field_name not in payload:
        return ()

    value = payload[field_name]
    if not isinstance(value, list):
        raise ValueError(f"Champ {field_name} non liste pour {context}.")

    values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(
                f"Entrée {field_name}[{index}] non textuelle pour {context}."
            )
        if item.strip() == "":
            raise ValueError(f"Entrée {field_name}[{index}] vide pour {context}.")
        if item != item.strip():
            raise ValueError(
                f"Entrée {field_name}[{index}] non normalisée pour {context}."
            )
        values.append(item)
    return tuple(values)


def _optional_env_file_list(
    payload: Mapping[str, Any], field_name: str, context: str
) -> tuple[str, ...]:
    if field_name not in payload:
        return ()

    value = payload[field_name]
    if isinstance(value, str):
        if value.strip() == "":
            raise ValueError(f"Champ {field_name} vide pour {context}.")
        if value != value.strip():
            raise ValueError(f"Champ {field_name} non normalisÃ© pour {context}.")
        return (value,)

    return _optional_text_list(payload, field_name, context)


def _optional_bool(payload: Mapping[str, Any], field_name: str, context: str) -> bool:
    if field_name not in payload:
        return False
    value = payload[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"Champ {field_name} non booléen pour {context}.")
    return value
