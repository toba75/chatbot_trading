import json
from pathlib import Path

import pytest

from docling_core.types.doc import (
    BoundingBox,
    CoordOrigin,
    DoclingDocument,
    ProvenanceItem,
    TableCell,
    TableData,
)

from pdf_math_audit.correction import CorrectionConfig, correct_document
from pdf_math_audit.correction_application import (
    apply_target,
    candidate_scope_reason,
    target_ineligibility,
)
from pdf_math_audit.correction_targets import correction_targets, ineligibility
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
    source_tokens = list("{(xi,yi)}i=1N")
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
        "candidate_tokens": source_tokens,
        "source_tokens": source_tokens,
        "source_canonical_tokens": source_tokens,
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
        "regions": 1,
        "target_region_ids": ["pdf-source:1:733"],
        "targets": 1,
        "accepted": 1,
        "accepted_regions": 1,
        "rejected": 0,
        "failed": 0,
        "engine": {
            "model": "gemma",
            "dpi": 300,
            "padding_points": 4.0,
            "strategy": "deterministic_source_then_proven_vision",
            "selected": {"deterministic_source": 1},
            "vision_calls": 0,
        },
    }
    assert document.texts[8].text == original_text
    assert document.texts[8].orig == original_orig
    derived = DoclingDocument.model_validate_json(result.document)
    records = json.loads(result.records)
    corrected = records["records"][0]["after"]
    assert derived.texts[8].text[83 : 83 + len(corrected)] == corrected
    assert derived.texts[8].orig == original_orig
    assert [item.model_dump() for item in derived.texts[8].prov] == original_provenance
    assert result.markdown == derived.export_to_markdown().encode("utf-8")
    assert records["records"][0]["before"] == _region()["candidate_text"]
    assert records["records"][0]["proposals"][0]["selected_engine"] == (
        "deterministic_source"
    )
    mathml = records["records"][0]["mathml"]
    assert mathml.startswith(
        '<math data-docling-ref="#/texts/8" '
        'data-docling-charspan="83:129" '
        'data-correction-id="pdf-source:1:733" '
    )
    assert 'xmlns="http://www.w3.org/1998/Math/MathML"' in mathml
    assert b'data-correction-id="pdf-source:1:733"' in result.html
    assert b'data-docling-ref="#/texts/8"' in result.html
    assert b"id='page-1'" in result.html
    assert corrected.encode() not in result.html
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


def test_regroupe_les_fragments_d_une_formule_en_un_remplacement_atomique() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    first = _region() | {
        "region_id": "formula:first",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, 1],
        "candidate_text": node.text[:1],
        "candidate_format": "latex",
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "glyph_sequence_indices": [10],
    }
    second = first | {
        "region_id": "formula:second",
        "candidate_charspan": [2, 3],
        "candidate_text": node.text[2:3],
        "glyph_sequence_indices": [20],
    }

    targets, region_count = correction_targets([first, second], document)

    assert region_count == 2
    assert len(targets) == 1
    assert targets[0]["kind"] == "formula_replacement"
    assert targets[0]["candidate_charspan"] == [0, len(node.text)]
    assert targets[0]["candidate_text"] == node.text
    assert [item["region_id"] for item in targets[0]["regions"]] == [
        "formula:first",
        "formula:second",
    ]


def test_regroupe_une_region_complete_et_un_fragment_de_la_meme_formule() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    fragment = _region() | {
        "region_id": "formula:fragment",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, 1],
        "candidate_text": node.text[:1],
        "candidate_format": "latex",
        "glyph_sequence_indices": [10],
    }
    complete = fragment | {
        "region_id": "formula:complete",
        "candidate_charspan": [0, len(node.text)],
        "candidate_text": node.text,
        "glyph_sequence_indices": [20],
    }

    targets, _region_count = correction_targets([fragment, complete], document)

    assert len(targets) == 1
    assert targets[0]["kind"] == "formula_replacement"
    assert {region["region_id"] for region in targets[0]["regions"]} == {
        "formula:fragment",
        "formula:complete",
    }


def test_classe_une_formule_complete_comme_remplacement_de_formule() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    complete = _region() | {
        "region_id": "formula:complete",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, len(node.text)],
        "candidate_text": node.text,
        "candidate_format": "latex",
        "glyph_sequence_indices": [10],
    }

    targets, _region_count = correction_targets([complete], document)

    assert len(targets) == 1
    assert targets[0]["kind"] == "formula_replacement"


def test_refuse_deux_preuves_source_superposees_dans_une_formule() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    first = _region() | {
        "region_id": "formula:first",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, 1],
        "candidate_text": node.text[:1],
        "candidate_format": "latex",
        "glyph_sequence_indices": [10],
    }
    second = first | {
        "region_id": "formula:second",
        "candidate_charspan": [2, 3],
        "candidate_text": node.text[2:3],
    }
    targets, _region_count = correction_targets([first, second], document)

    assert target_ineligibility(targets[0], document) == "source_loci_overlap"


def test_un_locus_invalide_bloque_toute_la_formule() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    valid = _region() | {
        "region_id": "formula:valid",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, 1],
        "candidate_text": node.text[:1],
        "candidate_format": "latex",
        "glyph_sequence_indices": [10],
    }
    invalid = valid | {
        "region_id": "formula:invalid",
        "candidate_charspan": None,
        "candidate_text": "",
        "glyph_sequence_indices": [20],
    }

    targets, _region_count = correction_targets([valid, invalid], document)

    assert len(targets) == 1
    assert targets[0]["kind"] == "formula_replacement"
    assert target_ineligibility(targets[0], document) == (
        "candidate_charspan_missing"
    )


def test_remplace_atomiquement_une_formule_complete_prouvee() -> None:
    target = {
        "target_id": "formula:complete",
        "kind": "formula_replacement",
        "candidate_text": "x - z + y",
        "regions": [
            {
                "candidate_charspan": [0, 9],
                "candidate_text": "x - z + y",
                "source_canonical_tokens": ["x", "+", "y"],
                "source_relation_signature": ["x", "+", "y"],
            },
        ],
    }

    after, mathml = apply_target(target, ["x + y"])

    assert after == "x + y"
    assert 'display="block"' in mathml


def test_refuse_une_formule_dont_des_jetons_ne_sont_pas_prouves() -> None:
    target = {
        "target_id": "formula:complete",
        "kind": "formula_replacement",
        "candidate_text": "x - z + y",
        "regions": [
            {
                "candidate_charspan": [0, 1],
                "candidate_text": "x",
                "source_canonical_tokens": ["x"],
                "source_relation_signature": ["x"],
            },
            {
                "candidate_charspan": [8, 9],
                "candidate_text": "y",
                "source_canonical_tokens": ["y"],
                "source_relation_signature": ["y"],
            },
        ],
    }

    with pytest.raises(ValueError, match="full_formula_reconstruction_unproven"):
        apply_target(target, ["x", "y"])


def test_ne_confond_pas_deux_occurrences_identiques_dans_une_formule() -> None:
    target = {
        "target_id": "formula:ambiguous",
        "kind": "formula_replacement",
        "candidate_text": "x + x",
        "regions": [
            {
                "candidate_charspan": [0, 5],
                "candidate_text": "x + x",
                "source_canonical_tokens": ["x"],
                "source_relation_signature": ["x"],
            }
        ],
    }

    after, _mathml = apply_target(target, ["x"])

    assert after == "x"


def test_regroupe_deux_loci_chevauches_si_leurs_sources_sont_distinctes() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    first = _region() | {
        "region_id": "overlap:first",
        "candidate_charspan": [80, 100],
        "candidate_text": document.texts[8].text[80:100],
        "glyph_sequence_indices": [10, 11],
    }
    second = first | {
        "region_id": "overlap:second",
        "candidate_charspan": [95, 110],
        "candidate_text": document.texts[8].text[95:110],
        "glyph_sequence_indices": [12, 13],
    }

    targets, region_count = correction_targets([first, second], document)

    assert region_count == 2
    assert len(targets) == 1
    assert targets[0]["kind"] == "merged_replacement"
    assert targets[0]["candidate_charspan"] == [80, 110]


def test_ajoute_une_region_sans_candidat_aux_cibles_d_acquisition() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    missing = _region() | {
        "verdict": "non_verifiable",
        "docling_ref": None,
        "candidate_charspan": None,
        "candidate_text": "",
        "candidate_format": None,
        "candidate_link_status": "not_linked",
        "candidate_link_reason": {"code": "docling_text_container_missing"},
        "glyph_sequence_indices": [10],
    }

    targets, region_count = correction_targets([missing], document)

    assert region_count == 1
    assert targets[0]["kind"] == "formula_insertion"


def test_normalise_un_indice_inline_separe_de_sa_base_par_les_dollars() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[8]
    node.text = "where σ$_{j,t}$ is observed"
    region = {
        "region_id": "pdf-source:9:31",
        "page": 1,
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "docling_ref": node.self_ref,
        "candidate_charspan": [6, 15],
        "candidate_text": "σ$_{j,t}$",
        "candidate_format": "mixed_text",
        "candidate_link_status": "linked",
        "candidate_tokens": ["σ", "j", ",", "t"],
        "candidate_relation_signature": [
            "σ",
            "<sub>",
            "j",
            ",",
            "t",
            "</sub>",
        ],
        "status": "traced",
        "semantic_status": "established",
        "verdict": "conformant_within_scope",
        "glyph_sequence_indices": [31, 32, 33, 34],
        "source_tokens": ["σ", "j", ",", "t"],
        "source_canonical_tokens": ["σ", "j", ",", "t"],
        "source_relation_signature": [
            "σ",
            "<sub>",
            "j",
            ",",
            "t",
            "</sub>",
        ],
        "source_relations": [
            {"token": "j", "role": "subscript"},
            {"token": ",", "role": "subscript"},
            {"token": "t", "role": "subscript"},
        ],
        "source_relation_reason": None,
    }

    targets, region_count = correction_targets([region], document)

    assert region_count == 1
    assert len(targets) == 1
    assert targets[0]["kind"] == "render_normalization"
    assert target_ineligibility(targets[0], document) is None

    result = correct_document(PDF, document, [region], _config())

    record = json.loads(result.records)["records"][0]
    assert result.summary["accepted"] == 1
    assert result.summary["engine"]["vision_calls"] == 0
    assert record["kind"] == "render_normalization"
    assert record["proposals"][0]["selected_engine"] == "deterministic_source"
    assert record["proposal_signature"] == region["source_relation_signature"]
    assert b'display="inline"' in result.html
    assert b"$_{j,t}$" not in result.html


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
    assert html.count(b'data-correction-id="formula-16"') == 1
    assert html.count(b'data-docling-ref="#/texts/16"') == 1
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
        "glyph_sequence_indices": [10],
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
    assert b'data-correction-id="formula-16"' in result.html
    assert b'data-docling-ref="#/texts/16"' in result.html


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


def test_rejette_une_proposition_non_prouvee_sans_produire_de_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    monkeypatch.setattr(
        "pdf_math_audit.correction_proposals.proven_source_latex",
        lambda _region: (None, "forced_model_path"),
    )

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


def test_rejette_une_relation_fausse_meme_si_les_symboles_sont_identiques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    monkeypatch.setattr(
        "pdf_math_audit.correction_proposals.proven_source_latex",
        lambda _region: (None, "forced_model_path"),
    )
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


def test_rejette_la_perte_du_gras_meme_si_les_symboles_sont_identiques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    monkeypatch.setattr(
        "pdf_math_audit.correction_proposals.proven_source_latex",
        lambda _region: (None, "forced_model_path"),
    )
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


def test_signale_explicitement_un_service_de_proposition_indisponible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    monkeypatch.setattr(
        "pdf_math_audit.correction_proposals.proven_source_latex",
        lambda _region: (None, "forced_model_path"),
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    monkeypatch.setattr(
        "pdf_math_audit.correction_proposals.proven_source_latex",
        lambda _region: (None, "forced_model_path"),
    )
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


def test_refuse_deux_preuves_source_qui_se_chevauchent_avant_tout_appel_modele() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    first = _region() | {"glyph_sequence_indices": [10]}
    second = first | {"region_id": "pdf-source:1:734"}
    calls = 0

    def unexpected(**_arguments: object) -> Proposal:
        nonlocal calls
        calls += 1
        return _proposal()

    result = correct_document(
        PDF, document, [first, second], _config(), proposal_client=unexpected
    )

    assert calls == 0
    assert result.summary["targets"] == 1
    assert result.summary["rejected"] == 1
    assert json.loads(result.records)["records"][0]["reason"] == (
        "source_loci_overlap"
    )
    assert result.document is None


def test_refuse_une_formule_absente_sans_ancrage_de_rendu_prouve() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    picture = document.add_picture(
        prov=ProvenanceItem(
            page_no=1,
            bbox=BoundingBox(
                l=0,
                t=0,
                r=40,
                b=40,
                coord_origin=CoordOrigin.TOPLEFT,
            ),
            charspan=(0, 0),
        )
    )
    calls = 0
    region = {
        "region_id": "missing:formula",
        "page": 1,
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "glyph_sequence_indices": [1],
        "docling_ref": picture.self_ref,
        "candidate_source_kind": "picture",
        "candidate_text": "",
        "candidate_format": None,
        "candidate_charspan": None,
        "candidate_link_status": "not_linked",
        "candidate_link_reason": {"code": "docling_picture_candidate_missing"},
        "status": "traced",
        "semantic_status": "established",
        "verdict": "non_verifiable",
        "source_canonical_tokens": ["x"],
        "source_relation_signature": ["x"],
        "source_relations": [],
        "source_relation_reason": None,
    }

    def vision(**arguments: object) -> Proposal:
        nonlocal calls
        calls += 1
        return Proposal("x", {}, {})

    result = correct_document(
        PDF, document, [region], _config(), proposal_client=vision
    )

    assert calls == 0
    assert result.summary["accepted"] == 0
    assert result.summary["rejected"] == 1
    assert result.summary["engine"]["vision_calls"] == 0
    assert result.document is None
    record = json.loads(result.records)["records"][0]
    assert record["kind"] == "formula_insertion"
    assert record["reason"] == "formula_insertion_rendering_unproven"


def test_refuse_un_connecteur_dont_le_role_textuel_n_est_pas_prouve() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "S if x$_{i}$",
        "regions": [
            {
                "candidate_tokens": ["S", "i", "f", "x", "i"],
                "source_tokens": ["S", "i", "f", "x", "i"],
                "source_canonical_tokens": ["S", "i", "f", "x", "i"],
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unproven_connective"


def test_refuse_aussi_le_connecteur_is_dans_une_phrase_courte() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "a is",
        "regions": [
            {
                "candidate_tokens": list("ais"),
                "source_tokens": list("ais"),
                "source_canonical_tokens": list("ais"),
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unproven_connective"


def test_refuse_generiquement_une_cible_qui_absorbe_de_la_prose() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "real-valued vector w",
        "regions": [
            {
                "candidate_tokens": list("real-valuedvectorw"),
                "source_tokens": list("real-valuedvectorw"),
                "source_canonical_tokens": list("real-valuedvectorw"),
            }
        ],
    }

    assert (
        candidate_scope_reason(target) == "candidate_contains_unstructured_prose"
    )


def test_refuse_une_phrase_courte_qui_absorbe_de_la_prose() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "let x",
        "regions": [
            {
                "candidate_tokens": list("letx"),
                "source_tokens": list("letx"),
                "source_canonical_tokens": list("letx"),
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unstructured_prose"


def test_refuse_une_phrase_accentuee_qui_absorbe_de_la_prose() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "café x",
        "regions": [
            {
                "candidate_tokens": list("caféx"),
                "source_tokens": list("caféx"),
                "source_canonical_tokens": list("caféx"),
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unstructured_prose"


def test_ne_confond_pas_un_operateur_moins_avec_un_mot_compose() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "wx - b = 0",
        "regions": [
            {
                "candidate_tokens": list("wx−b=0"),
                "source_tokens": list("wx−b=0"),
                "source_canonical_tokens": list("wx−b=0"),
                "source_relation_signature": list("wx−b=0"),
            }
        ],
    }

    assert candidate_scope_reason(target) is None


def test_ne_confond_pas_un_operateur_moins_sans_espaces_avec_un_mot_compose() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "wx-b",
        "regions": [
            {
                "candidate_tokens": list("wx−b"),
                "source_tokens": list("wx−b"),
                "source_canonical_tokens": list("wx−b"),
                "source_relation_signature": [
                    "w",
                    "<sub>",
                    "x",
                    "</sub>",
                    "−",
                    "b",
                ],
            }
        ],
    }

    assert candidate_scope_reason(target) is None


def test_refuse_une_phrase_accentuee_unicode_decomposee() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "cafe\u0301 x",
        "regions": [
            {
                "candidate_tokens": list("caféx"),
                "source_tokens": list("caféx"),
                "source_canonical_tokens": list("caféx"),
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unstructured_prose"


def test_accepte_def_quand_l_annotation_superieure_est_prouvee() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "xc def = [x]",
        "regions": [
            {
                "candidate_tokens": list("xcdef=[x]"),
                "source_tokens": list("xcdef=[x]"),
                "source_canonical_tokens": list("xc=def[x]"),
                "source_relation_signature": [
                    "x",
                    "c",
                    "=",
                    "<over>",
                    "d",
                    "e",
                    "f",
                    "</over>",
                    "[",
                    "x",
                    "]",
                ],
            }
        ],
    }

    assert candidate_scope_reason(target) is None


def test_une_annotation_def_ne_blanchit_pas_une_autre_occurrence_textuelle() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "def x xc def = [x]",
        "regions": [
            {
                "candidate_tokens": list("defxxcdef=[x]"),
                "source_tokens": list("defxxcdef=[x]"),
                "source_canonical_tokens": list("defxxc=def[x]"),
                "source_relation_signature": [
                    "d",
                    "e",
                    "f",
                    "x",
                    "x",
                    "c",
                    "=",
                    "<over>",
                    "d",
                    "e",
                    "f",
                    "</over>",
                    "[",
                    "x",
                    "]",
                ],
            }
        ],
    }

    assert candidate_scope_reason(target) == "candidate_contains_unstructured_prose"


def test_refuse_une_cible_dont_le_contenu_depasse_la_preuve_source() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "x and surrounding prose",
        "regions": [
            {
                "candidate_tokens": list("xandsurroundingprose"),
                "source_tokens": ["x"],
                "source_canonical_tokens": ["x"],
            }
        ],
    }

    assert (
        candidate_scope_reason(target) == "candidate_content_not_covered_by_source"
    )


def test_refuse_une_cible_qui_reordonne_les_tokens_de_la_preuve_source() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "y x",
        "regions": [
            {
                "candidate_tokens": ["y", "x"],
                "source_tokens": ["x", "y"],
                "source_canonical_tokens": ["x", "y"],
            }
        ],
    }

    assert (
        candidate_scope_reason(target) == "candidate_content_not_covered_by_source"
    )


def test_accepte_l_ordre_pdf_meme_si_la_structure_canonique_le_reordonne() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "} N i = 1",
        "regions": [
            {
                "candidate_tokens": ["}", "N", "i", "=", "1"],
                "source_tokens": ["}", "N", "i", "=", "1"],
                "source_canonical_tokens": ["}", "i", "=", "1", "N"],
            }
        ],
    }

    assert candidate_scope_reason(target) is None


def test_accepte_l_ordre_canonique_quand_le_flux_pdf_est_reordonne() -> None:
    target = {
        "kind": "replacement",
        "candidate_format": "mixed_text",
        "candidate_text": "x i prime",
        "regions": [
            {
                "candidate_tokens": ["x", "i", "′"],
                "source_tokens": ["x", "′", "i"],
                "source_canonical_tokens": ["x", "i", "′"],
            }
        ],
    }

    assert candidate_scope_reason(target) is None


def test_refuse_un_mot_serialise_comme_une_suite_de_variables() -> None:
    target = {
        "target_id": "unsafe-word",
        "kind": "replacement",
        "candidate_format": "mixed_text",
    }

    with pytest.raises(ValueError, match="mathematical_text_grouping_unproven"):
        apply_target(target, ["d e n s i t y"])


def test_normalise_arg_vers_une_commande_rendue() -> None:
    target = {
        "target_id": "arg-max",
        "kind": "replacement",
        "candidate_format": "latex",
    }

    after, mathml = apply_target(target, [r"\arg \max_{x}"])

    assert after == r"\operatorname{arg} \max_{x}"
    assert "<mo>arg</mo>" in mathml
    assert r"<mi>\arg</mi>" not in mathml


def test_exige_la_vision_independante_pour_une_formule_complete() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    node = document.texts[16]
    tokens, token_reason = candidate_tokens(node.text, "latex")
    signature, signature_reason = candidate_signature(node.text)
    assert token_reason is None
    assert signature_reason is None
    region = _region() | {
        "region_id": "formula:complete",
        "docling_ref": node.self_ref,
        "candidate_charspan": [0, len(node.text)],
        "candidate_text": node.text,
        "candidate_format": "latex",
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "glyph_sequence_indices": [10],
        "source_canonical_tokens": tokens,
        "source_relation_signature": signature,
    }
    calls = 0

    def vision(**_arguments: object) -> Proposal:
        nonlocal calls
        calls += 1
        return Proposal(node.text, {}, {})

    result = correct_document(
        PDF, document, [region], _config(), proposal_client=vision
    )

    records = json.loads(result.records)["records"]
    assert calls == 1, records
    assert result.summary["accepted"] == 1
    assert result.summary["engine"]["vision_calls"] == 1
    record = records[0]
    assert record["kind"] == "formula_replacement"
    assert record["proposals"][0]["selected_engine"] == (
        "vision_proven_by_source"
    )
    assert record["proposals"][0]["vision_confirmation"] == "exact"
