"""Chargement strict de configuration applicative M13-config."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml


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
_INLINE_SECRET_KEYS = frozenset({"password", "token", "api_key", "secret", "secret_value"})


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
class DockerLocalHostConfiguration:
    role: str
    bind_host: str
    public_access: bool


@dataclass(frozen=True)
class SparkInferenceHostConfiguration:
    role: str
    dns_name: str
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
class EndpointServiceConfiguration:
    url: str
    port: int


@dataclass(frozen=True)
class ApiServiceConfiguration:
    bind_host: str
    port: int


@dataclass(frozen=True)
class WorkerServiceConfiguration:
    queue_name: str
    concurrency: int


@dataclass(frozen=True)
class LLMGatewayServiceConfiguration:
    url: str
    port: int
    spark_endpoint_url: str
    timeout_seconds: int
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: int


@dataclass(frozen=True)
class ServicesConfiguration:
    postgres: EndpointServiceConfiguration
    qdrant: EndpointServiceConfiguration
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


@dataclass(frozen=True)
class SecretPathsConfiguration:
    postgres_password_path: str
    llm_gateway_api_key_path: str
    tls_ca_certificate_path: str


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
class MetricsConfiguration:
    bind_host: str
    port: int


@dataclass(frozen=True)
class TracingConfiguration:
    enabled: bool
    endpoint_path: str


@dataclass(frozen=True)
class LogsConfiguration:
    level: str
    retention_days: int
    include_payloads: bool


@dataclass(frozen=True)
class ObservabilityConfiguration:
    metrics: MetricsConfiguration
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
    return _build_application_configuration(payload, _configuration_hash(payload))


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _require_config_path(config_path: str | Path) -> Path:
    if config_path is None:
        raise ApplicationConfigurationError(CONFIG_FILE_REQUIRED, "chemin --config absent")

    path_text = str(config_path)
    if path_text.strip() == "":
        raise ApplicationConfigurationError(CONFIG_FILE_REQUIRED, "chemin --config absent")

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
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "YAML de configuration invalide",
            str(path),
        ) from exc

    if not isinstance(payload, Mapping):
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            "configuration racine non objet",
            str(path),
        )
    return payload


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
        if any(normalized_name.startswith(prefix) for prefix in _HISTORICAL_ENVIRONMENT_PREFIXES):
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
        if value.strip() == "" or value == _PLACEHOLDER_VALUE:
            raise ApplicationConfigurationError(
                CONFIG_KEY_EMPTY,
                f"clé obligatoire vide ou placeholder: {_format_path(path_parts)}",
            )


def _validate_schema(payload: Mapping[str, Any], schema: Mapping[str, Any], path: Path) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if len(errors) > 0:
        first_error = errors[0]
        error_path = _format_path(tuple(str(part) for part in first_error.absolute_path))
        raise ApplicationConfigurationError(
            CONFIG_SCHEMA_INVALID,
            f"schéma invalide à {error_path}: {first_error.message}",
            str(path),
        )


def _resolve_schema_node(
    schema_node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    reference = schema_node.get("$ref")
    if not isinstance(reference, str):
        return schema_node

    if not reference.startswith("#/"):
        raise ApplicationConfigurationError(CONFIG_SCHEMA_INVALID, f"référence de schéma externe interdite: {reference}")

    resolved: Any = root_schema
    for part in reference[2:].split("/"):
        resolved = resolved[part]
    if not isinstance(resolved, Mapping):
        raise ApplicationConfigurationError(CONFIG_SCHEMA_INVALID, f"référence de schéma non objet: {reference}")
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
        deployment=DeploymentConfiguration(
            topology=deployment["topology"],
            hosts=DeploymentHostsConfiguration(
                docker_local=DockerLocalHostConfiguration(
                    role=deployment_hosts["docker_local"]["role"],
                    bind_host=deployment_hosts["docker_local"]["bind_host"],
                    public_access=deployment_hosts["docker_local"]["public_access"],
                ),
                spark_inference=SparkInferenceHostConfiguration(
                    role=deployment_hosts["spark_inference"]["role"],
                    dns_name=deployment_hosts["spark_inference"]["dns_name"],
                    allowed_client_cidrs=tuple(deployment_hosts["spark_inference"]["allowed_client_cidrs"]),
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
            postgres=EndpointServiceConfiguration(
                url=services["postgres"]["url"],
                port=services["postgres"]["port"],
            ),
            qdrant=EndpointServiceConfiguration(
                url=services["qdrant"]["url"],
                port=services["qdrant"]["port"],
            ),
            api=ApiServiceConfiguration(
                bind_host=services["api"]["bind_host"],
                port=services["api"]["port"],
            ),
            workers=WorkerServiceConfiguration(
                queue_name=services["workers"]["queue_name"],
                concurrency=services["workers"]["concurrency"],
            ),
            llm_gateway=LLMGatewayServiceConfiguration(
                url=services["llm_gateway"]["url"],
                port=services["llm_gateway"]["port"],
                spark_endpoint_url=services["llm_gateway"]["spark_endpoint_url"],
                timeout_seconds=services["llm_gateway"]["timeout_seconds"],
                circuit_breaker_failure_threshold=services["llm_gateway"]["circuit_breaker_failure_threshold"],
                circuit_breaker_reset_seconds=services["llm_gateway"]["circuit_breaker_reset_seconds"],
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
        ),
        security=SecurityConfiguration(
            network_exposure=security["network_exposure"],
            allow_public_bind=security["allow_public_bind"],
            secrets=SecretPathsConfiguration(
                postgres_password_path=secrets["postgres_password_path"],
                llm_gateway_api_key_path=secrets["llm_gateway_api_key_path"],
                tls_ca_certificate_path=secrets["tls_ca_certificate_path"],
            ),
            audit=SecurityAuditConfiguration(
                configuration_hash_required=audit["configuration_hash_required"],
                log_configuration_changes=audit["log_configuration_changes"],
            ),
        ),
        quality_gates=QualityGatesConfiguration(
            post_conversion=PostConversionQualityGateConfiguration(
                page_count_match=quality_gates["post_conversion"]["page_count_match"],
                provenance_coverage_min=quality_gates["post_conversion"]["provenance_coverage_min"],
                missing_page_max=quality_gates["post_conversion"]["missing_page_max"],
            ),
            retrieval=RetrievalQualityGateConfiguration(
                citation_required=quality_gates["retrieval"]["citation_required"],
                min_evidence_candidates=quality_gates["retrieval"]["min_evidence_candidates"],
            ),
            answering=AnsweringQualityGateConfiguration(
                unsupported_claim_policy=quality_gates["answering"]["unsupported_claim_policy"],
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
            metrics=MetricsConfiguration(
                bind_host=observability["metrics"]["bind_host"],
                port=observability["metrics"]["port"],
            ),
            tracing=TracingConfiguration(
                enabled=observability["tracing"]["enabled"],
                endpoint_path=observability["tracing"]["endpoint_path"],
            ),
            logs=LogsConfiguration(
                level=observability["logs"]["level"],
                retention_days=observability["logs"]["retention_days"],
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
    "DeploymentConfiguration",
    "DeploymentHostsConfiguration",
    "DeploymentNetworkConfiguration",
    "DeploymentPlacementConfiguration",
    "DockerLocalHostConfiguration",
    "EndpointServiceConfiguration",
    "LLMGatewayServiceConfiguration",
    "LLMModelConfiguration",
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
