"""Preuve PostgreSQL réelle des corrections runtime T-004 gouvernées par ADR-052."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
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
        GranitePageTerminalEnvelope,
        GranitePageTerminalStatus,
        GraniteSlotLeaseLostError,
        PostgresGraniteSlotRepository,
        PostgresGraniteWorkerRegistry,
    )
    from app.platform.job_runtime.postgres import PostgresJobQueue
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
                           storage_environment, source_artifact_ref,
                           result_artifact_ref, execution_route_name
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
                    "artifact:source_processing.local/test/documents/source-1.pdf",
                    "artifact:source_processing.local/test/results/page-1.json",
                    "SCAN_GRANITE",
                )

            registry = PostgresGraniteWorkerRegistry(
                connection_factory=factory,
                environment_identity=environment_identity,
            )
            workers = tuple(
                _worker(environment_identity, ordinal) for ordinal in (1, 2, 3)
            )
            for worker in workers:
                registry.register(worker)
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
                        ),
                        executor.submit(
                            quota.claim_compatible_job,
                            worker=workers[1],
                            lease_seconds=30,
                            job_names=("CONVERT_PAGE",),
                        ),
                    )
                )
            assert all(lease is not None for lease in acquired)
            assert (
                quota.claim_compatible_job(
                    worker=workers[2],
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
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
            completed_job = quota.complete_page_execution(lease_2, terminal)
            assert completed_job.status is JobStatus.SUCCEEDED
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

            registry.begin_draining(
                worker_instance_id=workers[0].worker_instance_id,
                drain_deadline=datetime.now(timezone.utc) + timedelta(milliseconds=100),
            )
            assert (
                quota.claim_compatible_job(
                    worker=workers[0],
                    lease_seconds=30,
                    job_names=("CONVERT_PAGE",),
                )
                is None
            )
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

            _assert_page_result_discriminated_union(factory)
            _assert_granite_claim_index(factory)
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


def _assert_granite_claim_index(factory: PsycopgConnectionFactory) -> None:
    with (
        factory.connect() as connection,
        connection.transaction(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            INSERT INTO platform.technical_jobs (
                environment, deployment_id, job_name, priority, input_hash,
                configuration_hash, code_version, model_version, payload,
                trace_id, status, recalculation_number
            )
            SELECT 'test', 'ostrading-test-local', 'DIAGNOSE', 'P5',
                   repeat(md5(item::text), 2), %s, 'm014-mixed', 'none',
                   '{}'::jsonb, 'TRACE-MIXED-' || item, 'pending', 0
              FROM generate_series(1, 5000) AS item
            """,
            ("a" * 64,),
        )
        cursor.execute("ANALYZE platform.technical_jobs", ())
        cursor.execute(
            """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT sequence
              FROM platform.technical_jobs
             WHERE environment = 'test'
               AND deployment_id = 'ostrading-test-local'
               AND configuration_hash = %s
               AND execution_contract_name = 'CONVERT_PAGE'
               AND execution_contract_version = '1.0'
               AND capacity_capability = 'GRANITE_CUDA'
               AND capacity_slots = 1
               AND capacity_device = 'cuda:0'
               AND storage_environment = 'test'
               AND status = 'pending'
             ORDER BY priority, sequence
             LIMIT 1
            """,
            ("a" * 64,),
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
