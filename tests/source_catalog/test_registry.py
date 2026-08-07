from __future__ import annotations

from copy import deepcopy

from qualification.source_catalog.registry import build_skeleton, validate_catalog


def _manifest() -> dict:
    return {
        "documents": [
            {"name": "livre.pdf", "sha256": "a" * 64, "included": True},
            {"name": "article.pdf", "sha256": "b" * 64, "included": True},
            {"name": "exclu.pdf", "sha256": "c" * 64, "included": False},
        ]
    }


def _catalog() -> dict:
    return build_skeleton(_manifest(), now="2026-08-07T00:00:00+00:00")


def _issues(catalog: dict) -> list[str]:
    return validate_catalog(catalog, _manifest())


def test_le_squelette_ne_couvre_que_les_documents_retenus() -> None:
    catalog = _catalog()

    assert len(catalog["documents"]) == 2
    assert not _issues(catalog)


def test_refuse_une_identite_acceptee_sans_preuve() -> None:
    catalog = _catalog()
    entry = catalog["documents"][0]
    entry["bibliography"]["title"] = "Titre non prouvé"

    assert any("bibliography.title: valeur sans preuve" in issue for issue in _issues(catalog))


def test_refuse_une_note_sans_nombre_de_votes() -> None:
    catalog = _catalog()
    entry = catalog["documents"][0]
    entry["commercial_observations"].append({
        "provider": "google_books",
        "observed_at": "2026-08-07T00:00:00+00:00",
        "rating": {"average": 4.5},
        "proof": {"kind": "provider", "provider": "google_books", "resource_id": "v1", "observed_at": "2026-08-07T00:00:00+00:00"},
    })

    assert any("rating: moyenne et nombre de votes requis" in issue for issue in _issues(catalog))


def test_refuse_un_rang_sans_marche_categorie_et_instant() -> None:
    catalog = _catalog()
    catalog["documents"][0]["commercial_observations"].append({"provider": "amazon", "rank": 12})

    assert any("rank: marché, catégorie et instant requis" in issue for issue in _issues(catalog))


def test_refuse_de_confondre_date_d_edition_et_date_de_revision() -> None:
    catalog = _catalog()
    same = {
        "value": "2018",
        "precision": "year",
        "proof": {"kind": "manual", "reviewer": "test"},
    }
    catalog["documents"][0]["temporality"] = {
        "work_first_published": None,
        "edition_published": deepcopy(same),
        "content_revision": deepcopy(same),
    }

    assert any("date d'édition confondue" in issue for issue in _issues(catalog))


def test_refuse_une_resolution_acceptee_sans_candidat_correspondant() -> None:
    catalog = _catalog()
    catalog["documents"][0]["resolution"] = {
        "status": "accepted",
        "candidate_id": "google_books:inconnu",
        "proof": {
            "kind": "provider",
            "provider": "google_books",
            "resource_id": "inconnu",
            "observed_at": "2026-08-07T00:00:00+00:00",
        },
    }

    assert any("candidat accepté absent" in issue for issue in _issues(catalog))


def test_un_document_sans_identite_externe_reste_not_assessable() -> None:
    catalog = _catalog()

    assert all(entry["editorial_review"]["status"] == "not_assessable" for entry in catalog["documents"])
