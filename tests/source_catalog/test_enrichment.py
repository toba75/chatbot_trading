from __future__ import annotations

from typing import Any

from qualification.source_catalog.enrichment import (
    apply_reviews,
    enrich_catalog,
    summarize_catalog,
)
from qualification.source_catalog.google_books import GoogleBooksClient
from qualification.source_catalog.registry import build_skeleton


ACQUIS = "a" * 64
REPRIS = "b" * 64
OBSERVED = "2026-08-07T00:00:00+00:00"


def _manifest() -> dict[str, Any]:
    return {
        "documents": [
            {"name": "acquis.pdf", "sha256": ACQUIS, "included": True},
            {"name": "repris.pdf", "sha256": REPRIS, "included": True},
        ]
    }


def _provider_proof() -> dict[str, Any]:
    return {
        "kind": "provider",
        "provider": "google_books",
        "resource_id": "v1",
        "observed_at": OBSERVED,
    }


def _catalog() -> dict[str, Any]:
    catalog = build_skeleton(_manifest(), now=OBSERVED)
    acquis = next(e for e in catalog["documents"] if e["source_sha256"] == ACQUIS)
    acquis["provider_observations"] = [
        {
            "provider": "google_books",
            "observed_at": OBSERVED,
            "status": "succeeded",
            "candidates": [
                {
                    "candidate_id": "google_books:v1",
                    "status": "accepted",
                    "proof": _provider_proof(),
                }
            ],
        }
    ]
    acquis["resolution"] = {
        "status": "accepted",
        "candidate_id": "google_books:v1",
        "proof": _provider_proof(),
    }
    repris = next(e for e in catalog["documents"] if e["source_sha256"] == REPRIS)
    repris["resolution"] = {"status": "unavailable", "candidate_id": None, "proof": None}
    return catalog


def _volume(identifier: str, title: str) -> dict[str, Any]:
    return {"id": identifier, "volumeInfo": {"title": title, "authors": ["Autrice"]}}


def test_une_reprise_ciblee_ne_reinterroge_pas_une_consultation_aboutie() -> None:
    interrogees: list[str] = []

    def transport(url: str, timeout: float) -> dict[str, Any]:
        interrogees.append(url)
        assert "acquis" not in url, "une entrée déjà résolue ne doit pas être re-interrogée"
        return {"items": [_volume("v2", "repris")]}

    catalog = _catalog()
    acquis_avant = dict(catalog["documents"][0])

    catalog, report = enrich_catalog(
        _manifest(),
        catalog,
        client=GoogleBooksClient(transport=transport),
        only={REPRIS},
    )

    assert interrogees, "la seule entrée non résolue doit être consultée"
    acquis = next(e for e in catalog["documents"] if e["source_sha256"] == ACQUIS)
    assert acquis["resolution"] == acquis_avant["resolution"]
    assert acquis["provider_observations"] == acquis_avant["provider_observations"]
    # Le rapport décrit tout le registre, pas seulement le périmètre consulté.
    assert len(report["documents"]) == 2
    assert report["consultations"]["succeeded"] == 2
    assert report["consultations"]["unavailable"] == 0


def test_le_resume_distingue_l_indisponibilite_de_l_absence_de_correspondance() -> None:
    catalog = _catalog()

    report = summarize_catalog(catalog, observed_at=OBSERVED)

    assert report["consultations"]["succeeded"] == 1
    assert report["consultations"]["unavailable"] == 1
    assert report["consultations"]["no_match"] == 0
    assert report["resolutions"]["accepted"] == 1
    assert report["resolutions"]["unavailable"] == 1
    assert [document["reviewed"] for document in report["documents"]] == [False, False]
    accepte = next(d for d in report["documents"] if d["resolution"] == "accepted")
    assert accepte["accepted_candidate_id"] == "google_books:v1"
    assert accepte["accepted_proof"]["resource_id"] == "v1"


def test_aucun_document_ne_disparait_du_total_des_consultations() -> None:
    catalog = build_skeleton(_manifest(), now=OBSERVED)

    report = summarize_catalog(catalog, observed_at=OBSERVED)

    # Une entrée jamais consultée reste comptée : le total couvre le registre.
    assert report["consultations"]["not_queried"] == 2
    assert sum(report["consultations"].values()) == len(catalog["documents"])
    assert sum(report["resolutions"].values()) == len(catalog["documents"])


def test_une_revue_s_applique_hors_du_perimetre_consulte_et_se_voit_dans_le_resume() -> None:
    catalog = _catalog()
    repris = next(e for e in catalog["documents"] if e["source_sha256"] == REPRIS)
    repris["resolution"] = {"status": "candidate", "candidate_id": None, "proof": None}
    repris["provider_observations"] = [
        {
            "provider": "google_books",
            "observed_at": OBSERVED,
            "status": "succeeded",
            "candidates": [{"candidate_id": "google_books:v9", "status": "candidate"}],
        }
    ]
    reviews = {
        REPRIS: {
            "reviewer": "toba75",
            "reviewed_at": "2026-08-08",
            "decisions": {"google_books:v9": "rejected"},
            "justification": "Édition différente de celle du fichier.",
        }
    }

    apply_reviews(catalog, reviews=reviews)
    report = summarize_catalog(catalog, observed_at=OBSERVED)

    assert repris["resolution"]["status"] == "rejected"
    reviewed = {document["source_sha256"]: document["reviewed"] for document in report["documents"]}
    assert reviewed == {ACQUIS: False, REPRIS: True}
    assert report["candidate_states"]["rejected"] == 1


def test_la_revue_est_idempotente() -> None:
    catalog = _catalog()
    repris = next(e for e in catalog["documents"] if e["source_sha256"] == REPRIS)
    repris["resolution"] = {"status": "candidate", "candidate_id": None, "proof": None}
    repris["provider_observations"] = [
        {
            "provider": "google_books",
            "observed_at": OBSERVED,
            "status": "succeeded",
            "candidates": [{"candidate_id": "google_books:v9", "status": "candidate"}],
        }
    ]
    reviews = {
        REPRIS: {
            "reviewer": "toba75",
            "reviewed_at": "2026-08-08",
            "decisions": {"google_books:v9": "rejected"},
            "justification": "Édition différente de celle du fichier.",
        }
    }

    apply_reviews(catalog, reviews=reviews)
    premier = summarize_catalog(catalog, observed_at=OBSERVED)
    apply_reviews(catalog, reviews=reviews)
    second = summarize_catalog(catalog, observed_at=OBSERVED)

    assert premier == second
