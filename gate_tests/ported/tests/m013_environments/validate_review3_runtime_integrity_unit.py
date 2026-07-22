"""Scénarios RED de remédiation runtime des profils explicites."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest


class _Cursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, parameters=()):
        self.calls.append((" ".join(str(sql).split()), tuple(parameters)))

    def fetchone(self):
        return None


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def transaction(self):
        return self

    def cursor(self):
        return self._cursor


class _Factory:
    def __init__(self, cursor: _Cursor) -> None:
        self._connection = _Connection(cursor)

    def connect(self):
        return self._connection


def test_claim_vide_ne_reconcilie_jamais_un_autre_hash() -> None:
    """Given deux hashes, When un worker poll, Then il ne mute aucun job étranger."""

    from app.contracts.technical_jobs import JobEnvironmentIdentity
    from app.platform.job_runtime import JOB_RUNTIME_CATALOG
    from app.platform.job_runtime.postgres import PostgresJobQueue

    cursor = _Cursor()
    queue = PostgresJobQueue(
        connection_factory=_Factory(cursor),
        catalog=JOB_RUNTIME_CATALOG,
        environment_identity=JobEnvironmentIdentity(
            environment="development",
            deployment_id="ostrading-development-local",
            configuration_hash="a" * 64,
        ),
    )
    assert queue.claim_next(
        owner_id="worker-current",
        lease_seconds=30,
        job_names=("PROJECT_DOCUMENT",),
    ) is None
    assert len(cursor.calls) == 1
    claim_sql = cursor.calls[0][0]
    assert "configuration_hash = %s" in claim_sql
    assert "configuration_hash <> %s" not in claim_sql
    assert "SET status = 'failed'" not in claim_sql


class _LeaseQueue:
    def __init__(self) -> None:
        self.owner = "worker-a"
        self.expiry = time.monotonic() + 1
        self.renewals = 0

    def renew_lease(self, *, owner_id, lease_seconds, **_claim):
        if owner_id != self.owner or time.monotonic() >= self.expiry:
            from app.platform.job_runtime.postgres import JobLeaseConflictError

            raise JobLeaseConflictError()
        self.expiry = time.monotonic() + lease_seconds
        self.renewals += 1
        return SimpleNamespace()

    def claim_from_second_worker(self) -> bool:
        if time.monotonic() < self.expiry:
            return False
        self.owner = "worker-b"
        return True


def test_heartbeat_ka_protege_un_traitement_plus_long_que_la_lease() -> None:
    """Given un traitement KA long, When B tente après une lease, Then A la détient encore."""

    from app.platform.job_runtime.heartbeat import JobLeaseHeartbeat

    queue = _LeaseQueue()
    heartbeat = JobLeaseHeartbeat(
        job_queue=queue,
        job_id="JOB-KA-LONG",
        owner_id="worker-a",
        claim_generation=1,
        claim_token="claim-a",
        lease_seconds=1,
        heartbeat_seconds=0.2,
    )
    heartbeat.start()
    try:
        time.sleep(1.15)
        assert queue.claim_from_second_worker() is False
        assert queue.renewals >= 4
        heartbeat.finalize(lambda: "succeeded")
    finally:
        heartbeat.stop()

    import inspect
    import app.knowledge_access.adapters.worker_runtime as worker_runtime

    source = inspect.getsource(worker_runtime._run_worker)
    assert "JobLeaseHeartbeat(" in source
    assert "heartbeat.finalize(" in source


class _JsonResponse:
    def __init__(self, payload) -> None:
        import json

        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def test_conflit_qdrant_relit_identite_concurrente_sans_delete(monkeypatch) -> None:
    """Given A crée le marqueur, When B reçoit 409, Then B relit sans supprimer A."""

    import app.platform.datastore_identity as identity_module
    from app.platform.datastore_identity import (
        DatastoreIdentity,
        QdrantIdentityPreflight,
        QdrantRestIdentityClient,
    )

    expected = DatastoreIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
    )
    calls: list[tuple[str, str]] = []
    list_count = 0

    def urlopen(http_request, timeout):
        nonlocal list_count
        del timeout
        method = http_request.get_method()
        url = http_request.full_url
        calls.append((method, url))
        if method == "GET":
            list_count += 1
            collections = [] if list_count == 1 else [
                {"name": "ostrading-test-datastore-identity"}
            ]
            return _JsonResponse({"result": {"collections": collections}, "status": "ok"})
        if method == "PUT" and not url.endswith("/points?wait=true"):
            raise HTTPError(url, 409, "Conflict", {}, None)
        if method == "POST":
            return _JsonResponse(
                {
                    "result": [{"payload": expected.to_mapping()}],
                    "status": "ok",
                }
            )
        if method == "DELETE":
            raise AssertionError("la ressource du concurrent ne doit jamais être supprimée")
        raise AssertionError((method, url))

    monkeypatch.setattr(identity_module.request, "urlopen", urlopen)
    client = QdrantRestIdentityClient(
        base_url="http://qdrant-test:6333",
        timeout_seconds=5,
        collection_name="ostrading-test-datastore-identity",
        api_key="test-qdrant-key-concurrent-000001",
    )
    assert QdrantIdentityPreflight(
        client=client,
        expected_identity=expected,
        collection_name="ostrading-test-datastore-identity",
    ).run(initialize_if_empty=True) == expected
    assert all(method != "DELETE" for method, _url in calls)


class _PublicResponse:
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _ForeignPublicClient:
    def __init__(self, ready_payload, document_ids) -> None:
        self.ready_payload = ready_payload
        self.document_ids = tuple(document_ids)
        self.calls: list[str] = []

    def get(self, path):
        self.calls.append(path)
        if path == "/ready":
            return _PublicResponse(200, self.ready_payload)
        if path == "/v1/documents?limit=100":
            return _PublicResponse(
                200,
                {
                    "documents": [
                        {"document_id": document_id}
                        for document_id in self.document_ids
                    ],
                    "next_cursor": None,
                },
            )
        raise AssertionError(path)


def test_sonde_etrangere_lit_uniquement_le_contrat_public(monkeypatch) -> None:
    """Given test joignable, When development sonde, Then seule une lecture publique est faite."""

    import app.platform.development_e2e as development_e2e
    from app.platform.configuration import load_application_configuration

    repository_root = Path(__file__).resolve().parents[4]
    configuration = load_application_configuration(
        config_path=repository_root / "config/environments/test.yaml",
        environment_snapshot={},
    )
    client = _ForeignPublicClient(
        ready_payload={
            "service": "orchestrator-api",
            "status": "ready",
            "environment": "test",
            "deployment_id": "ostrading-test-ci",
            "configuration_hash": configuration.configuration_hash,
            "dependencies": [],
        },
        document_ids=("DOC-FOREIGN-SAFE",),
    )

    @contextmanager
    def public_client(*, base_url, timeout_seconds):
        assert base_url == "https://localhost:19443/api"
        assert timeout_seconds == 8
        yield client

    monkeypatch.setattr(
        development_e2e,
        "_foreign_public_client",
        public_client,
        raising=False,
    )
    assert development_e2e._probe_foreign_environment(
        repository_root=repository_root,
        source_environment="development",
        environment="test",
        forbidden_document_id="DOC-SOURCE-ONLY",
    ) == "test:ISOLATED"
    assert client.calls == ["/ready", "/v1/documents?limit=100"]

    client.document_ids = ("DOC-SOURCE-ONLY",)
    with pytest.raises(
        development_e2e.DevelopmentE2EError,
        match="DEVELOPMENT_E2E_FOREIGN_DOCUMENT_VISIBLE",
    ):
        development_e2e._probe_foreign_environment(
            repository_root=repository_root,
            source_environment="development",
            environment="test",
            forbidden_document_id="DOC-SOURCE-ONLY",
        )


def test_readiness_publie_identite_exacte_du_profil() -> None:
    """Given production, When /ready répond, Then son identité publique est exacte."""

    from fastapi import APIRouter
    from fastapi.testclient import TestClient

    from app.platform.configuration import load_application_configuration
    from app.platform.orchestrator_asgi import create_orchestrator_app
    from app.platform.orchestrator_composition import (
        DependencyReadiness,
        OrchestratorCompositionRoot,
    )

    repository_root = Path(__file__).resolve().parents[4]
    configuration = load_application_configuration(
        config_path=repository_root / "config/environments/production.yaml",
        environment_snapshot={},
    )

    class ReadyDependency:
        async def open(self):
            return None

        async def close(self):
            return None

        def readiness(self):
            return DependencyReadiness(name="postgres", status="ready")

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=lambda validated: OrchestratorCompositionRoot(
            configuration=validated,
            dependencies=(ReadyDependency(),),
            document_command_router=APIRouter(),
        ),
    )
    with TestClient(application) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "production"
    assert payload["deployment_id"] == "ostrading-production-primary"
    assert payload["configuration_hash"] == configuration.configuration_hash
