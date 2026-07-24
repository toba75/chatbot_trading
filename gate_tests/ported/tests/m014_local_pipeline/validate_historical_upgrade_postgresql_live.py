"""Preuve PostgreSQL réelle de l'upgrade historique strict M-014."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

import psycopg
import pytest

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.platform.postgres import PostgresConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
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


def _published_port(container: str) -> int:
    published = _docker("port", container, "5432/tcp")
    assert published.returncode == 0, published.stderr
    return int(published.stdout.strip().splitlines()[0].rsplit(":", 1)[1])


def _wait_postgres(
    *,
    container: str,
    connection_factory: PostgresConnectionFactory,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: psycopg.OperationalError | None = None
    while time.monotonic() < deadline:
        state = _docker(
            "inspect",
            "--format",
            "{{.State.Running}}|{{.State.Status}}|{{.State.ExitCode}}",
            container,
        )
        assert state.returncode == 0, state.stderr
        assert state.stdout.strip().startswith("true|running|"), state.stdout
        try:
            with connection_factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1", ())
                assert cursor.fetchone() == (1,)
        except psycopg.OperationalError as error:
            if error.sqlstate is not None:
                raise
            last_error = error
            time.sleep(0.5)
        else:
            return
    raise AssertionError("PostgreSQL upgrade historique non prêt") from last_error


@pytest.mark.timeout(180)
def test_upgrade_historique_revoque_rejoue_et_exige_les_preuves_operateur() -> None:
    from app.platform.datastore_identity import DatastoreIdentity, PostgresIdentityPreflight
    from app.platform.job_runtime import JobCatalog
    from app.platform.job_runtime.postgres import PostgresJobQueue
    from app.platform.job_runtime.relay import (
        ClaimedRelayMessage,
        JobOutboxRelay,
        RelayedJobMessage,
    )
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.source_processing.adapters.postgres_job_outbox import (
        JobOutboxLeaseConflictError,
        PostgresJobOutbox,
    )

    repository_root = Path(__file__).resolve().parents[4]
    migrations = repository_root / "deploy" / "postgres" / "migrations"
    container = f"ostrading-m014-upgrade-{uuid4().hex[:12]}"
    password = "m014-historical-upgrade-password"
    started = _docker(
        "run",
        "--detach",
        "--rm",
        "--name",
        container,
        "--publish",
        "127.0.0.1::5432",
        "--env",
        f"POSTGRES_PASSWORD={password}",
        LOCAL_POSTGRES_IMAGE,
    )
    assert started.returncode == 0, started.stderr
    try:
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-upgrade-") as temporary:
            temporary_path = Path(temporary)
            password_path = temporary_path / "postgres-password"
            password_path.write_text(password, encoding="utf-8")
            factory = PsycopgConnectionFactory(
                connection_url=(
                    f"postgresql://postgres@127.0.0.1:{_published_port(container)}/postgres"
                ),
                password_path=password_path,
                connect_timeout_seconds=10,
            )
            _wait_postgres(
                container=container,
                connection_factory=factory,
                timeout_seconds=60,
            )
            preflight = PostgresIdentityPreflight(
                expected_identity=DatastoreIdentity(
                    environment=IDENTITY.environment,
                    deployment_id=IDENTITY.deployment_id,
                )
            )
            migrations_027 = temporary_path / "migrations-027"
            migrations_027.mkdir()
            for path in sorted(migrations.glob("*.sql")):
                if int(path.name[:3]) <= 27:
                    shutil.copy2(path, migrations_027 / path.name)
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations_027,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()

            historical_ka_claim_token = str(uuid4())
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.source_documents (
                        document_id, fingerprint, original_storage_ref, title,
                        authors, publication_year, edition, work_title,
                        work_authors, status, quarantine_reason
                    ) VALUES (
                        'DOC-M014-HISTORICAL-UPGRADE', %s,
                        'artifact:source_processing.original_sources/historical-upgrade.pdf',
                        'Upgrade historique', ARRAY['OSTrading'], 2026, '1',
                        'Upgrade historique', ARRAY['OSTrading'], 'REGISTERED', NULL
                    )
                    """,
                    ("a" * 64,),
                )
                cursor.execute(
                    """
                    INSERT INTO source_processing.job_outbox (
                        environment, deployment_id, job_name, priority,
                        input_hash, configuration_hash, code_version,
                        model_version, payload, trace_id, status
                    ) VALUES (
                        'test', 'ostrading-test-local', 'CONVERT_DOCUMENT', 'P1',
                        %s, %s, 'm004-historical-v1', 'docling-m004-v1',
                        '{"document_id":"DOC-M014-HISTORICAL-UPGRADE"}'::jsonb,
                        'TRACE-M014-HISTORICAL-UPGRADE', 'pending'
                    ) RETURNING outbox_id
                    """,
                    ("a" * 64, IDENTITY.configuration_hash),
                )
                outbox_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO source_processing.document_conversion_requests (
                        document_id, conversion_status, canonical_version_id,
                        rejection_error_code, submission_id, job_id,
                        execution_phase, completed_units, total_units,
                        failure_error_code, orchestration_version
                    ) VALUES (
                        'DOC-M014-HISTORICAL-UPGRADE', 'CONVERSION_REQUESTED', NULL,
                        NULL, %s, NULL, 'QUEUED', 0, 3, NULL, 'm004-inline-v1'
                    )
                    """,
                    (outbox_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_source_versions (
                        canonical_version_id, canonical_source_id, document_id,
                        canonical_artifact_ref, canonical_artifact_sha256,
                        route_name, tool_version, accepted_at
                    ) VALUES (
                        'CVER-M014-HISTORICAL-UPGRADE', 'CSRC-M014-HISTORICAL-UPGRADE',
                        'DOC-M014-HISTORICAL-UPGRADE',
                        'artifact:source_processing.canonical_sources/'
                        'CSRC-M014-HISTORICAL-UPGRADE/'
                        'CVER-M014-HISTORICAL-UPGRADE/docling.json',
                        %s, 'NATIVE_STANDARD', 'docling-m004-v1',
                        '2026-07-24T10:00:00Z'::timestamptz
                    )
                    """,
                    ("b" * 64,),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version
                    ) VALUES (
                        'PROJ-M014-HISTORICAL-UPGRADE',
                        'DOC-M014-HISTORICAL-UPGRADE',
                        'CVER-M014-HISTORICAL-UPGRADE', 'historical-profile',
                        'historical-chunking', 'historical-embedding',
                        'historical-sparse', 'historical-schema', %s,
                        'REQUESTED', 0, CURRENT_TIMESTAMP, 0
                    )
                    """,
                    ("d" * 64,),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.canonical_publication_inbox (
                        event_id, event_fingerprint, canonical_version_id,
                        document_id, canonical_artifact_ref,
                        canonical_artifact_sha256, environment, deployment_id,
                        configuration_hash, event_payload
                    ) VALUES (
                        'EVT-M014-HISTORICAL-UPGRADE', %s,
                        'CVER-M014-HISTORICAL-UPGRADE',
                        'DOC-M014-HISTORICAL-UPGRADE',
                        'artifact:source_processing.canonical_sources/'
                        'CSRC-M014-HISTORICAL-UPGRADE/'
                        'CVER-M014-HISTORICAL-UPGRADE/docling.json',
                        %s, 'test', 'ostrading-test-local', %s,
                        '{"event_type":"CanonicalSourcePublished"}'::jsonb
                    )
                    """,
                    ("1" * 64, "b" * 64, "f" * 64),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.job_outbox (
                        environment, deployment_id, job_name, priority,
                        input_hash, configuration_hash, code_version,
                        model_version, payload, trace_id, status,
                        relay_attempts, relay_owner, relay_lease_expires_at,
                        relay_claim_generation, relay_claim_token
                    ) VALUES (
                        'test', 'ostrading-test-local', 'PROJECT_DOCUMENT', 'P1',
                        %s, %s, 'm005-historical-v1',
                        'hashing-dense-256-v1',
                        '{"projection_id":"PROJ-M014-HISTORICAL-UPGRADE",'
                        '"document_id":"DOC-M014-HISTORICAL-UPGRADE",'
                        '"canonical_version_id":"CVER-M014-HISTORICAL-UPGRADE"}'::jsonb,
                        'TRACE-M014-HISTORICAL-PROJECTION', 'relaying',
                        1, 'relay-ka-before-upgrade',
                        CURRENT_TIMESTAMP + INTERVAL '5 minutes',
                        1, %s::uuid
                    ) RETURNING outbox_id, payload
                    """,
                    ("d" * 64, "f" * 64, historical_ka_claim_token),
                )
                historical_ka_outbox_id, historical_ka_payload = cursor.fetchone()
                historical_ka_message = RelayedJobMessage(
                    message_id=historical_ka_outbox_id,
                    environment="test",
                    deployment_id="ostrading-test-local",
                    job_name="PROJECT_DOCUMENT",
                    priority="P1",
                    input_hash="d" * 64,
                    configuration_hash="f" * 64,
                    code_version="m005-historical-v1",
                    model_version="hashing-dense-256-v1",
                    payload=historical_ka_payload,
                    trace_id="TRACE-M014-HISTORICAL-PROJECTION",
                    execution_requirements=None,
                )
                cursor.execute(
                    """
                    INSERT INTO platform.technical_jobs (
                        environment, deployment_id, job_name, priority,
                        input_hash, configuration_hash, code_version,
                        model_version, payload, trace_id, status,
                        recalculation_number, lease_owner, lease_expires_at,
                        execution_attempts, claim_generation, claim_token,
                        source_message_id, source_message_hash
                    ) VALUES (
                        'test', 'ostrading-test-local', 'PROJECT_DOCUMENT', 'P1',
                        %s, %s, 'm005-historical-v1',
                        'hashing-dense-256-v1',
                        '{"projection_id":"PROJ-M014-HISTORICAL-UPGRADE",'
                        '"document_id":"DOC-M014-HISTORICAL-UPGRADE",'
                        '"canonical_version_id":"CVER-M014-HISTORICAL-UPGRADE"}'::jsonb,
                        'TRACE-M014-HISTORICAL-PROJECTION', 'running', 0,
                        'worker-ka-before-upgrade',
                        CURRENT_TIMESTAMP + INTERVAL '5 minutes',
                        1, 1, gen_random_uuid(), %s, %s
                    ) RETURNING job_id
                    """,
                    (
                        "d" * 64,
                        "f" * 64,
                        historical_ka_outbox_id,
                        historical_ka_message.content_hash,
                    ),
                )
                historical_project_job_id = cursor.fetchone()[0]

            old_ka_relay_claim = ClaimedRelayMessage(
                message=historical_ka_message,
                owner_id="relay-ka-before-upgrade",
                claim_generation=1,
                claim_token=historical_ka_claim_token,
            )

            outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=IDENTITY,
            )
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=JobCatalog.from_job_names(("CONVERT_DOCUMENT",)),
                environment_identity=IDENTITY,
            )
            old_relay_claim = outbox.claim_next(
                owner_id="relay-before-upgrade",
                lease_seconds=300,
            )
            assert old_relay_claim is not None
            platform_job_id = queue.consume_relay_message(old_relay_claim.message)
            old_worker_claim = queue.claim_next(
                owner_id="worker-before-upgrade",
                lease_seconds=300,
                job_names=("CONVERT_DOCUMENT",),
            )
            assert old_worker_claim is not None
            assert old_worker_claim.job.job_id == platform_job_id

            runner = PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=False,
                adopt_legacy_if_unidentified=False,
            )
            runner.run()
            runner.run()
            assert runner.required_schema_version == 29
            assert runner.is_required_schema_ready()

            with pytest.raises(JobOutboxLeaseConflictError):
                outbox.acknowledge(old_relay_claim, platform_job_id=platform_job_id)
            ka_outbox_before_qualification = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=JobEnvironmentIdentity(
                    environment="test",
                    deployment_id="ostrading-test-local",
                    configuration_hash="f" * 64,
                ),
                table_name="knowledge_access.job_outbox",
            )
            with pytest.raises(JobOutboxLeaseConflictError):
                ka_outbox_before_qualification.acknowledge(
                    old_ka_relay_claim,
                    platform_job_id=historical_project_job_id,
                )

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, lease_owner, lease_expires_at, claim_token,
                           claim_generation, execution_attempts,
                           source_message_id, source_message_hash
                      FROM platform.technical_jobs
                     WHERE job_id = %s
                    """,
                    (platform_job_id,),
                )
                state = cursor.fetchone()
                assert state[:4] == ("pending", None, None, None)
                assert state[4] == state[5]
                assert state[6:] == (None, None)
                cursor.execute(
                    """
                    SELECT to_regclass(
                        'source_processing.historical_canonical_reconciliation'
                    )
                    """,
                    (),
                )
                assert cursor.fetchone() == (
                    "source_processing.historical_canonical_reconciliation",
                )
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM source_processing.canonical_publication_outbox
                     WHERE canonical_version_id = 'CVER-M014-HISTORICAL-UPGRADE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    """
                    SELECT quality_policy_version, consumer_environment,
                           consumer_deployment_id, consumer_configuration_hash
                      FROM source_processing.historical_canonical_reconciliation
                     WHERE canonical_version_id = 'CVER-M014-HISTORICAL-UPGRADE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (None, None, None, None)
                cursor.execute(
                    """
                    SELECT source_processing.qualify_historical_canonical_publication(
                        'CVER-M014-HISTORICAL-UPGRADE',
                        'test', 'ostrading-test-local', %s,
                        'canonical-quality-operator-v1',
                        'test', 'ostrading-test-local', %s
                    )
                    """,
                    (IDENTITY.configuration_hash, "e" * 64),
                )
                cursor.fetchone()
                cursor.execute(
                    """
                    SELECT producer_configuration_hash,
                           consumer_configuration_hash,
                           quality_policy_version, status
                      FROM source_processing.historical_canonical_reconciliation
                     WHERE canonical_version_id =
                           'CVER-M014-HISTORICAL-UPGRADE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (
                    IDENTITY.configuration_hash,
                    "e" * 64,
                    "canonical-quality-operator-v1",
                    "qualified",
                )
                cursor.execute(
                    """
                    SELECT configuration_hash, status,
                           event_payload -> 'payload' ->> 'quality_policy_version'
                      FROM source_processing.canonical_publication_outbox
                     WHERE canonical_version_id =
                           'CVER-M014-HISTORICAL-UPGRADE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (
                    "e" * 64,
                    "pending",
                    "canonical-quality-operator-v1",
                )
                cursor.execute(
                    """
                    SELECT producer_configuration_hash,
                           qdrant_collection_name, consumer_configuration_hash,
                           status
                      FROM knowledge_access.historical_projection_reconciliation
                     WHERE projection_id = 'PROJ-M014-HISTORICAL-UPGRADE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (
                    "f" * 64,
                    None,
                    None,
                    "reconciliation_required",
                )
                cursor.execute(
                    """
                    SELECT status, claim_generation, execution_attempts,
                           source_message_id, source_message_hash
                      FROM platform.technical_jobs
                     WHERE job_id = %s
                    """,
                    (historical_project_job_id,),
                )
                project_state = cursor.fetchone()
                assert project_state[:3] == ("pending", 1, 1)
                assert project_state[3:] == (
                    historical_ka_outbox_id,
                    historical_ka_message.content_hash,
                )
                cursor.execute(
                    """
                    SELECT knowledge_access.qualify_historical_projection(
                        'PROJ-M014-HISTORICAL-UPGRADE',
                        'operator-supplied-qdrant-collection',
                        'test', 'ostrading-test-local', %s
                    )
                    """,
                    ("e" * 64,),
                )
                cursor.fetchone()

            relay = JobOutboxRelay(outbox=outbox, consumer=queue)
            assert relay.relay_pending(
                limit=1,
                owner_id="relay-after-upgrade",
                lease_seconds=30,
            ) == 1
            assert relay.relay_pending(
                limit=1,
                owner_id="relay-after-upgrade-replay",
                lease_seconds=30,
            ) == 0
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*), min(source_message_id),
                           min(source_message_hash), max(source_message_hash)
                      FROM platform.technical_jobs
                     WHERE job_name = 'CONVERT_DOCUMENT'
                       AND input_hash = %s
                    """,
                    ("a" * 64,),
                )
                count, source_id, minimum_hash, maximum_hash = cursor.fetchone()
                assert count == 1
                assert source_id == outbox_id
                assert minimum_hash == maximum_hash
                assert minimum_hash is not None

            claimed_after_upgrade = queue.claim_next(
                owner_id="worker-after-upgrade",
                lease_seconds=30,
                job_names=("CONVERT_DOCUMENT",),
            )
            assert claimed_after_upgrade is not None
            assert claimed_after_upgrade.job.job_id == platform_job_id

            active_projection_identity = JobEnvironmentIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
                configuration_hash="e" * 64,
            )
            active_ka_outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=active_projection_identity,
                table_name="knowledge_access.job_outbox",
            )
            active_projection_queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=JobCatalog.from_job_names(("PROJECT_DOCUMENT",)),
                environment_identity=active_projection_identity,
            )
            projection_relay = JobOutboxRelay(
                outbox=active_ka_outbox,
                consumer=active_projection_queue,
            )
            assert projection_relay.relay_pending(
                limit=1,
                owner_id="relay-ka-after-qualification",
                lease_seconds=30,
            ) == 1
            assert projection_relay.relay_pending(
                limit=1,
                owner_id="relay-ka-after-qualification-replay",
                lease_seconds=30,
            ) == 0
            claimed_projection = active_projection_queue.claim_next(
                owner_id="worker-ka-after-upgrade",
                lease_seconds=30,
                job_names=("PROJECT_DOCUMENT",),
            )
            assert claimed_projection is not None
            assert claimed_projection.job.job_id == historical_project_job_id
            assert (
                claimed_projection.job.request.payload["qdrant_collection_name"]
                == "operator-supplied-qdrant-collection"
            )

            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version
                    ) VALUES (
                        'PROJ-M014-PARTIAL-CHECK',
                        'DOC-M014-HISTORICAL-UPGRADE',
                        'CVER-M014-HISTORICAL-UPGRADE', 'partial-check-profile',
                        'partial-check-chunking', 'partial-check-embedding',
                        'partial-check-sparse', 'partial-check-schema', %s,
                        'REQUESTED', 0, CURRENT_TIMESTAMP, 0
                    )
                    """,
                    ("9" * 64,),
                )

            with factory.connect() as connection:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE source_processing.canonical_source_versions
                               SET canonical_assembly_id = %s
                             WHERE canonical_version_id =
                                   'CVER-M014-HISTORICAL-UPGRADE'
                            """,
                            ("e" * 64,),
                        )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE knowledge_access.knowledge_projections
                               SET environment = 'test'
                             WHERE projection_id =
                                   'PROJ-M014-PARTIAL-CHECK'
                            """,
                            (),
                        )
    finally:
        removed = _docker("rm", "--force", container)
        assert removed.returncode == 0, removed.stderr
