"""Preuve live du parcours produit complet dans le profil development."""

from __future__ import annotations

from pathlib import Path

from app.platform.development_e2e import run_development_environment_e2e


def test_validate_development_real_e2e_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    real_pdf = (
        repository_root
        / "data"
        / "corpus"
        / "the-original-turtle-trading-rules.pdf"
    )
    assert real_pdf.is_file()

    # Given la commande opérateur development et un PDF réel du corpus.
    # When le validateur traverse uniquement les contrats publics jusqu'à la
    # réponse documentaire et redémarre la pile sans supprimer ses volumes.
    report = run_development_environment_e2e(
        repository_root=repository_root,
        pdf_path=real_pdf,
    )

    # Then les preuves publiques, les identités des participants, le Spark
    # réel, la persistance et les sondes d'étanchéité sont toutes GREEN.
    assert report.environment == "development"
    assert report.deployment_id == "ostrading-development-local"
    assert report.source_pdf_path.endswith("the-original-turtle-trading-rules.pdf")
    assert report.source_pdf_sha256 != report.pdf_sha256
    assert report.pdf_sha256
    assert report.document_id.startswith("DOC-")
    assert report.canonical_version_id.startswith("CVER-")
    assert report.projection_id.startswith("PROJ-")
    assert report.answer_id.startswith("ANS-")
    assert report.citation_url.startswith("https://localhost:18443/")
    assert report.spark_raw_response_id
    assert report.progress_phases == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED")
    assert report.restart_persistence_verified is True
    assert report.foreign_environment_probes == ("test:ABSENT", "production:ABSENT")
    assert report.volume_sentinels_preserved is True
    assert report.report_path.is_file()
