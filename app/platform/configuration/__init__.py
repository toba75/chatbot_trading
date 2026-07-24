"""Chargement strict de configuration applicative M13-config."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlparse


CONFIG_FILE_REQUIRED = "CONFIG_FILE_REQUIRED"
CONFIG_FILE_UNREADABLE = "CONFIG_FILE_UNREADABLE"
CONFIG_SCHEMA_INVALID = "CONFIG_SCHEMA_INVALID"
CONFIG_KEY_MISSING = "CONFIG_KEY_MISSING"
CONFIG_KEY_EMPTY = "CONFIG_KEY_EMPTY"
CONFIG_ENV_INPUT_REJECTED = "CONFIG_ENV_INPUT_REJECTED"
CONFIG_SECRET_INLINE_REJECTED = "CONFIG_SECRET_INLINE_REJECTED"

_PLACEHOLDER_VALUE = "TO_BE_FILLED"
_SCHEMA_RELATIVE_PATH = Path("config") / "application.schema.json"
_HISTORICAL_ENVIRONMENT_NAMES = frozenset(
    {
        "DATABASE_URL",
        "QDRANT_URL",
        "LLM_GATEWAY_URL",
        "API_PORT",
        "LLM_GATEWAY_PORT",
        "SPARK_ALLOWED_CLIENT_CIDRS",
    }
)
_HISTORICAL_ENVIRONMENT_PREFIXES = ("GEMMA_",)
_INLINE_SECRET_KEYS = frozenset(
    {"password", "token", "api_key", "secret", "secret_value"}
)


class ApplicationConfigurationError(ValueError):
    """Erreur publique de configuration avec code stable CONFIG_*."""

    def __init__(self, code: str, message: str, configuration_path: str = "") -> None:
        self.code = code
        self.configuration_path = configuration_path
        if configuration_path == "":
            super().__init__(f"{code}: {message}")
        else:
            super().__init__(f"{code}: {message} Chemin: {configuration_path}")


@dataclass(frozen=True)
class ApplicationIdentityConfiguration:
    environment: str
    deployment_id: str


@dataclass(frozen=True)
class DockerLocalHostConfiguration:
    role: str
    bind_host: str
    container_listen_host: str
    public_access: bool


@dataclass(frozen=True)
class SparkInferenceHostConfiguration:
    role: str
    dns_name: str
    endpoint_hosts: tuple[str, ...]
    allowed_client_cidrs: tuple[str, ...]


@dataclass(frozen=True)
class DeploymentHostsConfiguration:
    docker_local: DockerLocalHostConfiguration
    spark_inference: SparkInferenceHostConfiguration


@dataclass(frozen=True)
class DeploymentNetworkConfiguration:
    require_tls: bool
    require_api_key: bool
    prefer_mtls: bool


@dataclass(frozen=True)
class DeploymentPlacementConfiguration:
    application: str
    postgres: str
    qdrant: str
    llm_gateway: str
    gemma_vllm: str


@dataclass(frozen=True)
class DeploymentConfiguration:
    topology: str
    hosts: DeploymentHostsConfiguration
    network: DeploymentNetworkConfiguration
    placement: DeploymentPlacementConfiguration


@dataclass(frozen=True)
class PostgresServiceConfiguration:
    url: str
    port: int
    database: str
    role: str
    data_volume: str


@dataclass(frozen=True)
class QdrantCollectionsConfiguration:
    datastore_identity: str
    knowledge_access: str


@dataclass(frozen=True)
class QdrantServiceConfiguration:
    url: str
    port: int
    instance_id: str
    storage_volume: str
    collections: QdrantCollectionsConfiguration


@dataclass(frozen=True)
class ApiServiceConfiguration:
    bind_host: str
    port: int


@dataclass(frozen=True)
class LocalDocumentDistributionConfiguration:
    replicas: int
    memory_bytes: int
    cpus: int
    granite_device: str
    granite_slots_global: int
    granite_slots_per_worker: int


@dataclass(frozen=True)
class WorkerServiceConfiguration:
    queue_name: str
    outbox_namespace: str
    progress_namespace: str
    document_orchestration_version: str
    concurrency: int
    docling_concurrency: int
    granite_concurrency: int
    local_distribution: LocalDocumentDistributionConfiguration


@dataclass(frozen=True)
class LLMGatewayServiceConfiguration:
    url: str
    port: int
    spark_endpoint_url: str
    auth_mode: str
    tls_mode: str
    timeout_seconds: int
    retry_before_first_token: int
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: int


@dataclass(frozen=True)
class ServicesConfiguration:
    postgres: PostgresServiceConfiguration
    qdrant: QdrantServiceConfiguration
    api: ApiServiceConfiguration
    workers: WorkerServiceConfiguration
    llm_gateway: LLMGatewayServiceConfiguration


@dataclass(frozen=True)
class LLMModelConfiguration:
    provider: str
    transport: str
    reference_model: str
    served_model_name: str
    model_revision: str
    runtime: str
    runtime_version: str
    context_length_tokens: int
    max_output_tokens: int
    temperature: float


@dataclass(frozen=True)
class ModelsConfiguration:
    llm: LLMModelConfiguration


@dataclass(frozen=True)
class PathsConfiguration:
    data_root: str
    corpus_root: str
    canonical_sources_root: str
    qdrant_storage_root: str
    postgres_data_root: str
    reports_root: str
    logs_root: str
    experiments_root: str
    cache_root: str
    corpus_quota_bytes: int


@dataclass(frozen=True)
class SecretPathsConfiguration:
    postgres_password_path: str
    qdrant_api_key_path: str
    llm_gateway_api_key_path: str
    tls_ca_certificate_path: str
    local_api_token_path: str


@dataclass(frozen=True)
class SecurityAuditConfiguration:
    configuration_hash_required: bool
    log_configuration_changes: bool


@dataclass(frozen=True)
class SecurityConfiguration:
    network_exposure: str
    allow_public_bind: bool
    secrets: SecretPathsConfiguration
    audit: SecurityAuditConfiguration


@dataclass(frozen=True)
class PostConversionQualityGateConfiguration:
    page_count_match: str
    provenance_coverage_min: float
    missing_page_max: int


@dataclass(frozen=True)
class RetrievalQualityGateConfiguration:
    citation_required: bool
    min_evidence_candidates: int


@dataclass(frozen=True)
class AnsweringQualityGateConfiguration:
    unsupported_claim_policy: str
    abstention_required_on_insufficient_evidence: bool


@dataclass(frozen=True)
class LLMQualityGateConfiguration:
    real_path_required: bool
    fallback_model_allowed: bool


@dataclass(frozen=True)
class QualityGatesConfiguration:
    post_conversion: PostConversionQualityGateConfiguration
    retrieval: RetrievalQualityGateConfiguration
    answering: AnsweringQualityGateConfiguration
    llm: LLMQualityGateConfiguration


@dataclass(frozen=True)
class TracingConfiguration:
    enabled: bool


@dataclass(frozen=True)
class LogsConfiguration:
    include_payloads: bool


@dataclass(frozen=True)
class ObservabilityConfiguration:
    tracing: TracingConfiguration
    logs: LogsConfiguration


@dataclass(frozen=True)
class RuntimeWorkersConfiguration:
    ingestion: int
    research: int
    experiments: int


@dataclass(frozen=True)
class RuntimeTimeoutsConfiguration:
    startup_seconds: int
    request_seconds: int
    shutdown_seconds: int


@dataclass(frozen=True)
class RuntimeResourceLimitsConfiguration:
    cpu_count: int
    memory_gb: int
    gpu_required: bool


@dataclass(frozen=True)
class RuntimeConfiguration:
    profile: str
    workers: RuntimeWorkersConfiguration
    timeouts: RuntimeTimeoutsConfiguration
    resource_limits: RuntimeResourceLimitsConfiguration


@dataclass(frozen=True)
class ApplicationConfiguration:
    application: ApplicationIdentityConfiguration
    deployment: DeploymentConfiguration
    services: ServicesConfiguration
    models: ModelsConfiguration
    paths: PathsConfiguration
    security: SecurityConfiguration
    quality_gates: QualityGatesConfiguration
    observability: ObservabilityConfiguration
    runtime: RuntimeConfiguration
    configuration_hash: str


def load_application_configuration(
    config_path: str | Path,
    environment_snapshot: Mapping[str, str],
) -> ApplicationConfiguration:
    path = _require_config_path(config_path)
    schema = _load_application_schema()
    _reject_environment_inputs(environment_snapshot, schema)
    payload = _read_configuration_payload(path)
    _reject_inline_secrets(payload)
    _validate_required_keys_and_values(payload, schema, schema, ())
    _validate_schema(payload, schema, path)
    _validate_cross_field_invariants(payload, path)
    return _build_application_configuration(payload, _configuration_hash(payload))


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _require_config_path(config_path: str | Path) -> Path:
    if config_path is None:
        raise ApplicationConfigurationError(
            CONFIG_FILE_REQUIRED, "chemin --config absent"
        )

    path_text = str(config_path)
    if path_text.strip() == "":
        raise ApplicationConfigurationError(
            CONFIG_FILE_REQUIRED, "chemin --config absent"
        )

    path = Path(path_text)
    if not path.is_file():
        raise ApplicationConfigurationError(
            CONFIG_FILE_UNREADABLE,
            "fichier de configuration absent ou non ouvrable",
            path_text,
        )
    return path


def _load_application_schema() -> Mapping[str, Any]:
    schema_path = _repository_root() / _SCHEMA_RELATIVE_PATH
    return json.loads(schema_path.read_text(encoding="utf-8-sig"))


def _read_configuration_payload(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ApplicationConfigurationError(
            CONFIG_FILE_UNREADABLE,
            "fichier de configuration illisible",
            str(path),
        ) from exc

    try:
        payload = _parse_application_yaml(content)
    except _ConfigurationSyntaxError as exc:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            f"YAML de configuration invalide: {exc}",
            str(path),
        ) from exc

    if not isinstance(payload, Mapping):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "configuration racine non objet",
            str(path),
        )
    return payload


class _ConfigurationSyntaxError(ValueError):
    pass


def _parse_application_yaml(content: str) -> Mapping[str, Any]:
    root: dict[str, Any] = {}
    lines = content.splitlines()
    stack: list[tuple[int, Any]] = [(-1, root)]

    for line_index, raw_line in enumerate(lines):
        if raw_line.strip() == "" or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line:
            raise _ConfigurationSyntaxError(
                f"tabulation interdite ligne {line_index + 1}"
            )

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2 != 0:
            raise _ConfigurationSyntaxError(
                f"indentation impaire ligne {line_index + 1}"
            )

        stripped = raw_line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise _ConfigurationSyntaxError(
                    f"entrée de liste sans liste parente ligne {line_index + 1}"
                )
            item_text = stripped[2:].strip()
            if item_text == "":
                raise _ConfigurationSyntaxError(
                    f"entrée de liste vide ligne {line_index + 1}"
                )
            parent.append(_parse_yaml_scalar(item_text))
            continue

        if ":" not in stripped:
            raise _ConfigurationSyntaxError(
                f"séparateur clé-valeur absent ligne {line_index + 1}"
            )

        key_text, value_text = stripped.split(":", 1)
        key = key_text.strip()
        if key == "":
            raise _ConfigurationSyntaxError(f"clé vide ligne {line_index + 1}")
        if not isinstance(parent, dict):
            raise _ConfigurationSyntaxError(
                f"clé sous liste scalaire ligne {line_index + 1}"
            )
        if key in parent:
            raise _ConfigurationSyntaxError(
                f"clé dupliquée ligne {line_index + 1}: {key}"
            )

        stripped_value = value_text.strip()
        if stripped_value == "":
            next_line = _next_yaml_content_line(lines, line_index + 1)
            if next_line is None:
                raise _ConfigurationSyntaxError(
                    f"valeur imbriquée absente ligne {line_index + 1}"
                )
            next_indent, next_stripped = next_line
            if next_indent <= indent:
                raise _ConfigurationSyntaxError(
                    f"valeur imbriquée absente ligne {line_index + 1}"
                )
            child: dict[str, Any] | list[Any]
            if next_stripped.startswith("- "):
                child = []
            else:
                child = {}
            parent[key] = child
            stack.append((indent, child))
            continue

        parent[key] = _parse_yaml_scalar(stripped_value)

    return root


def _next_yaml_content_line(
    lines: list[str], start_index: int
) -> tuple[int, str] | None:
    for raw_line in lines[start_index:]:
        if raw_line.strip() == "" or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        return indent, raw_line.strip()
    return None


def _parse_yaml_scalar(value: str) -> str | int | float | bool:
    if value == "true":
        return True
    if value == "false":
        return False
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    if re.fullmatch(r"[-+]?[0-9]+", value):
        return int(value)
    if re.fullmatch(r"[-+]?[0-9]+\.[0-9]+", value):
        return float(value)
    if value.startswith("[") or value.startswith("{"):
        raise _ConfigurationSyntaxError(f"syntaxe YAML non supportée: {value}")
    return value


def _reject_environment_inputs(
    environment_snapshot: Mapping[str, str],
    schema: Mapping[str, Any],
) -> None:
    rejected_names = _environment_homonyms_from_schema(schema)
    for environment_name in environment_snapshot:
        normalized_name = str(environment_name).upper()
        if normalized_name in _HISTORICAL_ENVIRONMENT_NAMES:
            raise ApplicationConfigurationError(
                CONFIG_ENV_INPUT_REJECTED,
                f"variable d'environnement applicative interdite: {environment_name}",
            )
        if any(
            normalized_name.startswith(prefix)
            for prefix in _HISTORICAL_ENVIRONMENT_PREFIXES
        ):
            raise ApplicationConfigurationError(
                CONFIG_ENV_INPUT_REJECTED,
                f"variable d'environnement applicative interdite: {environment_name}",
            )
        if normalized_name in rejected_names:
            raise ApplicationConfigurationError(
                CONFIG_ENV_INPUT_REJECTED,
                f"variable d'environnement homonyme interdite: {environment_name}",
            )


def _environment_homonyms_from_schema(schema: Mapping[str, Any]) -> frozenset[str]:
    names: set[str] = set(_HISTORICAL_ENVIRONMENT_NAMES)

    def walk(node: Mapping[str, Any], path_parts: tuple[str, ...]) -> None:
        resolved_node = _resolve_schema_node(node, schema)
        properties = resolved_node.get("properties")
        if isinstance(properties, Mapping):
            for property_name, property_schema in properties.items():
                walk(property_schema, (*path_parts, str(property_name)))
            return

        if len(path_parts) > 0:
            names.add("_".join(part.upper() for part in path_parts))

    walk(schema, ())
    return frozenset(names)


def _reject_inline_secrets(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _INLINE_SECRET_KEYS:
                raise ApplicationConfigurationError(
                    CONFIG_SECRET_INLINE_REJECTED,
                    f"secret en clair interdit dans la clé: {key}",
                )
            _reject_inline_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _reject_inline_secrets(item)


def _validate_required_keys_and_values(
    value: Any,
    schema_node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path_parts: tuple[str, ...],
) -> None:
    resolved_node = _resolve_schema_node(schema_node, root_schema)
    properties = resolved_node.get("properties")

    if isinstance(properties, Mapping):
        if not isinstance(value, Mapping):
            return

        for required_key in resolved_node.get("required", ()):
            if required_key not in value:
                raise ApplicationConfigurationError(
                    CONFIG_KEY_MISSING,
                    f"clé obligatoire absente: {_format_path((*path_parts, str(required_key)))}",
                )

        for key, item in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, Mapping):
                _validate_required_keys_and_values(
                    item,
                    child_schema,
                    root_schema,
                    (*path_parts, str(key)),
                )
        return

    if resolved_node.get("type") == "array" and isinstance(value, list):
        item_schema = resolved_node.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_required_keys_and_values(
                    item,
                    item_schema,
                    root_schema,
                    (*path_parts, str(index)),
                )
        return

    if resolved_node.get("type") == "string" and isinstance(value, str):
        if value.strip() == "" or value != value.strip() or value == _PLACEHOLDER_VALUE:
            raise ApplicationConfigurationError(
                CONFIG_KEY_EMPTY,
                f"clé obligatoire vide, non normalisée ou placeholder: {_format_path(path_parts)}",
            )


def _validate_schema(
    payload: Mapping[str, Any], schema: Mapping[str, Any], path: Path
) -> None:
    try:
        _validate_schema_node(payload, schema, schema, ())
    except _SchemaValidationError as exc:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            f"schéma invalide à {_format_path(exc.path_parts)}: {exc}",
            str(path),
        ) from exc


def _validate_cross_field_invariants(payload: Mapping[str, Any], path: Path) -> None:
    deployment_hosts = payload["deployment"]["hosts"]
    deployment_network = payload["deployment"]["network"]
    gateway_service = payload["services"]["llm_gateway"]
    security = payload["security"]
    workers = payload["services"]["workers"]
    runtime_resource_limits = payload["runtime"]["resource_limits"]

    if runtime_resource_limits["gpu_required"] is not True:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "runtime.resource_limits.gpu_required doit être true pour cuda:0",
            str(path),
        )

    if workers["docling_concurrency"] > workers["concurrency"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.workers.docling_concurrency ne peut pas dépasser services.workers.concurrency",
            str(path),
        )

    if workers["granite_concurrency"] > workers["concurrency"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.workers.granite_concurrency ne peut pas dépasser services.workers.concurrency",
            str(path),
        )

    if workers["granite_concurrency"] > workers["docling_concurrency"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.workers.granite_concurrency ne peut pas dépasser services.workers.docling_concurrency",
            str(path),
        )

    if (
        workers["granite_concurrency"] != 1
        or workers["local_distribution"]["granite_slots_per_worker"] != 1
        or workers["granite_concurrency"]
        != workers["local_distribution"]["granite_slots_per_worker"]
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.workers.granite_concurrency et granite_slots_per_worker doivent être égaux à 1",
            str(path),
        )

    docker_host = deployment_hosts["docker_local"]
    host_bind = docker_host["bind_host"]
    public_bindings = {"", "0.0.0.0", "::", "[::]", "*"}
    loopback_bindings = {"127.0.0.1", "localhost", "::1", "[::1]"}

    if (
        security["network_exposure"] == "loopback_only"
        and host_bind not in loopback_bindings
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "security.network_exposure=loopback_only exige deployment.hosts.docker_local.bind_host loopback",
            str(path),
        )
    if not security["allow_public_bind"] and host_bind in public_bindings:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "security.allow_public_bind=false interdit deployment.hosts.docker_local.bind_host public",
            str(path),
        )
    if docker_host["public_access"] and (
        security["network_exposure"] == "loopback_only"
        or not security["allow_public_bind"]
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "deployment.hosts.docker_local.public_access=true exige une exposition réseau publique explicite",
            str(path),
        )

    if deployment_network["prefer_mtls"] and not deployment_network["require_tls"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "prefer_mtls exige require_tls",
            str(path),
        )
    if deployment_network["require_tls"] and gateway_service["tls_mode"] != "ca_bundle":
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "require_tls exige services.llm_gateway.tls_mode=ca_bundle",
            str(path),
        )
    if (
        not deployment_network["require_tls"]
        and gateway_service["tls_mode"] == "ca_bundle"
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.tls_mode=ca_bundle exige require_tls",
            str(path),
        )
    if (
        deployment_network["require_api_key"]
        and gateway_service["auth_mode"] != "api_key_file"
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "require_api_key exige services.llm_gateway.auth_mode=api_key_file",
            str(path),
        )
    if (
        not deployment_network["require_api_key"]
        and gateway_service["auth_mode"] == "api_key_file"
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.auth_mode=api_key_file exige require_api_key",
            str(path),
        )

    _validate_spark_endpoint_invariants(
        deployment_hosts["spark_inference"],
        gateway_service["spark_endpoint_url"],
        path,
    )
    _validate_persistent_service_invariants(payload["services"], path)


def _validate_persistent_service_invariants(
    services: Mapping[str, Any],
    path: Path,
) -> None:
    postgres = services["postgres"]
    parsed_postgres = urlparse(postgres["url"])
    if (
        parsed_postgres.scheme not in {"postgresql", "postgresql+psycopg"}
        or parsed_postgres.hostname is None
    ):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.postgres.url doit être une URL PostgreSQL explicite",
            str(path),
        )
    if parsed_postgres.password is not None:
        raise ApplicationConfigurationError(
            CONFIG_SECRET_INLINE_REJECTED,
            "services.postgres.url interdit un mot de passe en clair",
            str(path),
        )
    if unquote(parsed_postgres.username or "") != postgres["role"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.postgres.role doit correspondre à l'utilisateur de l'URL",
            str(path),
        )
    if unquote(parsed_postgres.path.removeprefix("/")) != postgres["database"]:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.postgres.database doit correspondre à la base de l'URL",
            str(path),
        )

    parsed_qdrant = urlparse(services["qdrant"]["url"])
    if parsed_qdrant.scheme not in {"http", "https"} or parsed_qdrant.hostname is None:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.qdrant.url doit être une URL HTTP explicite",
            str(path),
        )
    if parsed_qdrant.username is not None or parsed_qdrant.password is not None:
        raise ApplicationConfigurationError(
            CONFIG_SECRET_INLINE_REJECTED,
            "services.qdrant.url interdit les credentials en clair",
            str(path),
        )


def _validate_spark_endpoint_invariants(
    spark_host: Mapping[str, Any],
    spark_endpoint_url: str,
    path: Path,
) -> None:
    parsed_endpoint = urlparse(spark_endpoint_url)
    if parsed_endpoint.scheme not in {"http", "https"} or parsed_endpoint.netloc == "":
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url doit être une URL HTTP explicite",
            str(path),
        )
    if parsed_endpoint.username is not None or parsed_endpoint.password is not None:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url interdit les identifiants",
            str(path),
        )
    if parsed_endpoint.path != "/v1":
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url doit cibler /v1",
            str(path),
        )
    try:
        parsed_port = parsed_endpoint.port
    except ValueError as exc:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url porte un port invalide",
            str(path),
        ) from exc
    if parsed_port is None:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url doit déclarer un port",
            str(path),
        )

    allowed_hosts = {
        "spark-inference",
        "spark-inference.test",
        spark_host["dns_name"],
        *spark_host["endpoint_hosts"],
    }
    if parsed_endpoint.hostname not in allowed_hosts:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "services.llm_gateway.spark_endpoint_url doit cibler un hôte Spark déclaré",
            str(path),
        )


class _SchemaValidationError(ValueError):
    def __init__(self, message: str, path_parts: tuple[str, ...]) -> None:
        self.path_parts = path_parts
        super().__init__(message)


def _validate_schema_node(
    value: Any,
    schema_node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path_parts: tuple[str, ...],
) -> None:
    resolved_node = _resolve_schema_node(schema_node, root_schema)

    expected_type = resolved_node.get("type")
    if isinstance(expected_type, str):
        _validate_json_schema_type(value, expected_type, path_parts)

    if "enum" in resolved_node and value not in resolved_node["enum"]:
        raise _SchemaValidationError("valeur hors enum", path_parts)

    if "const" in resolved_node and value != resolved_node["const"]:
        raise _SchemaValidationError("valeur const différente", path_parts)

    if isinstance(value, str):
        min_length = resolved_node.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise _SchemaValidationError("chaîne trop courte", path_parts)

        pattern = resolved_node.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise _SchemaValidationError("motif de chaîne non respecté", path_parts)

    if _is_json_number(value):
        minimum = resolved_node.get("minimum")
        if _is_json_number(minimum) and value < minimum:
            raise _SchemaValidationError("nombre sous le minimum", path_parts)

        maximum = resolved_node.get("maximum")
        if _is_json_number(maximum) and value > maximum:
            raise _SchemaValidationError("nombre au-dessus du maximum", path_parts)

    if isinstance(value, Mapping):
        properties = resolved_node.get("properties")
        if isinstance(properties, Mapping):
            for required_key in resolved_node.get("required", ()):
                if required_key not in value:
                    raise _SchemaValidationError(
                        f"clé obligatoire absente: {required_key}",
                        (*path_parts, str(required_key)),
                    )

            additional_properties = resolved_node.get("additionalProperties")
            for key, item in value.items():
                if key in properties:
                    child_schema = properties[key]
                    if not isinstance(child_schema, Mapping):
                        raise _SchemaValidationError(
                            "schéma de propriété non objet", (*path_parts, str(key))
                        )
                    _validate_schema_node(
                        item, child_schema, root_schema, (*path_parts, str(key))
                    )
                    continue

                if additional_properties is False:
                    raise _SchemaValidationError(
                        "propriété inconnue interdite", (*path_parts, str(key))
                    )

    if isinstance(value, list):
        min_items = resolved_node.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise _SchemaValidationError("liste trop courte", path_parts)

        item_schema = resolved_node.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema_node(
                    item, item_schema, root_schema, (*path_parts, str(index))
                )

    not_schema = resolved_node.get("not")
    if isinstance(not_schema, Mapping) and _matches_schema_node(
        value, not_schema, root_schema, path_parts
    ):
        raise _SchemaValidationError("condition not violée", path_parts)


def _matches_schema_node(
    value: Any,
    schema_node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path_parts: tuple[str, ...],
) -> bool:
    try:
        _validate_schema_node(value, schema_node, root_schema, path_parts)
    except _SchemaValidationError:
        return False
    return True


def _validate_json_schema_type(
    value: Any, expected_type: str, path_parts: tuple[str, ...]
) -> None:
    if expected_type == "object":
        if not isinstance(value, Mapping):
            raise _SchemaValidationError("objet attendu", path_parts)
        return
    if expected_type == "array":
        if not isinstance(value, list):
            raise _SchemaValidationError("liste attendue", path_parts)
        return
    if expected_type == "string":
        if not isinstance(value, str):
            raise _SchemaValidationError("chaîne attendue", path_parts)
        return
    if expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise _SchemaValidationError("entier attendu", path_parts)
        return
    if expected_type == "number":
        if not _is_json_number(value):
            raise _SchemaValidationError("nombre attendu", path_parts)
        return
    if expected_type == "boolean":
        if not isinstance(value, bool):
            raise _SchemaValidationError("booléen attendu", path_parts)
        return
    raise _SchemaValidationError(
        f"type de schéma non supporté: {expected_type}", path_parts
    )


def _is_json_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _resolve_schema_node(
    schema_node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    reference = schema_node.get("$ref")
    if not isinstance(reference, str):
        return schema_node

    if not reference.startswith("#/"):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID, f"référence de schéma externe interdite: {reference}"
        )

    resolved: Any = root_schema
    for part in reference[2:].split("/"):
        resolved = resolved[part]
    if not isinstance(resolved, Mapping):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID, f"référence de schéma non objet: {reference}"
        )
    return resolved


def _configuration_hash(payload: Mapping[str, Any]) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _build_application_configuration(
    payload: Mapping[str, Any],
    configuration_hash: str,
) -> ApplicationConfiguration:
    application = payload["application"]
    deployment = payload["deployment"]
    deployment_hosts = deployment["hosts"]
    deployment_network = deployment["network"]
    deployment_placement = deployment["placement"]
    services = payload["services"]
    llm_model = payload["models"]["llm"]
    paths = payload["paths"]
    security = payload["security"]
    secrets = security["secrets"]
    audit = security["audit"]
    quality_gates = payload["quality_gates"]
    observability = payload["observability"]
    runtime = payload["runtime"]

    return ApplicationConfiguration(
        application=ApplicationIdentityConfiguration(
            environment=application["environment"],
            deployment_id=application["deployment_id"],
        ),
        deployment=DeploymentConfiguration(
            topology=deployment["topology"],
            hosts=DeploymentHostsConfiguration(
                docker_local=DockerLocalHostConfiguration(
                    role=deployment_hosts["docker_local"]["role"],
                    bind_host=deployment_hosts["docker_local"]["bind_host"],
                    container_listen_host=deployment_hosts["docker_local"][
                        "container_listen_host"
                    ],
                    public_access=deployment_hosts["docker_local"]["public_access"],
                ),
                spark_inference=SparkInferenceHostConfiguration(
                    role=deployment_hosts["spark_inference"]["role"],
                    dns_name=deployment_hosts["spark_inference"]["dns_name"],
                    endpoint_hosts=tuple(
                        deployment_hosts["spark_inference"]["endpoint_hosts"]
                    ),
                    allowed_client_cidrs=tuple(
                        deployment_hosts["spark_inference"]["allowed_client_cidrs"]
                    ),
                ),
            ),
            network=DeploymentNetworkConfiguration(
                require_tls=deployment_network["require_tls"],
                require_api_key=deployment_network["require_api_key"],
                prefer_mtls=deployment_network["prefer_mtls"],
            ),
            placement=DeploymentPlacementConfiguration(
                application=deployment_placement["application"],
                postgres=deployment_placement["postgres"],
                qdrant=deployment_placement["qdrant"],
                llm_gateway=deployment_placement["llm_gateway"],
                gemma_vllm=deployment_placement["gemma_vllm"],
            ),
        ),
        services=ServicesConfiguration(
            postgres=PostgresServiceConfiguration(
                url=services["postgres"]["url"],
                port=services["postgres"]["port"],
                database=services["postgres"]["database"],
                role=services["postgres"]["role"],
                data_volume=services["postgres"]["data_volume"],
            ),
            qdrant=QdrantServiceConfiguration(
                url=services["qdrant"]["url"],
                port=services["qdrant"]["port"],
                instance_id=services["qdrant"]["instance_id"],
                storage_volume=services["qdrant"]["storage_volume"],
                collections=QdrantCollectionsConfiguration(
                    datastore_identity=services["qdrant"]["collections"][
                        "datastore_identity"
                    ],
                    knowledge_access=services["qdrant"]["collections"][
                        "knowledge_access"
                    ],
                ),
            ),
            api=ApiServiceConfiguration(
                bind_host=services["api"]["bind_host"],
                port=services["api"]["port"],
            ),
            workers=WorkerServiceConfiguration(
                queue_name=services["workers"]["queue_name"],
                outbox_namespace=services["workers"]["outbox_namespace"],
                progress_namespace=services["workers"]["progress_namespace"],
                document_orchestration_version=services["workers"][
                    "document_orchestration_version"
                ],
                concurrency=services["workers"]["concurrency"],
                docling_concurrency=services["workers"]["docling_concurrency"],
                granite_concurrency=services["workers"]["granite_concurrency"],
                local_distribution=LocalDocumentDistributionConfiguration(
                    replicas=services["workers"]["local_distribution"]["replicas"],
                    memory_bytes=services["workers"]["local_distribution"][
                        "memory_bytes"
                    ],
                    cpus=services["workers"]["local_distribution"]["cpus"],
                    granite_device=services["workers"]["local_distribution"][
                        "granite_device"
                    ],
                    granite_slots_global=services["workers"]["local_distribution"][
                        "granite_slots_global"
                    ],
                    granite_slots_per_worker=services["workers"]["local_distribution"][
                        "granite_slots_per_worker"
                    ],
                ),
            ),
            llm_gateway=LLMGatewayServiceConfiguration(
                url=services["llm_gateway"]["url"],
                port=services["llm_gateway"]["port"],
                spark_endpoint_url=services["llm_gateway"]["spark_endpoint_url"],
                auth_mode=services["llm_gateway"]["auth_mode"],
                tls_mode=services["llm_gateway"]["tls_mode"],
                timeout_seconds=services["llm_gateway"]["timeout_seconds"],
                retry_before_first_token=services["llm_gateway"][
                    "retry_before_first_token"
                ],
                circuit_breaker_failure_threshold=services["llm_gateway"][
                    "circuit_breaker_failure_threshold"
                ],
                circuit_breaker_reset_seconds=services["llm_gateway"][
                    "circuit_breaker_reset_seconds"
                ],
            ),
        ),
        models=ModelsConfiguration(
            llm=LLMModelConfiguration(
                provider=llm_model["provider"],
                transport=llm_model["transport"],
                reference_model=llm_model["reference_model"],
                served_model_name=llm_model["served_model_name"],
                model_revision=llm_model["model_revision"],
                runtime=llm_model["runtime"],
                runtime_version=llm_model["runtime_version"],
                context_length_tokens=llm_model["context_length_tokens"],
                max_output_tokens=llm_model["max_output_tokens"],
                temperature=llm_model["temperature"],
            ),
        ),
        paths=PathsConfiguration(
            data_root=paths["data_root"],
            corpus_root=paths["corpus_root"],
            canonical_sources_root=paths["canonical_sources_root"],
            qdrant_storage_root=paths["qdrant_storage_root"],
            postgres_data_root=paths["postgres_data_root"],
            reports_root=paths["reports_root"],
            logs_root=paths["logs_root"],
            experiments_root=paths["experiments_root"],
            cache_root=paths["cache_root"],
            corpus_quota_bytes=paths["corpus_quota_bytes"],
        ),
        security=SecurityConfiguration(
            network_exposure=security["network_exposure"],
            allow_public_bind=security["allow_public_bind"],
            secrets=SecretPathsConfiguration(
                postgres_password_path=secrets["postgres_password_path"],
                qdrant_api_key_path=secrets["qdrant_api_key_path"],
                llm_gateway_api_key_path=secrets["llm_gateway_api_key_path"],
                tls_ca_certificate_path=secrets["tls_ca_certificate_path"],
                local_api_token_path=secrets["local_api_token_path"],
            ),
            audit=SecurityAuditConfiguration(
                configuration_hash_required=audit["configuration_hash_required"],
                log_configuration_changes=audit["log_configuration_changes"],
            ),
        ),
        quality_gates=QualityGatesConfiguration(
            post_conversion=PostConversionQualityGateConfiguration(
                page_count_match=quality_gates["post_conversion"]["page_count_match"],
                provenance_coverage_min=quality_gates["post_conversion"][
                    "provenance_coverage_min"
                ],
                missing_page_max=quality_gates["post_conversion"]["missing_page_max"],
            ),
            retrieval=RetrievalQualityGateConfiguration(
                citation_required=quality_gates["retrieval"]["citation_required"],
                min_evidence_candidates=quality_gates["retrieval"][
                    "min_evidence_candidates"
                ],
            ),
            answering=AnsweringQualityGateConfiguration(
                unsupported_claim_policy=quality_gates["answering"][
                    "unsupported_claim_policy"
                ],
                abstention_required_on_insufficient_evidence=quality_gates["answering"][
                    "abstention_required_on_insufficient_evidence"
                ],
            ),
            llm=LLMQualityGateConfiguration(
                real_path_required=quality_gates["llm"]["real_path_required"],
                fallback_model_allowed=quality_gates["llm"]["fallback_model_allowed"],
            ),
        ),
        observability=ObservabilityConfiguration(
            tracing=TracingConfiguration(
                enabled=observability["tracing"]["enabled"],
            ),
            logs=LogsConfiguration(
                include_payloads=observability["logs"]["include_payloads"],
            ),
        ),
        runtime=RuntimeConfiguration(
            profile=runtime["profile"],
            workers=RuntimeWorkersConfiguration(
                ingestion=runtime["workers"]["ingestion"],
                research=runtime["workers"]["research"],
                experiments=runtime["workers"]["experiments"],
            ),
            timeouts=RuntimeTimeoutsConfiguration(
                startup_seconds=runtime["timeouts"]["startup_seconds"],
                request_seconds=runtime["timeouts"]["request_seconds"],
                shutdown_seconds=runtime["timeouts"]["shutdown_seconds"],
            ),
            resource_limits=RuntimeResourceLimitsConfiguration(
                cpu_count=runtime["resource_limits"]["cpu_count"],
                memory_gb=runtime["resource_limits"]["memory_gb"],
                gpu_required=runtime["resource_limits"]["gpu_required"],
            ),
        ),
        configuration_hash=configuration_hash,
    )


def _format_path(path_parts: tuple[str, ...]) -> str:
    if len(path_parts) == 0:
        return "application"
    return "application." + ".".join(path_parts)


__all__ = [
    "CONFIG_ENV_INPUT_REJECTED",
    "CONFIG_FILE_REQUIRED",
    "CONFIG_FILE_UNREADABLE",
    "CONFIG_KEY_EMPTY",
    "CONFIG_KEY_MISSING",
    "CONFIG_SCHEMA_INVALID",
    "CONFIG_SECRET_INLINE_REJECTED",
    "ApiServiceConfiguration",
    "ApplicationConfiguration",
    "ApplicationConfigurationError",
    "ApplicationIdentityConfiguration",
    "DeploymentConfiguration",
    "DeploymentHostsConfiguration",
    "DeploymentNetworkConfiguration",
    "DeploymentPlacementConfiguration",
    "DockerLocalHostConfiguration",
    "PostgresServiceConfiguration",
    "QdrantCollectionsConfiguration",
    "QdrantServiceConfiguration",
    "LLMGatewayServiceConfiguration",
    "LLMModelConfiguration",
    "LocalDocumentDistributionConfiguration",
    "ModelsConfiguration",
    "ObservabilityConfiguration",
    "PathsConfiguration",
    "QualityGatesConfiguration",
    "RuntimeConfiguration",
    "SecurityConfiguration",
    "ServicesConfiguration",
    "SparkInferenceHostConfiguration",
    "WorkerServiceConfiguration",
    "load_application_configuration",
]
