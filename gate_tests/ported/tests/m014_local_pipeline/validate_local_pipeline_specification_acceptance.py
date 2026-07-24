"""Acceptation BDD de la spécification du pipeline documentaire local."""

from __future__ import annotations

from pathlib import Path

from ost_gate.m014_local_pipeline import validate_local_pipeline_specification


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SPECIFICATION_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "specs"
    / "m014_local_pipeline_documentaire_distribue.md"
)


def test_specification_pipeline_local_distribue() -> None:
    # Given un manifeste SP figé et deux workers documentaires généralistes.
    assert SPECIFICATION_PATH.is_file(), "M014_LOCAL_PIPELINE_SPECIFICATION_MISSING"

    # When le contrat distribue, complète, assemble puis projette le document.
    specification = SPECIFICATION_PATH.read_text(encoding="utf-8")
    validate_local_pipeline_specification(specification)

    # Then les propriétaires, échanges et tranches restent explicites et bornés.
    assert "Given" in specification
    assert "When" in specification
    assert "Then" in specification
    assert all(f"DIST-00{index}" in specification for index in range(3, 6))
    assert all(
        filename in specification
        for filename in (
            "0003_eclater_conversion_en_jobs_pages.md",
            "0004_executer_persister_page_fenced.md",
            "0005_assembler_publier_document_canonique.md",
            "0006_projeter_document_publie_localement.md",
        )
    )
