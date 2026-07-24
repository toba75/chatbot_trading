"""Contrat d'acceptation T-007 de la publication canonique distribuée."""

from pathlib import Path


def test_assemblage_canonique_est_borne_et_atomique() -> None:
    root = Path(__file__).resolve().parents[4]
    application = root / "app/source_processing/application/assemble_canonical_document.py"
    adapter = root / "app/source_processing/adapters/postgres_canonical_assembly.py"
    migration = root / "deploy/postgres/migrations/024_canonical_assembly_publication.sql"

    assert application.is_file()
    assert adapter.is_file()
    assert migration.is_file()
    source = application.read_text(encoding="utf-8")
    persistence = adapter.read_text(encoding="utf-8")
    schema = migration.read_text(encoding="utf-8")

    assert "ASSEMBLE_CANONICAL_DOCUMENT" in source
    assert "CanonicalAcceptancePolicy" in source
    assert "TextAuthoritySelectionPolicy" in source
    assert "PublishCanonicalSourceHandler" in source
    assert "build_canonical_source_published_event" in source
    assert "model" not in source.lower() or "aucun modèle" in source.lower()
    assert "source_processing.canonical_publication_outbox" in persistence
    assert "source_processing.canonical_source_versions" in persistence
    assert "source_processing.document_conversion_requests" in persistence
    assert "CREATE TABLE source_processing.canonical_publication_outbox" in schema
    assert "canonical_assembly_id" in schema

