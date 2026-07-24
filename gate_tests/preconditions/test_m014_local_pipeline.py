from __future__ import annotations

from pathlib import Path


def test_precondition_m014_local_pipeline() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert (
        repository_root / "docs" / "tasks" / "milestone_014-local-pipeline"
    ).is_dir()
    assert (
        repository_root
        / "docs"
        / "tasks"
        / "milestone_014-distribution-core"
    ).is_dir()
    for relative_path in (
        "docs/specs/m004_version_canonique_publiee.md",
        "docs/specs/m005_projection_connaissance_recherchable.md",
        "docs/specs/m013_environments_environnements_explicites.md",
        "docs/adr/ADR-024-relais-outbox-transactions-locales.md",
        "docs/adr/ADR-025-fencing-claims-inspection-pdf-isolee.md",
        "docs/adr/ADR-052-distribution-locale-pages-quota-granite-fenced.md",
        "docs/adr/DDD-ADR-008-coherence-eventuelle-entre-contextes.md",
    ):
        assert (repository_root / relative_path).is_file()
