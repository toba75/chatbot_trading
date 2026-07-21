"""Composition des préflights d'identité depuis la configuration validée."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from app.platform.configuration import ApplicationConfiguration
from app.platform.datastore_identity import (
    DatastoreIdentity,
    DatastorePreflightPlan,
    FileRootIdentityPreflight,
    PostgresConnectionIdentityPreflight,
    PostgresIdentityPreflight,
    QdrantIdentityPreflight,
    QdrantRestIdentityClient,
)
from app.platform.postgres import PsycopgConnectionFactory


_FILE_ROOT_NAMES: Final = frozenset(
    (
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
)


def configured_datastore_identity(
    configuration: ApplicationConfiguration,
) -> DatastoreIdentity:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    return DatastoreIdentity(
        environment=configuration.application.environment,
        deployment_id=configuration.application.deployment_id,
    )


def build_configured_datastore_preflight(
    configuration: ApplicationConfiguration,
    *,
    include_postgres: bool,
    include_qdrant: bool,
    file_root_names: tuple[str, ...],
) -> DatastorePreflightPlan:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    if not isinstance(include_postgres, bool) or not isinstance(include_qdrant, bool):
        raise ValueError("sélection de stockage invalide")
    if not isinstance(file_root_names, tuple) or len(set(file_root_names)) != len(file_root_names):
        raise ValueError("racines fichiers de préflight invalides")
    if any(name not in _FILE_ROOT_NAMES for name in file_root_names):
        raise ValueError("racine fichier de préflight inconnue")
    identity = configured_datastore_identity(configuration)
    preflights = []
    if include_postgres:
        connection_factory = PsycopgConnectionFactory(
            connection_url=configuration.services.postgres.url,
            password_path=Path(configuration.security.secrets.postgres_password_path),
            connect_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
        )
        preflights.append(
            PostgresConnectionIdentityPreflight(
                connection_factory=connection_factory,
                identity_preflight=PostgresIdentityPreflight(
                    expected_identity=identity,
                ),
                operation_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
            )
        )
    if include_qdrant:
        preflights.append(
            QdrantIdentityPreflight(
                client=QdrantRestIdentityClient(
                    base_url=configuration.services.qdrant.url,
                    timeout_seconds=configuration.runtime.timeouts.startup_seconds,
                    collection_name=configuration.services.qdrant.collections.datastore_identity,
                ),
                expected_identity=identity,
                collection_name=configuration.services.qdrant.collections.datastore_identity,
            )
        )
    preflights.extend(
        FileRootIdentityPreflight(
            root=Path(getattr(configuration.paths, name)),
            expected_identity=identity,
        )
        for name in file_root_names
    )
    return DatastorePreflightPlan(preflights=tuple(preflights))


__all__ = [
    "build_configured_datastore_preflight",
    "configured_datastore_identity",
]
