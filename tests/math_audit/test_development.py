from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from docling_core.types.doc import BaseMeta, DoclingDocument

from pdf_math_audit.development import (
    develop_document,
    item_development_origin,
    pdf_supplement_records,
    recipe_from_operations,
    recipe_sha256,
)
from pdf_math_audit.derived_document import (
    derive_document_and_page_html,
    render_developed_markdown,
)


ROOT = Path(__file__).parents[2]
PDF = ROOT / "experiments/math_pipeline_comparison/source-pages-7-10.pdf"
DOCUMENT = ROOT / "experiments/math_pipeline_comparison/docling-subset-document.json"


def _region() -> dict[str, object]:
    return {
        "region_id": "pdf-source:1:9000",
        "page": 1,
        "bbox": [15.0, 20.0, 25.0, 30.0],
        "source_glyph_text": "x",
        "source_canonical_tokens": ["x"],
        "source_relation_signature": ["x"],
        "candidate_link_status": "not_linked",
        "candidate_link_reason": {"code": "docling_text_container_missing"},
        "candidate_status": "missing",
        "verdict": "contradicted",
        "semantic_status": "not_established",
    }


def test_la_recette_vide_est_l_identite_sans_modifier_le_natif() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    native = document.model_dump(mode="json")

    developed, created = develop_document(document, [])

    assert created == []
    assert developed is not document
    assert developed.model_dump(mode="json") == native
    assert document.model_dump(mode="json") == native


def test_le_supplement_recopie_la_preuve_et_reste_explicitement_non_verifie() -> None:
    records = pdf_supplement_records([_region()])

    assert records[0]["origin"] == "pdf_supplement"
    assert records[0]["operation"] == "pdf_supplement"
    assert records[0]["source_proof"]["verdict"] == "contradicted"
    assert records[0]["source_proof"]["candidate_link_reason"]["code"] == (
        "docling_text_container_missing"
    )

    with pytest.raises(ValueError, match="Texte glyphique absent"):
        pdf_supplement_records([_region() | {"source_glyph_text": ""}])

    degraded = pdf_supplement_records(
        [_region() | {"source_canonical_tokens": None, "source_tokens": ["x"]}]
    )[0]
    assert degraded["source_token_basis"] == "source_tokens"
    assert degraded["source_proof"]["source_canonical_tokens"] is None


def _fingerprint(document: DoclingDocument) -> str:
    payload = json.dumps(document.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_le_developpe_se_reconstruit_depuis_le_natif_et_la_recette() -> None:
    natif = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    operations = pdf_supplement_records([_region()])
    recette = recipe_from_operations(operations)

    premier, _ = develop_document(natif, operations)
    # Reconstruction depuis le seul couple natif + recette, sans réutiliser le
    # tirage précédent : le développé doit revenir à l'empreinte près.
    second, _ = develop_document(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes()), operations
    )

    assert _fingerprint(second) == _fingerprint(premier)
    assert recipe_sha256(recipe_from_operations(operations)) == recipe_sha256(recette)
    # Une recette différente ne peut pas rendre le même tirage.
    vide, _ = develop_document(DoclingDocument.model_validate_json(DOCUMENT.read_bytes()), [])
    assert _fingerprint(vide) != _fingerprint(premier)


def test_les_empreintes_de_recette_ignorent_les_metadonnees_de_derive() -> None:
    operation = pdf_supplement_records([_region()])[0]
    recipe = recipe_from_operations([operation])
    altered = copy.deepcopy(recipe)
    altered["operations"][0].update(
        derived_docling_ref="#/texts/99",
        derived_charspan=[0, 1],
    )

    assert recipe_sha256(recipe) == recipe_sha256(altered)

    correction = {
        "operation": "correction",
        "kind": "replacement",
        "docling_ref": "#/texts/8",
        "charspan": [0, 1],
        "before": "x",
        "after": "z",
        "mathml": "<math><mi>z</mi></math>",
    }
    changed = copy.deepcopy(correction)
    changed["mathml"] = "<math><mi>different</mi></math>"
    assert recipe_sha256(recipe_from_operations([correction])) != recipe_sha256(
        recipe_from_operations([changed])
    )


def test_refuse_une_origine_persistée_inconnue() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.texts[8].meta = BaseMeta.model_validate(
        {"rag__development_origin": "invented"}
    )

    with pytest.raises(ValueError, match="Origine de développement invalide"):
        item_development_origin(document.texts[8])


def test_refuse_un_before_incoherent_et_une_operation_inconnue() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[8]

    with pytest.raises(ValueError, match="Texte natif inattendu"):
        develop_document(
            document,
            [
                {
                    "operation": "correction",
                    "kind": "replacement",
                    "docling_ref": node.self_ref,
                    "charspan": [0, 1],
                    "before": "texte absent",
                    "after": "z",
                }
            ],
        )
    with pytest.raises(ValueError, match="Opération de développement inconnue"):
        develop_document(
            document,
            [
                {
                    "operation": "delete",
                    "docling_ref": node.self_ref,
                    "charspan": [0, 1],
                    "before": node.text[:1],
                    "after": "",
                }
            ],
        )
    with pytest.raises(ValueError, match="Opération de développement incohérente"):
        develop_document(
            document,
            [{"operation": "correction", "kind": "pdf_supplement"}],
        )


def test_un_supplement_ne_reordonne_pas_les_items_natifs() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    native_refs = [reference.resolve(document).self_ref for reference in document.body.children]
    operations = pdf_supplement_records([_region() | {"bbox": [0.0, 0.0, 1.0, 1.0]}])

    developed, created = develop_document(document, operations)

    developed_native_refs = [
        reference.resolve(developed).self_ref
        for reference in developed.body.children
        if reference.resolve(developed).self_ref in native_refs
    ]
    assert developed_native_refs == native_refs
    assert created[0][1].meta.model_extra["rag__development_origin"] == (
        "pdf_supplement"
    )


def test_html_et_markdown_affichent_le_supplement_et_les_empreintes() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    operations = pdf_supplement_records([_region()])
    native_sha256 = "a" * 64
    recipe_digest = recipe_sha256(recipe_from_operations(operations))

    derived, html = derive_document_and_page_html(
        document,
        operations,
        PDF,
        native_document_sha256=native_sha256,
        recipe_sha256_value=recipe_digest,
    )
    markdown = render_developed_markdown(
        derived,
        operations,
        native_document_sha256=native_sha256,
        recipe_sha256_value=recipe_digest,
    )

    assert b'data-origin="pdf_supplement"' in html
    assert "Suppl\u00e9ment PDF d\u00e9riv\u00e9".encode("utf-8") in html
    assert f'development-native-document-sha256" content="{native_sha256}"'.encode() in html
    assert f"native_document_sha256: {native_sha256}".encode() in markdown
    assert "Suppl\u00e9ment PDF d\u00e9riv\u00e9".encode("utf-8") in markdown
    assert b"pdf_supplement" not in markdown
