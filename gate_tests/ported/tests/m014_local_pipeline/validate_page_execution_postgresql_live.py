"""Preuve PostgreSQL réelle T-006 : claims, fencing, relais et atomicité SP."""

from __future__ import annotations

import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.platform.job_runtime import JobCatalog
from app.platform.job_runtime.granite_capacity import (
    GraniteSlotLeaseLostError,
    GraniteWorker,
    GraniteWorkerState,
    PostgresGraniteSlotRepository,
    PostgresGraniteWorkerRegistry,
)
from app.platform.job_runtime.page_completion import (
    PageCompletionRelay,
    PostgresPageCompletionOutbox,
    PostgresStandardPageExecutionRepository,
)
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay
from app.platform.postgres import PostgresConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE
from app.source_processing.adapters.postgres_page_completion import (
    PostgresPageResultRepository,
)
from app.source_processing.application.execute_document_page import (
    ExecuteDocumentPageHandler,
    PageConversionFailure,
)
from app.source_processing.application.record_page_completion import (
    RecordPageCompletionHandler,
)
from app.source_processing.domain.distribution_contracts import (
    PageResultErrorCode,
)
from validate_page_execution_unit import (
    _Converter,
    _Reader,
    _Writer,
    _converters,
    _standard_metrics,
)
from validate_page_fan_out_unit import (
    _FanOutRepository,
    _assets,
    _handler,
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
    raise AssertionError("PostgreSQL T-006 non prêt") from last_error


class _CrashBeforeAck:
    def __init__(self, outbox: PostgresPageCompletionOutbox) -> None:
        self._outbox = outbox
        self._must_crash = True

    def claim_next(self, *, owner_id: str, lease_seconds: int):
        return self._outbox.claim_next(
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    def acknowledge(self, claim) -> None:
        if self._must_crash:
            self._must_crash = False
            raise RuntimeError("M014_TEST_CRASH_BEFORE_COMPLETION_ACK")
        self._outbox.acknowledge(claim)


@pytest.mark.timeout(240)
def test_page_execution_postgresql_claim_fencing_relay_et_atomicite() -> None:
    from app.platform.datastore_identity import (
        DatastoreIdentity,
        PostgresIdentityPreflight,
    )
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.source_processing.adapters.postgres_document_persistence import (
        PostgresDocumentConversionRepository,
        PostgresDocumentPersistence,
        PostgresProcessingRunRepository,
    )
    from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox
    from app.source_processing.application.fan_out_document_pages import (
        FanOutDocumentPagesHandler,
    )

    repository_root = Path(__file__).resolve().parents[4]
    migrations = repository_root / "deploy" / "postgres" / "migrations"
    container = f"ostrading-m014-page-{uuid4().hex[:12]}"
    password = "m014-page-postgres-password"
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
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-page-") as temporary:
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
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()

            source = _source()
            run = _planned_run(source)
            persistence = PostgresDocumentPersistence(connection_factory=factory)
            persistence.save_if_absent(source)
            persistence.save(run)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.document_conversion_requests (
                        document_id, conversion_status, canonical_version_id,
                        rejection_error_code, submission_id, job_id,
                        execution_phase, completed_units, total_units,
                        failure_error_code, orchestration_version,
                        producer_environment, producer_deployment_id,
                        producer_configuration_hash
                    )
                    VALUES (%s, 'CONVERSION_REQUESTED', NULL, NULL, %s, NULL,
                            'QUEUED', 0, 4, NULL, 'm014-page-fanout-v1',
                            'test', 'ostrading-test-local', %s)
                    """,
                    (
                        source.document_id.value,
                        "OUTBOX-SP-M014-PAGE-PARENT",
                        "c" * 64,
                    ),
                )
            repository = PostgresDocumentConversionRepository(persistence)
            fan_out = FanOutDocumentPagesHandler(
                processing_run_repository=PostgresProcessingRunRepository(persistence),
                page_fan_out_repository=repository,
                locked_assets=_assets(),
            )
            planned = fan_out.handle(
                parent_job=_parent_job(source, run),
                source_artifact=_source_artifact(source),
                trace_id="TRACE-M014-PAGE-LIVE",
            )
            assert (planned.completed_units, planned.page_job_count) == (1, 3)

            identity = JobEnvironmentIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
                configuration_hash="c" * 64,
            )
            catalog = JobCatalog.from_job_names(("CONVERT_PAGE",))
            source_outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=identity,
            )
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=identity,
            )
            assert JobOutboxRelay(outbox=source_outbox, consumer=queue).relay_pending(
                limit=10,
                owner_id="relay-page-jobs",
                lease_seconds=30,
            ) == 3

            standard_repository = PostgresStandardPageExecutionRepository(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=identity,
            )
            granite_repository = PostgresGraniteSlotRepository(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=identity,
            )
            registry = PostgresGraniteWorkerRegistry(
                connection_factory=factory,
                environment_identity=identity,
            )

            def worker(name: str) -> GraniteWorker:
                return GraniteWorker(
                    worker_instance_id=name,
                    environment_identity=identity,
                    storage_environment="test",
                    state=GraniteWorkerState.READY,
                    capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
                )

            worker_a = worker("worker-documents-a")
            worker_b = worker("worker-documents-b")
            registry.register(worker_a, presence_lease_seconds=60)
            registry.register(worker_b, presence_lease_seconds=60)

            planned_repository = _FanOutRepository()
            _handler(run, planned_repository).handle(
                parent_job=_parent_job(source, run),
                source_artifact=_source_artifact(source),
                trace_id="TRACE-M014-FANOUT-UNIT",
            )
            assert planned_repository.plan is not None
            standard_requirements = (
                planned_repository.plan.page_jobs[0].execution_requirements
            )
            granite_requirements = (
                planned_repository.plan.page_jobs[1].execution_requirements
            )
            assert standard_requirements is not None and granite_requirements is not None
            with ThreadPoolExecutor(max_workers=2) as executor:
                standard_future = executor.submit(
                    standard_repository.claim_compatible_job,
                    worker=worker_b,
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=standard_requirements,
                )
                granite_future = executor.submit(
                    granite_repository.claim_compatible_job,
                    worker=worker_a,
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=granite_requirements,
                )
                standard_claim = standard_future.result()
                expired_granite = granite_future.result()
            assert standard_claim is not None and expired_granite is not None
            assert standard_claim.job.request.payload["page_number"] == 1
            assert expired_granite.claimed_job.job.request.payload["page_number"] == 3

            # Le premier détenteur perd les deux leases ; seul le second peut publier.
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.technical_jobs
                       SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE job_id = %s
                    """,
                    (expired_granite.claimed_job.job.job_id,),
                )
                cursor.execute(
                    """
                    UPDATE platform.granite_slots
                       SET lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE job_id = %s
                    """,
                    (expired_granite.claimed_job.job.job_id,),
                )
            resumed_granite = granite_repository.claim_compatible_job(
                worker=worker_b,
                lease_seconds=30,
                job_names=("CONVERT_PAGE",),
                execution_requirements=granite_requirements,
            )
            assert resumed_granite is not None
            assert resumed_granite.claimed_job.claim_generation == 2

            source_content = b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n"
            execution = ExecuteDocumentPageHandler(
                artifact_reader=_Reader(source_content),
                artifact_writer=_Writer(),
                converters=_converters(),
                standard_completion=standard_repository,
                granite_completion=granite_repository,
                expected_locked_assets=_assets(),
            )
            last_standard = standard_repository.claim_compatible_job(
                worker=worker_a,
                lease_seconds=30,
                job_names=("CONVERT_PAGE",),
                execution_requirements=standard_requirements,
            )
            assert last_standard is not None
            failed_converter = _Converter(
                metrics=_standard_metrics(),
                failure=PageConversionFailure(
                    error_code=PageResultErrorCode.ARTIFACT_HASH_MISMATCH,
                    technical_metrics=_standard_metrics(),
                ),
            )
            failed_execution = ExecuteDocumentPageHandler(
                artifact_reader=_Reader(source_content),
                artifact_writer=_Writer(),
                converters=_converters(native=failed_converter),
                standard_completion=standard_repository,
                granite_completion=granite_repository,
                expected_locked_assets=_assets(),
            )
            failed_execution.execute_standard(last_standard)
            standard_outcome = execution.execute_standard(standard_claim)
            with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
                execution.execute_granite(expired_granite)
            granite_outcome = execution.execute_granite(resumed_granite)
            assert standard_outcome.result.granite_slot_execution is None
            assert granite_outcome.result.granite_slot_execution is not None

            # La dernière page standard échoue avec un code stable transporté à SP.
            # L'échec est livré avant les succès déjà en vol : SP doit garder
            # ce premier échec public puis drainer les autres résultats.
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE FUNCTION source_processing.fail_progress_after_result_for_test()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'M014_TEST_PROGRESS_UPDATE_FAILURE';
                    END $$
                    """,
                    (),
                )
                cursor.execute(
                    """
                    CREATE TRIGGER fail_progress_after_result_for_test
                    BEFORE UPDATE OF completed_units
                    ON source_processing.document_conversion_requests
                    FOR EACH ROW EXECUTE FUNCTION
                        source_processing.fail_progress_after_result_for_test()
                    """,
                    (),
                )

            completion_outbox = PostgresPageCompletionOutbox(
                connection_factory=factory,
                environment_identity=identity,
            )
            consumer = RecordPageCompletionHandler(
                repository=PostgresPageResultRepository(connection_factory=factory)
            )
            rollback_relay = PageCompletionRelay(
                outbox=completion_outbox,
                consumer=consumer,
            )
            with pytest.raises(Exception, match="M014_TEST_PROGRESS_UPDATE_FAILURE"):
                rollback_relay.relay_pending(
                    limit=1,
                    owner_id="relay-page-results-rollback",
                    lease_seconds=30,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM source_processing.page_execution_results",
                    (),
                )
                assert cursor.fetchone() == (1,)
                cursor.execute(
                    """
                    SELECT completed_units
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == (1,)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER fail_progress_after_result_for_test ON source_processing.document_conversion_requests",
                    (),
                )
                cursor.execute(
                    "DROP FUNCTION source_processing.fail_progress_after_result_for_test()",
                    (),
                )
                cursor.execute(
                    """
                    UPDATE platform.page_completion_outbox
                       SET relay_lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE status = 'relaying'
                    """,
                    (),
                )
            crash_relay = PageCompletionRelay(
                outbox=_CrashBeforeAck(completion_outbox),
                consumer=consumer,
            )
            with pytest.raises(
                RuntimeError,
                match="M014_TEST_CRASH_BEFORE_COMPLETION_ACK",
            ):
                crash_relay.relay_pending(
                    limit=1,
                    owner_id="relay-page-results-crash",
                    lease_seconds=30,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM source_processing.page_execution_results",
                    (),
                )
                assert cursor.fetchone() == (2,)
                cursor.execute(
                    """
                    SELECT completed_units
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == (2,)

            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE platform.page_completion_outbox
                       SET relay_lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE status = 'relaying'
                    """,
                    (),
                )
            relay = PageCompletionRelay(outbox=completion_outbox, consumer=consumer)
            assert relay.relay_pending(
                limit=10,
                owner_id="relay-page-results-resume",
                lease_seconds=30,
            ) == 3
            assert relay.relay_pending(
                limit=10,
                owner_id="relay-page-results-resume",
                lease_seconds=30,
            ) == 0

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT page_number, result_status, slot_ordinal
                      FROM source_processing.page_execution_results
                     ORDER BY page_number
                    """,
                    (),
                )
                assert cursor.fetchall() == [
                    (1, "SUCCEEDED", None),
                    (2, "SKIP_EMPTY", None),
                    (3, "SUCCEEDED", resumed_granite.slot_ordinal),
                    (4, "FAILED", None),
                ]
                cursor.execute(
                    """
                    SELECT completed_units, total_units, execution_phase,
                           conversion_status, failure_error_code
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == (
                    4,
                    4,
                    "FAILED",
                    "QA_REJECTED",
                    "ARTIFACT_HASH_MISMATCH",
                )
                cursor.execute(
                    """
                    SELECT count(*) FILTER (WHERE status = 'relayed'), count(*)
                      FROM platform.page_completion_outbox
                    """,
                    (),
                )
                assert cursor.fetchone() == (3, 3)
    finally:
        removed = _docker("rm", "--force", container)
        assert removed.returncode == 0, removed.stderr
