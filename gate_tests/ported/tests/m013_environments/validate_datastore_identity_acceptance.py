from __future__ import annotations

from pathlib import Path

import pytest


def test_datastore_identity_acceptance(tmp_path: Path) -> None:
    from app.platform.datastore_identity import (
        DATASTORE_ENVIRONMENT_MISMATCH,
        DatastoreEnvironmentMismatchError,
        DatastoreIdentity,
        PostgresIdentityPreflight,
    )
    from app.platform.postgres_migrations import PostgresMigrationRunner

    expected = DatastoreIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
    )
    foreign = DatastoreIdentity(
        environment="production",
        deployment_id="ostrading-production-primary",
    )
    events: list[str] = []
    connection_factory = _ConnectionFactory(
        cursor=_Cursor(observed_identity=foreign, events=events),
    )
    migrations_path = tmp_path / "migrations"
    migrations_path.mkdir()
    (migrations_path / "001_business.sql").write_text(
        "CREATE TABLE business_data(id integer PRIMARY KEY);\n",
        encoding="utf-8",
    )
    runner = PostgresMigrationRunner(
        connection_factory=connection_factory,
        migrations_path=migrations_path,
        operation_timeout_seconds=10,
        identity_preflight=PostgresIdentityPreflight(expected_identity=expected),
        initialize_identity_if_empty=True,
    )

    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        runner.run()

    assert "identity:read" in events
    assert "migration:create-ledger" not in events
    assert "migration:business" not in events
    assert connection_factory.commit_count == 0

    downstream = _DownstreamOperations()
    for operation in (
        downstream.read,
        downstream.write,
        downstream.claim_job,
        downstream.qdrant_count,
        downstream.qdrant_upsert,
    ):
        with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
            _run_after_preflight(
                preflight=lambda: expected.require_match(foreign),
                operation=operation,
            )
    assert downstream.calls == []


def _run_after_preflight(*, preflight, operation):
    preflight()
    return operation()


class _DownstreamOperations:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def read(self):
        self.calls.append("read")

    def write(self):
        self.calls.append("write")

    def claim_job(self):
        self.calls.append("claim")

    def qdrant_count(self):
        self.calls.append("qdrant-count")

    def qdrant_upsert(self):
        self.calls.append("qdrant-upsert")


class _ConnectionFactory:
    def __init__(self, *, cursor) -> None:
        self.cursor = cursor
        self.commit_count = 0

    def connect(self):
        return _Connection(factory=self)


class _Connection:
    def __init__(self, *, factory) -> None:
        self.factory = factory

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.factory.commit_count += 1
        return False

    def cursor(self):
        return _CursorContext(cursor=self.factory.cursor)


class _CursorContext:
    def __init__(self, *, cursor) -> None:
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Cursor:
    def __init__(self, *, observed_identity, events) -> None:
        self.observed_identity = observed_identity
        self.events = events
        self._result = None

    def execute(self, sql, parameters=()):
        normalized = " ".join(str(sql).split())
        if "CREATE TABLE IF NOT EXISTS platform.schema_migrations" in normalized:
            self.events.append("migration:create-ledger")
        elif "CREATE TABLE business_data" in normalized:
            self.events.append("migration:business")
        elif "to_regclass('platform.datastore_identity')" in normalized:
            self.events.append("identity:presence")
            self._result = ("platform.datastore_identity",)
        elif "FROM platform.datastore_identity" in normalized:
            self.events.append("identity:read")
            self._result = (
                self.observed_identity.environment,
                self.observed_identity.deployment_id,
            )
        else:
            self._result = None

    def fetchone(self):
        return self._result

    def fetchall(self):
        return []

