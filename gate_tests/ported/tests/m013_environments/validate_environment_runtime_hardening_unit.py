from __future__ import annotations

import inspect
from pathlib import Path

import pytest


def test_environment_runtime_hardening_unit(tmp_path: Path) -> None:
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
    restore_source = inspect.getsource(restore._restore_manifest)
    assert "ignore_errors=True" not in restore_source
    assert "RESTORE_COMPENSATION_FAILED" in restore_source


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
