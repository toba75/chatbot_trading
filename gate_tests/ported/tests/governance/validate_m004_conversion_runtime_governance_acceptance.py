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
    recovery_adr_path = repository_root / "docs/adr/ADR-035-recuperation-gemma-explicite-apres-provenance-granite-absente.md"
    dense_recovery_adr_path = repository_root / "docs/adr/ADR-039-segmentation-gemma-bornee-pages-denses.md"
    adr_index_path = repository_root / "docs/adr/index.md"
    specification_path = repository_root / "docs/specs/m004_version_canonique_publiee.md"

    # Given ADR-032 est remplacée par ADR-035, ADR-033 et leurs preuves de runtime réel sont livrées.
    # When la gouvernance clôt M04-conversion.
    # Then la chaîne de décisions est explicite : Granite reste premier, Gemma
    #      ne récupère que DOCLING_PROVENANCE_MISSING et tous les autres échecs restent terminaux.
    assert adr_path.is_file(), "ADR-032 doit décider l'exécution réelle de la conversion."
    assert ocr_routing_adr_path.is_file(), "ADR-033 doit décider la priorité des signaux OCR."
    assert recovery_adr_path.is_file(), "ADR-035 doit décider la récupération Gemma explicite."
    assert dense_recovery_adr_path.is_file(), "ADR-039 doit borner la récupération des pages denses."
    assert adr_index_path.is_file(), "L'index ADR doit tracer les décisions acceptées."
    adr = adr_path.read_text(encoding="utf-8")
    ocr_routing_adr = ocr_routing_adr_path.read_text(encoding="utf-8")
    recovery_adr = recovery_adr_path.read_text(encoding="utf-8")
    dense_recovery_adr = dense_recovery_adr_path.read_text(encoding="utf-8")
    adr_index = adr_index_path.read_text(encoding="utf-8")
    specification = specification_path.read_text(encoding="utf-8")

    required_adr_fragments = (
        "**Statut :** Remplacée",
        "**Remplacée par :** ADR-035",
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

    required_recovery_adr_fragments = (
        "**Statut :** Acceptée",
        "**Remplace :** ADR-032",
        "GRANITE_DOCLING",
        "DOCLING_PROVENANCE_MISSING",
        "Gemma 4",
        "llm-gateway/v1/infer",
        "google/gemma-4-26B-A4B-it",
        "GEMMA_VISION_UNAVAILABLE",
        "GEMMA_VISION_OUTPUT_INVALID",
        "GEMMA_VISION_MODEL_MISMATCH",
        "GEMMA_VISION_RENDERING_FAILED",
        "GEMMA_VISION_IMAGE_TOO_LARGE",
        "RUNNING",
        "pages effectivement terminées",
        "Aucun autre modèle",
    )
    for fragment in required_recovery_adr_fragments:
        assert fragment in recovery_adr, f"ADR-035 doit imposer : {fragment}"

    required_dense_recovery_adr_fragments = (
        "**Statut :** Proposée",
        "**Remplace :** ADR-036 à l’acceptation",
        "GEMMA_VISION_OUTPUT_TRUNCATED",
        "LLM_PARTIAL_OUTPUT",
        "exactement quatre segments verticaux",
        "chevauchants",
        "render_segment_index",
        "render_segment_count",
        "render-segments-04",
        "2 048 jetons",
        "270 secondes",
    )
    for fragment in required_dense_recovery_adr_fragments:
        assert fragment in dense_recovery_adr, f"ADR-039 doit imposer : {fragment}"

    assert "**Statut :** Acceptée" in ocr_routing_adr
    assert "PREPROCESS_GRANITE" in ocr_routing_adr
    assert "BAD_OCR_TO_GRANITE" in ocr_routing_adr
    assert "L'issue reste terminale et publique" in ocr_routing_adr

    assert (
        "| [ADR-032](ADR-032-execution-reelle-conversion-canonique.md) | "
        "Exécution réelle et reproductible de la conversion canonique | Remplacée | "
        "2026-07-13 | Aucun | ADR-035 |"
    ) in adr_index
    assert (
        "| [ADR-033](ADR-033-priorite-signaux-routage-ocr.md) | "
        "Priorité des signaux pour les routes OCR atteignables | Acceptée | "
        "2026-07-14 | Aucun | Aucune |"
    ) in adr_index
    assert (
        "| [ADR-035](ADR-035-recuperation-gemma-explicite-apres-provenance-granite-absente.md) | "
        "Récupération Gemma explicite après provenance Granite absente | Acceptée | "
        "2026-07-14 | ADR-032 | Aucune |"
    ) in adr_index
    assert (
        "| [ADR-039](ADR-039-segmentation-gemma-bornee-pages-denses.md) | "
        "Segmentation Gemma bornée des pages denses | Proposée | "
        "2026-07-16 | ADR-036 à l’acceptation | Aucune |"
    ) in adr_index

    assert "## Exécution réelle et disponibilité des convertisseurs" in specification
    assert "ADR-039" in specification
    assert "CONVERSION_ASSET_MANIFEST_INVALID" in specification
    assert "DOCLING_PROVENANCE_MISSING" in specification
    assert "Gemma 4" in specification
