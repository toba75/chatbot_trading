"""Registre strict de topologie plateforme M-002."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DOCKER_LOCAL_HOST = "docker-local"
SPARK_INFERENCE_HOST = "spark-inference"
GEMMA_VLLM_SERVICE_ID = "gemma-vllm"
SPARK_MODEL_CACHE_SERVICE_ID = "spark-model-cache"

EXPECTED_HOST_RESPONSIBILITIES = {
    DOCKER_LOCAL_HOST: "business_data_and_local_processing",
    SPARK_INFERENCE_HOST: "gemma_inference_only",
}

EXPECTED_SERVICE_HOSTS = {
    GEMMA_VLLM_SERVICE_ID: SPARK_INFERENCE_HOST,
    SPARK_MODEL_CACHE_SERVICE_ID: SPARK_INFERENCE_HOST,
    "edge-gateway": DOCKER_LOCAL_HOST,
    "ui": DOCKER_LOCAL_HOST,
    "orchestrator-api": DOCKER_LOCAL_HOST,
    "llm-gateway": DOCKER_LOCAL_HOST,
    "granite-docling": DOCKER_LOCAL_HOST,
    "embedding-service": DOCKER_LOCAL_HOST,
    "reranker-service": DOCKER_LOCAL_HOST,
    "postgres": DOCKER_LOCAL_HOST,
    "qdrant": DOCKER_LOCAL_HOST,
    "corpus-store": DOCKER_LOCAL_HOST,
    "experiment-registry": DOCKER_LOCAL_HOST,
    "outbox": DOCKER_LOCAL_HOST,
    "job-queue": DOCKER_LOCAL_HOST,
    "worker-documents": DOCKER_LOCAL_HOST,
    "worker-research": DOCKER_LOCAL_HOST,
    "worker-backtest": DOCKER_LOCAL_HOST,
    "backtest-engine": DOCKER_LOCAL_HOST,
}

ALLOWED_SERVICE_KINDS = frozenset(
    {
        "application",
        "backtest",
        "corpus",
        "document-processing",
        "embedding",
        "entrypoint",
        "experiment-registry",
        "inference",
        "job-queue",
        "llm-gateway",
        "model-cache",
        "outbox",
        "reranker",
        "storage",
        "ui",
        "worker",
    }
)

ALLOWED_DURABILITY = frozenset(
    {
        "durable_business",
        "durable_technical",
        "regenerable_cache",
        "stateless",
    }
)

LOCAL_PROCESSING_KINDS = frozenset(
    {
        "application",
        "backtest",
        "corpus",
        "document-processing",
        "embedding",
        "entrypoint",
        "experiment-registry",
        "job-queue",
        "llm-gateway",
        "outbox",
        "reranker",
        "storage",
        "ui",
        "worker",
    }
)


@dataclass(frozen=True)
class HostPlacement:
    id: str
    exclusive_responsibility: str
    business_storage_allowed: bool
    durable_business_storage_allowed: bool


@dataclass(frozen=True)
class ServicePlacement:
    id: str
    host: str
    kind: str
    compose_local: bool
    business_storage: bool
    durability: str
    responsibility: str


@dataclass(frozen=True)
class PlatformTopology:
    schema_version: str
    architecture_decisions: tuple[str, ...]
    hosts: tuple[HostPlacement, ...]
    services: tuple[ServicePlacement, ...]

    def host(self, host_id: str) -> HostPlacement:
        for host in self.hosts:
            if host.id == host_id:
                return host
        raise ValueError(f"Hôte inconnu dans la topologie: {host_id}")

    def service(self, service_id: str) -> ServicePlacement:
        for service in self.services:
            if service.id == service_id:
                return service
        raise ValueError(f"Service inconnu dans la topologie: {service_id}")


def load_platform_topology(path: str | Path) -> PlatformTopology:
    registry_path = Path(path)
    payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    return parse_platform_topology_registry(payload)


def parse_platform_topology_registry(payload: Mapping[str, Any]) -> PlatformTopology:
    if not isinstance(payload, Mapping):
        raise ValueError("Registre de topologie non objet.")

    schema_version = _required_text(payload, "schema_version", "registre de topologie")
    if schema_version != "1.0":
        raise ValueError(f"schema_version de topologie non supportée: {schema_version}")

    architecture_decisions = _required_text_list(payload, "architecture_decisions", "registre de topologie")
    for adr_id in ("ADR-007", "ADR-009"):
        if adr_id not in architecture_decisions:
            raise ValueError(f"ADR de topologie absente: {adr_id}")

    hosts = tuple(_parse_hosts(_required_object_list(payload, "hosts", "registre de topologie")))
    services = tuple(_parse_services(_required_object_list(payload, "services", "registre de topologie")))

    topology = PlatformTopology(
        schema_version=schema_version,
        architecture_decisions=tuple(architecture_decisions),
        hosts=hosts,
        services=services,
    )
    _validate_topology(topology)
    return topology


def _parse_hosts(host_payloads: tuple[Mapping[str, Any], ...]) -> tuple[HostPlacement, ...]:
    hosts: list[HostPlacement] = []
    seen_ids: set[str] = set()
    seen_responsibilities: set[str] = set()

    for payload in host_payloads:
        host_id = _required_text(payload, "id", "hôte")
        if host_id in seen_ids:
            raise ValueError(f"Hôte dupliqué dans la topologie: {host_id}")
        if host_id not in EXPECTED_HOST_RESPONSIBILITIES:
            raise ValueError(f"Hôte inconnu dans le registre: {host_id}")

        exclusive_responsibility = _required_text(payload, "exclusive_responsibility", f"hôte {host_id}")
        if exclusive_responsibility in seen_responsibilities:
            raise ValueError(f"Responsabilité exclusive dupliquée: {exclusive_responsibility}")
        if exclusive_responsibility != EXPECTED_HOST_RESPONSIBILITIES[host_id]:
            raise ValueError(
                f"Responsabilité exclusive invalide pour {host_id}: {exclusive_responsibility}"
            )

        seen_ids.add(host_id)
        seen_responsibilities.add(exclusive_responsibility)
        hosts.append(
            HostPlacement(
                id=host_id,
                exclusive_responsibility=exclusive_responsibility,
                business_storage_allowed=_required_bool(
                    payload,
                    "business_storage_allowed",
                    f"hôte {host_id}",
                ),
                durable_business_storage_allowed=_required_bool(
                    payload,
                    "durable_business_storage_allowed",
                    f"hôte {host_id}",
                ),
            )
        )

    for expected_host_id in EXPECTED_HOST_RESPONSIBILITIES:
        if expected_host_id not in seen_ids:
            raise ValueError(f"Hôte attendu absent: {expected_host_id}")

    return tuple(hosts)


def _parse_services(service_payloads: tuple[Mapping[str, Any], ...]) -> tuple[ServicePlacement, ...]:
    services: list[ServicePlacement] = []
    seen_ids: set[str] = set()

    for payload in service_payloads:
        service_id = _required_text(payload, "id", "service")
        if service_id in seen_ids:
            raise ValueError(f"Service dupliqué dans la topologie: {service_id}")
        if service_id not in EXPECTED_SERVICE_HOSTS:
            raise ValueError(f"Service non prévu par M-002: {service_id}")

        host = _required_service_host(payload, service_id)
        kind = _required_text(payload, "kind", f"service {service_id}")
        if kind not in ALLOWED_SERVICE_KINDS:
            raise ValueError(f"Type de service inconnu pour {service_id}: {kind}")

        durability = _required_text(payload, "durability", f"service {service_id}")
        if durability not in ALLOWED_DURABILITY:
            raise ValueError(f"Durabilité inconnue pour {service_id}: {durability}")

        seen_ids.add(service_id)
        services.append(
            ServicePlacement(
                id=service_id,
                host=host,
                kind=kind,
                compose_local=_required_bool(payload, "compose_local", f"service {service_id}"),
                business_storage=_required_bool(payload, "business_storage", f"service {service_id}"),
                durability=durability,
                responsibility=_required_text(payload, "responsibility", f"service {service_id}"),
            )
        )

    for expected_service_id in EXPECTED_SERVICE_HOSTS:
        if expected_service_id not in seen_ids:
            raise ValueError(f"Service attendu absent: {expected_service_id}")

    return tuple(services)


def _validate_topology(topology: PlatformTopology) -> None:
    hosts_by_id = {host.id: host for host in topology.hosts}

    for service in topology.services:
        if service.host not in hosts_by_id:
            raise ValueError(f"Hôte inconnu pour service {service.id}: {service.host}")

        if service.id == GEMMA_VLLM_SERVICE_ID and (
            service.host != SPARK_INFERENCE_HOST or service.compose_local
        ):
            raise ValueError(f"Gemma/vLLM principal interdit dans Compose local: {service.id}")

        if service.host == SPARK_INFERENCE_HOST and service.business_storage:
            raise ValueError(f"Stockage métier interdit sur spark-inference: {service.id}")

        if service.host == SPARK_INFERENCE_HOST and service.kind in LOCAL_PROCESSING_KINDS:
            raise ValueError(f"Traitement local interdit sur spark-inference: {service.id}")

        if service.id == SPARK_MODEL_CACHE_SERVICE_ID and (
            service.host != SPARK_INFERENCE_HOST
            or service.business_storage
            or service.durability != "regenerable_cache"
        ):
            raise ValueError(f"Cache Spark non régénérable: {service.id}")

        expected_host = EXPECTED_SERVICE_HOSTS[service.id]
        if service.host != expected_host:
            raise ValueError(
                f"Placement invalide pour service {service.id}. "
                f"Attendu: {expected_host}. Obtenu: {service.host}"
            )

    spark_host = hosts_by_id[SPARK_INFERENCE_HOST]
    if spark_host.business_storage_allowed or spark_host.durable_business_storage_allowed:
        raise ValueError("Stockage métier durable interdit sur hôte: spark-inference")


def _required_service_host(payload: Mapping[str, Any], service_id: str) -> str:
    if "host" not in payload:
        raise ValueError(f"Hôte explicite absent pour service: {service_id}")

    host = payload["host"]
    if not isinstance(host, str):
        raise ValueError(f"Hôte non textuel pour service: {service_id}")
    if host.strip() == "":
        raise ValueError(f"Hôte explicite absent pour service: {service_id}")
    if host != host.strip():
        raise ValueError(f"Hôte non normalisé pour service: {service_id}")
    return host


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


def _required_bool(payload: Mapping[str, Any], field_name: str, context: str) -> bool:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")

    value = payload[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"Champ {field_name} non booléen pour {context}.")
    return value


def _required_object_list(
    payload: Mapping[str, Any],
    field_name: str,
    context: str,
) -> tuple[Mapping[str, Any], ...]:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")

    value = payload[field_name]
    if not isinstance(value, list):
        raise ValueError(f"Champ {field_name} non liste pour {context}.")
    if len(value) == 0:
        raise ValueError(f"Champ {field_name} vide pour {context}.")

    objects: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"Entrée {field_name}[{index}] non objet pour {context}.")
        objects.append(item)
    return tuple(objects)


def _required_text_list(payload: Mapping[str, Any], field_name: str, context: str) -> tuple[str, ...]:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")

    value = payload[field_name]
    if not isinstance(value, list):
        raise ValueError(f"Champ {field_name} non liste pour {context}.")
    if len(value) == 0:
        raise ValueError(f"Champ {field_name} vide pour {context}.")

    text_values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"Entrée {field_name}[{index}] non textuelle pour {context}.")
        if item.strip() == "":
            raise ValueError(f"Entrée {field_name}[{index}] vide pour {context}.")
        if item != item.strip():
            raise ValueError(f"Entrée {field_name}[{index}] non normalisée pour {context}.")
        text_values.append(item)
    return tuple(text_values)
