"""Preuve PostgreSQL réelle des corrections runtime T-004 gouvernées par ADR-052."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from types import ModuleType
from uuid import uuid4

import psycopg
import pytest

from app.platform.postgres import PsycopgConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _load_quota_live() -> ModuleType:
    path = Path(__file__).with_name("validate_granite_quota_live.py")
    specification = importlib.util.spec_from_file_location("m014_quota_live", path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


QUOTA_LIVE = _load_quota_live()


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def _worker(identity, ordinal: int):
    from app.platform.job_runtime.granite_capacity import (
        GraniteWorker,
        GraniteWorkerState,
    )

    return GraniteWorker(
        worker_instance_id=f"worker-documents-{ordinal}",
        environment_identity=identity,
        storage_environment=identity.environment,
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )


def _plan_nodes(plan: object):
    if not isinstance(plan, dict):
        return
    yield plan
    for child in plan.get("Plans", ()):
        yield from _plan_nodes(child)


@pytest.mark.timeout(180)
def test_runtime_postgresql_workers_terminal_union_et_chemin_chaud() -> None:
    """Given deux replicas et trois pages Granite, When ils exécutent, Then quota, drainage et terminal restent atomiques."""

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
        GranitePageCompletionConflictError,
        GranitePageTerminalEnvelope,
        GranitePageTerminalStatus,
        GraniteSlotLeaseLostError,
        PostgresGraniteSlotRepository,
        PostgresGraniteWorkerRegistry,
    )
    from app.platform.job_runtime.postgres import (
        JobRelayMessageConflictError,
        JobSubmissionConflictError,
        PostgresJobQueue,
    )
    from app.platform.job_runtime.relay import RelayedJobMessage
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.platform.request_context import bind_trace_id, reset_trace_id

    container = f"ostrading-m014-runtime-{uuid4().hex[:12]}"
    password = "m014-runtime-postgres-password"
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
        port = QUOTA_LIVE._published_port(container)
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-runtime-") as temporary:
            temporary_path = Path(temporary)
            password_path = temporary_path / "postgres-password"
            password_path.write_text(password, encoding="utf-8")
            factory = PsycopgConnectionFactory(
                connection_url=f"postgresql://postgres@127.0.0.1:{port}/postgres",
                password_path=password_path,
                connect_timeout_seconds=10,
            )
            QUOTA_LIVE._wait_postgres(
                container=container,
                connection_factory=factory,
                timeout_seconds=60,
                poll_seconds=0.5,
            )
            identity = DatastoreIdentity(
                environment="test",
                deployment_id="ostrading-test-local",
            )
            preflight = PostgresIdentityPreflight(expected_identity=identity)
            migrations = REPOSITORY_ROOT / "deploy/postgres/migrations"
            migrations_021 = temporary_path / "migrations-021"
            migrations_021.mkdir()
            for path in sorted(migrations.glob("*.sql")):
                if int(path.name[:3]) <= 21:
                    shutil.copy2(path, migrations_021 / path.name)
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations_021,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=migrations,
                operation_timeout_seconds=30,
                identity_preflight=preflight,
                initialize_identity_if_empty=False,
                adopt_legacy_if_unidentified=False,
            ).run()

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
            jobs = []
            for page_number in range(1, 4):
                token = bind_trace_id(f"TRACE-M014-RUNTIME-{page_number}")
                try:
                    jobs.append(
                        queue.submit(
                            QUOTA_LIVE._contract(
                                environment_identity, page_number
                            ).to_job_request(
                                priority=JobPriority.P1,
                                code_version="m014-runtime",
                                model_version="granite-locked",
                            ),
                            recalculate=False,
                        ).job
                    )
                finally:
                    reset_trace_id(token)

            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT execution_contract_name, execution_contract_version,
                           capacity_capability, capacity_slots, capacity_device,
                           storage_environment
                      FROM platform.technical_jobs
                     WHERE job_id = %s
                    """,
                    (jobs[0].job_id,),
                )
                assert cursor.fetchone() == (
                    "CONVERT_PAGE",
                    "1.0",
                    "GRANITE_CUDA",
                    1,
                    "cuda:0",
                    "test",
                )

            with pytest.raises(
                JobSubmissionConflictError, match="JOB_SUBMISSION_CONFLICT"
            ):
                queue.submit(
                    replace(
                        jobs[0].request,
                        payload=dict(jobs[0].request.payload) | {"page_number": 999},
                    ),
                    recalculate=False,
                )
            with pytest.raises(
                JobSubmissionConflictError, match="JOB_SUBMISSION_CONFLICT"
            ):
                queue.submit(
                    replace(jobs[0].request, priority=JobPriority.P2),
                    recalculate=False,
                )
            with factory.connect() as connection:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO platform.technical_jobs (
                                environment, deployment_id, job_name, priority,
                                input_hash, configuration_hash, code_version,
                                model_version, execution_contract_name,
                                execution_contract_version, payload, trace_id,
                                status, recalculation_number
                            ) VALUES (
                                'test', 'ostrading-test-local', 'CONVERT_PAGE', 'P1',
                                %s, %s, 'm014-cycle3-null', 'granite-locked',
                                'CONVERT_PAGE', '1.0', '{}'::jsonb,
                                'TRACE-M014-CYCLE3-NULL', 'pending', 0
                            )
                            """,
                            ("9" * 64, "a" * 64),
                        )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO platform.technical_jobs (
                                environment, deployment_id, job_name, priority,
                                input_hash, configuration_hash, code_version,
                                model_version, execution_contract_name,
                                execution_contract_version, capacity_capability,
                                capacity_slots, capacity_device, storage_environment,
                                payload, trace_id, status, recalculation_number
                            ) VALUES (
                                'test', 'ostrading-test-local', 'CONVERT_PAGE', 'P1',
                                %s, %s, 'm014-cycle3-storage', 'granite-locked',
                                'CONVERT_PAGE', '1.0', 'GRANITE_CUDA', 1,
                                'cuda:0', 'development', '{}'::jsonb,
                                'TRACE-M014-CYCLE3-STORAGE', 'pending', 0
                            )
                            """,
                            ("5" * 64, "a" * 64),
                        )
            assert jobs[2].request.execution_requirements is not None
            divergent_relay_request = replace(
                jobs[2].request,
                execution_requirements=replace(
                    jobs[2].request.execution_requirements,
                    capacity_device="cuda:1",
                ),
            )
            with pytest.raises(
                JobRelayMessageConflictError,
                match="JOB_RELAY_MESSAGE_CONFLICT",
            ):
                queue.consume_relay_message(
                    RelayedJobMessage.from_job_request(
                        message_id="OUTBOX-M014-CYCLE3-DIVERGENT",
                        request=divergent_relay_request,
                        trace_id="TRACE-M014-RUNTIME-3",
                    )
                )

            registry = PostgresGraniteWorkerRegistry(
                connection_factory=factory,
                environment_identity=environment_identity,
            )
            workers = tuple(
                _worker(environment_identity, ordinal) for ordinal in (1, 2, 3)
            )
            for worker in workers:
                registry.register(worker, presence_lease_seconds=10)
            presence_until = registry.heartbeat_presence(
                workers[2], presence_lease_seconds=10
            )
            assert presence_until > datetime.now(timezone.utc)
            quota = PostgresGraniteSlotRepository(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=environment_identity,
            )
            with ThreadPoolExecutor(max_workers=2) as executor:
                acquired = tuple(
                    future.result()
                    for future in (
                        executor.submit(
                            quota.claim_compatible_job,
                            worker=workers[0],
                            lease_seconds=30,
                            job_names=("CONVERT_PAGE",),
                            execution_requirements=jobs[
                                0
                            ].request.execution_requirements,
                        ),
                        executor.submit(
                            quota.claim_compatible_job,
                            worker=workers[1],
                            lease_seconds=30,
                            job_names=("CONVERT_PAGE",),
                            execution_requirements=jobs[
                                1
                            ].request.execution_requirements,
                        ),
                    )
                )
            assert all(lease is not None for lease in acquired)
            assert (
                quota.claim_compatible_job(
                    worker=workers[2],
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=jobs[2].request.execution_requirements,
                )
                is None
            )
            assert queue.job_for(jobs[2].job_id).status is JobStatus.PENDING

            lease_1, lease_2 = acquired
            assert lease_1 is not None
            assert lease_2 is not None
            terminal = GranitePageTerminalEnvelope.from_payload(
                completion_id="COMPLETE-M014-RUNTIME-2",
                status=GranitePageTerminalStatus.SUCCEEDED,
                payload={"contract_version": "1.0", "status": "SUCCEEDED"},
                failure_reason=None,
            )
            with (
                factory.connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """
                    CREATE FUNCTION platform.delay_cycle3_completion()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        PERFORM pg_sleep(0.25);
                        RETURN NEW;
                    END $$
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER delay_cycle3_completion
                    BEFORE INSERT ON platform.page_completion_outbox
                    FOR EACH ROW EXECUTE FUNCTION platform.delay_cycle3_completion()
                    """
                )
            completion_barrier = threading.Barrier(2)

            def complete_identically():
                completion_barrier.wait(timeout=5)
                return quota.complete_page_execution(lease_2, terminal)

            with ThreadPoolExecutor(max_workers=2) as executor:
                completion_futures = tuple(
                    executor.submit(complete_identically) for _ in range(2)
                )
                identical_results = tuple(
                    future.result(timeout=10) for future in completion_futures
                )
            completed_job, replayed_job = identical_results
            assert completed_job.status is JobStatus.SUCCEEDED
            assert replayed_job == completed_job
            with pytest.raises(
                GranitePageCompletionConflictError,
                match="GRANITE_PAGE_COMPLETION_CONFLICT",
            ):
                quota.complete_page_execution(
                    lease_2,
                    GranitePageTerminalEnvelope.from_payload(
                        completion_id=terminal.completion_id,
                        status=GranitePageTerminalStatus.SUCCEEDED,
                        payload={
                            "contract_version": "1.0",
                            "status": "DIVERGENT",
                        },
                        failure_reason=None,
                    ),
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT outbox.completion_id, outbox.terminal_status,
                           job.status, slot.lease_owner
                      FROM platform.page_completion_outbox AS outbox
                      JOIN platform.technical_jobs AS job USING (job_id)
                      JOIN platform.granite_slots AS slot
                        ON slot.environment = outbox.environment
                       AND slot.deployment_id = outbox.deployment_id
                       AND slot.slot_ordinal = outbox.slot_ordinal
                     WHERE outbox.completion_id = %s
                    """,
                    (terminal.completion_id,),
                )
                assert cursor.fetchone() == (
                    terminal.completion_id,
                    "succeeded",
                    "succeeded",
                    None,
                )
            with factory.connect() as connection:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction(), connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO platform.page_completion_outbox (
                                completion_id, environment, deployment_id, job_id,
                                claim_generation, claim_token, worker_instance_id,
                                slot_ordinal, slot_generation, slot_token, payload,
                                payload_fingerprint, terminal_status, failure_reason,
                                status, relay_generation
                            ) VALUES (
                                'COMPLETE-M014-CYCLE3-NULL-FAILURE',
                                'test', 'ostrading-test-local', %s, %s, %s::uuid,
                                %s, %s, %s, %s::uuid, '{}'::jsonb, %s,
                                'failed', NULL, 'pending', 0
                            )
                            """,
                            (
                                lease_2.claimed_job.job.job_id,
                                lease_2.claimed_job.claim_generation,
                                lease_2.claimed_job.claim_token,
                                lease_2.claimed_job.lease_owner,
                                lease_2.slot_ordinal,
                                lease_2.slot_generation,
                                lease_2.slot_token,
                                "8" * 64,
                            ),
                        )
                for missing_field in (
                    "slot_ordinal",
                    "slot_generation",
                    "slot_token",
                ):
                    slot_values = {
                        "slot_ordinal": lease_2.slot_ordinal,
                        "slot_generation": lease_2.slot_generation,
                        "slot_token": lease_2.slot_token,
                    }
                    slot_values[missing_field] = None
                    with pytest.raises(psycopg.errors.CheckViolation):
                        with connection.transaction(), connection.cursor() as cursor:
                            cursor.execute(
                                """
                                INSERT INTO platform.page_completion_outbox (
                                    completion_id, environment, deployment_id,
                                    job_id, claim_generation, claim_token,
                                    worker_instance_id, slot_ordinal,
                                    slot_generation, slot_token, payload,
                                    payload_fingerprint, terminal_status,
                                    failure_reason, status, relay_generation
                                ) VALUES (
                                    %s, 'test', 'ostrading-test-local', %s, %s,
                                    %s::uuid, %s, %s, %s, %s::uuid,
                                    '{}'::jsonb, %s, 'succeeded', NULL,
                                    'pending', 0
                                )
                                """,
                                (
                                    f"COMPLETE-M014-CYCLE3-NULL-{missing_field}",
                                    lease_2.claimed_job.job.job_id,
                                    lease_2.claimed_job.claim_generation,
                                    lease_2.claimed_job.claim_token,
                                    lease_2.claimed_job.lease_owner,
                                    slot_values["slot_ordinal"],
                                    slot_values["slot_generation"],
                                    slot_values["slot_token"],
                                    "6" * 64,
                                ),
                            )

            drain_deadline = datetime.now(timezone.utc) + timedelta(seconds=5)
            registry.begin_draining(
                worker_instance_id=workers[0].worker_instance_id,
                drain_deadline=drain_deadline,
            )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT worker.drain_deadline, job.lease_expires_at,
                           slot.lease_until
                      FROM platform.document_workers AS worker
                      JOIN platform.technical_jobs AS job
                        ON job.environment = worker.environment
                       AND job.deployment_id = worker.deployment_id
                       AND job.lease_owner = worker.worker_instance_id
                      JOIN platform.granite_slots AS slot
                        ON slot.environment = worker.environment
                       AND slot.deployment_id = worker.deployment_id
                       AND slot.lease_owner = worker.worker_instance_id
                     WHERE worker.worker_instance_id = %s
                    """,
                    (workers[0].worker_instance_id,),
                )
                bounded_deadlines = cursor.fetchone()
            assert bounded_deadlines == (
                drain_deadline,
                drain_deadline,
                drain_deadline,
            )
            assert (
                quota.claim_compatible_job(
                    worker=workers[0],
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=jobs[0].request.execution_requirements,
                )
                is None
            )
            draining_lease = quota.heartbeat(lease_1, lease_seconds=30)
            assert draining_lease.lease_until <= drain_deadline
            with (
                factory.connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
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
                     WHERE environment = 'test'
                       AND deployment_id = 'ostrading-test-local'
                       AND slot_ordinal = %s
                    """,
                    (lease_1.slot_ordinal,),
                )
            with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
                quota.complete_page_execution(
                    lease_1,
                    GranitePageTerminalEnvelope.from_payload(
                        completion_id="COMPLETE-M014-STALE",
                        status=GranitePageTerminalStatus.FAILED,
                        payload={"contract_version": "1.0", "status": "FAILED"},
                        failure_reason="MODEL_FAILED",
                    ),
                )

            with (
                factory.connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """
                    UPDATE platform.document_workers
                       SET presence_lease_until = CURRENT_TIMESTAMP - INTERVAL '1 second'
                     WHERE worker_instance_id = %s
                    """,
                    (workers[2].worker_instance_id,),
                )
            assert (
                quota.claim_compatible_job(
                    worker=workers[2],
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                    execution_requirements=jobs[2].request.execution_requirements,
                )
                is None
            )

            _assert_page_result_discriminated_union(factory)
            _assert_granite_claim_index(
                factory,
                quota=quota,
                worker=workers[1],
                requirements=jobs[2].request.execution_requirements,
            )
    finally:
        _docker("rm", "--force", container)


def _assert_page_result_discriminated_union(factory: PsycopgConnectionFactory) -> None:
    with (
        factory.connect() as connection,
        connection.transaction(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            INSERT INTO source_processing.source_documents (
                document_id, fingerprint, original_storage_ref, status
            ) VALUES ('DOC-M014-UNION', %s, 'artifact:test/union.pdf', 'REGISTERED')
            """,
            ("1" * 64,),
        )
        cursor.execute(
            """
            INSERT INTO source_processing.document_processing_runs (
                processing_run_id, document_id, source_page_count, status,
                aggregate_version
            ) VALUES ('RUN-M014-UNION', 'DOC-M014-UNION', 4, 'MANIFEST_CREATED', 0)
            """,
            (),
        )
        cursor.execute(
            """
            INSERT INTO source_processing.page_manifest_entries (
                processing_run_id, page_number, state
            ) SELECT 'RUN-M014-UNION', page_number,
                     CASE WHEN page_number = 1 THEN 'EMPTY' ELSE 'PRESENT' END
                FROM generate_series(1, 4) AS page_number
            """,
            (),
        )
        cursor.execute(
            """
            INSERT INTO source_processing.page_execution_results (
                processing_run_id, page_number, completion_id, job_id,
                claim_generation, claim_token, worker_instance_id,
                slot_ordinal, slot_generation, slot_token,
                result_contract_version, route_name, result_status,
                result_payload, result_fingerprint
            ) VALUES (
                'RUN-M014-UNION', 1, 'COMPLETE-SKIP', NULL,
                NULL, NULL, NULL, NULL, NULL, NULL,
                '1.0', 'SKIP_EMPTY', 'SKIP_EMPTY', '{}'::jsonb, %s
            )
            """,
            ("2" * 64,),
        )

        invalid_rows = (
            (2, "COMPLETE-SKIP-WITH-EXEC", "SKIP_EMPTY", "SKIP_EMPTY", False, True),
            (2, "COMPLETE-GRANITE-NO-SLOT", "SCAN_GRANITE", "FAILED", False, True),
            (
                3,
                "COMPLETE-STANDARD-WITH-SLOT",
                "NATIVE_STANDARD",
                "SUCCEEDED",
                True,
                False,
            ),
        )
        for page, completion, route, status, with_slot, with_execution in invalid_rows:
            with pytest.raises(psycopg.errors.CheckViolation):
                with connection.transaction(), connection.cursor() as rejected:
                    rejected.execute(
                        """
                        INSERT INTO source_processing.page_execution_results (
                            processing_run_id, page_number, completion_id, job_id,
                            claim_generation, claim_token, worker_instance_id,
                            slot_ordinal, slot_generation, slot_token,
                            result_contract_version, route_name, result_status,
                            result_payload, result_fingerprint
                        ) VALUES (
                            'RUN-M014-UNION', %s, %s,
                            CASE WHEN %s THEN 'JOB-M002-999999' ELSE NULL END,
                            CASE WHEN %s THEN 1 ELSE NULL END,
                            CASE WHEN %s THEN %s::uuid ELSE NULL END,
                            CASE WHEN %s THEN 'worker-documents-1' ELSE NULL END,
                            CASE WHEN %s THEN 1 ELSE NULL END,
                            CASE WHEN %s THEN 1 ELSE NULL END,
                            CASE WHEN %s THEN %s::uuid ELSE NULL END,
                            '1.0', %s, %s, '{}'::jsonb, %s
                        )
                        """,
                        (
                            page,
                            completion,
                            with_execution,
                            with_execution,
                            with_execution,
                            str(uuid4()),
                            with_execution,
                            with_slot,
                            with_slot,
                            with_slot,
                            str(uuid4()),
                            route,
                            status,
                            "3" * 64,
                        ),
                    )

        for missing_field in (
            "slot_ordinal",
            "slot_generation",
            "slot_token",
        ):
            slot_values = {
                "slot_ordinal": 1,
                "slot_generation": 1,
                "slot_token": str(uuid4()),
            }
            slot_values[missing_field] = None
            with pytest.raises(psycopg.errors.CheckViolation):
                with connection.transaction(), connection.cursor() as rejected:
                    rejected.execute(
                        """
                        INSERT INTO source_processing.page_execution_results (
                            processing_run_id, page_number, completion_id, job_id,
                            claim_generation, claim_token, worker_instance_id,
                            slot_ordinal, slot_generation, slot_token,
                            result_contract_version, route_name, result_status,
                            result_payload, result_fingerprint
                        ) VALUES (
                            'RUN-M014-UNION', 2, %s, 'JOB-M002-888888',
                            1, %s::uuid, 'worker-documents-1', %s, %s, %s::uuid,
                            '1.0', 'SCAN_GRANITE', 'SUCCEEDED', '{}'::jsonb, %s
                        )
                        """,
                        (
                            f"COMPLETE-GRANITE-NULL-{missing_field}",
                            str(uuid4()),
                            slot_values["slot_ordinal"],
                            slot_values["slot_generation"],
                            slot_values["slot_token"],
                            "7" * 64,
                        ),
                    )


def _assert_granite_claim_index(
    factory: PsycopgConnectionFactory,
    *,
    quota,
    worker,
    requirements,
) -> None:
    from app.platform.job_runtime.granite_capacity import (
        _CLAIM_COMPATIBLE_JOB_SQL,
        _claim_compatible_job_parameters,
    )

    with (
        factory.connect() as connection,
        connection.transaction(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            INSERT INTO platform.technical_jobs (
                environment, deployment_id, job_name, priority, input_hash,
                configuration_hash, code_version, model_version,
                execution_contract_name, execution_contract_version,
                capacity_capability, capacity_slots, capacity_device,
                storage_environment, payload, trace_id, status,
                recalculation_number
            )
            SELECT 'test', 'ostrading-test-local', 'CONVERT_PAGE',
                   CASE WHEN item %% 2 = 0 THEN 'P1' ELSE 'P5' END,
                   repeat(md5(('cycle3-' || item)::text), 2), %s,
                   'm014-mixed', 'granite-locked', 'CONVERT_PAGE', '1.0',
                   CASE WHEN item %% 3 = 0
                        THEN 'DOCUMENT_STANDARD' ELSE 'GRANITE_CUDA' END,
                   CASE WHEN item %% 3 = 0 THEN 0 ELSE 1 END,
                   CASE WHEN item %% 3 = 0 THEN NULL ELSE 'cuda:0' END,
                   'test', '{}'::jsonb, 'TRACE-MIXED-' || item, 'pending', 0
              FROM generate_series(1, 5000) AS item
            """,
            ("a" * 64,),
        )
        cursor.execute("ANALYZE platform.technical_jobs", ())
        parameters = _claim_compatible_job_parameters(
            environment_identity=quota._environment_identity,
            worker=worker,
            lease_seconds=30,
            job_names=("CONVERT_PAGE",),
            execution_requirements=requirements,
        )
        cursor.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + _CLAIM_COMPATIBLE_JOB_SQL,
            parameters,
        )
        plan = cursor.fetchone()[0][0]["Plan"]
        nodes = tuple(_plan_nodes(plan))
        assert any(
            node.get("Index Name") == "technical_jobs_granite_claim_idx"
            for node in nodes
        )
        assert not any(
            node.get("Node Type") == "Seq Scan"
            and node.get("Relation Name") == "technical_jobs"
            for node in nodes
        )
        assert not any(
            node.get("Node Type") in {"Sort", "Incremental Sort"}
            for node in nodes
        ), json.dumps(plan, indent=2)
        candidate_limits = tuple(
            node
            for node in nodes
            if node.get("Node Type") == "Limit" and node.get("Actual Rows") == 1
        )
        assert candidate_limits
        job_index_nodes = tuple(
            node
            for node in nodes
            if node.get("Index Name") == "technical_jobs_granite_claim_idx"
        )
        assert job_index_nodes
        assert all(node.get("Actual Rows", 0) <= 1 for node in job_index_nodes)
        assert all(
            node.get("Rows Removed by Filter", 0) <= 8 for node in job_index_nodes
        )
        assert sum(
            node.get("Shared Hit Blocks", 0) + node.get("Shared Read Blocks", 0)
            for node in job_index_nodes
        ) <= 64
