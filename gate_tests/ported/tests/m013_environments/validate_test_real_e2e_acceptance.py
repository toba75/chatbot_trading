"""Preuve live de deux parcours produit complets dans le profil test."""

from __future__ import annotations

from pathlib import Path

from app.platform.test_e2e import run_test_environment_e2e


def test_validate_test_real_e2e_acceptance() -> None:
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

    # Given les seules ressources test sont créées depuis un état vide
    # déterministe et les sentinelles development/production existent.
    # When deux cycles réels traversent les contrats publics puis exécutent le
    # teardown contrôlé, y compris la supervision des workers et du Spark réel.
    report = run_test_environment_e2e(
        repository_root=repository_root,
        pdf_path=real_pdf,
    )

    # Then les deux parcours sont distincts, complets et les seules ressources
    # supprimées portent l'identité test.
    assert report.environment == "test"
    assert report.deployment_id == "ostrading-test-ci"
    assert len(report.runs) == 2
    assert tuple(run.run_number for run in report.runs) == (1, 2)
    assert len({run.document_id for run in report.runs}) == 2
    assert all(
        run.progress_phases == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED")
        for run in report.runs
    )
    assert all(run.citation_url.startswith("https://localhost:19443/") for run in report.runs)
    assert all(run.spark_raw_response_id for run in report.runs)
    assert all(
        run.qualification_routes
        == (
            "NATIVE_STANDARD",
            "MIXED_PAGEWISE",
            "PREPROCESS_GRANITE",
            "TARGETED_ENRICHMENT",
            "SKIP_EMPTY",
        )
        for run in report.runs
    )
    assert all(run.worker_identity_count == 4 for run in report.runs)
    assert all(run.environment_job_count >= 3 for run in report.runs)
    assert all(run.pre_teardown_report_path.is_file() for run in report.runs)
    assert report.non_test_credentials_inaccessible is True
    assert report.foreign_volume_sentinels_preserved is True
    assert report.test_resources_removed is True
    assert report.report_path.is_file()
