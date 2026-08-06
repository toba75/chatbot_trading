from pathlib import Path

import fitz
from docling_core.types.doc import DocItemLabel, DoclingDocument
from latex2mathml.converter import convert

from pdf_math_audit.derived_document import derive_document_and_page_html
from pdf_math_audit.html_integrity import audit_page_html
from pdf_math_audit.page_html import render_page_anchored_html


ROOT = Path(__file__).parents[2]
DOCUMENT = ROOT / "experiments/math_pipeline_comparison/docling-subset-document.json"


def _pdf(path: Path, *, first_page_text: bool = False) -> Path:
    document = fitz.open()
    first = document.new_page()
    if first_page_text:
        first.insert_text((20, 20), "couverture")
    document.new_page().insert_text((20, 20), "contenu")
    document.save(path)
    document.close()
    return path


def _without_inline_latex(document: DoclingDocument) -> DoclingDocument:
    clean = document.model_copy(deep=True)
    for item, _level in clean.iterate_items():
        if item.label != DocItemLabel.FORMULA and hasattr(item, "text"):
            item.text = item.text.replace("$", "")
    return clean


def test_valide_les_ancres_et_l_inventaire_canonique(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "passed", audit["issues"]
    assert audit["pages_checked"] == 2
    assert audit["issues"] == []


def test_detecte_une_formule_inline_restee_sous_forme_de_dollars(
    tmp_path: Path,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.texts[0].text += " et $x_i$"
    html = render_page_anchored_html(document)

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "failed"
    assert any(
        issue["code"] == "math_inventory_incomplete" for issue in audit["issues"]
    )


def test_signale_le_latex_brut_d_une_formule_non_serialisable(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    formula.text = (
        r"\left [ \begin{matrix} v \\ X \end{matrix} \right ] \sim N "
        r"\left [ \begin{matrix} 0 \\ 0 \end{matrix} \right ) , "
        r"\left ( \begin{matrix} 1 & 1 \\ 1 & 1 + \delta ^ { 2 } "
        r"\end{matrix} \right ) \right ]"
    )

    audit = audit_page_html(
        document,
        render_page_anchored_html(document),
        _pdf(tmp_path / "source.pdf"),
    )

    assert any(
        issue["code"] == "formula_rendering_fallback"
        for issue in audit["issues"]
    )
    assert any(
        issue["code"] == "formula_visual_delimiters_invalid"
        for issue in audit["issues"]
    )


def test_ne_prend_pas_des_montants_en_dollars_pour_une_formule(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " Prices moved from $5 to $10."
    html = render_page_anchored_html(document)

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "passed"


def test_distingue_les_dollars_monetaires_d_une_formule_inline(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " Capitalisation 10 M$, coût $5 et formule $x_i$."
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "passed", audit["issues"]
    assert b"10 M$" in html
    assert b"$5" in html
    assert b"$x_i$" not in html


def test_ignore_les_dollars_litteraux_echappes(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += r" Price \$5 to \$10."
    html = render_page_anchored_html(document)

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "passed"


def test_detecte_une_page_html_vide_malgre_un_contenu_pdf(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    html = render_page_anchored_html(document)
    html = html.replace(b"class='page'", b"class='page blank-page'", 1)

    audit = audit_page_html(
        document,
        html,
        _pdf(tmp_path / "source.pdf", first_page_text=True),
    )

    assert audit["status"] == "failed"
    assert {
        "page": 1,
        "code": "source_content_missing",
        "message": "Le PDF contient du contenu mais la page HTML est vide",
    } in audit["issues"]


def test_detecte_une_page_html_videe_sans_marqueur_blank_page(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    html = render_page_anchored_html(document)
    start = html.index(b"<div class='page' id='page-1'>")
    content_start = html.index(b">", start) + 1
    end = html.index(b"</div>", content_start)
    html = html[:content_start] + html[end:]

    audit = audit_page_html(
        document,
        html,
        _pdf(tmp_path / "source.pdf", first_page_text=True),
    )

    assert any(
        issue["code"] == "source_content_missing" for issue in audit["issues"]
    )


def test_detecte_un_dollar_non_apparie(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " $x"
    html = render_page_anchored_html(document)

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert any(
        issue["code"] == "inline_math_delimiters_invalid"
        for issue in audit["issues"]
    )


def test_detecte_une_ancre_inattendue(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    html = render_page_anchored_html(document).replace(
        b"</body>", b"<div id='page-999'></div></body>"
    )

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert any(
        issue["code"] == "page_anchor_sequence_invalid"
        for issue in audit["issues"]
    )


def test_compte_comme_controlee_une_page_dont_l_ancre_manque(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    html = render_page_anchored_html(document).replace(b"id='page-1'", b"", 1)

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "failed"
    assert audit["pages_checked"] == audit["pages_total"] == 2
    assert any(
        issue["code"] == "page_anchor_count_invalid" for issue in audit["issues"]
    )


def test_detecte_une_formule_html_dupliquee(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    html = render_page_anchored_html(document)
    start = html.index(b"<math")
    end = html.index(b"</math>", start) + len(b"</math>")
    html = html[:end] + html[start:end] + html[end:]

    audit = audit_page_html(document, html, _pdf(tmp_path / "source.pdf"))

    assert any(
        issue["code"] == "math_inventory_unexpected"
        for issue in audit["issues"]
    )


def test_prouve_le_lien_region_docling_dom(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    page = formula.prov[0].page_no
    region = {
        "region_id": "pdf-source:1",
        "page": page,
        "verdict": "conformant_within_scope",
        "candidate_link_status": "linked",
        "docling_ref": formula.self_ref,
        "candidate_charspan": [0, len(formula.text)],
        "candidate_text": formula.text,
    }

    audit = audit_page_html(
        document,
        render_page_anchored_html(document),
        _pdf(tmp_path / "source.pdf"),
        [region],
    )

    assert audit["region_links"] == [
        {
            "region_id": "pdf-source:1",
            "page": page,
            "docling_ref": formula.self_ref,
            "candidate_charspan": [0, len(formula.text)],
            "dom_charspan": [0, len(formula.text)],
            "dom_selector": (
                f"math[@data-docling-ref='{formula.self_ref}']"
                f"[@data-docling-charspan='0:{len(formula.text)}']"
            ),
            "matches": 1,
            "status": "matched",
        }
    ]


def test_refuse_une_region_prouvee_sans_noeud_mathml_identifie(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    html = render_page_anchored_html(document).replace(
        f' data-docling-ref="{formula.self_ref}"'.encode(), b"", 1
    )
    region = {
        "region_id": "pdf-source:missing",
        "page": formula.prov[0].page_no,
        "verdict": "conformant_within_scope",
        "candidate_link_status": "linked",
        "docling_ref": formula.self_ref,
        "candidate_charspan": [0, len(formula.text)],
        "candidate_text": formula.text,
    }

    audit = audit_page_html(
        document, html, _pdf(tmp_path / "source.pdf"), [region]
    )

    assert audit["region_links"][0]["status"] == "missing"
    assert any(issue["code"] == "linked_math_missing" for issue in audit["issues"])
    assert next(
        page for page in audit["pages"] if page["page"] == formula.prov[0].page_no
    )["status"] == "failed"


def test_refuse_une_region_liee_sans_identite_docling(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    region = {
        "region_id": "pdf-source:identity-missing",
        "page": formula.prov[0].page_no,
        "verdict": "conformant_within_scope",
        "candidate_link_status": "linked",
        "docling_ref": None,
        "candidate_charspan": None,
        "candidate_text": None,
    }

    audit = audit_page_html(
        document,
        render_page_anchored_html(document),
        _pdf(tmp_path / "source.pdf"),
        [region],
    )

    assert audit["region_links"] == []
    assert any(
        issue["code"] == "linked_math_identity_missing"
        for issue in audit["issues"]
    )


def test_refuse_un_charspan_qui_ne_designe_pas_le_texte_candidat(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    region = {
        "region_id": "pdf-source:wrong-charspan",
        "page": formula.prov[0].page_no,
        "verdict": "conformant_within_scope",
        "candidate_link_status": "linked",
        "docling_ref": formula.self_ref,
        "candidate_charspan": [0, 1],
        "candidate_text": formula.text,
    }

    audit = audit_page_html(
        document,
        render_page_anchored_html(document),
        _pdf(tmp_path / "source.pdf"),
        [region],
    )

    assert audit["region_links"] == []
    assert any(
        issue["code"] == "linked_math_identity_missing"
        for issue in audit["issues"]
    )


def test_prouve_le_lien_d_une_formule_corrigee_dans_le_document_derive(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    formula = next(item for item in document.texts if item.label == DocItemLabel.FORMULA)
    region = {
        "region_id": "pdf-source:corrected",
        "page": formula.prov[0].page_no,
        "verdict": "contradicted",
        "candidate_link_status": "linked",
        "docling_ref": formula.self_ref,
        "candidate_charspan": [0, len(formula.text)],
        "candidate_text": formula.text,
    }
    correction = {
        "target_id": "pdf-source:corrected",
        "kind": "formula_replacement",
        "region_id": region["region_id"],
        "region_ids": [region["region_id"]],
        "page": region["page"],
        "docling_ref": formula.self_ref,
        "charspan": region["candidate_charspan"],
        "before": formula.text,
        "after": "x",
        "mathml": convert("x").replace(
            "<math ",
            '<math data-correction-id="pdf-source:corrected" ',
            1,
        ),
        "status": "accepted",
        "source_proofs": [
            {
                "region_id": region["region_id"],
                "candidate_charspan": region["candidate_charspan"],
                "candidate_text": region["candidate_text"],
            }
        ],
    }
    derived, html = derive_document_and_page_html(document, [correction])

    audit = audit_page_html(
        derived,
        html,
        _pdf(tmp_path / "source.pdf"),
        [region],
        [correction],
    )

    assert correction["derived_charspan"] == [0, 1]
    assert audit["region_links"][0]["status"] == "matched"
    assert audit["region_links"][0]["dom_charspan"] == [0, 1]
    assert not any(
        issue["code"] == "linked_math_identity_missing"
        for issue in audit["issues"]
    )


def test_decale_le_locus_d_une_formule_inline_apres_une_correction_precedente(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    node = document.texts[0]
    node.text = "a $y$"
    region = {
        "region_id": "pdf-source:unchanged-inline",
        "page": node.prov[0].page_no,
        "verdict": "conformant_within_scope",
        "candidate_link_status": "linked",
        "docling_ref": node.self_ref,
        "candidate_charspan": [2, 5],
        "candidate_text": "$y$",
    }
    correction = {
        "target_id": "pdf-source:earlier-correction",
        "kind": "replacement",
        "region_id": "pdf-source:earlier-correction",
        "region_ids": ["pdf-source:earlier-correction"],
        "page": region["page"],
        "docling_ref": node.self_ref,
        "charspan": [0, 1],
        "before": "a",
        "after": "$x$",
        "mathml": convert("x").replace(
            "<math ",
            '<math data-correction-id="pdf-source:earlier-correction" ',
            1,
        ),
        "status": "accepted",
        "source_proofs": [
            {
                "region_id": "pdf-source:earlier-correction",
                "candidate_charspan": [0, 1],
                "candidate_text": "a",
            }
        ],
    }
    derived, html = derive_document_and_page_html(document, [correction])

    audit = audit_page_html(
        derived,
        html,
        _pdf(tmp_path / "source.pdf"),
        [region],
        [correction],
    )

    assert audit["region_links"][0]["status"] == "matched"
    assert audit["region_links"][0]["candidate_charspan"] == [2, 5]
    assert audit["region_links"][0]["dom_charspan"] == [4, 7]


def test_un_mot_isole_ne_prouve_pas_un_delimiteur_mathematique(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " Capitalisation 10 M$ et $x_i$ vaut $5."
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert audit["status"] == "passed", audit["issues"]
    assert b"10 M$" in html
    assert b"$5." in html
    assert b"$x_i$" not in html
    assert b"<mi>e</mi><mi>t</mi>" not in html


def test_ne_convertit_pas_les_dollars_d_un_bloc_de_code(tmp_path: Path) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.add_code(
        text="export PATH=$HOME/bin:$PATH",
        prov=document.texts[0].prov[0],
    )
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert b"export PATH=$HOME/bin:$PATH" in html
    assert audit["status"] == "passed", audit["issues"]


def test_signale_un_fragment_inline_non_convertible_au_lieu_de_l_alterer(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " coût $100%$ environ."
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert "coût $100%$ environ.".encode() in html
    assert audit["status"] == "failed"
    assert any(
        issue["code"] == "math_inventory_incomplete" for issue in audit["issues"]
    )


def test_ne_plante_pas_sur_un_fragment_inline_latex_invalide(
    tmp_path: Path,
) -> None:
    document = _without_inline_latex(
        DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    )
    document.texts[0].text += " on note $x_$ ici."
    derived, html = derive_document_and_page_html(document, [])

    audit = audit_page_html(derived, html, _pdf(tmp_path / "source.pdf"))

    assert b"$x_$" in html
    assert any(
        issue["code"] == "math_inventory_incomplete" for issue in audit["issues"]
    )
