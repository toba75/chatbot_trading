"""Preuve PostgreSQL réelle : le lookup CONVERT_PAGE reste indexé avec historique."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE
from validate_page_execution_postgresql_live import (
    _docker,
    _published_port,
    _wait_postgres,
)


def _index_names(plan: dict[str, object]) -> tuple[str, ...]:
    names: list[str] = []
    name = plan.get("Index Name")
    if isinstance(name, str):
        names.append(name)
    children = plan.get("Plans", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                names.extend(_index_names(child))
    return tuple(names)


@pytest.mark.timeout(180)
def test_lookup_completion_explain_utilise_index_sur_historique_volumineux() -> None:
    from app.platform.datastore_identity import DatastoreIdentity, PostgresIdentityPreflight
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner

    root = Path(__file__).resolve().parents[4]
    container = f"ostrading-m014-completion-index-{uuid4().hex[:8]}"
    password = "m014-completion-index-password"
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
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-completion-index-") as temporary:
            password_path = Path(temporary) / "postgres-password"
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
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.job_outbox (
                        job_name, priority, input_hash, configuration_hash,
                        code_version, model_version, payload, trace_id, status,
                        environment, deployment_id
                    )
                    SELECT 'CONVERT_PAGE', 'P1', repeat(md5(value::text), 2),
                           repeat('c', 64), 'm014-index-test', 'docling-test',
                           jsonb_build_object(
                               'processing_run_id', 'RUN-M014-HIST-' || value::text,
                               'page_number', (value %% 100) + 1
                           ),
                           'TRACE-M014-HIST-' || value::text, 'pending',
                           'test', 'ostrading-test-local'
                      FROM generate_series(1, 20000) AS value
                    """,
                    (),
                )
                cursor.execute("ANALYZE source_processing.job_outbox", ())
                cursor.execute("SET LOCAL enable_seqscan = off", ())
                cursor.execute(
                    """
                    EXPLAIN (FORMAT JSON)
                    SELECT payload
                      FROM source_processing.job_outbox
                     WHERE job_name = 'CONVERT_PAGE'
                       AND payload ->> 'processing_run_id' = %s
                       AND payload ->> 'page_number' = %s
                    """,
                    ("RUN-M014-HIST-19999", "100"),
                )
                explained = cursor.fetchone()
                assert explained is not None
                plan = explained[0][0]["Plan"]
                assert (
                    "source_processing_job_outbox_convert_page_lookup_idx"
                    in _index_names(plan)
                )
    finally:
        _docker("rm", "--force", container)
