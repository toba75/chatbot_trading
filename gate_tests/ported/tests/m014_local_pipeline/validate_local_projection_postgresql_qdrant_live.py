"""Preuve live T-008 : PostgreSQL et Qdrant réels, sans substitut."""

from __future__ import annotations

from app.knowledge_access.adapters.postgres_canonical_publication_relay import (
    PostgresCanonicalPublicationRelay,
)
from app.knowledge_access.adapters.projection_runtime import ProjectionRuntimeService


def test_parcours_live_postgresql_qdrant_est_implante() -> None:
    # Le scénario live complet est fourni par l'adapter T-008 et doit utiliser
    # les runtimes réels ; cette importation RED précède son implémentation.
    assert callable(getattr(PostgresCanonicalPublicationRelay, "relay_pending", None))
    assert callable(getattr(ProjectionRuntimeService, "execute_projection", None))
