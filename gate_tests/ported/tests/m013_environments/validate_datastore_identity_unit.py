from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_datastore_identity_unit(tmp_path: Path) -> None:
    from app.platform.datastore_identity import (
        DATASTORE_ENVIRONMENT_MISMATCH,
        DatastoreEnvironmentMismatchError,
        DatastoreIdentity,
        FileRootIdentityPreflight,
        QdrantIdentityPreflight,
    )

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

    expected = identities["test"]
    empty_root = tmp_path / "empty"
    preflight = FileRootIdentityPreflight(root=empty_root, expected_identity=expected)
    observed = preflight.run(initialize_if_empty=True)
    assert observed == expected
    assert json.loads((empty_root / ".ostrading-datastore-identity.json").read_text("utf-8")) == {
        "deployment_id": "ostrading-test-ci",
        "environment": "test",
    }
    assert preflight.run(initialize_if_empty=False) == expected

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
    ).run(initialize_if_empty=True) == expected
    assert qdrant.initialize_calls == [expected]

    foreign_qdrant = _QdrantIdentityClient(
        collections=("platform_datastore_identity_v1",),
        observed=identities["production"],
    )
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        QdrantIdentityPreflight(
            client=foreign_qdrant,
            expected_identity=expected,
        ).run(initialize_if_empty=True)
    assert foreign_qdrant.initialize_calls == []

    non_empty_qdrant = _QdrantIdentityClient(collections=("knowledge_projection_local_v1",))
    with pytest.raises(DatastoreEnvironmentMismatchError, match=DATASTORE_ENVIRONMENT_MISMATCH):
        QdrantIdentityPreflight(
            client=non_empty_qdrant,
            expected_identity=expected,
        ).run(initialize_if_empty=True)
    assert non_empty_qdrant.initialize_calls == []


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
        self.collections = ("platform_datastore_identity_v1",)
        self.observed = identity

