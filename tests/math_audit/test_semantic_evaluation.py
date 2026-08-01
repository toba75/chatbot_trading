from __future__ import annotations

import pytest

from pdf_math_audit.semantic_evaluation import evaluate_regions


def _region(candidate: str, glyph_count: int) -> dict[str, object]:
    return {
        "region_id": "#/texts/0:formula:0",
        "kind": "formula",
        "page": 1,
        "status": "traced",
        "candidate_text": candidate,
        "candidate_format": "latex",
        "glyph_sequence_indices": list(range(glyph_count)),
    }


def _glyph(
    sequence: int,
    text: str,
    *,
    to_unicode: str | None = None,
    rendered_unicode: str | None = None,
    rawdict_char: int | None = None,
    origin_y: float = 10.0,
    size: float = 10.0,
) -> dict[str, object]:
    return {
        "page": 1,
        "sequence_index": sequence,
        "glyph_name": "minus" if text == "−" else text,
        "unicode": text,
        "font_resource": "/F1",
        "code": ord(text),
        "code_hex": f"{ord(text):02X}",
        "cff_gid": sequence + 1,
        "rendered_gid": sequence + 1,
        "to_unicode": text if to_unicode is None else to_unicode,
        "rendered_unicode": text if rendered_unicode is None else rendered_unicode,
        "rendered_origin_y": origin_y,
        "rendered_size": size,
        "rawdict": {
            "block": 0,
            "line": 0,
            "span": 0,
            "char": sequence if rawdict_char is None else rawdict_char,
        },
    }


def _glyphs(text: str) -> list[dict[str, object]]:
    return [_glyph(index, character) for index, character in enumerate(text)]


@pytest.mark.parametrize(
    ("candidate", "expected_status"),
    [
        ("w x - b = 0", "matching"),
        ("", "missing"),
        ("w - b = 0", "missing"),
        (r"w x \neq b = 0", "contradicting"),
        (r"w x - b = 0 \quad w x \neq b = 0", "contradicting"),
    ],
)
def test_compare_la_sequence_complete_sans_accepter_une_sous_chaine(
    candidate: str, expected_status: str
) -> None:
    source = "wx−b=0"

    regions, metrics = evaluate_regions(
        [_region(candidate, len(source))], _glyphs(source)
    )

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == expected_status
    assert result["verdict"] == (
        "conformant_within_scope" if expected_status == "matching" else "contradicted"
    )
    assert metrics["overall"]["candidate_statuses"][expected_status] == 1


def test_conserve_le_conflit_tounicode_sans_remplacer_le_glyphe_rendu() -> None:
    glyphs = _glyphs("wx−b")
    glyphs[2] = _glyph(2, "−", to_unicode="≠", rendered_unicode="≠")

    regions, _metrics = evaluate_regions([_region("w x - b", 4)], glyphs)

    result = regions[0]
    assert result["semantic_status"] == "conflicting"
    assert result["candidate_status"] == "not_evaluated"
    assert result["verdict"] == "non_verifiable"
    assert result["source_signal_conflicts"] == [2]
    assert result["semantic_resolution_rules"] == []
    assert result["semantic_reasons"] == [
        {
            "code": "source_signal_conflict",
            "message": "Les signaux Unicode source se contredisent",
        }
    ]
    assert result["semantic_evidence"][2] == {
        "page": 1,
        "sequence_index": 2,
        "font_resource": "/F1",
        "code": 8722,
        "code_hex": "2212",
        "cff_gid": 3,
        "rendered_gid": 3,
        "glyph_name": "minus",
        "agl_unicode": "−",
        "to_unicode": "≠",
        "rendered_unicode": "≠",
        "rendered_origin_y": 10.0,
        "rendered_size": 10.0,
    }


def test_tounicode_absent_reste_observable_et_l_ordre_divergent_bloque() -> None:
    missing_signal = _glyphs("xy")
    missing_signal[1]["to_unicode"] = None
    reversed_order = _glyphs("xy")
    reversed_order[0]["rawdict"]["char"] = 1
    reversed_order[1]["rawdict"]["char"] = 0

    missing_regions, _ = evaluate_regions([_region("xy", 2)], missing_signal)
    unordered_regions, _ = evaluate_regions([_region("xy", 2)], reversed_order)

    assert missing_regions[0]["semantic_status"] == "established"
    assert missing_regions[0]["candidate_status"] == "matching"
    assert missing_regions[0]["source_signal_missing"] == [1]
    assert unordered_regions[0]["semantic_status"] == "ambiguous"
    assert unordered_regions[0]["semantic_reasons"][0]["code"] == (
        "glyph_order_ambiguous"
    )


def test_aplatit_une_relation_uniquement_pour_la_sequence() -> None:
    regions, _metrics = evaluate_regions([_region(r"w ^ { * }", 2)], _glyphs("w∗"))

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == "matching"
    assert result["verdict"] == "conformant_within_scope"


def test_compare_la_sequence_meme_si_la_geometrie_source_differe() -> None:
    glyphs = [_glyph(0, "x"), _glyph(1, "y", origin_y=7.0, size=7.0)]

    regions, _metrics = evaluate_regions([_region("x y", 2)], glyphs)

    assert regions[0]["semantic_status"] == "established"
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_n_exige_pas_que_la_region_couvre_la_prose_de_sa_ligne() -> None:
    regions, _metrics = evaluate_regions([_region("x", 1)], _glyphs("x=1"))

    assert regions[0]["semantic_status"] == "established"
    assert regions[0]["candidate_status"] == "matching"


def test_ignore_les_espaces_des_deux_cotes_de_la_comparaison() -> None:
    regions, _metrics = evaluate_regions([_region("xy", 3)], _glyphs("x y"))

    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_normalise_la_sequence_source_complete_en_nfc() -> None:
    regions, _metrics = evaluate_regions(
        [_region("é", 2)], _glyphs("e\N{COMBINING ACUTE ACCENT}")
    )

    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_aplatit_un_fragment_textuel_mathml_dans_la_sequence() -> None:
    regions, _metrics = evaluate_regions([_region(r"\text {x+y}", 3)], _glyphs("x+y"))

    assert regions[0]["semantic_status"] == "established"
    assert regions[0]["candidate_status"] == "matching"


@pytest.mark.parametrize(
    ("candidate", "source"),
    [
        ("x$_{i}$", "xi"),
        ("{ spam, not_spam }", "{spam,not_spam}"),
    ],
)
def test_preserve_les_litteraux_du_texte_mixte_docling(
    candidate: str, source: str
) -> None:
    region = _region(candidate, len(source))
    region["candidate_format"] = "mixed_text"

    regions, _metrics = evaluate_regions([region], _glyphs(source))

    assert regions[0]["candidate_status"] == "matching"


def test_refuse_semantiquement_une_region_structurellement_ambigue() -> None:
    region = _region("x", 1)
    region["status"] = "ambiguous"

    regions, metrics = evaluate_regions([region], _glyphs("x"))

    assert regions[0]["semantic_status"] == "ambiguous"
    assert regions[0]["candidate_status"] == "not_evaluated"
    assert regions[0]["verdict"] == "non_verifiable"
    assert metrics["pages"][0]["page"] == 1
    assert metrics["pages"][0]["verdicts"] == {
        "conformant_within_scope": 0,
        "contradicted": 0,
        "non_verifiable": 1,
    }
