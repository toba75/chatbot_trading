"""Preuve live T-008 : relais PostgreSQL puis génération Qdrant locale réelle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import psycopg
import pytest

from app.contracts.event_envelope import EventEnvelope
from app.contracts.llm_inference import LlmInferenceResponse
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.knowledge_access.adapters.postgres_canonical_publication_relay import (
    PostgresCanonicalPublicationRelay,
)
from app.knowledge_access.adapters.projection_runtime import (
    LOCAL_PROJECTION_PROFILE,
    ProjectionRuntimeService,
)
from app.knowledge_access.application.project_published_canonical import (
    ProjectionPublicationError,
)
from app.platform.job_runtime import JobCatalog
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay
from app.platform.postgres import PostgresConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE, LOCAL_QDRANT_IMAGE
from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
)
COLLECTION = "ostrading-test-knowledge-access-m014"


class _BibliographicGateway:
    def infer(self, _request: object) -> LlmInferenceResponse:
        return LlmInferenceResponse(
            status_code=200,
            payload={
                "structured_output": {
                    "title": "Pipeline documentaire local",
                    "authors": ["Équipe OSTrading"],
                    "publication_year": "NON_RENSEIGNEE",
                    "edition": "NON_RENSEIGNEE",
                    "evidence": [
                        {
                            "field": "title",
                            "page_pdf": 1,
                            "quoted_text": "Pipeline documentaire local",
                        },
                        {
                            "field": "authors",
                            "page_pdf": 1,
                            "quoted_text": "Équipe OSTrading",
                        },
                    ],
                },
                "provenance": {
                    "model_id": "granite-live-test",
                    "model_revision": "m014",
                    "runtime_version": "1",
                },
            },
            latency_ms=1.0,
        )


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def _published_port(container: str, container_port: int) -> int:
    result = _docker("port", container, f"{container_port}/tcp")
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip().splitlines()[0].rsplit(":", 1)[1])


def _wait_postgres(container: str, factory: PostgresConnectionFactory) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1", ())
                assert cursor.fetchone() == (1,)
        except psycopg.OperationalError as error:
            if error.sqlstate is not None:
                raise
            time.sleep(0.5)
        else:
            return
    raise AssertionError(f"PostgreSQL non prêt: {container}")


def _wait_qdrant(port: int) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/collections", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise AssertionError("Qdrant T-008 non prêt")


def _event(*, artifact_sha256: str) -> EventEnvelope:
    return EventEnvelope.from_payload(
        {
            "event_id": "EVT-M014-PROJECTION-LIVE-0001",
            "event_type": "CanonicalSourcePublished",
            "event_version": 1,
            "occurred_at": "2026-07-24T10:00:00Z",
            "aggregate_type": "CanonicalSource",
            "aggregate_id": "CSRC-M014-PROJECTION-LIVE",
            "aggregate_version": 1,
            "correlation_id": "CORR-M014-PROJECTION-LIVE",
            "causation_id": "CMD-M014-PROJECTION-LIVE",
            "producer_context": "SP",
            "payload": {
                "schema_version": "1.0",
                "canonical_source_id": "CSRC-M014-PROJECTION-LIVE",
                "document_id": "DOC-M014-PROJECTION-LIVE",
                "canonical_version_id": "CVER-M014-PROJECTION-LIVE-0001",
                "source_sha256": "a" * 64,
                "canonical_artifact_sha256": artifact_sha256,
                "page_count": 1,
                "accepted_at": "2026-07-24T10:00:00Z",
                "quality_policy_version": "canonical-quality-m004-v1",
            },
        }
    )


@pytest.mark.timeout(600)
def test_projection_postgresql_qdrant_complete_rejouee_et_isolee() -> None:
    from app.platform.datastore_identity import DatastoreIdentity, PostgresIdentityPreflight
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner

    root = Path(__file__).resolve().parents[4]
    postgres = f"ostrading-m014-projection-pg-{uuid4().hex[:10]}"
    qdrant = f"ostrading-m014-projection-qdrant-{uuid4().hex[:10]}"
    password = "m014-projection-postgres-password"
    started_postgres = _docker(
        "run", "--detach", "--rm", "--name", postgres,
        "--publish", "127.0.0.1::5432", "--env", f"POSTGRES_PASSWORD={password}",
        LOCAL_POSTGRES_IMAGE,
    )
    assert started_postgres.returncode == 0, started_postgres.stderr
    started_qdrant = _docker(
        "run", "--detach", "--rm", "--name", qdrant,
        "--publish", "127.0.0.1::6333", LOCAL_QDRANT_IMAGE,
    )
    assert started_qdrant.returncode == 0, started_qdrant.stderr
    try:
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-projection-") as temporary:
            temporary_path = Path(temporary)
            password_path = temporary_path / "postgres-password"
            password_path.write_text(password, encoding="utf-8")
            factory = PsycopgConnectionFactory(
                connection_url=(
                    f"postgresql://postgres@127.0.0.1:{_published_port(postgres, 5432)}/postgres"
                ),
                password_path=password_path,
                connect_timeout_seconds=10,
            )
            _wait_postgres(postgres, factory)
            qdrant_port = _published_port(qdrant, 6333)
            _wait_qdrant(qdrant_port)
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=root / "deploy/postgres/migrations",
                operation_timeout_seconds=30,
                identity_preflight=PostgresIdentityPreflight(
                    expected_identity=DatastoreIdentity(
                        environment="test",
                        deployment_id="ostrading-test-local",
                    )
                ),
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()

            text = "Pipeline documentaire local — Équipe OSTrading"
            locator = {
                "schema_version": "1.0",
                "canonical_version_id": "CVER-M014-PROJECTION-LIVE-0001",
                "document_id": "DOC-M014-PROJECTION-LIVE",
                "page_pdf": 1,
                "item_id": "item-page-1",
                "bbox": [0.0, 0.0, 1.0, 0.2],
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            artifact = {
                "canonical_version_id": "CVER-M014-PROJECTION-LIVE-0001",
                "pages": [
                    {
                        "page_number": 1,
                        "items": [{"text": text, "provenance": locator}],
                    }
                ],
            }
            artifact_bytes = json.dumps(
                artifact,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
            event = _event(artifact_sha256=artifact_sha)
            relative_artifact = (
                "DOC-M014-PROJECTION-LIVE/"
                "CVER-M014-PROJECTION-LIVE-0001/docling.json"
            )
            artifact_ref = (
                "artifact:source_processing.canonical_sources/" + relative_artifact
            )
            canonical_root = temporary_path / "canonical-sources"
            artifact_path = canonical_root / relative_artifact
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(artifact_bytes)

            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.source_documents (
                        document_id, fingerprint, original_storage_ref, title,
                        authors, publication_year, edition, work_title,
                        work_authors, status, quarantine_reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'REGISTERED', NULL)
                    """,
                    (
                        "DOC-M014-PROJECTION-LIVE",
                        "a" * 64,
                        "artifact:source_processing.original_sources/m014-projection-live.pdf",
                        "Pipeline documentaire local",
                        ["Équipe OSTrading"],
                        2026,
                        "1",
                        "Pipeline documentaire local",
                        ["Équipe OSTrading"],
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_source_versions (
                        canonical_version_id, canonical_source_id, document_id,
                        canonical_artifact_ref, canonical_artifact_sha256,
                        route_name, tool_version, accepted_at
                    ) VALUES (%s, %s, %s, %s, %s, 'NATIVE_STANDARD', %s, %s::timestamptz)
                    """,
                    (
                        "CVER-M014-PROJECTION-LIVE-0001",
                        "CSRC-M014-PROJECTION-LIVE",
                        "DOC-M014-PROJECTION-LIVE",
                        artifact_ref,
                        artifact_sha,
                        "docling-m014-live",
                        "2026-07-24T10:00:00Z",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_publication_outbox (
                        event_id, canonical_version_id, environment, deployment_id,
                        configuration_hash, event_payload, event_fingerprint,
                        status, relay_generation
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', 0)
                    """,
                    (
                        event.event_id,
                        "CVER-M014-PROJECTION-LIVE-0001",
                        IDENTITY.environment,
                        IDENTITY.deployment_id,
                        IDENTITY.configuration_hash,
                        event.to_json(),
                        hashlib.sha256(event.to_json().encode("utf-8")).hexdigest(),
                    ),
                )

            publication_relay = PostgresCanonicalPublicationRelay(
                connection_factory=factory,
                environment_identity=IDENTITY,
                projection_profile=LOCAL_PROJECTION_PROFILE,
                configured_collection_name=COLLECTION,
            )
            assert publication_relay.relay_pending(
                limit=1,
                owner_id="relay-m014-projection-live",
                lease_seconds=30,
            ) == 1
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.canonical_publication_outbox
                       SET status = 'pending', relayed_at = NULL,
                           relay_owner = NULL, relay_lease_until = NULL,
                           relay_token = NULL
                     WHERE event_id = %s
                    """,
                    (event.event_id,),
                )
            assert publication_relay.relay_pending(
                limit=1,
                owner_id="relay-m014-projection-live-replay",
                lease_seconds=30,
            ) == 1
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM knowledge_access.knowledge_projections",
                    (),
                )
                assert cursor.fetchone() == (1,)
                cursor.execute(
                    "SELECT count(*) FROM knowledge_access.job_outbox",
                    (),
                )
                assert cursor.fetchone() == (1,)
                cursor.execute(
                    """
                    SELECT delivery_count
                      FROM knowledge_access.projection_event_receipts
                     WHERE event_id = %s
                    """,
                    (event.event_id,),
                )
                assert cursor.fetchone() == (2,)

            divergent_event = _event(artifact_sha256="d" * 64)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.canonical_publication_outbox
                       SET status = 'pending', relayed_at = NULL,
                           relay_owner = NULL, relay_lease_until = NULL,
                           relay_token = NULL, event_payload = %s::jsonb,
                           event_fingerprint = %s
                     WHERE event_id = %s
                    """,
                    (
                        divergent_event.to_json(),
                        hashlib.sha256(
                            divergent_event.to_json().encode("utf-8")
                        ).hexdigest(),
                        event.event_id,
                    ),
                )
            with pytest.raises(
                ProjectionPublicationError,
                match="PROJECTION_EVENT_REPLAY_DIVERGENCE",
            ):
                publication_relay.relay_pending(
                    limit=1,
                    owner_id="relay-m014-projection-live-divergent",
                    lease_seconds=30,
                )

            ka_outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=IDENTITY,
                table_name="knowledge_access.job_outbox",
            )
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=JobCatalog.from_job_names(("PROJECT_DOCUMENT",)),
                environment_identity=IDENTITY,
            )
            assert JobOutboxRelay(outbox=ka_outbox, consumer=queue).relay_pending(
                limit=1,
                owner_id="relay-ka-job-m014-live",
                lease_seconds=30,
            ) == 1
            claimed = queue.claim_next(
                owner_id="worker-projection-m014-live",
                lease_seconds=30,
                job_names=("PROJECT_DOCUMENT",),
            )
            assert claimed is not None
            runtime = ProjectionRuntimeService(
                connection_factory=factory,
                canonical_sources_root=canonical_root,
                environment=IDENTITY.environment,
                deployment_id=IDENTITY.deployment_id,
                configuration_hash=IDENTITY.configuration_hash,
                qdrant_url=f"http://127.0.0.1:{qdrant_port}",
                qdrant_collection_name=COLLECTION,
                qdrant_timeout_seconds=10,
                qdrant_api_key="q" * 32,
                max_parallel_workers=2,
                inference_gateway=_BibliographicGateway(),
            )
            first = runtime.execute_projection(request=claimed.job.request)
            replay = runtime.execute_projection(request=claimed.job.request)
            assert replay == first
            assert first["published_point_count"] == first["chunk_count"]
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, execution_phase, completed_units, total_units,
                           index_generation, qdrant_collection_name
                      FROM knowledge_access.knowledge_projections
                    """,
                    (),
                )
                state = cursor.fetchone()
                assert state[:4] == (
                    "SEARCHABLE",
                    "SUCCEEDED",
                    first["chunk_count"] + 1,
                    first["chunk_count"] + 1,
                )
                assert state[4:] == (first["index_generation"], COLLECTION)
                cursor.execute(
                    """
                    SELECT source_locators
                      FROM knowledge_access.knowledge_projection_chunk_samples
                     ORDER BY sample_ordinal
                    """,
                    (),
                )
                persisted_locators = {
                    item["item_id"]
                    for row in cursor.fetchall()
                    for item in row[0]
                }
                assert persisted_locators == {locator["item_id"]}
    finally:
        assert _docker("rm", "--force", postgres).returncode == 0
        assert _docker("rm", "--force", qdrant).returncode == 0
