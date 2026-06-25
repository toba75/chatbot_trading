"""Politique statique de frontière réseau M-002."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from app.platform.local_compose import ComposeService, LocalCompose
from app.platform.topology import PlatformTopology


DOCKER_LOCAL_HOST = "docker-local"
SPARK_INFERENCE_HOST = "spark-inference"
LLM_GATEWAY_SERVICE_ID = "llm-gateway"
SPARK_SERVICE_ID = "gemma-vllm"
SPARK_EGRESS_NETWORK_ID = "spark-egress"
EDGE_GATEWAY_SERVICE_ID = "edge-gateway"
SPARK_PORT = 8443
SPARK_PROTOCOL = "tcp"
EXPECTED_SPARK_BASE_PATH = "/v1"

REQUIRED_ADR_IDS = ("ADR-007", "ADR-008", "ADR-009")
PRIVATE_STORAGE_SERVICE_IDS = frozenset(
    {
        "postgres",
        "qdrant",
        "corpus-store",
        "experiment-registry",
        "outbox",
    }
)
EXPECTED_DENIED_INITIATORS = frozenset(
    {
        "browser",
        "internet",
        "worker-documents",
        "worker-research",
        "worker-backtest",
        "postgres",
        "qdrant",
        "granite-docling",
        "ui",
        "orchestrator-api",
    }
)
PUBLIC_BINDINGS = frozenset(("", "0.0.0.0", "::", "[::]", "*"))
LOCAL_USER_BINDING = "127.0.0.1"
TLS_VERIFY_KEYS = frozenset(("GEMMA_TLS_VERIFY", "VLLM_TLS_VERIFY", "TLS_VERIFY", "SSL_VERIFY"))
TLS_DISABLE_KEYS = frozenset(
    (
        "GEMMA_DISABLE_TLS",
        "GEMMA_TLS_DISABLED",
        "GEMMA_INSECURE_SKIP_VERIFY",
        "GEMMA_SKIP_TLS_VERIFY",
        "VLLM_DISABLE_TLS",
        "VLLM_INSECURE_SKIP_VERIFY",
    )
)
FALSE_VALUES = frozenset(("false", "0", "no", "off", "disabled"))
TRUE_VALUES = frozenset(("true", "1", "yes", "on", "enabled"))
VLLM_SECRET_MARKERS = ("GEMMA", "VLLM", "OPENAI_API_KEY", "LLM_API_KEY")
BROWSER_REACHABLE_SERVICE_IDS = frozenset(("ui", "edge-gateway"))


@dataclass(frozen=True)
class SparkEndpoint:
    host: str
    service: str
    port: int
    protocol: str
    tls_required: bool
    certificate_authority_required: bool


@dataclass(frozen=True)
class SparkIngressRule:
    source_host: str
    source_service: str
    destination_host: str
    destination_service: str
    destination_port: int
    purpose: str


@dataclass(frozen=True)
class RemoteUserAccessPolicy:
    enabled: bool
    entrypoint_service: str
    allowed_bindings: tuple[str, ...]


@dataclass(frozen=True)
class SparkFirewallPolicy:
    schema_version: str
    architecture_decisions: tuple[str, ...]
    spark_endpoint: SparkEndpoint
    allowed_ingress: tuple[SparkIngressRule, ...]
    denied_initiators: tuple[str, ...]
    callbacks_from_spark_allowed: bool
    browser_direct_access_allowed: bool
    internet_ingress_allowed: bool
    remote_user_access: RemoteUserAccessPolicy


@dataclass(frozen=True)
class NetworkFlow:
    source_service: str
    destination_host: str
    destination_service: str
    destination_port: int
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PublishedPort:
    host_binding: str
    published_port: str
    container_port: str
    raw: str


def load_spark_firewall_policy(path: str | Path) -> SparkFirewallPolicy:
    firewall_path = Path(path)
    payload = json.loads(firewall_path.read_text(encoding="utf-8-sig"))
    return parse_spark_firewall_policy(payload)


def parse_spark_firewall_policy(payload: Mapping[str, Any]) -> SparkFirewallPolicy:
    if not isinstance(payload, Mapping):
        raise ValueError("Politique pare-feu Spark non objet.")

    spark_endpoint_payload = _required_mapping(payload, "spark_endpoint", "politique pare-feu Spark")
    remote_user_access_payload = _required_mapping(
        payload,
        "remote_user_access",
        "politique pare-feu Spark",
    )

    policy = SparkFirewallPolicy(
        schema_version=_required_text(payload, "schema_version", "politique pare-feu Spark"),
        architecture_decisions=_required_text_list(
            payload,
            "architecture_decisions",
            "politique pare-feu Spark",
            allow_empty=False,
        ),
        spark_endpoint=SparkEndpoint(
            host=_required_text(spark_endpoint_payload, "host", "endpoint Spark"),
            service=_required_text(spark_endpoint_payload, "service", "endpoint Spark"),
            port=_required_int(spark_endpoint_payload, "port", "endpoint Spark"),
            protocol=_required_text(spark_endpoint_payload, "protocol", "endpoint Spark"),
            tls_required=_required_bool(spark_endpoint_payload, "tls_required", "endpoint Spark"),
            certificate_authority_required=_required_bool(
                spark_endpoint_payload,
                "certificate_authority_required",
                "endpoint Spark",
            ),
        ),
        allowed_ingress=tuple(
            _parse_allowed_ingress(
                _required_object_list(payload, "allowed_ingress", "politique pare-feu Spark")
            )
        ),
        denied_initiators=_required_text_list(
            payload,
            "denied_initiators",
            "politique pare-feu Spark",
            allow_empty=False,
        ),
        callbacks_from_spark_allowed=_required_bool(
            payload,
            "callbacks_from_spark_allowed",
            "politique pare-feu Spark",
        ),
        browser_direct_access_allowed=_required_bool(
            payload,
            "browser_direct_access_allowed",
            "politique pare-feu Spark",
        ),
        internet_ingress_allowed=_required_bool(
            payload,
            "internet_ingress_allowed",
            "politique pare-feu Spark",
        ),
        remote_user_access=RemoteUserAccessPolicy(
            enabled=_required_bool(remote_user_access_payload, "enabled", "accès utilisateur distant"),
            entrypoint_service=_required_text(
                remote_user_access_payload,
                "entrypoint_service",
                "accès utilisateur distant",
            ),
            allowed_bindings=_required_text_list(
                remote_user_access_payload,
                "allowed_bindings",
                "accès utilisateur distant",
                allow_empty=True,
            ),
        ),
    )
    validate_spark_firewall_policy(policy)
    return policy


def validate_spark_firewall_policy(policy: SparkFirewallPolicy) -> None:
    if policy.schema_version != "1.0":
        raise ValueError(f"schema_version pare-feu Spark non supportée: {policy.schema_version}")

    for adr_id in REQUIRED_ADR_IDS:
        if adr_id not in policy.architecture_decisions:
            raise ValueError(f"ADR pare-feu Spark absente: {adr_id}")

    endpoint = policy.spark_endpoint
    if endpoint.host != SPARK_INFERENCE_HOST:
        raise ValueError(f"Hôte Spark invalide: {endpoint.host}")
    if endpoint.service != SPARK_SERVICE_ID:
        raise ValueError(f"Service Spark invalide: {endpoint.service}")
    if endpoint.port != SPARK_PORT:
        raise ValueError(f"Port Spark invalide: {endpoint.port}")
    if endpoint.protocol != SPARK_PROTOCOL:
        raise ValueError(f"Protocole Spark invalide: {endpoint.protocol}")
    if not endpoint.tls_required:
        raise ValueError("TLS Spark obligatoire")
    if not endpoint.certificate_authority_required:
        raise ValueError("Certificat Spark obligatoire")

    if len(policy.allowed_ingress) != 1:
        raise ValueError("Une seule règle ingress Spark est autorisée.")

    rule = policy.allowed_ingress[0]
    if rule.source_service != LLM_GATEWAY_SERVICE_ID:
        raise ValueError(f"Source Spark non autorisée: {rule.source_service}")
    if rule.source_host != DOCKER_LOCAL_HOST:
        raise ValueError(f"Hôte source Spark non autorisé: {rule.source_host}")
    if rule.destination_host != SPARK_INFERENCE_HOST:
        raise ValueError(f"Destination Spark invalide: {rule.destination_host}")
    if rule.destination_service != SPARK_SERVICE_ID:
        raise ValueError(f"Service destination Spark invalide: {rule.destination_service}")
    if rule.destination_port != SPARK_PORT:
        raise ValueError(f"Port destination Spark invalide: {rule.destination_port}")

    denied_initiators = frozenset(policy.denied_initiators)
    for initiator in EXPECTED_DENIED_INITIATORS:
        if initiator not in denied_initiators:
            raise ValueError(f"Initiateur refusé absent: {initiator}")

    if policy.callbacks_from_spark_allowed:
        raise ValueError("Callback Spark interdit")
    if policy.browser_direct_access_allowed:
        raise ValueError("Accès navigateur direct au Spark interdit")
    if policy.internet_ingress_allowed:
        raise ValueError("Accès Internet entrant Spark interdit")

    _validate_remote_user_access_policy(policy.remote_user_access)


def validate_network_boundary(
    *,
    compose: LocalCompose,
    topology: PlatformTopology,
    spark_firewall: SparkFirewallPolicy,
) -> None:
    validate_spark_firewall_policy(spark_firewall)
    _validate_topology_contract(topology)
    _validate_compose_ports(compose, spark_firewall.remote_user_access)
    _validate_compose_spark_egress(compose)
    _validate_gateway_tls_and_secret_scope(compose, spark_firewall)
    _validate_flow_matrix(build_network_flow_matrix(compose=compose, spark_firewall=spark_firewall))


def build_network_flow_matrix(
    *,
    compose: LocalCompose,
    spark_firewall: SparkFirewallPolicy,
) -> tuple[NetworkFlow, ...]:
    endpoint = spark_firewall.spark_endpoint
    flows: list[NetworkFlow] = []
    seen_sources: set[str] = set()

    for service in compose.services:
        allowed = service.id == LLM_GATEWAY_SERVICE_ID
        reason = "gateway LLM unique" if allowed else "egress Spark refusé hors gateway"
        flows.append(
            NetworkFlow(
                source_service=service.id,
                destination_host=endpoint.host,
                destination_service=endpoint.service,
                destination_port=endpoint.port,
                allowed=allowed,
                reason=reason,
            )
        )
        seen_sources.add(service.id)

    for initiator in spark_firewall.denied_initiators:
        if initiator in seen_sources:
            continue
        flows.append(
            NetworkFlow(
                source_service=initiator,
                destination_host=endpoint.host,
                destination_service=endpoint.service,
                destination_port=endpoint.port,
                allowed=False,
                reason="initiateur externe refusé",
            )
        )

    return tuple(flows)


def _parse_allowed_ingress(
    rule_payloads: tuple[Mapping[str, Any], ...]
) -> tuple[SparkIngressRule, ...]:
    rules: list[SparkIngressRule] = []
    for payload in rule_payloads:
        source_service = _required_text(payload, "source_service", "règle ingress Spark")
        rules.append(
            SparkIngressRule(
                source_host=_required_text(payload, "source_host", f"règle {source_service}"),
                source_service=source_service,
                destination_host=_required_text(payload, "destination_host", f"règle {source_service}"),
                destination_service=_required_text(
                    payload,
                    "destination_service",
                    f"règle {source_service}",
                ),
                destination_port=_required_int(
                    payload,
                    "destination_port",
                    f"règle {source_service}",
                ),
                purpose=_required_text(payload, "purpose", f"règle {source_service}"),
            )
        )
    return tuple(rules)


def _validate_topology_contract(topology: PlatformTopology) -> None:
    llm_gateway = topology.service(LLM_GATEWAY_SERVICE_ID)
    if llm_gateway.host != DOCKER_LOCAL_HOST:
        raise ValueError(f"Placement llm-gateway invalide: {llm_gateway.host}")

    spark_service = topology.service(SPARK_SERVICE_ID)
    if spark_service.host != SPARK_INFERENCE_HOST:
        raise ValueError(f"Placement Spark invalide: {spark_service.host}")
    if spark_service.compose_local:
        raise ValueError("vLLM Spark ne doit pas être dans le Compose local.")


def _validate_compose_ports(compose: LocalCompose, remote_user_access: RemoteUserAccessPolicy) -> None:
    edge_gateway_seen = False
    for service in compose.services:
        if service.id == EDGE_GATEWAY_SERVICE_ID:
            edge_gateway_seen = True
            _validate_edge_gateway_ports(service, remote_user_access)
            continue

        if len(service.ports) == 0:
            continue

        if len(service.profiles) > 0:
            raise ValueError(
                f"Profil Compose avec port public interdit pour service interne: {service.id}"
            )

        if service.id in PRIVATE_STORAGE_SERVICE_IDS:
            raise ValueError(f"Port public interdit pour stockage local: {service.id}")

        raise ValueError(f"Port public interdit pour service interne: {service.id}")

    if not edge_gateway_seen:
        raise ValueError("Service edge-gateway absent de la frontière réseau.")


def _validate_edge_gateway_ports(
    service: ComposeService,
    remote_user_access: RemoteUserAccessPolicy,
) -> None:
    if len(service.ports) == 0:
        raise ValueError("Port utilisateur absent pour edge-gateway.")

    for raw_port in service.ports:
        port = _parse_published_port(raw_port)
        if port.host_binding in PUBLIC_BINDINGS:
            raise ValueError(f"Port public implicite interdit pour edge-gateway: {raw_port}")
        if port.host_binding == LOCAL_USER_BINDING:
            continue
        if not remote_user_access.enabled:
            raise ValueError(
                f"Accès utilisateur distant non déclaré pour edge-gateway: {port.host_binding}"
            )
        if port.host_binding not in remote_user_access.allowed_bindings:
            raise ValueError(f"Accès utilisateur distant non autorisé: {port.host_binding}")


def _validate_compose_spark_egress(compose: LocalCompose) -> None:
    gateway = compose.service(LLM_GATEWAY_SERVICE_ID)
    if SPARK_EGRESS_NETWORK_ID not in gateway.networks:
        raise ValueError("Egress Spark absent pour llm-gateway.")

    for service in compose.services:
        if service.id == LLM_GATEWAY_SERVICE_ID:
            continue
        if SPARK_EGRESS_NETWORK_ID in service.networks:
            raise ValueError(f"Egress Spark interdit hors llm-gateway: {service.id}")


def _validate_gateway_tls_and_secret_scope(compose: LocalCompose, spark_firewall: SparkFirewallPolicy) -> None:
    gateway = compose.service(LLM_GATEWAY_SERVICE_ID)
    _require_gateway_environment(gateway, "GEMMA_BASE_URL")
    _require_gateway_environment(gateway, "GEMMA_API_KEY_FILE")
    _require_gateway_environment(gateway, "GEMMA_CA_BUNDLE")

    base_url = gateway.environment["GEMMA_BASE_URL"]
    _validate_gateway_base_url(base_url, spark_firewall)
    if base_url.lower().startswith("http://"):
        raise ValueError("TLS Spark désactivé pour llm-gateway: GEMMA_BASE_URL")

    for key, value in gateway.environment.items():
        key_upper = key.upper()
        value_normalized = value.strip().lower()
        if key_upper in TLS_VERIFY_KEYS and value_normalized in FALSE_VALUES:
            raise ValueError(f"TLS Spark désactivé pour llm-gateway: {key}")
        if key_upper in TLS_DISABLE_KEYS and value_normalized in TRUE_VALUES:
            raise ValueError(f"TLS Spark désactivé pour llm-gateway: {key}")

    for service in compose.services:
        if service.id not in BROWSER_REACHABLE_SERVICE_IDS:
            continue
        for key in service.environment:
            key_upper = key.upper()
            if any(marker in key_upper for marker in VLLM_SECRET_MARKERS):
                raise ValueError(f"Secret vLLM interdit pour accès navigateur: {service.id}")
        for secret_id in service.secrets:
            secret_upper = secret_id.upper()
            if any(marker in secret_upper for marker in VLLM_SECRET_MARKERS):
                raise ValueError(f"Secret vLLM interdit pour accès navigateur: {service.id}")


def _validate_gateway_base_url(base_url: str, spark_firewall: SparkFirewallPolicy) -> None:
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme != "https":
        raise ValueError("TLS Spark désactivé pour llm-gateway: GEMMA_BASE_URL")
    if parsed_base_url.hostname != spark_firewall.spark_endpoint.host:
        raise ValueError("Endpoint Spark invalide pour llm-gateway: GEMMA_BASE_URL")
    if parsed_base_url.port != spark_firewall.spark_endpoint.port:
        raise ValueError("Endpoint Spark invalide pour llm-gateway: GEMMA_BASE_URL")
    if parsed_base_url.path != EXPECTED_SPARK_BASE_PATH:
        raise ValueError("Endpoint Spark invalide pour llm-gateway: GEMMA_BASE_URL")
    if parsed_base_url.username is not None or parsed_base_url.password is not None:
        raise ValueError("Endpoint Spark invalide pour llm-gateway: GEMMA_BASE_URL")


def _validate_flow_matrix(flows: tuple[NetworkFlow, ...]) -> None:
    allowed_flows = tuple(flow for flow in flows if flow.allowed)
    if len(allowed_flows) != 1:
        raise ValueError("Matrice de flux Spark invalide: une seule autorisation attendue.")

    flow = allowed_flows[0]
    if flow.source_service != LLM_GATEWAY_SERVICE_ID:
        raise ValueError(f"Matrice de flux Spark invalide: {flow.source_service}")
    if flow.destination_host != SPARK_INFERENCE_HOST or flow.destination_port != SPARK_PORT:
        raise ValueError("Matrice de flux Spark cible invalide.")


def _validate_remote_user_access_policy(policy: RemoteUserAccessPolicy) -> None:
    if policy.entrypoint_service != EDGE_GATEWAY_SERVICE_ID:
        raise ValueError(f"Point d'entrée utilisateur distant invalide: {policy.entrypoint_service}")

    if policy.enabled and len(policy.allowed_bindings) == 0:
        raise ValueError("Accès utilisateur distant sans binding autorisé.")
    if not policy.enabled and len(policy.allowed_bindings) > 0:
        raise ValueError("Accès utilisateur distant désactivé avec bindings déclarés.")

    for binding in policy.allowed_bindings:
        if binding in PUBLIC_BINDINGS:
            raise ValueError(f"Accès utilisateur distant public interdit: {binding}")
        if binding == LOCAL_USER_BINDING:
            raise ValueError(f"Accès utilisateur distant local déclaré comme distant: {binding}")


def _require_gateway_environment(service: ComposeService, key: str) -> None:
    if key not in service.environment:
        raise ValueError(f"Variable gateway Spark absente: {key}")
    if service.environment[key].strip() == "":
        raise ValueError(f"Variable gateway Spark vide: {key}")


def _parse_published_port(raw_port: str) -> PublishedPort:
    parts = raw_port.split(":")
    if len(parts) == 2:
        host_binding = ""
        published_port = parts[0]
        container_port = parts[1]
    elif len(parts) == 3:
        host_binding = parts[0]
        published_port = parts[1]
        container_port = parts[2]
    else:
        raise ValueError(f"Port Compose ambigu interdit: {raw_port}")

    if published_port.strip() == "" or container_port.strip() == "":
        raise ValueError(f"Port Compose incomplet interdit: {raw_port}")

    return PublishedPort(
        host_binding=host_binding,
        published_port=published_port,
        container_port=container_port,
        raw=raw_port,
    )


def _required_mapping(payload: Mapping[str, Any], field_name: str, context: str) -> Mapping[str, Any]:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")
    value = payload[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"Champ {field_name} non objet pour {context}.")
    if len(value) == 0:
        raise ValueError(f"Champ {field_name} vide pour {context}.")
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


def _required_text_list(
    payload: Mapping[str, Any],
    field_name: str,
    context: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")
    value = payload[field_name]
    if not isinstance(value, list):
        raise ValueError(f"Champ {field_name} non liste pour {context}.")
    if len(value) == 0 and not allow_empty:
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


def _required_int(payload: Mapping[str, Any], field_name: str, context: str) -> int:
    if field_name not in payload:
        raise ValueError(f"Champ {field_name} absent pour {context}.")
    value = payload[field_name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Champ {field_name} non entier pour {context}.")
    return value
