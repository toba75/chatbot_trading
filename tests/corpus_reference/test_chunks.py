from __future__ import annotations

import json
from pathlib import Path

import pytest
from docling_core.types.doc import DoclingDocument

from pdf_math_audit.development import develop_document, pdf_supplement_records
from qualification.corpus_reference.chunks import (
    build_chunks,
    main,
    validate_chunk,
)
from qualification.source_catalog.registry import stable_projection


def _document(*texts: dict, height: float = 100.0) -> DoclingDocument:
    pages = sorted({text["prov"][0]["page_no"] for text in texts if text["prov"]})
    return DoclingDocument.model_validate(
        {
            "name": "chunks-test",
            "pages": {
                str(page): {"page_no": page, "size": {"width": 100, "height": height}}
                for page in pages
            },
            "body": {
                "self_ref": "#/body",
                "children": [{"$ref": text["self_ref"]} for text in texts],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "body",
            },
            "furniture": {
                "self_ref": "#/furniture",
                "children": [],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "furniture",
            },
            "texts": list(texts),
        }
    )


def _text(index: int, text: str, *, label: str = "text", page: int = 1) -> dict:
    return {
        "self_ref": f"#/texts/{index}",
        "parent": {"$ref": "#/body"},
        "label": label,
        "content_layer": "body",
        "orig": text,
        "text": text,
        "prov": [
            {
                "page_no": page,
                "bbox": {
                    "l": 10.0, "t": 90.0, "r": 90.0, "b": 80.0,
                    "coord_origin": "BOTTOMLEFT",
                },
                "charspan": [0, len(text)],
            }
        ],
    }


def _report(*source_regions: dict, docling_regions: list[dict] | None = None) -> dict:
    return {
        "analyzer_version": "0.8.0",
        "capability_profile": "pdf-docling-semantic-correction-v3",
        "alignment": {
            "pdf_source_math_regions": list(source_regions),
            "regions": docling_regions or [],
        },
    }


_VERDICTS = {
    "matching": "conformant_within_scope",
    "contradicting": "contradicted",
    "missing": "contradicted",
    "not_evaluated": "non_verifiable",
}


def _source(ref: str, span: list[int], status: str) -> dict:
    return {
        "docling_ref": ref,
        "candidate_charspan": span,
        "candidate_link_status": "linked",
        "candidate_status": status,
        "verdict": _VERDICTS[status],
    }


ENTRY = {"name": "livre.pdf", "sha256": "f" * 64, "pages": 2, "included": True}


def test_regroupe_les_items_et_coupe_au_titre_et_a_la_page() -> None:
    document = _document(
        _text(0, "Premier paragraphe."),
        _text(1, "Deuxième paragraphe."),
        _text(2, "Titre de section", label="section_header"),
        _text(3, "Sous le titre."),
        _text(4, "Autre page.", page=2),
    )

    chunks, _unlocatable = build_chunks(document, _report(), ENTRY)

    assert [c["text"] for c in chunks] == [
        "Premier paragraphe.\nDeuxième paragraphe.",
        "Titre de section\nSous le titre.",
        "Autre page.",
    ]
    assert chunks[0]["items"][1]["charspan"] == [20, 40]
    assert chunks[2]["provenance"]["page"] == 2
    # bbox convertie en TOPLEFT : t = hauteur - 90 = 10
    assert chunks[0]["provenance"]["bbox"][1] == pytest.approx(10.0)


def test_enumere_les_formules_inline_et_display_avec_leurs_spans() -> None:
    document = _document(
        _text(0, "On note $x_i$ la valeur."),
        _text(1, "E = m c^2", label="formula"),
        _text(2, "print('$PATH$')", label="code"),
    )

    chunks, _unlocatable = build_chunks(document, _report(), ENTRY)

    formulas = [f for c in chunks for f in c["formulas"]]
    assert [(f["kind"], f["docling_ref"]) for f in formulas] == [
        ("inline", "#/texts/0"),
        ("display", "#/texts/1"),
    ]
    inline = formulas[0]
    assert chunks[0]["text"][inline["charspan"][0] : inline["charspan"][1]] == "$x_i$"
    assert inline["item_charspan"] == [8, 13]
    assert inline["flag"] == "unverified"


def test_une_contradiction_domine_le_drapeau() -> None:
    document = _document(_text(0, "Valeur $x>0$ ici."))
    report = _report(
        _source("#/texts/0", [8, 11], "matching"),
        _source("#/texts/0", [8, 11], "contradicting"),
    )

    chunks, _unlocatable = build_chunks(document, report, ENTRY)

    formula = chunks[0]["formulas"][0]
    assert formula["flag"] == "contradicted"
    assert formula["evidence"]["conformant"] == 1
    assert formula["evidence"]["contradicted"] == 1


def test_prouvee_exige_la_couverture_integrale() -> None:
    document = _document(_text(0, "Valeur $x>0$ ici."))
    complet = _report(_source("#/texts/0", [8, 11], "matching"))
    partiel = _report(_source("#/texts/0", [8, 9], "matching"))

    assert build_chunks(document, complet, ENTRY)[0][0]["formulas"][0]["flag"] == "proven"
    partial = build_chunks(document, partiel, ENTRY)[0][0]["formulas"][0]
    assert partial["flag"] == "unverified"
    assert partial["evidence"]["coverage"] == pytest.approx(1 / 3)


def test_la_provenance_prefere_la_boite_de_la_region_docling() -> None:
    document = _document(_text(0, "Valeur $x>0$ ici."))
    report = _report(
        docling_regions=[
            {
                "docling_ref": "#/texts/0",
                "charspan": [7, 12],
                "bbox": [40.0, 12.0, 60.0, 18.0],
                "page": 1,
            }
        ]
    )

    formula = build_chunks(document, report, ENTRY)[0][0]["formulas"][0]

    assert formula["provenance"] == {
        "page": 1,
        "bbox": [40.0, 12.0, 60.0, 18.0],
        "precision": "region",
    }


def test_refuse_une_formule_sans_drapeau_ou_sans_provenance() -> None:
    chunk = {
        "chunk_id": "abc:00000",
        "formulas": [
            {
                "origin": "transcription",
                "flag": "unverified",
                "provenance": {"page": 1, "bbox": [1, 2, 3, 4]},
            }
        ],
    }
    validate_chunk(chunk)

    chunk["formulas"][0]["flag"] = "certain"
    with pytest.raises(ValueError, match="sans drapeau valide"):
        validate_chunk(chunk)

    chunk["formulas"][0]["flag"] = "proven"
    chunk["formulas"][0]["provenance"] = {"page": 1}
    with pytest.raises(ValueError, match="sans provenance"):
        validate_chunk(chunk)

    missing_origin = {
        "chunk_id": "abc:00000",
        "text": "x",
        "items": [{"origin": None}],
        "formulas": [],
    }
    with pytest.raises(ValueError, match="Item sans origine"):
        validate_chunk(missing_origin)

    for items in (None, []):
        without_items = {
            "chunk_id": "abc:00000",
            "text": "x",
            "items": items,
            "formulas": [],
        }
        with pytest.raises(ValueError, match="Contenu sans origine"):
            validate_chunk(without_items)


def test_un_supplement_est_publie_avec_son_origine_sans_devenir_prouve() -> None:
    document = _document(_text(0, "Contexte localisé."))
    region = {
        "region_id": "pdf-source:1:1",
        "page": 1,
        "bbox": [20.0, 20.0, 30.0, 30.0],
        "source_glyph_text": "x",
        "source_canonical_tokens": ["x"],
        "source_relation_signature": ["x"],
        "candidate_link_status": "not_linked",
        "candidate_link_reason": {"code": "docling_text_container_missing"},
        "verdict": "contradicted",
        "semantic_status": "not_established",
    }
    operations = pdf_supplement_records([region])
    developed, created = develop_document(document, operations)
    for record, item in created:
        record["derived_docling_ref"] = item.self_ref
        record["derived_charspan"] = [0, len(item.text)]

    chunks, _unlocatable = build_chunks(
        developed, _report(region), ENTRY, development_operations=operations
    )

    formula = chunks[0]["formulas"][0]
    assert formula["origin"] == "pdf_supplement"
    assert formula["flag"] == "unverified"
    assert any(
        item["origin"] == "pdf_supplement" for item in chunks[0]["items"]
    )


def test_une_correction_reconstruite_porte_son_origine_et_sa_preuve() -> None:
    document = _document(_text(0, "Valeur $x$ ici."))
    operation = {
        "operation": "correction",
        "kind": "replacement",
        "target_id": "correction:1",
        "docling_ref": "#/texts/0",
        "derived_docling_ref": "#/texts/0",
        "charspan": [7, 10],
        "derived_charspan": [7, 10],
        "before": "$x$",
        "after": "$y$",
        "mathml": '<math data-correction-id="correction:1"><mi>y</mi></math>',
    }
    developed, _created = develop_document(document, [operation])
    report = _report(_source("#/texts/0", [7, 10], "matching"))

    chunks, _unlocatable = build_chunks(
        developed, report, ENTRY, development_operations=[operation]
    )

    assert chunks[0]["items"][0]["origin"] == "correction"
    assert chunks[0]["formulas"][0]["origin"] == "correction"
    assert chunks[0]["formulas"][0]["flag"] == "proven"


def test_le_budget_de_caracteres_coupe_sans_scinder_un_item() -> None:
    long_a = "a" * 1_000
    long_b = "b" * 1_000
    document = _document(_text(0, long_a), _text(1, long_b))

    chunks, _unlocatable = build_chunks(document, _report(), ENTRY)

    assert [c["text"] for c in chunks] == [long_a, long_b]


def test_l_export_ecrit_l_en_tete_et_les_chunks(tmp_path: Path) -> None:
    directory = tmp_path / ("f" * 12)
    directory.mkdir(parents=True)
    document = _document(_text(0, "Texte avec $x$ dedans."))
    (directory / "docling-document.json").write_text(
        document.model_dump_json(), encoding="utf-8"
    )
    (directory / "report.json").write_text(
        json.dumps(_report(_source("#/texts/0", [12, 13], "matching"))),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "documents": [ENTRY]}), encoding="utf-8"
    )

    code = main(
        ["export", "--manifest", str(manifest_path), "--work", str(tmp_path)]
    )

    assert code == 0
    lines = [
        json.loads(line)
        for line in (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert lines[0]["type"] == "header"
    assert lines[0]["schema_version"] == 2
    assert lines[0]["document"]["sha256"] == "f" * 64
    assert len(lines[0]["native_document_sha256"]) == 64
    assert len(lines[0]["recipe_sha256"]) == 64
    assert lines[0]["origin_counts"] == {
        "transcription": 1,
        "correction": 0,
        "pdf_supplement": 0,
    }
    assert lines[0]["chunks"] == len(lines) - 1
    assert lines[1]["type"] == "chunk"
    assert lines[1]["formulas"][0]["flag"] == "proven"
    assert lines[1]["formulas"][0]["origin"] == "transcription"
    assert lines[1]["items"][0]["origin"] == "transcription"


def test_l_export_refuse_un_rapport_qui_annonce_une_autre_empreinte(tmp_path: Path) -> None:
    directory = tmp_path / ("f" * 12)
    directory.mkdir(parents=True)
    document = _document(_text(0, "Texte avec $x$ dedans."))
    (directory / "docling-document.json").write_text(
        document.model_dump_json(), encoding="utf-8"
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "documents": [ENTRY]}), encoding="utf-8"
    )
    rapport = _report(_source("#/texts/0", [12, 13], "matching"))

    # Une empreinte de natif annoncée qui ne correspond pas au fichier lu.
    rapport["docling_document"] = {"sha256": "0" * 64}
    (directory / "report.json").write_text(json.dumps(rapport), encoding="utf-8")
    assert main(["export", "--manifest", str(manifest_path), "--work", str(tmp_path)]) == 1

    # Et une empreinte de recette annoncée qui ne correspond pas aux opérations.
    del rapport["docling_document"]
    rapport["development"] = {"recipe_sha256": "0" * 64}
    (directory / "report.json").write_text(json.dumps(rapport), encoding="utf-8")
    assert main(["export", "--manifest", str(manifest_path), "--work", str(tmp_path)]) == 1


def test_la_projection_source_est_stable_et_sans_signal_commercial() -> None:
    catalog_entry = {
        "source_sha256": ENTRY["sha256"],
        "file_name": ENTRY["name"],
        "document_kind": "book",
        "bibliography": {
            "title": "Titre prouvé",
            "authors": ["Auteur"],
            "language": "en",
            "publisher": "Éditeur",
            "identifiers": {"isbn10": [], "isbn13": ["9780000000000"], "issn": []},
            "provenance": [{"kind": "manual", "reviewer": "test"}],
        },
        "temporality": {
            "work_first_published": None,
            "edition_published": {"value": "2020", "proof": {"kind": "manual", "reviewer": "test"}},
            "content_revision": None,
        },
        "resolution": {"status": "accepted"},
        "editorial_review": {
            "status": "reviewed",
            "reviewed_at": "2026-08-07",
            "domains": ["trading"],
            "authority_basis": {"level": "domain_specific"},
            "review_flags": [],
        },
        "provider_observations": [],
        "commercial_observations": [{"provider": "amazon", "rank": 1}],
    }
    projection = stable_projection(catalog_entry)
    document = _document(_text(0, "Texte avec $x$ dedans."))
    chunks, _unlocatable = build_chunks(
        document,
        _report(_source("#/texts/0", [12, 13], "matching")),
        ENTRY,
        projection,
    )

    assert chunks[0]["source"]["source_sha256"] == ENTRY["sha256"]
    assert chunks[0]["source"]["bibliography"]["provenance"] == catalog_entry["bibliography"]["provenance"]
    assert "commercial_observations" not in chunks[0]["source"]
    assert chunks[0]["source"]["source_catalog_schema_version"] == 1


def test_une_region_missing_contredit_le_drapeau() -> None:
    """Le verdict du pipeline est l'autorité : missing porte contradicted."""
    document = _document(_text(0, "Valeur $x>0$ ici."))
    report = _report(
        _source("#/texts/0", [8, 11], "matching"),
        _source("#/texts/0", [8, 11], "missing"),
    )

    formula = build_chunks(document, report, ENTRY)[0][0]["formulas"][0]

    assert formula["flag"] == "contradicted"
    assert formula["evidence"]["contradicted"] == 1


def test_une_region_qui_deborde_ne_fournit_pas_la_boite_de_citation() -> None:
    """Un appariement naïf de dollars peut produire une région à cheval sur la
    prose : sans contenement, on citerait la mauvaise boîte."""
    document = _document(_text(0, "Valeur $x>0$ ici."))
    report = _report(
        docling_regions=[
            {
                "docling_ref": "#/texts/0",
                "charspan": [2, 10],
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "page": 1,
            }
        ]
    )

    formula = build_chunks(document, report, ENTRY)[0][0]["formulas"][0]

    assert formula["provenance"]["precision"] == "item"
    assert formula["provenance"]["bbox"] != [1.0, 2.0, 3.0, 4.0]


def test_un_item_sans_provenance_garde_son_texte_et_cite_le_chunk() -> None:
    sans_prov = _text(1, "loc_171>Bobby C. et $y$ ici.")
    sans_prov["prov"] = []
    document = _document(_text(0, "Contexte localisé."), sans_prov)

    chunks, _unlocatable = build_chunks(document, _report(), ENTRY)

    assert len(chunks) == 1
    assert "loc_171>" in chunks[0]["text"]
    formula = chunks[0]["formulas"][0]
    assert formula["provenance"]["precision"] == "chunk"
    assert formula["provenance"]["page"] == 1


def test_consigne_sans_publier_un_chunk_entierement_intracable() -> None:
    """Une suite d'artefacts sans localisation est écartée mais observable."""
    seul = _text(0, "Orphelin $z$ total.")
    seul["prov"] = []
    document = _document_sans_page(seul)

    chunks, unlocatable = build_chunks(document, _report(), ENTRY)

    assert chunks == []
    assert unlocatable == ["#/texts/0"]


def _document_sans_page(*texts: dict) -> DoclingDocument:
    return DoclingDocument.model_validate(
        {
            "name": "chunks-test",
            "pages": {},
            "body": {
                "self_ref": "#/body",
                "children": [{"$ref": text["self_ref"]} for text in texts],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "body",
            },
            "furniture": {
                "self_ref": "#/furniture",
                "children": [],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "furniture",
            },
            "texts": list(texts),
        }
    )


def test_les_couches_hors_corps_ne_produisent_ni_texte_ni_formule() -> None:
    meuble = _text(1, "E = m c^2", label="formula")
    meuble["content_layer"] = "furniture"
    meuble["parent"] = {"$ref": "#/furniture"}
    document = _document(_text(0, "Corps du texte."))
    document = DoclingDocument.model_validate(
        document.model_dump(mode="json") | {"texts": [
            document.texts[0].model_dump(mode="json"), meuble
        ]}
    )

    chunks, _unlocatable = build_chunks(document, _report(), ENTRY)

    assert len(chunks) == 1
    assert "E = m c^2" not in chunks[0]["text"]
    assert chunks[0]["formulas"] == []
