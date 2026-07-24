"""Preuve PostgreSQL réelle T-004 du quota Granite fenced."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import UUID, uuid4

import psycopg
import pytest

from app.platform.postgres import PostgresConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def _wait_postgres(
    *,
    container: str,
    connection_factory: PostgresConnectionFactory,
    timeout_seconds: float,
    poll_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_connection_error: psycopg.OperationalError | None = None
    while True:
        state = _docker(
            "inspect",
            "--format",
            "{{.State.Running}}|{{.State.Status}}|{{.State.ExitCode}}",
            container,
        )
        if state.returncode != 0:
            raise AssertionError(
                "Inspection du conteneur PostgreSQL T-004 impossible: "
                f"{state.stderr.strip()}"
            )
        running, status, exit_code = state.stdout.strip().split("|", 2)
        if running != "true" or status != "running":
            raise AssertionError(
                "Conteneur PostgreSQL T-004 arrêté avant readiness: "
                f"status={status}, exit_code={exit_code}"
            )

        try:
            with (
                connection_factory.connect() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("SELECT 1", ())
                response = cursor.fetchone()
        except psycopg.OperationalError as error:
            if error.sqlstate is not None:
                raise
            last_connection_error = error
        else:
            if response != (1,):
                raise AssertionError(
                    "Réponse PostgreSQL T-004 invalide sur le port publié: "
                    f"{response!r}"
                )
            return

        if time.monotonic() >= deadline:
            raise AssertionError(
                "PostgreSQL T-004 non prêt sur son port TCP publié "
                f"après {timeout_seconds} secondes"
            ) from last_connection_error
        time.sleep(poll_seconds)


def _published_port(container: str) -> int:
    published = _docker("port", container, "5432/tcp")
    assert published.returncode == 0, published.stderr
    endpoint = published.stdout.strip().splitlines()[0]
    return int(endpoint.rsplit(":", 1)[1])


def _contract(identity, page_number: int):
    from app.source_processing.domain.distribution_contracts import (
        CONVERT_PAGE_CONTRACT_VERSION,
        PAGE_RESULT_CONTRACT_VERSION,
        ConvertPageContract,
        ExecutionCapacityRequirement,
        ExecutionCapability,
        LocalArtifactDescriptor,
        LocalArtifactIdentity,
        LockedAssetVersion,
        convert_page_idempotence_key,
    )
    from app.source_processing.domain.document_processing_run import PageRouteName

    run_id = f"RUN-M014-QUOTA-{page_number}"
    route = PageRouteName.SCAN_GRANITE
    policy = "routing-m014-v1"
    return ConvertPageContract(
        contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=identity,
        document_id=f"DOC-M014-QUOTA-{page_number}",
        processing_run_id=run_id,
        page_number=page_number,
        route_name=route,
        routing_policy_version=policy,
        source_artifact=LocalArtifactDescriptor(
            identity=LocalArtifactIdentity(
                environment="test",
                artifact_ref=(
                    "artifact:source_processing.local/test/"
                    f"documents/source-{page_number}.pdf"
                ),
                relative_path=f"documents/source-{page_number}.pdf",
            ),
            sha256=f"{page_number:064x}",
            size_bytes=100 + page_number,
        ),
        expected_result_artifact=LocalArtifactIdentity(
            environment="test",
            artifact_ref=(
                f"artifact:source_processing.local/test/results/page-{page_number}.json"
            ),
            relative_path=f"results/page-{page_number}.json",
        ),
        required_capacity=ExecutionCapacityRequirement(
            capability=ExecutionCapability.GRANITE_CUDA,
            slots=1,
            device="cuda:0",
        ),
        locked_assets=(
            LockedAssetVersion(
                name="granite-docling",
                version="locked-m014",
                sha256="f" * 64,
            ),
        ),
        idempotence_key=convert_page_idempotence_key(
            processing_run_id=run_id,
            page_number=page_number,
            route_name=route.value,
            routing_policy_version=policy,
            contract_version=CONVERT_PAGE_CONTRACT_VERSION,
        ),
    )


@pytest.mark.timeout(120)
def test_quota_granite_postgresql_concurrence_reprise_et_ledger() -> None:
    """Deux slots réussissent, le troisième attend, puis reprend sous nouveau fencing."""

    from app.contracts.technical_jobs import (
        JobEnvironmentIdentity,
        JobPriority,
        JobStatus,
    )
    from app.platform.datastore_identity import (
        DatastoreIdentity,
        PostgresIdentityPreflight,
    )
    from app.platform.job_runtime import JobCatalog
    from app.platform.job_runtime.granite_capacity import (
        GraniteCapacityController,
        GraniteSlotLeaseLostError,
        GraniteWorker,
        GraniteWorkerState,
        PostgresGraniteSlotRepository,
        PostgresGraniteWorkerRegistry,
    )
    from app.platform.job_runtime.postgres import PostgresJobQueue
    from app.platform.job_runtime.postgres import JobLeaseConflictError
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.platform.request_context import bind_trace_id, reset_trace_id

    repository_root = Path(__file__).resolve().parents[4]
    migrations = repository_root / "deploy" / "postgres" / "migrations"
    container = f"ostrading-m014-quota-{uuid4().hex[:12]}"
    password = "m014-quota-postgres-password"
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
        port = _published_port(container)
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-quota-") as temporary:
            temporary_path = Path(temporary)
            password_path = temporary_path / "postgres-password"
            password_path.write_text(password, encoding="utf-8")
            factory = PsycopgConnectionFactory(
                connection_url=f"postgresql://postgres@127.0.0.1:{port}/postgres",
                password_path=password_path,
                connect_timeout_seconds=10,
            )
            _wait_postgres(
                container=container,
                connection_factory=factory,
                timeout_seconds=60,
                poll_seconds=0.5,
            )
            datastore_identity = DatastoreIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
            )
            preflight = PostgresIdentityPreflight(expected_identity=datastore_identity)

            migrations_021 = temporary_path / "migrations-021"
            migrations_021.mkdir()
            for path in sorted(migrations.glob("*.sql")):
                if int(path.name[:3]) <= 21:
                    shutil.copy2(path, migrations_021 / path.name)
            runner_021 = PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations_021,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            )
            runner_021.run()
            assert runner_021.required_schema_version == 21

            migrations_022 = temporary_path / "migrations-022"
            migrations_022.mkdir()
            for path in sorted(migrations.glob("*.sql")):
                if int(path.name[:3]) <= 22:
                    shutil.copy2(path, migrations_022 / path.name)
            runner_022 = PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations_022,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=False,
                adopt_legacy_if_unidentified=False,
            )
            runner_022.run()
            runner_022.run()
            assert runner_022.required_schema_version == 22
            assert runner_022.is_required_schema_ready()

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT max(version), count(*) FROM platform.schema_migrations",
                    (),
                )
                assert cursor.fetchone() == (22, 22)
                cursor.execute(
                    """
                    SELECT environment, deployment_id, array_agg(slot_ordinal ORDER BY slot_ordinal)
                      FROM platform.granite_slots
                     GROUP BY environment, deployment_id
                    """,
                    (),
                )
                assert cursor.fetchall() == [("test", "ostrading-test-local", [1, 2])]

            environment_identity = JobEnvironmentIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
                configuration_hash="a" * 64,
            )
            catalog = JobCatalog.from_job_names(("CONVERT_PAGE",))
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=environment_identity,
            )
            submitted = []
            for page_number in range(1, 5):
                trace_token = bind_trace_id(f"TRACE-M014-QUOTA-{page_number}")
                try:
                    decision = queue.submit(
                        _contract(environment_identity, page_number).to_job_request(
                            priority=JobPriority.P1,
                            code_version="m014-quota",
                            model_version="granite-locked",
                        ),
                        recalculate=False,
                    )
                finally:
                    reset_trace_id(trace_token)
                submitted.append(decision.job)

            def worker(number: int, *, environment: str = "test") -> GraniteWorker:
                identity = (
                    environment_identity
                    if environment == "test"
                    else JobEnvironmentIdentity(
                        environment=environment,
                        deployment_id=f"ostrading-{environment}-local",
                        configuration_hash="a" * 64,
                    )
                )
                return GraniteWorker(
                    worker_instance_id=f"worker-documents-{number}",
                    environment_identity=identity,
                    storage_environment=environment,
                    state=GraniteWorkerState.READY,
                    capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
                )

            quota = PostgresGraniteSlotRepository(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=environment_identity,
            )
            registry = PostgresGraniteWorkerRegistry(
                connection_factory=factory,
                environment_identity=environment_identity,
            )
            for worker_number in range(1, 5):
                registry.register(worker(worker_number), presence_lease_seconds=60)
            with ThreadPoolExecutor(max_workers=2) as executor:
                acquisition_1 = executor.submit(
                    quota.claim_compatible_job,
                    worker=worker(1),
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=submitted[0].request.execution_requirements,
                )
                acquisition_2 = executor.submit(
                    quota.claim_compatible_job,
                    worker=worker(2),
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=submitted[1].request.execution_requirements,
                )
                lease_1 = acquisition_1.result()
                lease_2 = acquisition_2.result()
            assert lease_1 is not None
            assert lease_2 is not None
            assert {lease_1.slot_ordinal, lease_2.slot_ordinal} == {1, 2}
            assert UUID(lease_1.slot_token).version == 4
            assert UUID(lease_2.slot_token).version == 4

            model_calls = []
            waiting = GraniteCapacityController(repository=quota).execute_next(
                worker=worker(3),
                lease_seconds=30,
                heartbeat_seconds=5,
                job_names=("CONVERT_PAGE",),
                execution_requirements=(submitted[2].request.execution_requirements),
                start_model=lambda lease: model_calls.append(lease),
                success_envelope=lambda lease, result: None,
                failure_envelope=lambda lease, error: None,
            )
            assert waiting is None
            assert model_calls == []
            assert queue.job_for(submitted[2].job_id).status is JobStatus.PENDING

            draining_worker = GraniteWorker(
                worker_instance_id="worker-documents-4",
                environment_identity=environment_identity,
                storage_environment="test",
                state=GraniteWorkerState.DRAINING,
                capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
            )
            registry.begin_draining(
                worker_instance_id=draining_worker.worker_instance_id,
                drain_deadline=datetime.now(UTC) + timedelta(seconds=30),
            )
            assert (
                quota.claim_compatible_job(
                    worker=draining_worker,
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=submitted[2].request.execution_requirements,
                )
                is None
            )

            same_worker = quota.claim_compatible_job(
                worker=worker(2), lease_seconds=30, job_names=("CONVERT_PAGE",),
                execution_requirements=submitted[1].request.execution_requirements,
            )
            assert same_worker is None

            renewed_2 = quota.heartbeat(lease_2, lease_seconds=60)
            assert renewed_2.lease_until > lease_2.lease_until

            with factory.connect() as connection:
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE platform.technical_jobs
                           SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                         WHERE job_id = %s
                        """,
                        (lease_1.claimed_job.job.job_id,),
                    )
                    cursor.execute(
                        """
                        UPDATE platform.granite_slots
                           SET lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                         WHERE environment = %s AND deployment_id = %s
                           AND slot_ordinal = %s
                        """,
                        (
                            environment_identity.environment,
                            environment_identity.deployment_id,
                            lease_1.slot_ordinal,
                        ),
                    )

            resumed = quota.claim_compatible_job(
                worker=worker(3), lease_seconds=30, job_names=("CONVERT_PAGE",),
                execution_requirements=submitted[2].request.execution_requirements,
            )
            assert resumed is not None
            assert resumed.claimed_job.job.job_id == submitted[2].job_id
            assert resumed.slot_ordinal == lease_1.slot_ordinal
            assert resumed.slot_generation > lease_1.slot_generation
            assert resumed.slot_token != lease_1.slot_token

            with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
                quota.heartbeat(lease_1, lease_seconds=30)
            with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
                quota.release(lease_1)
            with pytest.raises(JobLeaseConflictError, match="JOB_LEASE_LOST"):
                queue.mark_succeeded(
                    job_id=lease_1.claimed_job.job.job_id,
                    owner_id=lease_1.claimed_job.lease_owner,
                    claim_generation=lease_1.claimed_job.claim_generation,
                    claim_token=lease_1.claimed_job.claim_token,
                    result={"status": "obsolete"},
                )

            production_quota = PostgresGraniteSlotRepository(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=worker(
                    9, environment="production"
                ).environment_identity,
            )
            assert (
                production_quota.claim_compatible_job(
                    worker=worker(9, environment="production"),
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=submitted[2].request.execution_requirements,
                )
                is None
            )

            quota.release(renewed_2)
            quota.release(resumed)
            with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
                quota.release(resumed)

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) FILTER (WHERE lease_owner IS NOT NULL),
                           count(*), max(slot_generation)
                      FROM platform.granite_slots
                     WHERE environment = 'test'
                       AND deployment_id = 'ostrading-test-local'
                    """,
                    (),
                )
                active, total, maximum_generation = cursor.fetchone()
                assert (active, total) == (0, 2)
                assert maximum_generation >= 2
                cursor.execute("SET enable_seqscan = off", ())
                cursor.execute(
                    """
                    EXPLAIN SELECT slot_ordinal
                      FROM platform.granite_slots
                     WHERE environment = 'test'
                       AND deployment_id = 'ostrading-test-local'
                       AND (lease_owner IS NULL OR lease_until <= CURRENT_TIMESTAMP)
                     ORDER BY slot_ordinal
                     FOR UPDATE SKIP LOCKED
                     LIMIT 1
                    """,
                    (),
                )
                explain = "\n".join(row[0] for row in cursor.fetchall())
                assert "granite_slots" in explain
                assert "Index" in explain
    finally:
        _docker("rm", "--force", container)
