"""Contrat SQL M-014 : lookup de complétion borné par index d'expression."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.source_processing.adapters.postgres_page_completion import (
    PostgresPageResultRepository,
)


def test_lookup_completion_utilise_un_index_partiel_exact() -> None:
    root = Path(__file__).resolve().parents[4]
    migration = root / "deploy/postgres/migrations/030_m014_resource_bounds.sql"
    assert migration.is_file()
    sql = migration.read_text(encoding="utf-8")
    assert "source_processing_job_outbox_convert_page_lookup_idx" in sql
    assert "(payload ->> 'processing_run_id')" in sql
    assert "(payload ->> 'page_number')" in sql
    assert "WHERE job_name = 'CONVERT_PAGE'" in sql

    adapter = inspect.getsource(PostgresPageResultRepository.persist_page_result)
    assert "payload ->> 'page_number' = %s" in adapter
    assert "::integer" not in adapter
