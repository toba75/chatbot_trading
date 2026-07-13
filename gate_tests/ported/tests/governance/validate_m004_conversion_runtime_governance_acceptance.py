from __future__ import annotations

from pathlib import Path


def test_validate_m004_conversion_runtime_governance_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    adr_path = repository_root / "docs/adr/ADR-032-execution-reelle-conversion-canonique.md"
    specification_path = repository_root / "docs/specs/m004_version_canonique_publiee.md"

    # Given une page ayant une route M-003 explicite.
    # When la gouvernance contrôle la décision d'exécution de la conversion.
    # Then l'outil imposé, son runtime reproductible et son échec public restent
    #      nommés sans conversion de remplacement.
    assert adr_path.is_file(), "ADR-032 doit décider l'exécution réelle de la conversion."
    adr = adr_path.read_text(encoding="utf-8")
    specification = specification_path.read_text(encoding="utf-8")

    required_adr_fragments = (
        "**Statut :** Proposée",
        "ADR-001",
        "ADR-002",
        "ADR-003",
        "ADR-004",
        "ADR-031",
        "M-003",
        "NATIVE_STANDARD",
        "Docling standard",
        "GRANITE_DOCLING",
        "Granite-Docling",
        "PREPROCESS_GRANITE",
        "OCRmyPDF",
        "docling[vlm]==2.111.0",
        "uv.lock",
        "processus isolé",
        "exécutable global",
        "téléchargement silencieux",
        "SHA-256",
        "artefact canonique immuable",
        "DOCLING_STANDARD_UNAVAILABLE",
        "GRANITE_DOCLING_UNAVAILABLE",
        "OCRMYPDF_UNAVAILABLE",
        "CONVERSION_ASSET_MANIFEST_INVALID",
        "uv run ui",
        "pas de fallback",
    )
    for fragment in required_adr_fragments:
        assert fragment in adr, f"ADR-032 doit imposer : {fragment}"

    assert "## Exécution réelle et disponibilité des convertisseurs" in specification
    assert "ADR-032" in specification
    assert "CONVERSION_ASSET_MANIFEST_INVALID" in specification
    assert "pas de fallback" in specification
