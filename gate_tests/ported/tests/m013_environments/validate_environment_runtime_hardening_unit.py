from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest


def test_environment_runtime_hardening_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given trois profils, When un participant agit, Then son identité précède tout effet."""

    from app.platform.configuration import load_application_configuration
    from app.platform.datastore_identity import (
        DatastoreIdentity,
        QdrantIdentityPreflight,
    )
    from app.platform.environment_compose import (
        EXPECTED_SERVICE_REPLICAS,
        REQUIRED_SERVICE_IDS,
    )
    from app.platform.worker_environment import (
        WORKER_JOB_NAMES,
        WorkerHealthFilePublisher,
        read_worker_health_file,
    )

    # Les actions sans chaîne API -> outbox -> relais -> worker -> lecture publique
    # ne sont pas annoncées par une boucle factice qui attend indéfiniment.
    assert WORKER_JOB_NAMES == {
        "worker-documents": ("DIAGNOSE", "CONVERT_DOCUMENT"),
        "worker-projection": ("PROJECT_DOCUMENT",),
    }
    assert "worker-research" not in REQUIRED_SERVICE_IDS
    assert "worker-backtest" not in REQUIRED_SERVICE_IDS
    assert "backtest-engine" not in REQUIRED_SERVICE_IDS
    assert EXPECTED_SERVICE_REPLICAS == {
        **{service: 1 for service in REQUIRED_SERVICE_IDS if not service.startswith("worker-")},
        "worker-documents": 2,
        "worker-projection": 2,
    }
    assert sum(EXPECTED_SERVICE_REPLICAS.values()) == 14

    repository_root = Path(__file__).resolve().parents[4]
    configuration = load_application_configuration(
        config_path=repository_root / "config/environments/development.yaml",
        environment_snapshot={},
    )
    health_path = tmp_path / "worker-health.json"
    publisher = WorkerHealthFilePublisher(
        binding=__import__(
            "app.platform.worker_environment", fromlist=["build_worker_environment_binding"]
        ).build_worker_environment_binding(configuration, worker_id="worker-documents"),
        path=health_path,
        heartbeat_interval_seconds=0.01,
    )
    publisher.publish_once()
    observed = read_worker_health_file(
        path=health_path,
        expected_identity=publisher.binding.identity,
        expected_worker_id="worker-documents",
        maximum_age_seconds=1.0,
    )
    assert observed["status"] == "ready"
    assert observed["environment"] == "development"
    assert observed["deployment_id"] == "ostrading-development-local"
    assert observed["configuration_hash"] == configuration.configuration_hash
    stale_payload = dict(observed)
    stale_payload["updated_at_epoch"] = 0.0
    health_path.write_text(json.dumps(stale_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="WORKER_HEALTH_STALE"):
        read_worker_health_file(
            path=health_path,
            expected_identity=publisher.binding.identity,
            expected_worker_id="worker-documents",
            maximum_age_seconds=1.0,
        )

    # Une panne après création de la collection d'identité est compensée. Le retry
    # repart de zéro et ne peut donc pas adopter une collection étrangère.
    identity = DatastoreIdentity(
        environment="development",
        deployment_id="ostrading-development-local",
    )
    qdrant = _FailingQdrantIdentityClient("ostrading-development-datastore-identity")
    preflight = QdrantIdentityPreflight(
        client=qdrant,
        expected_identity=identity,
        collection_name="ostrading-development-datastore-identity",
    )
    with pytest.raises(RuntimeError, match="QDRANT_POINT_WRITE_FAILED"):
        preflight.run(initialize_if_empty=True)
    assert qdrant.collections == ()
    assert qdrant.compensations == 1
    assert preflight.run(initialize_if_empty=True) == identity
    assert qdrant.observed == identity

    # Les points d'entrée long-vivants et administratifs contrôlent le vrai
    # snapshot de processus; aucun dictionnaire vide ne masque une variable interdite.
    import app.knowledge_access.adapters.worker_runtime as ka_worker
    import app.source_processing.adapters.worker_runtime as sp_worker
    import app.platform.postgres_migrations as migrations
    import ost_gate.operations.backup as backup
    import ost_gate.operations.restore as restore

    for module in (ka_worker, sp_worker, migrations, backup, restore):
        source = inspect.getsource(module)
        assert "environment_snapshot=dict(os.environ)" in source

    migration_sql = (repository_root / "deploy/postgres/migrations/020_job_environment_identity.sql").read_text(
        encoding="utf-8"
    )
    assert "IF NOT EXISTS" in migration_sql
    assert "MIGRATION_020_LEGACY_ADOPTION_REQUIRED" in migration_sql
    assert "NOT VALID" in migration_sql
    assert "VALIDATE CONSTRAINT" in migration_sql

    # Les neuf racines déclarées sont contrôlées avant toute création de rapport.
    for module_name in (
        "app.platform.development_e2e",
        "app.platform.test_e2e",
        "app.platform.production_e2e",
    ):
        module = __import__(module_name, fromlist=["*"])
        source = inspect.getsource(module)
        assert "preflight_all_mutable_roots" in source
        assert source.index("preflight_all_mutable_roots") < source.index("report_root.mkdir")

    # Les sauvegardes/restaurations hôte passent explicitement par le service
    # administratif Compose du profil au lieu d'appeler les DNS internes depuis l'hôte.
    assert "docker" in inspect.getsource(backup.execute_compose_storage_command)
    assert "orchestrator-api" in inspect.getsource(backup.execute_compose_storage_command)
    assert "input=manifest_document" in inspect.getsource(
        backup.execute_compose_storage_command
    )
    dockerfile = (repository_root / "deploy/local-compose/Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "COPY --chown=ostrading:ostrading ost_gate ./ost_gate" in dockerfile
    restore_source = inspect.getsource(restore._restore_manifest)
    assert "ignore_errors=True" not in restore_source
    assert "RESTORE_COMPENSATION_FAILED" in restore_source

    # La clé Qdrant du profil est transmise à tous les appels REST ; aucun client
    # d'identité, d'écriture, de recherche ou de readiness ne reste anonyme.
    from app.knowledge_access.adapters import live_documentary_retrieval, projection_runtime
    from app.knowledge_access.adapters.live_documentary_retrieval import QdrantSparseChunkSelector
    from app.knowledge_access.adapters.projection_runtime import QdrantHttpClient

    qdrant_calls = []
    monkeypatch.setattr(
        projection_runtime,
        "urlopen",
        lambda request, timeout: _QdrantJsonResponse(
            request=request,
            timeout=timeout,
            calls=qdrant_calls,
            payload={"result": {"status": "green"}, "status": "ok"},
        ),
    )
    QdrantHttpClient(
        base_url="http://qdrant-development:6333",
        timeout_seconds=5,
        dense_dimensions=8,
        api_key="development-qdrant-key-000000000001",
    ).ensure_collection(collection_name="ostrading-development-knowledge-access")

    monkeypatch.setattr(
        live_documentary_retrieval,
        "urlopen",
        lambda request, timeout: _QdrantJsonResponse(
            request=request,
            timeout=timeout,
            calls=qdrant_calls,
            payload={"result": {"points": []}, "status": "ok"},
        ),
    )
    assert QdrantSparseChunkSelector(
        qdrant_url="http://qdrant-development:6333",
        collection_name="ostrading-development-knowledge-access",
        timeout_seconds=5,
        api_key="development-qdrant-key-000000000001",
    ).select_chunk_ids(
        projection_id="PROJ-" + "A" * 64,
        question="Quelle preuve ?",
        limit=4,
    ) == ()
    assert len(qdrant_calls) == 2
    assert all(
        call["headers"].get("api-key") == "development-qdrant-key-000000000001"
        for call in qdrant_calls
    )

    from app.platform.llm_gateway import orchestrator_health
    from app.platform.llm_gateway.orchestrator_health import HttpHealthOrchestratorDependency

    monkeypatch.setattr(
        orchestrator_health,
        "urlopen",
        lambda request, timeout: _QdrantJsonResponse(
            request=request,
            timeout=timeout,
            calls=qdrant_calls,
            payload={"status": "ok"},
        ),
    )
    assert HttpHealthOrchestratorDependency(
        name="qdrant",
        health_url="http://qdrant-development:6333/healthz",
        timeout_seconds=5,
        not_ready_error_code="QDRANT_NOT_READY",
        api_key="development-qdrant-key-000000000001",
    )._is_ready()
    assert qdrant_calls[-1]["headers"].get("api-key") == (
        "development-qdrant-key-000000000001"
    )


class _FailingQdrantIdentityClient:
    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self.collections: tuple[str, ...] = ()
        self.observed = None
        self.failures_remaining = 1
        self.compensations = 0

    def list_collections(self):
        return self.collections

    def read_identity(self):
        return None if self.observed is None else self.observed.to_mapping()

    def initialize_identity(self, identity):
        self.collections = (self.collection_name,)
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("QDRANT_POINT_WRITE_FAILED")
        self.observed = identity

    def compensate_failed_initialization(self):
        self.compensations += 1
        self.collections = ()
        self.observed = None


class _QdrantJsonResponse:
    def __init__(self, *, request, timeout, calls, payload) -> None:
        self.request = request
        self.timeout = timeout
        self.calls = calls
        self.payload = payload
        self.status = 200

    def __enter__(self):
        self.calls.append(
            {
                "headers": {key.lower(): value for key, value in self.request.header_items()},
                "timeout": self.timeout,
                "url": self.request.full_url,
            }
        )
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")
