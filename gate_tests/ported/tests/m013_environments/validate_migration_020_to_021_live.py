"""Upgrade PostgreSQL réel d'un schéma ayant déjà appliqué 020 vers 021."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time
from uuid import uuid4


def _docker(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def test_upgrade_ancien_020_vers_021_est_rejouable() -> None:
    """Given 020 déjà appliquée, When 021 joue deux fois, Then aucun drift n'apparaît."""

    repository_root = Path(__file__).resolve().parents[4]
    migrations = repository_root / "deploy/postgres/migrations"
    container = f"ostrading-migration-021-{uuid4().hex[:12]}"
    started = _docker(
        "run",
        "--detach",
        "--rm",
        "--name",
        container,
        "--env",
        "POSTGRES_PASSWORD=migration-test-password",
        "postgres:16-alpine",
    )
    assert started.returncode == 0, started.stderr
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            readiness = _docker(
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-At",
                "-c",
                "SELECT 1",
            )
            if readiness.returncode == 0 and readiness.stdout.strip() == "1":
                break
            time.sleep(0.5)
        else:
            raise AssertionError("PostgreSQL éphémère non prêt")

        historical_sql = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(migrations.glob("0*.sql"))
            if int(path.name[:3]) <= 19
        )
        historical = _docker(
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            input_text=f"BEGIN;\n{historical_sql}\nCOMMIT;\n",
        )
        assert historical.returncode == 0, historical.stderr
        identity = _docker(
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            input_text=(
                "CREATE TABLE platform.datastore_identity ("
                "singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),"
                "environment text NOT NULL, deployment_id text NOT NULL);"
                "INSERT INTO platform.datastore_identity(environment,deployment_id) "
                "VALUES ('development','ostrading-development-local');"
            ),
        )
        assert identity.returncode == 0, identity.stderr
        migration_020 = _docker(
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            input_text=(migrations / "020_job_environment_identity.sql").read_text(
                encoding="utf-8"
            ),
        )
        assert migration_020.returncode == 0, migration_020.stderr

        migration_021 = migrations / "021_job_environment_identity_hardening.sql"
        sql_021 = migration_021.read_text(encoding="utf-8")
        for _attempt in range(2):
            applied = _docker(
                "exec",
                "-i",
                container,
                "psql",
                "-U",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                input_text=sql_021,
            )
            assert applied.returncode == 0, applied.stderr

        validated = _docker(
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            input_text=(
                "SELECT count(*) FROM pg_constraint WHERE conname IN ("
                "'technical_jobs_environment_check',"
                "'technical_jobs_deployment_id_check',"
                "'source_processing_job_outbox_environment_check',"
                "'source_processing_job_outbox_deployment_id_check',"
                "'knowledge_access_job_outbox_environment_check',"
                "'knowledge_access_job_outbox_deployment_id_check') AND convalidated;"
            ),
        )
        assert validated.returncode == 0, validated.stderr
        assert validated.stdout.strip() == "6"
    finally:
        _docker("rm", "--force", container)
