"""Runner strict des migrations PostgreSQL requises par l'image applicative."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import os
import re

from app.platform.configuration import ApplicationConfiguration, load_application_configuration
from app.platform.datastore_identity import (
    DatastoreEnvironmentMismatchError,
    DatastoreIdentity,
    PostgresIdentityPreflight,
)
from app.platform.postgres import PostgresConnectionFactory
from app.platform.postgres import PsycopgConnectionFactory


_MIGRATION_FILENAME = re.compile(r"^(?P<version>[0-9]{3})_[a-z0-9_]+\.sql$")
_MIGRATION_LOCK_ID = 4_602_113_021
POSTGRES_MIGRATIONS_PATH = Path(__file__).resolve().parents[2] / "deploy/postgres/migrations"


@dataclass(frozen=True, slots=True)
class PostgresMigration:
    version: int
    filename: str
    sha256: str
    sql: str


class PostgresMigrationRunner:
    """Applique les migrations absentes sous verrou et ledger transactionnels."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        migrations_path: Path,
        operation_timeout_seconds: int,
        identity_preflight: PostgresIdentityPreflight,
        initialize_identity_if_empty: bool,
        adopt_legacy_if_unidentified: bool,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory PostgreSQL invalide")
        if not isinstance(migrations_path, Path):
            raise ValueError("migrations_path PostgreSQL invalide")
        if (
            isinstance(operation_timeout_seconds, bool)
            or not isinstance(operation_timeout_seconds, int)
            or operation_timeout_seconds < 1
        ):
            raise ValueError("operation_timeout_seconds PostgreSQL invalide")
        if not isinstance(identity_preflight, PostgresIdentityPreflight):
            raise ValueError("identity_preflight PostgreSQL invalide")
        if not isinstance(initialize_identity_if_empty, bool):
            raise ValueError("initialize_identity_if_empty PostgreSQL invalide")
        if not isinstance(adopt_legacy_if_unidentified, bool):
            raise ValueError("adopt_legacy_if_unidentified PostgreSQL invalide")
        self._connection_factory = connection_factory
        self._migrations = _load_migrations(migrations_path)
        self._operation_timeout_seconds = operation_timeout_seconds
        self._identity_preflight = identity_preflight
        self._initialize_identity_if_empty = initialize_identity_if_empty
        self._adopt_legacy_if_unidentified = adopt_legacy_if_unidentified

    @property
    def required_schema_version(self) -> int:
        return self._migrations[-1].version

    def run(self) -> None:
        timeout_milliseconds = str(self._operation_timeout_seconds * 1000)
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (timeout_milliseconds,),
                )
                cursor.execute(
                    "SELECT set_config('lock_timeout', %s, true)",
                    (timeout_milliseconds,),
                )
                try:
                    self._identity_preflight.run(
                        cursor,
                        initialize_if_empty=self._initialize_identity_if_empty,
                    )
                except DatastoreEnvironmentMismatchError:
                    if not self._adopt_legacy_if_unidentified:
                        raise
                    self._identity_preflight.adopt_legacy(cursor)
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_ID,))
                _create_ledger(cursor)
                applied = _read_ledger(cursor)
                _validate_applied_migrations(applied, self._migrations)
                for migration in self._migrations:
                    if migration.version in applied:
                        continue
                    cursor.execute(migration.sql)
                    cursor.execute(
                        """
                        INSERT INTO platform.schema_migrations(version, filename, sha256)
                        VALUES (%s, %s, %s)
                        """,
                        (migration.version, migration.filename, migration.sha256),
                    )

    def is_required_schema_ready(self) -> bool:
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                self._identity_preflight.run(cursor, initialize_if_empty=False)
                cursor.execute("SELECT to_regclass('platform.schema_migrations')", ())
                if cursor.fetchone() != ("platform.schema_migrations",):
                    return False
                applied = _read_ledger(cursor)
        try:
            _validate_applied_migrations(applied, self._migrations)
        except RuntimeError:
            return False
        return len(applied) == len(self._migrations)


def _load_migrations(migrations_path: Path) -> tuple[PostgresMigration, ...]:
    if not migrations_path.is_dir():
        raise RuntimeError("POSTGRES_MIGRATIONS_PATH_UNREADABLE")
    migrations: list[PostgresMigration] = []
    for path in sorted(migrations_path.glob("*.sql"), key=lambda candidate: candidate.name):
        match = _MIGRATION_FILENAME.fullmatch(path.name)
        if match is None:
            raise RuntimeError(f"POSTGRES_MIGRATION_FILENAME_INVALID:{path.name}")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"POSTGRES_MIGRATION_UNREADABLE:{path.name}") from exc
        if content.strip() == "":
            raise RuntimeError(f"POSTGRES_MIGRATION_EMPTY:{path.name}")
        migrations.append(
            PostgresMigration(
                version=int(match.group("version")),
                filename=path.name,
                sha256=sha256(content.encode("utf-8")).hexdigest(),
                sql=content,
            )
        )
    if len(migrations) == 0:
        raise RuntimeError("POSTGRES_MIGRATIONS_EMPTY")
    versions = tuple(migration.version for migration in migrations)
    expected_versions = tuple(range(1, len(migrations) + 1))
    if versions != expected_versions:
        raise RuntimeError("POSTGRES_MIGRATION_SEQUENCE_INVALID")
    return tuple(migrations)


def _create_ledger(cursor: object) -> None:
    cursor.execute("CREATE SCHEMA IF NOT EXISTS platform")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS platform.schema_migrations (
            version integer PRIMARY KEY CHECK (version > 0),
            filename text NOT NULL UNIQUE,
            sha256 char(64) NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _read_ledger(cursor: object) -> dict[int, tuple[str, str]]:
    cursor.execute(
        "SELECT version, filename, sha256 FROM platform.schema_migrations ORDER BY version",
        (),
    )
    return {
        int(version): (str(filename), str(digest))
        for version, filename, digest in cursor.fetchall()
    }


def _validate_applied_migrations(
    applied: dict[int, tuple[str, str]],
    migrations: tuple[PostgresMigration, ...],
) -> None:
    expected = {migration.version: migration for migration in migrations}
    for version, (filename, digest) in applied.items():
        migration = expected.get(version)
        if migration is None:
            raise RuntimeError(f"POSTGRES_SCHEMA_VERSION_UNSUPPORTED:{version}")
        if (filename, digest) != (migration.filename, migration.sha256):
            raise RuntimeError(f"POSTGRES_MIGRATION_DRIFT:{version:03d}")


def build_configured_postgres_migration_runner(
    configuration: ApplicationConfiguration,
    *,
    initialize_identity_if_empty: bool,
    adopt_legacy_if_unidentified: bool,
) -> PostgresMigrationRunner:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    connection_factory = PsycopgConnectionFactory(
        connection_url=configuration.services.postgres.url,
        password_path=Path(configuration.security.secrets.postgres_password_path),
        connect_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
    )
    return PostgresMigrationRunner(
        connection_factory=connection_factory,
        migrations_path=POSTGRES_MIGRATIONS_PATH,
        operation_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
        identity_preflight=PostgresIdentityPreflight(
            expected_identity=DatastoreIdentity(
                environment=configuration.application.environment,
                deployment_id=configuration.application.deployment_id,
            )
        ),
        initialize_identity_if_empty=initialize_identity_if_empty,
        adopt_legacy_if_unidentified=adopt_legacy_if_unidentified,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner de migrations PostgreSQL OSTrading.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--adopt-legacy-datastore", action="store_true")
    arguments = parser.parse_args()
    configuration = load_application_configuration(
        config_path=arguments.config,
        environment_snapshot=dict(os.environ),
    )
    runner = build_configured_postgres_migration_runner(
        configuration,
        initialize_identity_if_empty=True,
        adopt_legacy_if_unidentified=arguments.adopt_legacy_datastore,
    )
    runner.run()
    print(f"POSTGRES_SCHEMA_READY:{runner.required_schema_version:03d}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "POSTGRES_MIGRATIONS_PATH",
    "PostgresMigration",
    "PostgresMigrationRunner",
    "build_configured_postgres_migration_runner",
]
