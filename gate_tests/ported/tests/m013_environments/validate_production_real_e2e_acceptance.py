"""Preuve live du parcours produit complet dans le profil production."""

from __future__ import annotations

from pathlib import Path

from app.platform.production_e2e import run_production_environment_e2e


def test_validate_production_real_e2e_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    real_pdf = (
        repository_root
        / "data"
        / "corpus"
        / "ostrading-environment-qualification-5-pages.pdf"
    )

    # Given la pile production porte son identité et tous ses workers sont prêts.
    # When le PDF réel traverse les contrats publics jusqu'à la réponse vérifiée,
    # puis la pile est redémarrée sans aucune purge.
    report = run_production_environment_e2e(
        repository_root=repository_root,
        pdf_path=real_pdf,
    )

    # Then les preuves sont persistantes, strictement production et invisibles
    # depuis development et test.
    assert report.environment == "production"
    assert report.deployment_id == "ostrading-production-primary"
    assert report.source_pdf_path.endswith("ostrading-environment-qualification-5-pages.pdf")
    assert report.source_pdf_sha256 != report.pdf_sha256
    assert report.document_id.startswith("DOC-")
    assert report.canonical_version_id.startswith("CVER-")
    assert report.projection_id.startswith("PROJ-")
    assert report.answer_id.startswith("ANS-")
    assert report.citation_url.startswith("https://localhost:20443/")
    assert report.spark_raw_response_id
    assert report.qualification_routes == (
        "NATIVE_STANDARD",
        "MIXED_PAGEWISE",
        "PREPROCESS_GRANITE",
        "TARGETED_ENRICHMENT",
        "SKIP_EMPTY",
    )
    assert report.progress_phases == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED")
    assert report.worker_identity_count == 4
    assert report.environment_job_count >= 3
    assert report.restart_persistence_verified is True
    assert report.foreign_environment_probes == ("development:ABSENT", "test:ABSENT")
    assert report.production_resources_preserved is True
    assert report.non_production_credentials_inaccessible is True
    assert report.report_path.is_file()
