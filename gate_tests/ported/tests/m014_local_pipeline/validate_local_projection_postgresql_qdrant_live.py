"""Preuve live T-008 : relais PostgreSQL puis génération Qdrant locale réelle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
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
from app.knowledge_access.adapters.postgres_projection_read import (
    KnowledgeProjectionVersionConflictError,
    PostgresProjectionReadRepository,
)
from app.knowledge_access.adapters.live_documentary_retrieval import (
    CanonicalProjectionChunkReader,
    DocumentaryProjectionRetriever,
    PostgresSearchableProjectionReader,
    QdrantSparseChunkSelector,
)
from app.knowledge_access.adapters.projection_runtime import (
    LOCAL_PROJECTION_PROFILE,
    QdrantHttpClient,
    ProjectionRuntimeError,
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
                observation_sink=lambda _observation: None,
            )
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE FUNCTION knowledge_access.fail_projection_job_outbox_once()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'M014_INJECTED_KA_TRANSACTION_FAILURE';
                    END;
                    $$
                    """,
                    (),
                )
                cursor.execute(
                    """
                    CREATE TRIGGER fail_projection_job_outbox_once
                    BEFORE INSERT ON knowledge_access.job_outbox
                    FOR EACH ROW EXECUTE FUNCTION
                        knowledge_access.fail_projection_job_outbox_once()
                    """,
                    (),
                )
            with pytest.raises(psycopg.errors.RaiseException):
                publication_relay.relay_pending(
                    limit=1,
                    owner_id="relay-m014-projection-live-crash",
                    lease_seconds=30,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                for table in (
                    "knowledge_access.canonical_publication_inbox",
                    "knowledge_access.projection_event_receipts",
                    "knowledge_access.knowledge_projections",
                    "knowledge_access.job_outbox",
                ):
                    cursor.execute(f"SELECT count(*) FROM {table}", ())
                    assert cursor.fetchone() == (0,)
                cursor.execute(
                    """
                    SELECT status
                      FROM source_processing.canonical_publication_outbox
                     WHERE event_id = %s
                    """,
                    (event.event_id,),
                )
                assert cursor.fetchone() == ("relaying",)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER fail_projection_job_outbox_once ON knowledge_access.job_outbox",
                    (),
                )
                cursor.execute(
                    "DROP FUNCTION knowledge_access.fail_projection_job_outbox_once()",
                    (),
                )
                cursor.execute(
                    """
                    UPDATE source_processing.canonical_publication_outbox
                       SET relay_lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE event_id = %s
                    """,
                    (event.event_id,),
                )
            with ThreadPoolExecutor(max_workers=2) as executor:
                relay_results = tuple(
                    future.result()
                    for future in (
                        executor.submit(
                            publication_relay.relay_pending,
                            limit=1,
                            owner_id=f"relay-m014-projection-live-{ordinal}",
                            lease_seconds=30,
                        )
                        for ordinal in (1, 2)
                    )
                )
            assert sorted(relay_results) == [0, 1]
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
            assert claimed.trace_id == event.correlation_id
            assert claimed.job.request.execution_requirements is not None
            assert (
                claimed.job.request.execution_requirements.contract_name
                == "project-canonical-document"
            )
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
            expired_claim = claimed
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.technical_jobs
                       SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE job_id = %s
                    """,
                    (expired_claim.job.job_id,),
                )
            claimed = queue.claim_next(
                owner_id="worker-projection-m014-live-reprise",
                lease_seconds=30,
                job_names=("PROJECT_DOCUMENT",),
            )
            assert claimed is not None
            assert claimed.claim_generation == expired_claim.claim_generation + 1
            with pytest.raises(KnowledgeProjectionVersionConflictError):
                runtime._set_running_progress(
                    claimed_job=expired_claim,
                    projection_id=claimed.job.request.payload["projection_id"],
                    completed_units=0,
                    total_units=1,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, execution_phase, completed_units, total_units
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                    """,
                    (claimed.job.request.payload["projection_id"],),
                )
                assert cursor.fetchone() == ("REQUESTED", "QUEUED", 0, 1)
            first = runtime.execute_projection(claimed_job=claimed)
            for resumable_status in ("BUILT", "INDEXING"):
                with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE knowledge_access.knowledge_projections
                           SET status = %s, execution_phase = 'RUNNING',
                               aggregate_version = aggregate_version + 1
                         WHERE projection_id = %s
                        """,
                        (
                            resumable_status,
                            claimed.job.request.payload["projection_id"],
                        ),
                    )
                resumed = runtime.execute_projection(claimed_job=claimed)
                assert resumed["index_generation"] == first["index_generation"]
            qdrant_client = QdrantHttpClient(
                base_url=f"http://127.0.0.1:{qdrant_port}",
                timeout_seconds=10,
                dense_dimensions=256,
                api_key="q" * 32,
            )
            scroll = qdrant_client._request(
                "POST",
                f"/collections/{COLLECTION}/points/scroll",
                {
                    "filter": {
                        "must": [
                            {
                                "key": "index_generation",
                                "match": {"value": first["index_generation"]},
                            }
                        ]
                    },
                    "limit": 1,
                    "with_payload": False,
                    "with_vector": False,
                },
            )
            assert scroll is not None
            deleted_point_id = scroll["result"]["points"][0]["id"]
            qdrant_client.delete(
                collection_name=COLLECTION,
                points_selector={"points": [deleted_point_id]},
            )
            with pytest.raises(
                ProjectionRuntimeError,
                match="PROJECTION_REPLAY_INCOMPLETE",
            ):
                runtime.execute_projection(claimed_job=claimed)
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, execution_phase, index_generation
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                    """,
                    (claimed.job.request.payload["projection_id"],),
                )
                assert cursor.fetchone() == (
                    "STALE",
                    "SUCCEEDED",
                    first["index_generation"],
                )
            repaired = runtime.execute_projection(claimed_job=claimed)
            assert repaired["index_generation"] == first["index_generation"]
            assert repaired["published_point_count"] == first["published_point_count"]
            replay = runtime.execute_projection(claimed_job=claimed)
            assert replay == repaired
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
            retriever = DocumentaryProjectionRetriever(
                projection_reader=PostgresSearchableProjectionReader(
                    projection_read_repository=PostgresProjectionReadRepository(
                        connection_factory=factory,
                        environment_identity=IDENTITY,
                    )
                ),
                canonical_reader=CanonicalProjectionChunkReader(
                    projection_runtime=runtime
                ),
                chunk_selector=QdrantSparseChunkSelector(
                    qdrant_url=f"http://127.0.0.1:{qdrant_port}",
                    collection_name=COLLECTION,
                    timeout_seconds=10,
                    api_key="q" * 32,
                    environment_identity=IDENTITY,
                ),
                result_limit=1,
            )
            evidences = retriever.retrieve(
                question="pipeline documentaire local",
                selected_document_ids=("DOC-M014-PROJECTION-LIVE",),
            )
            assert len(evidences) == 1
            assert {
                (source["item_id"], source["content_hash"])
                for evidence in evidences
                for source in evidence.source_locators
            } == {(locator["item_id"], locator["content_hash"])}

            artifact_path.write_bytes(b"artefact-corrompu")
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET status = 'BUILT', execution_phase = 'RUNNING',
                           failure_error_code = NULL,
                           aggregate_version = aggregate_version + 1
                     WHERE projection_id = %s
                    """,
                    (claimed.job.request.payload["projection_id"],),
                )
            with pytest.raises(
                ProjectionRuntimeError,
                match="CANONICAL_ARTIFACT_HASH_MISMATCH",
            ):
                runtime.execute_projection(claimed_job=claimed)
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, execution_phase, failure_error_code
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                    """,
                    (claimed.job.request.payload["projection_id"],),
                )
                assert cursor.fetchone() == (
                    "FAILED",
                    "FAILED",
                    "CANONICAL_ARTIFACT_HASH_MISMATCH",
                )
    finally:
        assert _docker("rm", "--force", postgres).returncode == 0
        assert _docker("rm", "--force", qdrant).returncode == 0
