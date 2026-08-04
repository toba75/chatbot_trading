import json
from pathlib import Path

import pytest

from docling_core.types.doc import DoclingDocument, TableCell, TableData

from pdf_math_audit.correction import CorrectionConfig, correct_document
from pdf_math_audit.correction_targets import ineligibility
from pdf_math_audit.derived_document import (
    derive_document,
    derive_document_and_page_html,
)
from pdf_math_audit.gemma_proposal import Proposal, ProposalError
from pdf_math_audit.mathml_candidate import candidate_signature, candidate_tokens


ROOT = Path(__file__).parents[2]
PDF = ROOT / "experiments/math_pipeline_comparison/source-pages-7-10.pdf"
DOCUMENT = ROOT / "experiments/math_pipeline_comparison/docling-subset-document.json"
FORMULA = r"\{(\mathbf{x}_i,y_i)\}_{i=1}^{N}"


def _region() -> dict[str, object]:
    return {
        "region_id": "pdf-source:1:733",
        "page": 1,
        "bbox": [415.401, 310.126, 467.854, 324.486],
        "docling_ref": "#/texts/8",
        "candidate_charspan": [83, 119],
        "candidate_text": "( x$_{i}$ , y$_{i}$ ) } N i = $_{1}$",
        "candidate_link_status": "linked",
        "status": "traced",
        "semantic_status": "established",
        "verdict": "contradicted",
        "source_canonical_tokens": list("{(xi,yi)}i=1N"),
        "source_relation_signature": [
            "{",
            "(",
            "<bold>",
            "x",
            "</bold>",
            "<sub>",
            "i",
            "</sub>",
            ",",
            "y",
            "<sub>",
            "i",
            "</sub>",
            ")",
            "}",
            "<sub>",
            "i",
            "=",
            "1",
            "</sub>",
            "<sup>",
            "N",
            "</sup>",
        ],
        "source_relations": [
            {"token": "i", "role": "subscript"},
            {"token": "N", "role": "superscript"},
        ],
        "source_relation_reason": None,
    }


def _config() -> CorrectionConfig:
    return CorrectionConfig("http://gemma/v1", "gemma", 300, 4.0, 10, 10_000)


def _proposal(**_arguments: object) -> Proposal:
    return Proposal(FORMULA, {"request": True}, {"response": True})


def test_cree_un_document_derive_sans_modifier_le_document_natif() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.texts[8].text += (
        " Renvoi$^{(2)}$. $^{2}$Texte de la note. "
        "Variables $x_i$, $a + b$ et $f ( x )$. "
        "Prix $5, puis $10. Spendings, M$."
    )
    original_text = document.texts[8].text
    original_orig = document.texts[8].orig
    original_provenance = [item.model_dump() for item in document.texts[8].prov]

    result = correct_document(
        PDF, document, [_region()], _config(), proposal_client=_proposal
    )

    assert result.summary == {
        "status": "corrected",
        "targets": 1,
        "accepted": 1,
        "rejected": 0,
        "failed": 0,
        "engine": {"model": "gemma", "dpi": 300, "padding_points": 4.0},
    }
    assert document.texts[8].text == original_text
    assert document.texts[8].orig == original_orig
    derived = DoclingDocument.model_validate_json(result.document)
    assert derived.texts[8].text[83 : 83 + len(FORMULA) + 2] == f"${FORMULA}$"
    assert derived.texts[8].orig == original_orig
    assert [item.model_dump() for item in derived.texts[8].prov] == original_provenance
    assert result.markdown == derived.export_to_markdown().encode("utf-8")
    records = json.loads(result.records)
    assert records["records"][0]["before"] == _region()["candidate_text"]
    assert records["records"][0]["after"] == f"${FORMULA}$"
    mathml = records["records"][0]["mathml"]
    assert mathml.startswith('<math data-correction-id="pdf-source:1:733" ')
    assert 'xmlns="http://www.w3.org/1998/Math/MathML"' in mathml
    assert mathml.encode() in result.html
    assert b"id='page-1'" in result.html
    assert f"${FORMULA}$".encode() not in result.html
    assert b"$^{1}$" not in result.html
    assert b"$^{(2)}$" not in result.html
    assert b"$^{2}$" not in result.html
    assert b"$x_i$" not in result.html
    assert b"$a + b$" not in result.html
    assert b"$f ( x )$" not in result.html
    assert b'data-docling-kind="inline-math"' in result.html
    assert b"Prix $5, puis $10." in result.html
    assert b"Spendings, M$." in result.html
    assert "$^{(2)}$" in derived.texts[8].text
    assert "$^{2}$" in derived.texts[8].text
    assert result.evidence.startswith(b"PK")


def test_refuse_le_remplacement_partiel_d_une_formule_docling() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    region = {
        "verdict": "contradicted",
        "status": "traced",
        "semantic_status": "established",
        "candidate_link_status": "linked",
        "source_relation_reason": None,
        "source_canonical_tokens": ["x"],
        "source_relation_signature": ["x"],
        "docling_ref": node.self_ref,
        "candidate_charspan": [2, len(node.text)],
        "candidate_text": node.text[2:],
        "bbox": [0.0, 0.0, 10.0, 10.0],
    }

    assert ineligibility(region, document) == (
        "formula_partial_replacement_unsupported"
    )


@pytest.mark.parametrize("span", [[-1, 3], [3, 3], [5, 3], [0, 10_000]])
def test_refuse_un_charspan_invalide(span: list[int]) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    region = _region()
    region["candidate_charspan"] = span
    region["candidate_text"] = document.texts[8].text[slice(*span)]

    assert ineligibility(region, document) == "candidate_charspan_invalid"


def test_l_export_derive_refuse_aussi_un_charspan_invalide() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())

    with pytest.raises(ValueError, match="Charspan de correction invalide"):
        derive_document(
            document,
            [{"docling_ref": "#/texts/8", "charspan": [5, 3], "after": "$x$"}],
        )


def test_remplace_une_formule_complete_sans_exposer_le_marqueur_html() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    literal_marker = "OSTMATHCORRECTION00000000END"
    document.texts[2].text += literal_marker
    node = document.texts[16]
    proposal = r"\mathbf{w}\mathbf{x}+b"
    mathml = (
        '<math data-correction-id="formula-16" '
        'xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
        "<mrow><mi>wx+b</mi></mrow></math>"
    )
    record = {
        "docling_ref": node.self_ref,
        "charspan": [0, len(node.text)],
        "after": proposal,
        "proposal": proposal,
        "mathml": mathml,
    }

    derived, html = derive_document_and_page_html(document, [record])

    assert document.texts[16].text == "w x - b = 0 ,"
    assert derived.texts[16].text == proposal
    assert html.count(mathml.encode()) == 1
    assert literal_marker.encode() in html
    assert b'<annotation encoding="TeX"><math' not in html


def test_le_registre_d_une_formule_complete_conserve_le_latex_brut() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    proposal = node.text
    tokens, token_reason = candidate_tokens(proposal, "latex")
    signature, signature_reason = candidate_signature(proposal)
    assert token_reason is None
    assert signature_reason is None
    region = {
        "region_id": "formula-16",
        "page": 2,
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, len(node.text)],
        "candidate_text": node.text,
        "candidate_format": "latex",
        "candidate_link_status": "linked",
        "status": "traced",
        "semantic_status": "established",
        "verdict": "contradicted",
        "source_canonical_tokens": tokens,
        "source_relation_signature": signature,
        "source_relations": [],
        "source_relation_reason": None,
    }

    result = correct_document(
        PDF,
        document,
        [region],
        _config(),
        proposal_client=lambda **_arguments: Proposal(proposal, {}, {}),
    )

    record = json.loads(result.records)["records"][0]
    derived = DoclingDocument.model_validate_json(result.document)
    assert record["status"] == "accepted"
    assert record["after"] == proposal
    assert 'display="block"' in record["mathml"]
    assert derived.texts[16].text == proposal
    assert record["mathml"].encode() in result.html


def test_ne_remplace_pas_un_marqueur_inline_present_dans_le_texte() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    literal_marker = "OSTDOCLINGMATH00000000END"
    document.texts[2].text += literal_marker
    document.texts[8].text += " Variable $x_i$."

    _derived, html = derive_document_and_page_html(document, [])

    assert literal_marker.encode() in html
    assert b'data-docling-kind="inline-math"' in html


def test_ne_remplace_pas_un_marqueur_inline_present_dans_un_tableau() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    literal_marker = "OSTDOCLINGMATH00000000END"
    document.add_table(
        TableData(
            num_rows=1,
            num_cols=1,
            table_cells=[
                TableCell(
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=0,
                    end_col_offset_idx=1,
                    text=literal_marker,
                )
            ],
        )
    )
    document.texts[8].text += " Variable $x_i$."

    _derived, html = derive_document_and_page_html(document, [])

    assert literal_marker.encode() in html
    assert b'data-docling-kind="inline-math"' in html


def test_ne_retraite_pas_le_latex_inline_d_un_noeud_formule() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.texts[16].text = (
        r"\begin{cases} 0 & \text{if $z<0$} \\ z & \text{otherwise} \end{cases}"
    )

    _derived, html = derive_document_and_page_html(document, [])

    assert b"OSTDOCLINGMATH" not in html
    assert b'<annotation encoding="TeX">' in html


def test_rejette_une_proposition_non_prouvee_sans_produire_de_document() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())

    result = correct_document(
        PDF,
        document,
        [_region()],
        _config(),
        proposal_client=lambda **_arguments: Proposal("x_i", {}, {}),
    )

    assert result.summary["status"] == "rejected"
    assert result.document is None
    assert json.loads(result.records)["records"][0]["reason"] == (
        "proposal_not_proven_by_source"
    )


def test_rejette_une_relation_fausse_meme_si_les_symboles_sont_identiques() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    wrong_relation = r"\{(\mathbf{x}^i,y_i)\}_{i=1}^{N}"

    result = correct_document(
        PDF,
        document,
        [_region()],
        _config(),
        proposal_client=lambda **_arguments: Proposal(wrong_relation, {}, {}),
    )

    record = json.loads(result.records)["records"][0]
    assert record["proposal_tokens"] == _region()["source_canonical_tokens"]
    assert record["proposal_signature"] != _region()["source_relation_signature"]
    assert record["status"] == "rejected"
    assert result.document is None


def test_rejette_la_perte_du_gras_meme_si_les_symboles_sont_identiques() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    without_bold = r"\{(x_i,y_i)\}_{i=1}^{N}"

    result = correct_document(
        PDF,
        document,
        [_region()],
        _config(),
        proposal_client=lambda **_arguments: Proposal(without_bold, {}, {}),
    )

    record = json.loads(result.records)["records"][0]
    assert record["proposal_tokens"] == _region()["source_canonical_tokens"]
    assert record["proposal_signature"] != _region()["source_relation_signature"]
    assert record["status"] == "rejected"


def test_signale_explicitement_un_service_de_proposition_indisponible() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())

    def unavailable(**_arguments: object) -> Proposal:
        raise ProposalError("indisponible", request={"request": True}, response=b"brut")

    result = correct_document(
        PDF, document, [_region()], _config(), proposal_client=unavailable
    )

    assert result.summary["status"] == "failed"
    assert result.summary["failed"] == 1
    assert json.loads(result.records)["records"][0]["reason"] == (
        "proposal_service_failed"
    )
    assert b"response.bin" in result.evidence


def test_checkpoint_chaque_proposition_avant_la_fin_du_traitement(
    tmp_path: Path,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    records = tmp_path / "records.ndjson"
    evidence = tmp_path / "evidence"

    correct_document(
        PDF,
        document,
        [_region()],
        _config(),
        proposal_client=_proposal,
        checkpoint_records=records,
        checkpoint_evidence=evidence,
    )

    assert json.loads(records.read_text("utf-8"))["status"] == "accepted"
    assert (
        (evidence / "pdf-source_1_733" / "crop.png").read_bytes().startswith(b"\x89PNG")
    )
    assert (evidence / "pdf-source_1_733" / "request.json").is_file()
    assert (evidence / "pdf-source_1_733" / "response.json").is_file()


def test_refuse_deux_loci_qui_se_chevauchent_avant_tout_appel_modele() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    second = _region() | {"region_id": "pdf-source:1:734"}
    calls = 0

    def unexpected(**_arguments: object) -> Proposal:
        nonlocal calls
        calls += 1
        return _proposal()

    result = correct_document(
        PDF, document, [_region(), second], _config(), proposal_client=unexpected
    )

    assert calls == 0
    assert result.summary["rejected"] == 2
    assert {record["reason"] for record in json.loads(result.records)["records"]} == {
        "candidate_loci_overlap"
    }
    assert result.document is None
