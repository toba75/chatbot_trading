from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_datastore_identity_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.platform.datastore_identity as identity_module
    from app.platform.datastore_identity import (
        DATASTORE_ENVIRONMENT_MISMATCH,
        DatastoreEnvironmentMismatchError,
        DatastoreIdentity,
        FileRootIdentityPreflight,
        PostgresIdentityPreflight,
        QdrantIdentityPreflight,
        QdrantRestIdentityClient,
    )
    from app.platform.configuration import load_application_configuration

    deployments = {
        "development": "ostrading-development-local",
        "test": "ostrading-test-ci",
        "production": "ostrading-production-primary",
    }
    identities = {
        environment: DatastoreIdentity(
            environment=environment,
            deployment_id=deployment_id,
        )
        for environment, deployment_id in deployments.items()
    }

    for expected_environment, expected in identities.items():
        for observed_environment, observed in identities.items():
            if expected_environment == observed_environment:
                assert expected.require_match(observed) is observed
            else:
                with pytest.raises(
                    DatastoreEnvironmentMismatchError,
                    match=DATASTORE_ENVIRONMENT_MISMATCH,
                ):
                    expected.require_match(observed)

    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        DatastoreIdentity.from_mapping({"environment": "test"})
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        DatastoreIdentity.from_mapping(
            {
                "environment": "test",
                "deployment_id": "ostrading-test-ci",
                "force": True,
            }
        )
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        identities["test"].require_match(
            DatastoreIdentity(
                environment="test",
                deployment_id="ostrading-test-other",
            )
        )

    expected = identities["test"]
    identity_collection = "ostrading-test-datastore-identity"
    empty_root = tmp_path / "empty"
    preflight = FileRootIdentityPreflight(root=empty_root, expected_identity=expected)
    observed = preflight.run(initialize_if_empty=True)
    assert observed == expected
    assert json.loads((empty_root / ".ostrading-datastore-identity.json").read_text("utf-8")) == {
        "deployment_id": "ostrading-test-ci",
        "environment": "test",
    }
    assert preflight.run(initialize_if_empty=False) == expected

    uninitialized_root = tmp_path / "uninitialized"
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        FileRootIdentityPreflight(
            root=uninitialized_root,
            expected_identity=expected,
        ).run(initialize_if_empty=False)
    assert not uninitialized_root.exists()

    missing_non_empty = tmp_path / "missing-non-empty"
    missing_non_empty.mkdir()
    (missing_non_empty / "business.pdf").write_bytes(b"%PDF-1.7\n")
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        FileRootIdentityPreflight(
            root=missing_non_empty,
            expected_identity=expected,
        ).run(initialize_if_empty=True)
    assert not (missing_non_empty / ".ostrading-datastore-identity.json").exists()

    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    marker = foreign_root / ".ostrading-datastore-identity.json"
    marker.write_text(
        json.dumps(identities["production"].to_mapping()),
        encoding="utf-8",
    )
    before = marker.read_bytes()
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        FileRootIdentityPreflight(
            root=foreign_root,
            expected_identity=expected,
        ).run(initialize_if_empty=True)
    assert marker.read_bytes() == before

    qdrant = _QdrantIdentityClient(collections=())
    assert QdrantIdentityPreflight(
        client=qdrant,
        expected_identity=expected,
        collection_name=identity_collection,
    ).run(initialize_if_empty=True) == expected
    assert qdrant.initialize_calls == [expected]

    qdrant_without_initialization = _QdrantIdentityClient(collections=())
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        QdrantIdentityPreflight(
            client=qdrant_without_initialization,
            expected_identity=expected,
            collection_name=identity_collection,
        ).run(initialize_if_empty=False)
    assert qdrant_without_initialization.initialize_calls == []

    foreign_qdrant = _QdrantIdentityClient(
        collections=(identity_collection,),
        observed=identities["production"],
    )
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        QdrantIdentityPreflight(
            client=foreign_qdrant,
            expected_identity=expected,
            collection_name=identity_collection,
        ).run(initialize_if_empty=True)
    assert foreign_qdrant.initialize_calls == []

    non_empty_qdrant = _QdrantIdentityClient(collections=("knowledge_projection_local_v1",))
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        QdrantIdentityPreflight(
            client=non_empty_qdrant,
            expected_identity=expected,
            collection_name=identity_collection,
        ).run(initialize_if_empty=True)
    assert non_empty_qdrant.initialize_calls == []

    http_calls = []
    monkeypatch.setattr(
        identity_module.request,
        "urlopen",
        lambda http_request, timeout: _QdrantResponse(
            request=http_request,
            timeout=timeout,
            calls=http_calls,
            identity=expected,
        ),
    )
    rest_client = QdrantRestIdentityClient(
        base_url="http://qdrant.test:6333",
        timeout_seconds=9,
        collection_name=identity_collection,
        api_key="test-qdrant-key-identity-00000001",
    )
    assert rest_client.list_collections() == (identity_collection,)
    assert rest_client.read_identity() == expected.to_mapping()
    rest_client.initialize_identity(expected)
    assert [call[0] for call in http_calls] == ["GET", "POST", "PUT", "PUT"]
    assert all(call[2] == 9 for call in http_calls)
    assert all(call[4].get("api-key") == "test-qdrant-key-identity-00000001" for call in http_calls)

    postgres_preflight = PostgresIdentityPreflight(expected_identity=expected)
    empty_postgres = _PostgresIdentityCursor(object_count=0)
    assert postgres_preflight.run(
        empty_postgres,
        initialize_if_empty=True,
    ) == expected
    assert empty_postgres.events.index("identity:presence") < empty_postgres.events.index(
        "identity:inventory"
    ) < empty_postgres.events.index("identity:create")
    assert empty_postgres.insert_parameters == (
        expected.environment,
        expected.deployment_id,
    )
    assert any(
        "namespace.nspname NOT LIKE 'pg_toast%%'" in sql
        for sql in empty_postgres.executed_sql
    )

    postgres_without_initialization = _PostgresIdentityCursor(object_count=0)
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        postgres_preflight.run(
            postgres_without_initialization,
            initialize_if_empty=False,
        )
    assert "identity:create" not in postgres_without_initialization.events

    non_empty_postgres = _PostgresIdentityCursor(object_count=1)
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        postgres_preflight.run(non_empty_postgres, initialize_if_empty=True)
    assert "identity:create" not in non_empty_postgres.events

    legacy_postgres = _PostgresIdentityCursor(object_count=3)
    assert postgres_preflight.adopt_legacy(legacy_postgres) == expected
    assert legacy_postgres.insert_parameters == (
        expected.environment,
        expected.deployment_id,
    )
    empty_legacy_postgres = _PostgresIdentityCursor(object_count=0)
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        postgres_preflight.adopt_legacy(empty_legacy_postgres)
    assert empty_legacy_postgres.insert_parameters is None

    repository_root = Path(__file__).resolve().parents[4]
    configuration = load_application_configuration(
        config_path=repository_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    assert configuration.application.environment == "development"
    assert configuration.application.deployment_id == "ostrading-development-local"


class _QdrantIdentityClient:
    def __init__(self, *, collections, observed=None) -> None:
        self.collections = tuple(collections)
        self.observed = observed
        self.initialize_calls = []

    def list_collections(self):
        return self.collections

    def read_identity(self):
        return None if self.observed is None else self.observed.to_mapping()

    def initialize_identity(self, identity):
        self.initialize_calls.append(identity)
        self.collections = ("ostrading-test-datastore-identity",)
        self.observed = identity

    def compensate_failed_initialization(self):
        self.collections = ()
        self.observed = None


class _PostgresIdentityCursor:
    def __init__(self, *, object_count) -> None:
        self.object_count = object_count
        self.events = []
        self.executed_sql = []
        self.insert_parameters = None
        self._result = None

    def execute(self, sql, parameters=()):
        self.executed_sql.append(str(sql))
        normalized = " ".join(str(sql).split())
        if "pg_advisory_xact_lock" in normalized:
            self.events.append("identity:lock")
            self._result = None
        elif "to_regclass('platform.datastore_identity')" in normalized:
            self.events.append("identity:presence")
            self._result = (None,)
        elif "FROM pg_class AS relation" in normalized:
            self.events.append("identity:inventory")
            self._result = (self.object_count,)
        elif normalized.startswith("CREATE SCHEMA platform"):
            self.events.append("identity:create")
            self._result = None
        elif normalized.startswith("INSERT INTO platform.datastore_identity"):
            self.events.append("identity:insert")
            self.insert_parameters = parameters
            self._result = None
        else:
            self._result = None

    def fetchone(self):
        return self._result


class _QdrantResponse:
    def __init__(self, *, request, timeout, calls, identity) -> None:
        self.request = request
        self.timeout = timeout
        self.calls = calls
        self.identity = identity

    def __enter__(self):
        body = None if self.request.data is None else json.loads(self.request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in self.request.header_items()}
        self.calls.append((self.request.get_method(), self.request.full_url, self.timeout, body, headers))
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        path = self.request.full_url
        if self.request.get_method() == "GET":
            payload = {
                "result": {"collections": [{"name": "ostrading-test-datastore-identity"}]},
                "status": "ok",
            }
        elif self.request.get_method() == "POST":
            payload = {
                "result": [
                    {
                        "id": "7e7aaf4e-b479-5ceb-9187-17d07e996852",
                        "payload": self.identity.to_mapping(),
                    }
                ],
                "status": "ok",
            }
        else:
            assert "/collections/ostrading-test-datastore-identity" in path
            payload = {"result": True, "status": "ok"}
        return json.dumps(payload).encode("utf-8")
