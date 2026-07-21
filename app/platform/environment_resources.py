"""Validation fail-closed de l'étanchéité des ressources par environnement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final
from urllib.parse import unquote, urlparse

from app.platform.configuration import ApplicationConfiguration


RESOURCE_ISOLATION_VIOLATION = "RESOURCE_ISOLATION_VIOLATION"

_ENVIRONMENTS: Final = ("development", "test", "production")
_FILE_ROOT_NAMES: Final = (
    "data_root",
    "corpus_root",
    "canonical_sources_root",
    "qdrant_storage_root",
    "postgres_data_root",
    "reports_root",
    "logs_root",
    "experiments_root",
    "cache_root",
)
_SECRET_PATH_NAMES: Final = (
    "postgres_password_path",
    "qdrant_api_key_path",
    "llm_gateway_api_key_path",
    "tls_ca_certificate_path",
    "local_api_token_path",
)
_PROFILE_BOUND_COORDINATES: Final = (
    "application.deployment_id",
    "services.postgres.url",
    "services.postgres.database",
    "services.postgres.role",
    "services.postgres.data_volume",
    "services.qdrant.url",
    "services.qdrant.instance_id",
    "services.qdrant.storage_volume",
    "services.qdrant.collections.datastore_identity",
    "services.qdrant.collections.knowledge_access",
    "services.workers.queue_name",
    "services.workers.outbox_namespace",
    "services.workers.progress_namespace",
    *tuple(f"paths.{name}" for name in _FILE_ROOT_NAMES),
    *tuple(f"security.secrets.{name}" for name in _SECRET_PATH_NAMES),
)
_CONTEXT_STORAGE_COORDINATES: Final = MappingProxyType(
    {
        "postgres_schema": (
            "services.postgres.url",
            "services.postgres.database",
            "services.postgres.role",
        ),
        "qdrant_collection": ("services.qdrant.collections.knowledge_access",),
        "queue": ("services.workers.queue_name",),
        "outbox": ("services.workers.outbox_namespace",),
        "cache": ("paths.cache_root",),
        "log": ("paths.logs_root",),
        "report": ("paths.reports_root",),
        "snapshot": ("paths.data_root", "paths.experiments_root"),
        "graph": ("paths.data_root",),
        "artifact": (
            "paths.data_root",
            "paths.corpus_root",
            "paths.canonical_sources_root",
            "paths.reports_root",
            "paths.experiments_root",
        ),
    }
)


class EnvironmentResourceIsolationError(ValueError):
    """Erreur terminale lorsqu'une frontière de données est ambiguë."""

    def __init__(self, message: str) -> None:
        super().__init__(f"{RESOURCE_ISOLATION_VIOLATION}: {message}")


@dataclass(frozen=True, slots=True)
class EnvironmentResourceMatrix:
    coordinates: Mapping[str, Mapping[str, str]]
    context_storage_ids: tuple[str, ...]


def mutable_file_roots(configuration: ApplicationConfiguration) -> Mapping[str, str]:
    """Retourne toutes les racines fichiers mutables du profil, sans en omettre."""

    _require_configuration(configuration)
    return MappingProxyType(
        {
            name: _required_coordinate(getattr(configuration.paths, name), f"paths.{name}")
            for name in _FILE_ROOT_NAMES
        }
    )


def inventory_context_mutable_resources(context_registry_path: Path) -> tuple[str, ...]:
    """Inventorie et qualifie chaque stockage déclaré par les bounded contexts."""

    if not isinstance(context_registry_path, Path) or not context_registry_path.is_file():
        raise EnvironmentResourceIsolationError("registre des contextes absent")
    try:
        payload = json.loads(context_registry_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentResourceIsolationError("registre des contextes illisible") from exc
    if not isinstance(payload, Mapping):
        raise EnvironmentResourceIsolationError("registre des contextes invalide")

    contexts = payload.get("contexts")
    platform = payload.get("platform")
    if not isinstance(contexts, list) or not isinstance(platform, Mapping):
        raise EnvironmentResourceIsolationError("inventaire des stockages absent")
    owners = (*contexts, platform)
    storage_ids: list[str] = []
    for owner in owners:
        if not isinstance(owner, Mapping) or not isinstance(owner.get("owned_storages"), list):
            raise EnvironmentResourceIsolationError("propriétaire de stockage invalide")
        for storage in owner["owned_storages"]:
            if not isinstance(storage, Mapping):
                raise EnvironmentResourceIsolationError("stockage déclaré invalide")
            storage_id = storage.get("id")
            if not isinstance(storage_id, str) or storage_id.strip() != storage_id or ":" not in storage_id:
                raise EnvironmentResourceIsolationError("identifiant de stockage invalide")
            family = storage_id.split(":", 1)[0]
            if family not in _CONTEXT_STORAGE_COORDINATES:
                raise EnvironmentResourceIsolationError(
                    f"famille de stockage sans frontière configurée: {family}"
                )
            storage_ids.append(storage_id)
    if len(storage_ids) != len(set(storage_ids)):
        raise EnvironmentResourceIsolationError("identifiant de stockage dupliqué")
    return tuple(sorted(storage_ids))


def validate_environment_resource_matrix(
    configurations: Mapping[str, ApplicationConfiguration],
    *,
    repository_root: Path,
) -> EnvironmentResourceMatrix:
    """Valide l'unicité exhaustive des coordonnées et chemins des trois profils."""

    if not isinstance(configurations, Mapping) or tuple(sorted(configurations)) != tuple(sorted(_ENVIRONMENTS)):
        raise EnvironmentResourceIsolationError("les trois profils exacts sont obligatoires")
    if not isinstance(repository_root, Path) or not repository_root.is_dir():
        raise EnvironmentResourceIsolationError("racine du dépôt invalide")
    resolved_repository_root = repository_root.resolve()

    coordinates: dict[str, Mapping[str, str]] = {}
    for environment in _ENVIRONMENTS:
        configuration = configurations[environment]
        _require_configuration(configuration)
        if configuration.application.environment != environment:
            raise EnvironmentResourceIsolationError(
                f"alias de profil contradictoire: {environment}"
            )
        profile_coordinates = _coordinates_for(configuration)
        for coordinate_name in _PROFILE_BOUND_COORDINATES:
            value = profile_coordinates[coordinate_name]
            if environment not in value.lower():
                raise EnvironmentResourceIsolationError(
                    f"coordonnée non liée au profil {environment}: {coordinate_name}"
                )
        _validate_postgres_url(configuration)
        _validate_qdrant_url(configuration)
        coordinates[environment] = MappingProxyType(profile_coordinates)

    _validate_coordinate_uniqueness(coordinates)
    _validate_resolved_path_isolation(
        configurations,
        repository_root=resolved_repository_root,
    )

    context_storage_ids = inventory_context_mutable_resources(
        resolved_repository_root / "app" / "context_registry.json"
    )
    for storage_id in context_storage_ids:
        family = storage_id.split(":", 1)[0]
        for coordinate_name in _CONTEXT_STORAGE_COORDINATES[family]:
            if any(coordinate_name not in profile for profile in coordinates.values()):
                raise EnvironmentResourceIsolationError(
                    f"stockage sans coordonnée: {storage_id}"
                )

    return EnvironmentResourceMatrix(
        coordinates=MappingProxyType(coordinates),
        context_storage_ids=context_storage_ids,
    )


def _coordinates_for(configuration: ApplicationConfiguration) -> dict[str, str]:
    postgres = configuration.services.postgres
    qdrant = configuration.services.qdrant
    workers = configuration.services.workers
    coordinates = {
        "application.deployment_id": configuration.application.deployment_id,
        "services.postgres.url": postgres.url,
        "services.postgres.database": postgres.database,
        "services.postgres.role": postgres.role,
        "services.postgres.data_volume": postgres.data_volume,
        "services.qdrant.url": qdrant.url,
        "services.qdrant.instance_id": qdrant.instance_id,
        "services.qdrant.storage_volume": qdrant.storage_volume,
        "services.qdrant.collections.datastore_identity": qdrant.collections.datastore_identity,
        "services.qdrant.collections.knowledge_access": qdrant.collections.knowledge_access,
        "services.workers.queue_name": workers.queue_name,
        "services.workers.outbox_namespace": workers.outbox_namespace,
        "services.workers.progress_namespace": workers.progress_namespace,
    }
    coordinates.update(
        {
            f"paths.{name}": value
            for name, value in mutable_file_roots(configuration).items()
        }
    )
    coordinates.update(
        {
            f"security.secrets.{name}": _required_coordinate(
                getattr(configuration.security.secrets, name),
                f"security.secrets.{name}",
            )
            for name in _SECRET_PATH_NAMES
        }
    )
    return {
        name: _required_coordinate(value, name)
        for name, value in coordinates.items()
    }


def _validate_coordinate_uniqueness(coordinates: Mapping[str, Mapping[str, str]]) -> None:
    for coordinate_name in _PROFILE_BOUND_COORDINATES:
        values: dict[str, str] = {}
        for environment in _ENVIRONMENTS:
            value = coordinates[environment][coordinate_name]
            normalized_value = _normalize_coordinate(coordinate_name, value)
            previous_environment = values.get(normalized_value)
            if previous_environment is not None:
                raise EnvironmentResourceIsolationError(
                    f"collision {coordinate_name}: {previous_environment}/{environment}"
                )
            values[normalized_value] = environment


def _validate_resolved_path_isolation(
    configurations: Mapping[str, ApplicationConfiguration],
    *,
    repository_root: Path,
) -> None:
    resolved_paths: dict[str, dict[str, Path]] = {}
    for environment in _ENVIRONMENTS:
        configuration = configurations[environment]
        raw_paths = {
            **mutable_file_roots(configuration),
            **{
                f"secret:{name}": getattr(configuration.security.secrets, name)
                for name in _SECRET_PATH_NAMES
            },
        }
        resolved_paths[environment] = {
            name: _resolve_path(value, repository_root=repository_root)
            for name, value in raw_paths.items()
        }

    for left_index, left_environment in enumerate(_ENVIRONMENTS):
        for right_environment in _ENVIRONMENTS[left_index + 1 :]:
            for left_name, left_path in resolved_paths[left_environment].items():
                for right_name, right_path in resolved_paths[right_environment].items():
                    if _paths_overlap(left_path, right_path):
                        raise EnvironmentResourceIsolationError(
                            "chemins résolus chevauchants: "
                            f"{left_environment}.{left_name}/{right_environment}.{right_name}"
                        )


def _validate_postgres_url(configuration: ApplicationConfiguration) -> None:
    postgres = configuration.services.postgres
    parsed = urlparse(postgres.url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or parsed.hostname is None:
        raise EnvironmentResourceIsolationError("URL PostgreSQL invalide")
    if parsed.password is not None:
        raise EnvironmentResourceIsolationError("credential PostgreSQL en clair dans l'URL")
    if unquote(parsed.username or "") != postgres.role:
        raise EnvironmentResourceIsolationError("rôle PostgreSQL divergent de l'URL")
    if unquote(parsed.path.removeprefix("/")) != postgres.database:
        raise EnvironmentResourceIsolationError("base PostgreSQL divergente de l'URL")


def _validate_qdrant_url(configuration: ApplicationConfiguration) -> None:
    parsed = urlparse(configuration.services.qdrant.url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise EnvironmentResourceIsolationError("URL Qdrant invalide")
    if parsed.username is not None or parsed.password is not None:
        raise EnvironmentResourceIsolationError("credential Qdrant en clair dans l'URL")


def _required_coordinate(value: object, coordinate_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise EnvironmentResourceIsolationError(f"coordonnée invalide: {coordinate_name}")
    return value


def _normalize_coordinate(coordinate_name: str, value: str) -> str:
    if coordinate_name.endswith(".url"):
        return value.rstrip("/").lower()
    return value.casefold()


def _resolve_path(value: str, *, repository_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repository_root / path
    return path.resolve(strict=False)


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _require_configuration(configuration: object) -> ApplicationConfiguration:
    if not isinstance(configuration, ApplicationConfiguration):
        raise EnvironmentResourceIsolationError("configuration applicative validée obligatoire")
    return configuration


__all__ = [
    "RESOURCE_ISOLATION_VIOLATION",
    "EnvironmentResourceIsolationError",
    "EnvironmentResourceMatrix",
    "inventory_context_mutable_resources",
    "mutable_file_roots",
    "validate_environment_resource_matrix",
]
