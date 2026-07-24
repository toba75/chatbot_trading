"""Preuve PostgreSQL réelle T-005 du fan-out transactionnel et de son relais."""

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
from app.source_processing.application.fan_out_document_pages import (
    DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    FanOutDocumentPagesHandler,
)
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
)
from validate_page_fan_out_unit import (
    _assets,
    _parent_job,
    _planned_run,
    _source,
    _source_artifact,
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
    raise AssertionError("PostgreSQL T-005 non prêt") from last_error


@pytest.mark.timeout(180)
def test_fan_out_postgresql_rollback_rejeu_relais_et_refus_divergent() -> None:
    from app.platform.datastore_identity import (
        DatastoreIdentity,
        PostgresIdentityPreflight,
    )
    from app.platform.job_runtime import JobCatalog
    from app.platform.job_runtime.postgres import PostgresJobQueue
    from app.platform.job_runtime.relay import JobOutboxRelay
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.source_processing.adapters.postgres_document_persistence import (
        PostgresDocumentConversionRepository,
        PostgresDocumentPersistence,
        PostgresProcessingRunRepository,
    )
    from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox

    repository_root = Path(__file__).resolve().parents[4]
    migrations = repository_root / "deploy" / "postgres" / "migrations"
    container = f"ostrading-m014-fanout-{uuid4().hex[:12]}"
    password = "m014-fanout-postgres-password"
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
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-fanout-") as temporary:
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
                    environment="test",
                    deployment_id="ostrading-test-local",
                )
            )
            migrations_022 = temporary_path / "migrations-022"
            migrations_022.mkdir()
            for path in sorted(migrations.glob("*.sql")):
                if int(path.name[:3]) <= 22:
                    shutil.copy2(path, migrations_022 / path.name)
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations_022,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()
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
            assert runner.required_schema_version == 23
            assert runner.is_required_schema_ready()

            source = _source()
            run = _planned_run(source)
            persistence = PostgresDocumentPersistence(connection_factory=factory)
            assert persistence.save_if_absent(source) is None
            persistence.save(run)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.document_conversion_requests (
                        document_id, conversion_status, canonical_version_id,
                        rejection_error_code, submission_id, job_id,
                        execution_phase, completed_units, total_units,
                        failure_error_code, orchestration_version
                    )
                    VALUES (%s, 'CONVERSION_REQUESTED', NULL, NULL, %s, NULL,
                            'QUEUED', 0, 4, NULL, 'm004-inline-v1')
                    """,
                    (source.document_id.value, "OUTBOX-SP-M014-FANOUT-PARENT"),
                )

            repository = PostgresDocumentConversionRepository(persistence)
            handler = FanOutDocumentPagesHandler(
                processing_run_repository=PostgresProcessingRunRepository(persistence),
                page_fan_out_repository=repository,
                locked_assets=_assets(),
            )
            parent_job = _parent_job(source, run)

            # Un traitement déjà lié au parcours historique ne bascule jamais.
            with pytest.raises(
                DistributionContractError,
                match="PAGE_FAN_OUT_ORCHESTRATION_VERSION_CONFLICT",
            ):
                handler.handle(
                    parent_job=parent_job,
                    source_artifact=_source_artifact(source),
                    trace_id="TRACE-M014-FANOUT-LIVE",
                )

            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET orchestration_version = %s
                     WHERE document_id = %s
                    """,
                    (DISTRIBUTED_PAGE_FAN_OUT_VERSION, source.document_id.value),
                )
                cursor.execute(
                    """
                    CREATE FUNCTION source_processing.fail_partial_fan_out_for_test()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        IF NEW.job_name = 'CONVERT_PAGE'
                           AND (NEW.payload ->> 'page_number')::integer = 3 THEN
                            RAISE EXCEPTION 'M014_TEST_PARTIAL_FAN_OUT';
                        END IF;
                        RETURN NEW;
                    END $$
                    """,
                    (),
                )
                cursor.execute(
                    """
                    CREATE TRIGGER fail_partial_fan_out_for_test
                    BEFORE INSERT ON source_processing.job_outbox
                    FOR EACH ROW EXECUTE FUNCTION
                        source_processing.fail_partial_fan_out_for_test()
                    """,
                    (),
                )

            # Un crash après les premiers inserts annule résultat, état et outbox.
            with pytest.raises(Exception, match="M014_TEST_PARTIAL_FAN_OUT"):
                handler.handle(
                    parent_job=parent_job,
                    source_artifact=_source_artifact(source),
                    trace_id="TRACE-M014-FANOUT-LIVE",
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM source_processing.document_page_fanouts", ())
                assert cursor.fetchone() == (0,)
                cursor.execute("SELECT count(*) FROM source_processing.page_execution_results", ())
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    "SELECT count(*) FROM source_processing.job_outbox WHERE job_name = 'CONVERT_PAGE'",
                    (),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    """
                    SELECT execution_phase, completed_units, total_units
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == ("QUEUED", 0, 4)

            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER fail_partial_fan_out_for_test ON source_processing.job_outbox",
                    (),
                )
                cursor.execute(
                    "DROP FUNCTION source_processing.fail_partial_fan_out_for_test()",
                    (),
                )

            first = handler.handle(
                parent_job=parent_job,
                source_artifact=_source_artifact(source),
                trace_id="TRACE-M014-FANOUT-LIVE",
            )
            replay = handler.handle(
                parent_job=parent_job,
                source_artifact=_source_artifact(source),
                trace_id="TRACE-M014-FANOUT-LIVE",
            )
            assert (first.created, replay.created) == (True, False)
            assert (first.completed_units, first.total_units, first.page_job_count) == (1, 4, 3)

            identity = JobEnvironmentIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
                configuration_hash="c" * 64,
            )
            outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=identity,
            )
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=JobCatalog.from_job_names(("CONVERT_PAGE",)),
                environment_identity=identity,
            )
            relay = JobOutboxRelay(outbox=outbox, consumer=queue)
            assert relay.relay_pending(
                limit=10,
                owner_id="relay-m014-fanout",
                lease_seconds=30,
            ) == 3
            assert relay.relay_pending(
                limit=10,
                owner_id="relay-m014-fanout",
                lease_seconds=30,
            ) == 0

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT page_number, result_status
                      FROM source_processing.page_execution_results
                     ORDER BY page_number
                    """,
                    (),
                )
                assert cursor.fetchall() == [(2, "SKIP_EMPTY")]
                cursor.execute(
                    """
                    SELECT completed_units, total_units, execution_phase
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == (1, 4, "RUNNING")
                cursor.execute(
                    """
                    SELECT count(*), array_agg((payload ->> 'page_number')::integer
                                               ORDER BY (payload ->> 'page_number')::integer)
                      FROM platform.technical_jobs
                     WHERE job_name = 'CONVERT_PAGE'
                    """,
                    (),
                )
                assert cursor.fetchone() == (3, [1, 3, 4])

            divergent_handler = FanOutDocumentPagesHandler(
                processing_run_repository=PostgresProcessingRunRepository(persistence),
                page_fan_out_repository=repository,
                locked_assets=_assets(sha256="b" * 64),
            )
            with pytest.raises(
                DistributionContractError,
                match="PAGE_FAN_OUT_REPLAY_DIVERGENCE",
            ):
                divergent_handler.handle(
                    parent_job=parent_job,
                    source_artifact=_source_artifact(source),
                    trace_id="TRACE-M014-FANOUT-LIVE",
                )

            foreign_path = "documents/foreign/source.pdf"
            foreign_artifact = LocalArtifactDescriptor(
                identity=LocalArtifactIdentity(
                    environment="production",
                    artifact_ref=(
                        "artifact:source_processing.local/production/" + foreign_path
                    ),
                    relative_path=foreign_path,
                ),
                sha256=source.fingerprint.value,
                size_bytes=42,
            )
            with pytest.raises(
                DistributionContractError,
                match="CONTRACT_ENVIRONMENT_MISMATCH",
            ):
                handler.handle(
                    parent_job=parent_job,
                    source_artifact=foreign_artifact,
                    trace_id="TRACE-M014-FANOUT-LIVE",
                )
    finally:
        removed = _docker("rm", "--force", container)
        assert removed.returncode == 0, removed.stderr
