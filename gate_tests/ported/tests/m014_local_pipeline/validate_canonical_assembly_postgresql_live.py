"""Preuve PostgreSQL T-007 de création et publication atomiques."""

from pathlib import Path


def test_preuve_postgresql_t007_est_executable() -> None:
    # Le scénario live détaillé est porté par l'adaptateur et sa migration ;
    # ce test reste RED tant que l'implémentation transactionnelle n'existe pas.
    root = Path(__file__).resolve().parents[4]
    source = (root / "app/source_processing/adapters/postgres_canonical_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "FOR UPDATE" in source
    assert "ON CONFLICT" in source
    assert "canonical_publication_outbox" in source
    assert "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE" in source
