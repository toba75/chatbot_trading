from __future__ import annotations

from pathlib import Path


def test_validate_m004_conversion_runtime_governance_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    adr_path = repository_root / "docs/adr/ADR-032-execution-reelle-conversion-canonique.md"
    ocr_routing_adr_path = repository_root / "docs/adr/ADR-033-priorite-signaux-routage-ocr.md"
    adr_index_path = repository_root / "docs/adr/index.md"
    specification_path = repository_root / "docs/specs/m004_version_canonique_publiee.md"

    # Given ADR-032, ADR-033 et leurs preuves de runtime réel sont livrées.
    # When la gouvernance clôt M04-conversion.
    # Then les deux ADR et leur index portent le statut Acceptée, sans masquer
    #      l'échec terminal OCR vers Granite ni introduire de fallback.
    assert adr_path.is_file(), "ADR-032 doit décider l'exécution réelle de la conversion."
    assert ocr_routing_adr_path.is_file(), "ADR-033 doit décider la priorité des signaux OCR."
    assert adr_index_path.is_file(), "L'index ADR doit tracer les décisions acceptées."
    adr = adr_path.read_text(encoding="utf-8")
    ocr_routing_adr = ocr_routing_adr_path.read_text(encoding="utf-8")
    adr_index = adr_index_path.read_text(encoding="utf-8")
    specification = specification_path.read_text(encoding="utf-8")

    required_adr_fragments = (
        "**Statut :** Acceptée",
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

    assert "**Statut :** Acceptée" in ocr_routing_adr
    assert "PREPROCESS_GRANITE" in ocr_routing_adr
    assert "BAD_OCR_TO_GRANITE" in ocr_routing_adr
    assert "issue terminale et publique" in ocr_routing_adr

    assert (
        "| [ADR-032](ADR-032-execution-reelle-conversion-canonique.md) | "
        "Exécution réelle et reproductible de la conversion canonique | Acceptée | "
        "2026-07-13 | Aucun | Aucune |"
    ) in adr_index
    assert (
        "| [ADR-033](ADR-033-priorite-signaux-routage-ocr.md) | "
        "Priorité des signaux pour les routes OCR atteignables | Acceptée | "
        "2026-07-14 | Aucun | Aucune |"
    ) in adr_index

    assert "## Exécution réelle et disponibilité des convertisseurs" in specification
    assert "ADR-032" in specification
    assert "CONVERSION_ASSET_MANIFEST_INVALID" in specification
    assert "pas de fallback" in specification
