"""Identité attendue et préflights stricts des stockages persistants."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Protocol
from urllib import request
from uuid import uuid4


DATASTORE_ENVIRONMENT_MISMATCH = "DATASTORE_ENVIRONMENT_MISMATCH"
DATASTORE_IDENTITY_MARKER = ".ostrading-datastore-identity.json"
QDRANT_IDENTITY_POINT_ID = "7e7aaf4e-b479-5ceb-9187-17d07e996852"

_ENVIRONMENTS = frozenset(("development", "test", "production"))
_DEPLOYMENT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDENTITY_KEYS = frozenset(("environment", "deployment_id"))
_POSTGRES_IDENTITY_LOCK_ID = 4_602_113_020


class DatastoreEnvironmentMismatchError(RuntimeError):
    """Erreur terminale avant tout effet métier sur un stockage étranger."""

    code = DATASTORE_ENVIRONMENT_MISMATCH

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or reason.strip() == "":
            raise ValueError("raison de divergence de stockage invalide")
        super().__init__(f"{self.code}: {reason}")


@dataclass(frozen=True, slots=True)
class DatastoreIdentity:
    """Couple immuable porté par la configuration et par chaque stockage."""

    environment: str
    deployment_id: str

    def __post_init__(self) -> None:
        if self.environment not in _ENVIRONMENTS:
            raise DatastoreEnvironmentMismatchError("environment observé invalide")
        if not isinstance(self.deployment_id, str) or _DEPLOYMENT_ID.fullmatch(self.deployment_id) is None:
            raise DatastoreEnvironmentMismatchError("deployment_id observé invalide")

    @classmethod
    def from_mapping(cls, value: object) -> DatastoreIdentity:
        if not isinstance(value, Mapping) or frozenset(value) != _IDENTITY_KEYS:
            raise DatastoreEnvironmentMismatchError("marqueur d'identité absent ou invalide")
        try:
            return cls(
                environment=value["environment"],
                deployment_id=value["deployment_id"],
            )
        except (KeyError, TypeError) as exc:
            raise DatastoreEnvironmentMismatchError("marqueur d'identité invalide") from exc

    def to_mapping(self) -> dict[str, str]:
        return {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
        }

    def require_match(self, observed: object) -> DatastoreIdentity:
        if not isinstance(observed, DatastoreIdentity):
            raise DatastoreEnvironmentMismatchError("identité observée invalide")
        if observed != self:
            raise DatastoreEnvironmentMismatchError(
                "identité attendue et identité observée divergentes"
            )
        return observed


class IdentityPreflight(Protocol):
    def run(self, *, initialize_if_empty: bool) -> DatastoreIdentity: ...


class QdrantIdentityClientPort(Protocol):
    def list_collections(self) -> Sequence[str]: ...
    def read_identity(self) -> Mapping[str, Any] | None: ...
    def initialize_identity(self, identity: DatastoreIdentity) -> None: ...
    def compensate_failed_initialization(self) -> None: ...


@dataclass(frozen=True, slots=True)
class FileRootIdentityPreflight:
    root: Path
    expected_identity: DatastoreIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise ValueError("racine fichier de préflight invalide")
        if not isinstance(self.expected_identity, DatastoreIdentity):
            raise ValueError("identité attendue de racine fichier invalide")

    def run(self, *, initialize_if_empty: bool) -> DatastoreIdentity:
        _require_initialization_choice(initialize_if_empty)
        marker = self.root / DATASTORE_IDENTITY_MARKER
        if self.root.is_symlink() or marker.is_symlink():
            raise DatastoreEnvironmentMismatchError("lien symbolique de racine fichier interdit")
        if marker.is_file():
            return self.expected_identity.require_match(_read_file_identity(marker))
        if self.root.exists() and not self.root.is_dir():
            raise DatastoreEnvironmentMismatchError("racine fichier non répertoire")
        if self.root.is_dir() and any(self.root.iterdir()):
            raise DatastoreEnvironmentMismatchError(
                "marqueur absent sur une racine fichier non vierge"
            )
        if not initialize_if_empty:
            raise DatastoreEnvironmentMismatchError("marqueur de racine fichier absent")
        self.root.mkdir(parents=True, exist_ok=True)
        _create_file_identity_atomically(marker, self.expected_identity)
        return self.expected_identity.require_match(_read_file_identity(marker))


@dataclass(frozen=True, slots=True)
class QdrantIdentityPreflight:
    client: QdrantIdentityClientPort
    expected_identity: DatastoreIdentity
    collection_name: str

    def __post_init__(self) -> None:
        for method_name in (
            "list_collections",
            "read_identity",
            "initialize_identity",
            "compensate_failed_initialization",
        ):
            if not callable(getattr(self.client, method_name, None)):
                raise ValueError(f"client Qdrant sans {method_name}")
        if not isinstance(self.expected_identity, DatastoreIdentity):
            raise ValueError("identité attendue Qdrant invalide")
        _require_qdrant_collection_name(self.collection_name)

    def run(self, *, initialize_if_empty: bool) -> DatastoreIdentity:
        _require_initialization_choice(initialize_if_empty)
        collections = _collection_names(self.client.list_collections())
        if self.collection_name in collections:
            return self.expected_identity.require_match(
                DatastoreIdentity.from_mapping(self.client.read_identity())
            )
        if len(collections) != 0:
            raise DatastoreEnvironmentMismatchError(
                "marqueur absent sur un stockage Qdrant non vierge"
            )
        if not initialize_if_empty:
            raise DatastoreEnvironmentMismatchError("marqueur Qdrant absent")
        try:
            self.client.initialize_identity(self.expected_identity)
        except Exception:
            try:
                self.client.compensate_failed_initialization()
            except Exception as compensation_error:
                raise DatastoreEnvironmentMismatchError(
                    "compensation de l'initialisation Qdrant échouée"
                ) from compensation_error
            raise
        initialized_collections = _collection_names(self.client.list_collections())
        if self.collection_name not in initialized_collections:
            raise DatastoreEnvironmentMismatchError("initialisation Qdrant incomplète")
        return self.expected_identity.require_match(
            DatastoreIdentity.from_mapping(self.client.read_identity())
        )


@dataclass(frozen=True, slots=True)
class PostgresIdentityPreflight:
    expected_identity: DatastoreIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.expected_identity, DatastoreIdentity):
            raise ValueError("identité attendue PostgreSQL invalide")

    def run(self, cursor: object, *, initialize_if_empty: bool) -> DatastoreIdentity:
        if not callable(getattr(cursor, "execute", None)):
            raise ValueError("curseur PostgreSQL de préflight invalide")
        _require_initialization_choice(initialize_if_empty)
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_POSTGRES_IDENTITY_LOCK_ID,))
        cursor.execute("SELECT to_regclass('platform.datastore_identity')", ())
        presence = cursor.fetchone()
        if presence == ("platform.datastore_identity",):
            cursor.execute(
                """
                SELECT jsonb_agg(to_jsonb(identity_marker))
                  FROM platform.datastore_identity AS identity_marker
                """,
                (),
            )
            row = cursor.fetchone()
            rows = row[0] if isinstance(row, tuple) and len(row) == 1 else None
            if not isinstance(rows, list) or len(rows) != 1:
                raise DatastoreEnvironmentMismatchError("marqueur PostgreSQL invalide")
            marker = rows[0]
            if not isinstance(marker, Mapping) or frozenset(marker) != {
                "singleton",
                "environment",
                "deployment_id",
            }:
                raise DatastoreEnvironmentMismatchError("marqueur PostgreSQL invalide")
            if marker["singleton"] is not True:
                raise DatastoreEnvironmentMismatchError("marqueur PostgreSQL invalide")
            return self.expected_identity.require_match(
                DatastoreIdentity.from_mapping(
                    {
                        "environment": marker["environment"],
                        "deployment_id": marker["deployment_id"],
                    }
                )
            )
        if presence != (None,):
            raise DatastoreEnvironmentMismatchError("état du marqueur PostgreSQL invalide")
        cursor.execute(
            """
            SELECT
                (
                    SELECT count(*)
                      FROM pg_class AS relation
                      JOIN pg_namespace AS namespace
                        ON namespace.oid = relation.relnamespace
                     WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema')
                       AND namespace.nspname NOT LIKE 'pg_toast%%'
                       AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                )
                +
                (
                    SELECT count(*)
                      FROM pg_namespace AS namespace
                     WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'public')
                       AND namespace.nspname NOT LIKE 'pg_toast%%'
                )
            """,
            (),
        )
        count_row = cursor.fetchone()
        if not isinstance(count_row, tuple) or len(count_row) != 1:
            raise DatastoreEnvironmentMismatchError("inventaire PostgreSQL invalide")
        object_count = count_row[0]
        if isinstance(object_count, bool) or not isinstance(object_count, int) or object_count < 0:
            raise DatastoreEnvironmentMismatchError("inventaire PostgreSQL invalide")
        if object_count != 0:
            raise DatastoreEnvironmentMismatchError(
                "marqueur absent sur un stockage PostgreSQL non vierge"
            )
        if not initialize_if_empty:
            raise DatastoreEnvironmentMismatchError("marqueur PostgreSQL absent")
        cursor.execute("CREATE SCHEMA platform")
        cursor.execute(
            """
            CREATE TABLE platform.datastore_identity (
                singleton boolean PRIMARY KEY CHECK (singleton),
                environment text NOT NULL
                    CHECK (environment IN ('development', 'test', 'production')),
                deployment_id text NOT NULL
                    CHECK (deployment_id ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO platform.datastore_identity(singleton, environment, deployment_id)
            VALUES (true, %s, %s)
            """,
            (
                self.expected_identity.environment,
                self.expected_identity.deployment_id,
            ),
        )
        return self.expected_identity

    def adopt_legacy(self, cursor: object) -> DatastoreIdentity:
        """Marque explicitement une base historique non vide avant sa migration."""

        if not callable(getattr(cursor, "execute", None)):
            raise ValueError("curseur PostgreSQL de préflight invalide")
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_POSTGRES_IDENTITY_LOCK_ID,))
        cursor.execute("SELECT to_regclass('platform.datastore_identity')", ())
        if cursor.fetchone() != (None,):
            raise DatastoreEnvironmentMismatchError("adoption PostgreSQL déjà matérialisée")
        cursor.execute(
            """
            SELECT count(*)
              FROM pg_class AS relation
              JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema')
               AND namespace.nspname NOT LIKE 'pg_toast%%'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
            """,
            (),
        )
        row = cursor.fetchone()
        if not isinstance(row, tuple) or len(row) != 1 or not isinstance(row[0], int):
            raise DatastoreEnvironmentMismatchError("inventaire PostgreSQL invalide")
        if row[0] < 1:
            raise DatastoreEnvironmentMismatchError("base historique PostgreSQL vide")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS platform")
        cursor.execute(
            """
            CREATE TABLE platform.datastore_identity (
                singleton boolean PRIMARY KEY CHECK (singleton),
                environment text NOT NULL
                    CHECK (environment IN ('development', 'test', 'production')),
                deployment_id text NOT NULL
                    CHECK (deployment_id ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO platform.datastore_identity(singleton, environment, deployment_id)
            VALUES (true, %s, %s)
            """,
            (self.expected_identity.environment, self.expected_identity.deployment_id),
        )
        return self.expected_identity


@dataclass(frozen=True, slots=True)
class PostgresConnectionIdentityPreflight:
    connection_factory: object
    identity_preflight: PostgresIdentityPreflight
    operation_timeout_seconds: int

    def __post_init__(self) -> None:
        if not callable(getattr(self.connection_factory, "connect", None)):
            raise ValueError("connection_factory de préflight PostgreSQL invalide")
        if not isinstance(self.identity_preflight, PostgresIdentityPreflight):
            raise ValueError("préflight PostgreSQL invalide")
        if (
            isinstance(self.operation_timeout_seconds, bool)
            or not isinstance(self.operation_timeout_seconds, int)
            or self.operation_timeout_seconds < 1
        ):
            raise ValueError("timeout de préflight PostgreSQL invalide")

    def run(self, *, initialize_if_empty: bool) -> DatastoreIdentity:
        _require_initialization_choice(initialize_if_empty)
        timeout_milliseconds = str(self.operation_timeout_seconds * 1000)
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (timeout_milliseconds,),
                )
                cursor.execute(
                    "SELECT set_config('lock_timeout', %s, true)",
                    (timeout_milliseconds,),
                )
                return self.identity_preflight.run(
                    cursor,
                    initialize_if_empty=initialize_if_empty,
                )


@dataclass(frozen=True, slots=True)
class DatastorePreflightPlan:
    preflights: tuple[IdentityPreflight, ...]

    def __post_init__(self) -> None:
        if len(self.preflights) == 0:
            raise ValueError("préflight de stockage vide")
        if any(not callable(getattr(preflight, "run", None)) for preflight in self.preflights):
            raise ValueError("préflight de stockage invalide")

    def run(self, *, initialize_if_empty: bool) -> tuple[DatastoreIdentity, ...]:
        _require_initialization_choice(initialize_if_empty)
        return tuple(
            preflight.run(initialize_if_empty=initialize_if_empty)
            for preflight in self.preflights
        )


class QdrantRestIdentityClient:
    """Client REST borné au marqueur d'identité de Qdrant."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int,
        collection_name: str,
        api_key: str,
    ) -> None:
        if not isinstance(base_url, str) or base_url.strip() == "" or base_url != base_url.strip():
            raise ValueError("URL Qdrant d'identité invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise ValueError("timeout Qdrant d'identité invalide")
        _require_qdrant_collection_name(collection_name)
        if not isinstance(api_key, str) or len(api_key.encode("utf-8")) < 32:
            raise ValueError("clé API Qdrant d'identité invalide")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._collection_name = collection_name
        self._api_key = api_key

    def list_collections(self) -> tuple[str, ...]:
        payload = self._json_request(method="GET", path="/collections", body=None)
        result = payload.get("result")
        collections = result.get("collections") if isinstance(result, Mapping) else None
        if not isinstance(collections, list):
            raise DatastoreEnvironmentMismatchError("réponse collections Qdrant invalide")
        names = []
        for collection in collections:
            name = collection.get("name") if isinstance(collection, Mapping) else None
            if not isinstance(name, str) or name.strip() == "":
                raise DatastoreEnvironmentMismatchError("nom de collection Qdrant invalide")
            names.append(name)
        return tuple(names)

    def read_identity(self) -> Mapping[str, Any] | None:
        payload = self._json_request(
            method="POST",
            path=f"/collections/{self._collection_name}/points",
            body={
                "ids": [QDRANT_IDENTITY_POINT_ID],
                "with_payload": True,
                "with_vector": False,
            },
        )
        result = payload.get("result")
        if not isinstance(result, list) or len(result) != 1:
            return None
        point_payload = result[0].get("payload") if isinstance(result[0], Mapping) else None
        return point_payload if isinstance(point_payload, Mapping) else None

    def initialize_identity(self, identity: DatastoreIdentity) -> None:
        if not isinstance(identity, DatastoreIdentity):
            raise ValueError("identité Qdrant à initialiser invalide")
        self._json_request(
            method="PUT",
            path=f"/collections/{self._collection_name}",
            body={"vectors": {"size": 1, "distance": "Cosine"}},
        )
        self._json_request(
            method="PUT",
            path=f"/collections/{self._collection_name}/points?wait=true",
            body={
                "points": [
                    {
                        "id": QDRANT_IDENTITY_POINT_ID,
                        "payload": identity.to_mapping(),
                        "vector": [0.0],
                    }
                ]
            },
        )

    def compensate_failed_initialization(self) -> None:
        """Supprime uniquement la collection d'identité créée par cette tentative."""

        self._json_request(
            method="DELETE",
            path=f"/collections/{self._collection_name}",
            body=None,
        )

    def _json_request(
        self,
        *,
        method: str,
        path: str,
        body: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {"api-key": self._api_key}
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        http_request = request.Request(
            f"{self._base_url}{path}",
            data=encoded,
            headers=headers,
            method=method,
        )
        with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DatastoreEnvironmentMismatchError(
                    "réponse Qdrant d'identité illisible"
                ) from exc
        if not isinstance(payload, Mapping) or payload.get("status") != "ok":
            raise DatastoreEnvironmentMismatchError("réponse Qdrant d'identité invalide")
        return payload


def _read_file_identity(marker: Path) -> DatastoreIdentity:
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatastoreEnvironmentMismatchError("marqueur de racine fichier illisible") from exc
    return DatastoreIdentity.from_mapping(payload)


def _create_file_identity_atomically(marker: Path, identity: DatastoreIdentity) -> None:
    temporary = marker.parent / f".{marker.name}.{uuid4().hex}.tmp"
    payload = (
        json.dumps(identity.to_mapping(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, marker)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def _collection_names(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DatastoreEnvironmentMismatchError("inventaire Qdrant invalide")
    names = tuple(value)
    if any(not isinstance(name, str) or name.strip() == "" for name in names):
        raise DatastoreEnvironmentMismatchError("inventaire Qdrant invalide")
    if len(set(names)) != len(names):
        raise DatastoreEnvironmentMismatchError("inventaire Qdrant dupliqué")
    return names


def _require_qdrant_collection_name(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", value) is None:
        raise ValueError("nom de collection d'identité Qdrant invalide")
    return value


def _require_initialization_choice(value: bool) -> None:
    if not isinstance(value, bool):
        raise ValueError("choix d'initialisation du stockage invalide")


__all__ = [
    "DATASTORE_ENVIRONMENT_MISMATCH",
    "DATASTORE_IDENTITY_MARKER",
    "DatastoreEnvironmentMismatchError",
    "DatastoreIdentity",
    "DatastorePreflightPlan",
    "FileRootIdentityPreflight",
    "IdentityPreflight",
    "PostgresIdentityPreflight",
    "PostgresConnectionIdentityPreflight",
    "QdrantIdentityPreflight",
    "QdrantRestIdentityClient",
]
