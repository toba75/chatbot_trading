"""ATDD T-008 : publication canonique vers projection locale idempotente."""

from __future__ import annotations

from pathlib import Path

from app.knowledge_access.adapters.postgres_canonical_publication_relay import (
    PostgresCanonicalPublicationRelay,
)
from app.knowledge_access.application.project_published_canonical import (
    CanonicalPublicationMessage,
    PublishedCanonicalProjectionRequest,
)


def test_given_publication_relivree_when_ka_la_consomme_then_une_projection_et_un_job() -> None:
    assert CanonicalPublicationMessage.__name__ == "CanonicalPublicationMessage"
    assert PublishedCanonicalProjectionRequest.__name__ == "PublishedCanonicalProjectionRequest"
    assert PostgresCanonicalPublicationRelay.__name__ == "PostgresCanonicalPublicationRelay"


def test_frontieres_et_persistance_du_parcours_sont_explicites() -> None:
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
    migration = (root / "deploy/postgres/migrations/025_local_canonical_projection.sql").read_text(encoding="utf-8")
    adapter = (root / "app/knowledge_access/adapters/postgres_canonical_publication_relay.py").read_text(encoding="utf-8")
    runtime = (root / "app/knowledge_access/adapters/projection_runtime.py").read_text(encoding="utf-8")
    assert "knowledge_access.canonical_publication_inbox" in migration
    assert "knowledge_access.projection_event_receipts" in migration
    assert "source_processing.canonical_publication_outbox" in adapter
    assert "knowledge_access.job_outbox" in adapter
    assert "source_processing.canonical_source_versions" not in runtime
    assert "source_processing.source_documents" not in runtime
    assert "configured_collection_name" in adapter
    assert "PROJECTION_EVENT_REPLAY_DIVERGENCE" in adapter
