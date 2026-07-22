"""Scénarios RED de la quatrième revue des environnements explicites."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


class _Cursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.rowcount = 0

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


def test_sonde_etrangere_valide_la_ca_et_refuse_une_erreur_tls(monkeypatch, tmp_path) -> None:
    """Given une pile étrangère active, When TLS échoue, Then la preuve est RED."""

    import app.platform.development_e2e as module

    exported: list[str] = []

    monkeypatch.setattr(
        module,
        "_foreign_edge_connection_refused",
        lambda **_arguments: False,
        raising=False,
    )

    def export_ca(*, environment, destination_path, **_arguments):
        exported.append(environment)
        destination_path.write_text(
            "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
            encoding="ascii",
        )

    monkeypatch.setattr(module, "export_environment_caddy_ca", export_ca)
    @contextmanager
    def temporary_directory(**_arguments):
        yield str(tmp_path)

    monkeypatch.setattr(module, "TemporaryDirectory", temporary_directory, raising=False)

    class TlsFailureClient:
        def get(self, _path):
            raise httpx.ConnectError("private CA rejected")

    @contextmanager
    def public_client(*, base_url, timeout_seconds, ca_bundle_path=None):
        assert base_url == "https://localhost:20443/api"
        assert timeout_seconds == 8
        assert ca_bundle_path is not None
        assert ca_bundle_path.is_file()
        yield TlsFailureClient()

    monkeypatch.setattr(module, "_foreign_public_client", public_client)
    with pytest.raises(
        module.DevelopmentE2EError,
        match="DEVELOPMENT_E2E_FOREIGN_TRANSPORT_FAILED",
    ):
        module._probe_foreign_environment(
            repository_root=Path.cwd(),
            source_environment="development",
            environment="production",
            forbidden_document_id="DOC-DEVELOPMENT-ONLY",
        )
    assert exported == ["production"]


def test_sonde_etrangere_accepte_uniquement_un_refus_explicite(monkeypatch) -> None:
    """Given aucun listener étranger, When TCP refuse, Then seulement ce cas vaut ABSENT."""

    import app.platform.development_e2e as module

    monkeypatch.setattr(
        module,
        "_foreign_edge_connection_refused",
        lambda **_arguments: True,
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "export_environment_caddy_ca",
        lambda **_arguments: pytest.fail("aucune CA ne doit être exportée après refus TCP"),
    )
    assert module._probe_foreign_environment(
        repository_root=Path.cwd(),
        source_environment="development",
        environment="test",
        forbidden_document_id="DOC-DEVELOPMENT-ONLY",
    ) == "test:ABSENT"


def test_production_sonde_test_avec_le_document_production(monkeypatch) -> None:
    """Given un document production, When test est sondé, Then son identifiant est recherché."""

    import app.platform.production_e2e as module

    observed: list[str] = []

    def probe(**arguments):
        observed.append(arguments["forbidden_document_id"])
        return "test:ISOLATED"

    monkeypatch.setattr(module, "_probe_foreign_environment", probe)
    assert module._probe_test_storage_absence(
        repository_root=Path.cwd(),
        forbidden_document_id="DOC-PRODUCTION-ONLY",
    ) == "test:ISOLATED"
    assert observed == ["DOC-PRODUCTION-ONLY"]


def test_outbox_filtre_identite_complete_avant_la_lease() -> None:
    """Given une outbox, When elle claim, Then l'identité filtre le candidat atomiquement."""

    from app.contracts.technical_jobs import JobEnvironmentIdentity
    from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox

    cursor = _Cursor()
    identity = JobEnvironmentIdentity(
        environment="development",
        deployment_id="ostrading-development-local",
        configuration_hash="a" * 64,
    )
    outbox = PostgresJobOutbox(
        connection_factory=_Factory(cursor),
        table_name="source_processing.job_outbox",
        environment_identity=identity,
    )
    assert outbox.claim_next(owner_id="relay-development", lease_seconds=30) is None
    assert len(cursor.calls) == 1
    sql, parameters = cursor.calls[0]
    assert "environment = %s" in sql
    assert "deployment_id = %s" in sql
    assert "configuration_hash = %s" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert parameters[:3] == (
        identity.environment,
        identity.deployment_id,
        identity.configuration_hash,
    )


def test_jobs_ancien_hash_sont_claims_un_par_un_et_terminalises() -> None:
    """Given un ancien hash du même déploiement, When le worker démarre, Then il devient FAILED."""

    from app.platform.job_runtime.reconciliation import reconcile_stale_configuration_jobs

    request = SimpleNamespace(job_name="PROJECT_DOCUMENT", payload={"projection_id": "PROJ-OLD"})
    claimed = SimpleNamespace(
        job=SimpleNamespace(job_id="JOB-OLD-HASH", request=request),
        lease_owner="worker-projection:reconcile",
        claim_generation=4,
        claim_token="00000000-0000-4000-8000-000000000004",
    )

    class Queue:
        def __init__(self):
            self.claims = [claimed, None]
            self.failed: list[tuple[str, str]] = []

        def claim_next_environment_mismatch(self, **_arguments):
            return self.claims.pop(0)

        def mark_failed(self, *, job_id, failure_reason, **_arguments):
            self.failed.append((job_id, failure_reason))
            return SimpleNamespace()

    queue = Queue()
    public_failures: list[object] = []
    assert reconcile_stale_configuration_jobs(
        job_queue=queue,
        job_names=("PROJECT_DOCUMENT",),
        owner_id="worker-projection:reconcile",
        lease_seconds=30,
        maximum_jobs=16,
        persist_public_failure=public_failures.append,
    ) == 1
    assert public_failures == [request]
    assert queue.failed == [("JOB-OLD-HASH", "WORKER_ENVIRONMENT_MISMATCH")]


def test_readiness_llm_compare_identite_complete(monkeypatch) -> None:
    """Given un gateway d'un autre profil, When readiness le lit, Then il reste indisponible."""

    import app.platform.llm_gateway.orchestrator_health as module
    from app.contracts.technical_jobs import JobEnvironmentIdentity
    from app.platform.llm_gateway.orchestrator_health import HttpHealthOrchestratorDependency

    expected = JobEnvironmentIdentity(
        environment="production",
        deployment_id="ostrading-production-primary",
        configuration_hash="a" * 64,
    )
    payload = {
        "service": "llm-gateway",
        "status": "ready",
        "environment": "development",
        "deployment_id": "ostrading-development-local",
        "configuration_hash": "f" * 64,
    }

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())
    dependency = HttpHealthOrchestratorDependency(
        name="llm-gateway",
        health_url="http://llm-gateway:8090/health",
        timeout_seconds=5,
        not_ready_error_code="LLM_GATEWAY_NOT_READY",
        api_key=None,
        expected_identity=expected,
    )
    assert dependency._is_ready() is False
    payload.update(expected.to_mapping())
    assert dependency._is_ready() is True


def test_gateway_publie_identite_complete_du_fichier() -> None:
    """Given production, When le gateway publie health, Then les trois champs concordent."""

    from app.platform.configuration import load_application_configuration
    from app.platform.local_runtime import _llm_gateway_readiness_response

    configuration = load_application_configuration(
        config_path=Path("config/environments/production.yaml"),
        environment_snapshot={},
    )
    status, payload = _llm_gateway_readiness_response(
        application_configuration=configuration,
    )
    assert status == 200
    assert payload["environment"] == configuration.application.environment
    assert payload["deployment_id"] == configuration.application.deployment_id
    assert payload["configuration_hash"] == configuration.configuration_hash


def test_qdrant_relit_identite_apres_perte_de_reponse_sans_supprimer() -> None:
    """Given le PUT point commité, When sa réponse est perdue, Then l'identité est relue."""

    from app.platform.datastore_identity import (
        DatastoreIdentity,
        QdrantIdentityPreflight,
    )

    expected = DatastoreIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
    )

    class AmbiguousClient:
        def __init__(self) -> None:
            self.compensated = False

        def list_collections(self):
            return ()

        def initialize_identity(self, _identity):
            raise TimeoutError("réponse perdue après commit")

        def read_identity(self):
            return expected.to_mapping()

        def compensate_failed_initialization(self):
            self.compensated = True

    client = AmbiguousClient()
    assert QdrantIdentityPreflight(
        client=client,
        expected_identity=expected,
        collection_name="ostrading-test-datastore-identity",
    ).run(initialize_if_empty=True) == expected
    assert client.compensated is False


def test_manual_review_est_protegee_par_le_middleware(tmp_path) -> None:
    """Given aucun Bearer, When manual-review est appelée, Then le handler ne s'exécute pas."""

    from app.platform.orchestrator_asgi import LocalMutationAuthorizationMiddleware

    token_path = tmp_path / "local_api_token"
    token_path.write_text("x" * 32, encoding="ascii")
    called = False
    sent: list[dict[str, object]] = []

    async def inner(_scope, _receive, send):
        nonlocal called
        called = True
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    application = LocalMutationAuthorizationMiddleware(inner, token_path=str(token_path))
    asyncio.run(
        application(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/documents/DOC-MANUAL/manual-review",
                "headers": (),
            },
            receive,
            send,
        )
    )
    assert called is False
    assert sent[0]["status"] == 401
    payload = json.loads(sent[1]["body"])
    assert payload == {"error_code": "LOCAL_API_TOKEN_REQUIRED"}
