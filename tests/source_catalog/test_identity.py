from __future__ import annotations

import json
from pathlib import Path

from qualification.source_catalog.identity import extract_identifiers, lookup_for_entry


def test_extrait_isbn_et_issn_avec_localisation_source(tmp_path: Path) -> None:
    document = tmp_path / "docling-document.json"
    document.write_text(
        json.dumps(
            {
                "texts": [
                    {
                        "self_ref": "#/texts/0",
                        "text": "ISBN 978-0-307-72078-8 ISSN 2049-3630",
                        "prov": [{"page_no": 1}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    found = extract_identifiers(document)

    assert found["isbn13"][0]["value"] == "9780307720788"
    assert found["issn"][0]["value"] == "20493630"
    assert found["issn"][0]["proof"]["locator"]["page"] == 1


def test_titre_et_auteurs_des_publications_sans_isbn_sont_distincts() -> None:
    lookup = lookup_for_entry({
        "name": "A Century of Profitable Industry Trends Carlo Zarattini Gary Antonacci.pdf",
        "sha256": "a" * 64,
    })

    assert lookup["title"] == "A Century of Profitable Industry Trends"
    assert lookup["authors"] == ["Carlo Zarattini", "Gary Antonacci"]


def test_extrait_editeur_annee_et_variante_du_nom_de_fichier() -> None:
    lookup = lookup_for_entry({
        "name": "Advances in Financial Machine Learning-Wiley (2018).pdf",
        "sha256": "b" * 64,
    })

    assert lookup["title"] == "Advances in Financial Machine Learning"
    assert lookup["publisher_hint"] == "Wiley"
    assert lookup["publication_year_hint"] == "2018"
    assert "Advances in Financial Machine Learning-Wiley (2018)" in lookup["title_variants"]
