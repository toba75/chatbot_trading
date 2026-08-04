from __future__ import annotations

import pytest

from pdf_math_audit.semantic_evaluation import evaluate_regions


def _region(
    candidate: str,
    glyph_count: int,
    *,
    structural_rules: dict[str, dict[str, float | int]] | None = None,
) -> dict[str, object]:
    region = {
        "region_id": "#/texts/0:formula:0",
        "kind": "formula",
        "page": 1,
        "status": "traced",
        "candidate_text": candidate,
        "candidate_format": "latex",
        "glyph_sequence_indices": list(range(glyph_count)),
    }
    if structural_rules:
        region["structural_rules"] = structural_rules
    return region


def _glyph(
    sequence: int,
    text: str,
    *,
    to_unicode: str | None = None,
    rendered_unicode: str | None = None,
    rawdict_char: int | None = None,
    origin_y: float = 10.0,
    origin_x: float | None = None,
    size: float = 10.0,
    rendered_font: str = "Regular",
    span_flags: int = 0,
) -> dict[str, object]:
    x = float(sequence) if origin_x is None else origin_x
    return {
        "page": 1,
        "sequence_index": sequence,
        "glyph_name": "minus" if text == "−" else text,
        "unicode": text,
        "source_unicode": text,
        "source_unicode_method": "agl",
        "agl_unicode": text,
        "font_resource": "/F1",
        "code": ord(text),
        "code_hex": f"{ord(text):02X}",
        "cff_gid": sequence + 1,
        "rendered_gid": sequence + 1,
        "to_unicode": text if to_unicode is None else to_unicode,
        "rendered_unicode": text if rendered_unicode is None else rendered_unicode,
        "rendered_font": rendered_font,
        "rendered_origin_x": x,
        "rendered_origin_y": origin_y,
        "rendered_size": size,
        "bbox": [x, origin_y - size, x + max(3.0, size * 0.4), origin_y],
        "rawdict": {
            "block": 0,
            "line": 0,
            "span": 0,
            "char": sequence if rawdict_char is None else rawdict_char,
            "span_flags": span_flags,
        },
    }


def _glyphs(text: str) -> list[dict[str, object]]:
    return [_glyph(index, character) for index, character in enumerate(text)]


@pytest.mark.parametrize(
    ("candidate", "expected_status"),
    [
        ("w x - b = 0", "matching"),
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


def test_ne_transforme_pas_une_absence_de_candidat_en_contradiction() -> None:
    source = "wx−b=0"

    regions, metrics = evaluate_regions([_region("", len(source))], _glyphs(source))

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_tokens"] == []
    assert result["candidate_status"] == "not_evaluated"
    assert result["verdict"] == "non_verifiable"
    assert result["semantic_reasons"] == [
        {
            "code": "candidate_content_missing",
            "message": "Aucun contenu candidat n’est disponible pour la comparaison",
        }
    ]
    assert metrics["overall"]["verdicts"]["non_verifiable"] == 1


@pytest.mark.parametrize(
    ("reason_code", "expected_stage"),
    [
        ("docling_picture_candidate_missing", "candidate_acquisition"),
        ("docling_text_container_missing", "candidate_acquisition"),
        ("docling_text_alignment_incomplete", "text_alignment"),
    ],
)
def test_localise_l_etape_qui_a_empeche_l_acquisition_du_candidat(
    reason_code: str, expected_stage: str
) -> None:
    region = _region("", 1)
    region["candidate_link_reason"] = {"code": reason_code, "message": "cause"}

    regions, _ = evaluate_regions([region], _glyphs("x"))

    assert regions[0]["candidate_failure_stage"] == expected_stage


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
        "source_unicode": "−",
        "source_unicode_method": "agl",
        "agl_unicode": "−",
        "to_unicode": "≠",
        "rendered_unicode": "≠",
        "rendered_font": "Regular",
        "rendered_origin_x": 2.0,
        "rendered_origin_y": 10.0,
        "rendered_size": 10.0,
    }


def test_conserve_la_provenance_tounicode_sans_la_declarer_agl() -> None:
    glyph = _glyph(0, "x")
    glyph["source_unicode_method"] = "to_unicode"
    glyph["agl_unicode"] = None

    regions, _metrics = evaluate_regions([_region("x", 1)], [glyph])

    evidence = regions[0]["semantic_evidence"][0]
    assert evidence["source_unicode"] == "x"
    assert evidence["source_unicode_method"] == "to_unicode"
    assert evidence["agl_unicode"] is None


def test_resout_un_conflit_unicode_par_un_nom_cff_tex_explicitement_supporte() -> None:
    glyph = _glyph(
        0,
        "‖",
        to_unicode="Î",
        rendered_unicode="Î",
        rendered_font="LMMathSymbols10-Regular",
    )
    glyph["glyph_name"] = "bardbl"

    regions, _metrics = evaluate_regions([_region("‖", 1)], [glyph])

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == "matching"
    assert result["source_signal_conflicts"] == []
    assert result["semantic_resolution_rules"] == [
        {
            "code": "cff_tex_glyph_name_authoritative",
            "message": "Le nom du glyphe CFF TeX résout les signaux Unicode divergents",
        }
    ]


def test_resout_le_symbole_d_appartenance_errone_de_lm_math_symbols() -> None:
    glyph = _glyph(
        0,
        "∈",
        to_unicode="œ",
        rendered_unicode="œ",
        rendered_font="LMMathSymbols7-Regular",
    )
    glyph["glyph_name"] = "element"

    regions, _metrics = evaluate_regions([_region(r"\in", 1)], [glyph])

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == "matching"
    assert result["source_signal_conflicts"] == []


@pytest.mark.parametrize(
    ("glyph_name", "unicode", "rendered_font"),
    [
        ("Sigma", "Σ", "LMRoman7-Bold"),
        ("Sigma", "Σ", "LMRoman10-Bold"),
        ("alpha", "α", "LMMathItalic7-Regular"),
        ("alpha", "α", "LMMathItalic10-Regular"),
        ("angle", "∠", "MSAM10"),
        ("arrowleft", "←", "LMMathSymbols10-Regular"),
        ("arrowright", "→", "LMMathSymbols10-Regular"),
        ("asteriskmath", "∗", "LMMathSymbols5-Regular"),
        ("asteriskmath", "∗", "LMMathSymbols7-Regular"),
        ("asteriskmath", "∗", "LMMathSymbols10-Regular"),
        ("element", "∈", "LMMathSymbols8-Regular"),
        ("gamma", "γ", "LMMathItalic10-Regular"),
        ("greaterequal", "≥", "LMMathSymbols10-Regular"),
        ("intersection", "∩", "LMMathSymbols10-Regular"),
        ("lambda", "λ", "LMMathItalic10-Regular"),
        ("lessequal", "≤", "LMMathSymbols10-Regular"),
        ("minus", "−", "LMMathSymbols5-Regular"),
        ("minus", "−", "LMMathSymbols8-Regular"),
        ("multiply", "×", "LMMathSymbols10-Regular"),
        ("nabla", "∇", "LMMathSymbols10-Regular"),
        ("partialdiff", "∂", "LMMathItalic7-Regular"),
        ("partialdiff", "∂", "LMMathItalic10-Regular"),
        ("phi", "φ", "LMMathItalic10-Regular"),
        ("pi", "π", "LMMathItalic10-Regular"),
        ("radical", "√", "LMMathSymbols10-Regular"),
        ("rho", "ρ", "LMMathItalic7-Regular"),
        ("rho", "ρ", "LMMathItalic10-Regular"),
        ("sigma", "σ", "LMMathItalic5-Regular"),
        ("sigma", "σ", "LMMathItalic10-Regular"),
        ("sigma", "σ", "LMMathItalic10-Bold"),
        ("similar", "∼", "LMMathSymbols10-Regular"),
        ("tau", "τ", "LMMathItalic10-Regular"),
        ("theta", "θ", "LMMathItalic7-Regular"),
        ("theta", "θ", "LMMathItalic10-Regular"),
        ("union", "∪", "LMMathSymbols10-Regular"),
    ],
)
def test_resout_les_couples_glyphe_police_observes_dans_le_pdf_reel(
    glyph_name: str, unicode: str, rendered_font: str
) -> None:
    glyph = _glyph(
        0,
        unicode,
        to_unicode="?",
        rendered_unicode="?",
        rendered_font=rendered_font,
    )
    glyph["glyph_name"] = glyph_name

    regions, _metrics = evaluate_regions([_region("", 1)], [glyph])

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["source_signal_conflicts"] == []
    assert result["semantic_resolution_rules"] == [
        {
            "code": "cff_tex_glyph_name_authoritative",
            "message": "Le nom du glyphe CFF TeX résout les signaux Unicode divergents",
        }
    ]


@pytest.mark.parametrize(
    "glyph_name",
    ["bracketleftbt", "bracketlefttp", "bracketrightbt", "bracketrighttp"],
)
def test_identifie_un_fragment_de_delimiteur_extensible_sans_l_aplatir(
    glyph_name: str,
) -> None:
    glyph = _glyph(
        0,
        "\uf8ee",
        to_unicode="[",
        rendered_unicode="[",
        rendered_font="LMMathExtension10-Regula",
    )
    glyph["glyph_name"] = glyph_name

    regions, _ = evaluate_regions([_region("", 1)], [glyph])

    assert regions[0]["semantic_status"] == "not_established"
    assert regions[0]["source_signal_conflicts"] == []
    assert regions[0]["semantic_reasons"][0]["code"] == (
        "source_extensible_delimiter_fragment"
    )


@pytest.mark.parametrize(
    "rendered_font", ["LMMathSymbols7-Regular", "LMMathSymbols10-Regular"]
)
def test_resout_le_minus_errone_de_lm_math_symbols(rendered_font: str) -> None:
    glyphs = _glyphs("wx−b")
    glyphs[2] = _glyph(
        2,
        "−",
        to_unicode="≠",
        rendered_unicode="≠",
        rendered_font=rendered_font,
    )

    regions, _metrics = evaluate_regions([_region("w x - b", 4)], glyphs)

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == "matching"
    assert result["source_signal_conflicts"] == []
    assert result["semantic_resolution_rules"] == [
        {
            "code": "cff_tex_glyph_name_authoritative",
            "message": "Le nom du glyphe CFF TeX résout les signaux Unicode divergents",
        }
    ]


@pytest.mark.parametrize(
    "rendered_font", ["Regular", "LMMathSymbolsEvil", "LMMathSymbols10-Evil"]
)
def test_ne_fait_pas_autorite_d_un_nom_tex_hors_d_une_police_tex(
    rendered_font: str,
) -> None:
    glyph = _glyph(
        0,
        "‖",
        to_unicode="Î",
        rendered_unicode="Î",
        rendered_font=rendered_font,
    )
    glyph["glyph_name"] = "bardbl"

    regions, _metrics = evaluate_regions([_region("‖", 1)], [glyph])

    assert regions[0]["semantic_status"] == "conflicting"
    assert regions[0]["candidate_status"] == "not_evaluated"


@pytest.mark.parametrize("summation_glyph", ["summationdisplay", "summationtext"])
def test_prouve_une_racine_et_une_somme_avec_bornes_superposees(
    summation_glyph: str,
) -> None:
    glyphs = [
        _glyph(0, "√", origin_x=370.2, origin_y=401.2, size=10),
        _glyph(1, "∑", origin_x=380.1, origin_y=405.4, size=10),
        _glyph(2, "D", origin_x=390.7, origin_y=407.9, size=7),
        _glyph(3, "j", origin_x=390.7, origin_y=415.9, size=7),
        _glyph(4, "=", origin_x=394.4, origin_y=415.9, size=7),
        _glyph(5, "1", origin_x=400.5, origin_y=415.9, size=7),
        _glyph(6, "(", origin_x=404.9, origin_y=412.9, size=10),
        _glyph(7, "w", origin_x=408.8, origin_y=412.9, size=10),
        _glyph(8, "(", origin_x=416.2, origin_y=410.0, size=7),
        _glyph(9, "j", origin_x=419.3, origin_y=410.0, size=7),
        _glyph(10, ")", origin_x=423.0, origin_y=410.0, size=7),
        _glyph(11, ")", origin_x=426.6, origin_y=412.9, size=10),
        _glyph(12, "2", origin_x=430.5, origin_y=410.0, size=7),
    ]
    glyphs[0]["glyph_name"] = "radicalBig"
    glyphs[1]["glyph_name"] = summation_glyph
    glyphs[0]["rendered_font"] = "LMMathExtension10-Regular"
    glyphs[1]["rendered_font"] = "LMMathExtension10-Regular"

    regions, _metrics = evaluate_regions(
        [
            _region(
                r"\sqrt{\sum_{j=1}^{D}(w^{(j)})^2}",
                len(glyphs),
                structural_rules={
                    "radical": {
                        "x0": 380.1,
                        "y": 401.0,
                        "x1": 435.0,
                        "width": 0.4,
                        "seqno": 94,
                    }
                },
            )
        ],
        glyphs,
    )

    result = regions[0]
    assert result["source_relation_reason"] is None
    assert result["source_canonical_tokens"] == list("√∑j=1D(w(j))2")
    assert result["candidate_status"] == "matching"
    assert result["verdict"] == "conformant_within_scope"


def test_limite_la_portee_de_la_racine_a_sa_barre() -> None:
    glyphs = [
        _glyph(0, "√", origin_x=0, origin_y=10),
        _glyph(1, "∑", origin_x=5, origin_y=14),
        _glyph(2, "D", origin_x=10, origin_y=17, size=7),
        _glyph(3, "j", origin_x=10, origin_y=23, size=7),
        _glyph(4, "=", origin_x=13, origin_y=23, size=7),
        _glyph(5, "1", origin_x=16, origin_y=23, size=7),
        _glyph(6, "x", origin_x=20, origin_y=20),
        _glyph(7, "+", origin_x=32, origin_y=20),
        _glyph(8, "z", origin_x=36, origin_y=20),
    ]
    glyphs[0]["glyph_name"] = "radicalBig"
    glyphs[1]["glyph_name"] = "summationtext"
    rules = {"radical": {"x0": 4.0, "y": 9.8, "x1": 28.0, "width": 0.4, "seqno": 1}}

    correct, _ = evaluate_regions(
        [_region(r"\sqrt{\sum_{j=1}^{D}x}+z", len(glyphs), structural_rules=rules)],
        glyphs,
    )
    incorrect, _ = evaluate_regions(
        [_region(r"\sqrt{\sum_{j=1}^{D}x+z}", len(glyphs), structural_rules=rules)],
        glyphs,
    )

    assert correct[0]["candidate_status"] == "matching"
    assert incorrect[0]["candidate_status"] == "contradicting"


def test_refuse_une_barre_qui_traverse_le_radicand() -> None:
    glyphs = [
        _glyph(0, "√", origin_x=0, origin_y=10),
        _glyph(1, "∑", origin_x=5, origin_y=14),
        _glyph(2, "D", origin_x=10, origin_y=17, size=7),
        _glyph(3, "j", origin_x=10, origin_y=23, size=7),
        _glyph(4, "=", origin_x=13, origin_y=23, size=7),
        _glyph(5, "1", origin_x=16, origin_y=23, size=7),
        _glyph(6, "x", origin_x=20, origin_y=20),
    ]
    glyphs[0]["glyph_name"] = "radicalBig"
    glyphs[1]["glyph_name"] = "summationtext"
    rules = {"radical": {"x0": 4.0, "y": 15.0, "x1": 28.0, "width": 0.4, "seqno": 1}}

    regions, _ = evaluate_regions(
        [_region(r"\sqrt{\sum_{j=1}^{D}x}", len(glyphs), structural_rules=rules)],
        glyphs,
    )

    assert (
        regions[0]["source_relation_reason"] == "source_radical_rule_position_invalid"
    )
    assert regions[0]["verdict"] == "non_verifiable"


def test_prouve_une_fraction_par_sa_barre() -> None:
    glyphs = [
        _glyph(0, "2", origin_x=5, origin_y=5, size=7),
        _glyph(1, "‖", origin_x=0, origin_y=15, size=7),
        _glyph(
            2,
            "w",
            origin_x=4,
            origin_y=15,
            size=7,
            rendered_font="LMRoman7-Bold",
            span_flags=16,
        ),
        _glyph(3, "‖", origin_x=9, origin_y=15, size=7),
    ]
    for glyph in (glyphs[1], glyphs[3]):
        glyph["glyph_name"] = "bardbl"
        glyph["rendered_font"] = "LMMathSymbols7-Regular"
    rule = {"fraction": {"x0": 0.0, "y": 7.0, "x1": 13.0, "width": 0.4, "seqno": 2}}

    regions, _ = evaluate_regions(
        [_region(r"\frac{2}{\|\mathbf{w}\|}", 4, structural_rules=rule)],
        glyphs,
    )

    assert regions[0]["source_canonical_tokens"] == list("2‖w‖")
    assert regions[0]["candidate_status"] == "matching"


def test_canonicalise_indices_et_exposants_selon_leur_position_rendue() -> None:
    glyphs = [
        _glyph(0, "{", origin_x=0),
        _glyph(1, "x", origin_x=1),
        _glyph(2, "i", origin_x=2, origin_y=11.5, size=7),
        _glyph(3, "}", origin_x=3),
        _glyph(4, "N", origin_x=4, origin_y=6.5, size=7),
        _glyph(5, "i", origin_x=4, origin_y=12.5, size=7),
        _glyph(6, "=", origin_x=5, origin_y=12.5, size=7),
        _glyph(7, "1", origin_x=6, origin_y=12.5, size=7),
    ]

    regions, _ = evaluate_regions([_region(r"\{x_i\}_{i=1}^{N}", 8)], glyphs)

    assert regions[0]["source_canonical_tokens"] == list("{xi}i=1N")
    assert regions[0]["source_relation_signature"] == [
        "{",
        "x",
        "<sub>",
        "i",
        "</sub>",
        "}",
        "<sub>",
        "i",
        "=",
        "1",
        "</sub>",
        "<sup>",
        "N",
        "</sup>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert [relation["role"] for relation in regions[0]["source_relations"]] == [
        "subscript",
        "superscript",
        "subscript",
        "subscript",
        "subscript",
    ]
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_prouve_une_fraction_inseree_suivie_d_une_somme_avec_borne() -> None:
    glyphs = [
        _glyph(0, "a", origin_x=0, origin_y=20),
        _glyph(1, "=", origin_x=5, origin_y=20),
        _glyph(2, "1", origin_x=20, origin_y=10, size=7),
        _glyph(3, "2", origin_x=20, origin_y=20, size=7),
        _glyph(4, "∑", origin_x=30, origin_y=20, size=14),
        _glyph(5, "i", origin_x=28, origin_y=30, size=7),
        _glyph(6, "=", origin_x=31, origin_y=30, size=7),
        _glyph(7, "1", origin_x=34, origin_y=30, size=7),
        _glyph(8, "y", origin_x=40, origin_y=20),
    ]
    glyphs[4]["glyph_name"] = "summationdisplay"
    rule = {"fraction": {"x0": 20.0, "y": 11.5, "x1": 23.0, "width": 0.4, "seqno": 2}}

    regions, _ = evaluate_regions(
        [_region(r"a=\frac{1}{2}\sum_{i=1}y", len(glyphs), structural_rules=rule)],
        glyphs,
    )

    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_separe_la_ligne_de_base_autour_d_un_operateur_empile() -> None:
    glyphs = [
        _glyph(0, "E", origin_x=0, origin_y=20),
        _glyph(1, "=", origin_x=5, origin_y=20),
        _glyph(2, "∑", origin_x=20, origin_y=20, size=14),
        _glyph(3, "i", origin_x=18, origin_y=30, size=7),
        _glyph(4, "=", origin_x=21, origin_y=30, size=7),
        _glyph(5, "1", origin_x=24, origin_y=30, size=7),
        _glyph(6, "n", origin_x=22, origin_y=5, size=7),
        _glyph(7, "x", origin_x=30, origin_y=20),
    ]
    glyphs[2]["glyph_name"] = "summationdisplay"

    regions, _ = evaluate_regions(
        [_region(r"E=\sum_{i=1}^{n}x", len(glyphs))],
        glyphs,
    )

    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_reconnait_des_bornes_inline_decalees_a_droite_de_la_somme() -> None:
    glyphs = [
        _glyph(0, "f", origin_x=0, origin_y=20),
        _glyph(1, "=", origin_x=5, origin_y=20),
        _glyph(2, "∑", origin_x=10, origin_y=13, size=10),
        _glyph(3, "n", origin_x=20, origin_y=15, size=7),
        _glyph(4, "i", origin_x=20, origin_y=23, size=7),
        _glyph(5, "=", origin_x=23, origin_y=23, size=7),
        _glyph(6, "1", origin_x=26, origin_y=23, size=7),
        _glyph(7, "x", origin_x=32, origin_y=20),
    ]
    glyphs[2]["glyph_name"] = "summationtext"

    regions, _ = evaluate_regions(
        [_region(r"f=\sum_{i=1}^{n}x", len(glyphs))],
        glyphs,
    )

    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_ne_confond_pas_l_exposant_du_premier_operande_avec_une_borne() -> None:
    glyphs = [
        _glyph(0, "∑", origin_x=0, origin_y=20, size=10),
        _glyph(1, "x", origin_x=12, origin_y=20, size=10),
        _glyph(2, "2", origin_x=18, origin_y=15, size=7),
    ]
    glyphs[0]["glyph_name"] = "summationtext"

    correct, _ = evaluate_regions([_region(r"\sum x^2", 3)], glyphs)
    incorrect, _ = evaluate_regions([_region(r"\sum^2 x", 3)], glyphs)

    assert correct[0]["candidate_status"] == "matching"
    assert correct[0]["verdict"] == "conformant_within_scope"
    assert incorrect[0]["candidate_status"] == "contradicting"


def test_refuse_la_formule_inline_docling_structurellement_incorrecte() -> None:
    glyphs = [
        _glyph(0, "{", origin_x=0),
        _glyph(1, "x", origin_x=1, rendered_font="LMRoman10-Bold", span_flags=16),
        _glyph(2, "i", origin_x=2, origin_y=11.5, size=7),
        _glyph(3, "}", origin_x=3),
        _glyph(4, "N", origin_x=4, origin_y=6.5, size=7),
        _glyph(5, "i", origin_x=4, origin_y=12.5, size=7),
        _glyph(6, "=", origin_x=5, origin_y=12.5, size=7),
        _glyph(7, "1", origin_x=6, origin_y=12.5, size=7),
    ]
    region = _region("{ x$_{i}$ } N i = $_{1}$", 8)
    region["candidate_format"] = "mixed_text"

    regions, _metrics = evaluate_regions([region], glyphs)

    result = regions[0]
    assert result["source_relation_signature"] != result["candidate_relation_signature"]
    assert result["candidate_status"] == "contradicting"
    assert result["verdict"] == "contradicted"


def test_conserve_dans_la_preuve_canonique_un_glyphe_rendu_en_gras() -> None:
    glyphs = [_glyph(0, "x", rendered_font="LMRoman10-Bold", span_flags=16)]

    regions, _ = evaluate_regions([_region(r"\mathbf{x}", 1)], glyphs)

    assert regions[0]["source_canonical_tokens"] == ["x"]
    assert regions[0]["source_relation_signature"] == ["<bold>", "x", "</bold>"]
    assert regions[0]["candidate_status"] == "matching"


def test_refuse_un_candidat_gras_face_a_une_source_non_grasse() -> None:
    regions, _ = evaluate_regions([_region(r"\mathbf{x}", 1)], [_glyph(0, "x")])

    assert regions[0]["candidate_status"] == "contradicting"
    assert regions[0]["verdict"] == "contradicted"


def test_classe_une_structure_mathml_non_supportee_comme_structure() -> None:
    regions, _ = evaluate_regions(
        [_region(r"\begin{matrix}x\end{matrix}", 1)],
        [_glyph(0, "x")],
    )

    assert regions[0]["candidate_failure_stage"] == "math_structure"


def test_prouve_le_gras_par_le_flag_rendu_independamment_du_nom_de_police() -> None:
    glyphs = [_glyph(0, "x", rendered_font="CMBX10", span_flags=16)]

    regions, _ = evaluate_regions([_region(r"\mathbf{x}", 1)], glyphs)

    assert regions[0]["source_canonical_tokens"] == ["x"]
    assert regions[0]["source_relation_signature"] == ["<bold>", "x", "</bold>"]
    assert regions[0]["candidate_status"] == "matching"


def test_canonicalise_un_indice_imbrique_prouve_par_deux_corps() -> None:
    glyphs = [
        _glyph(0, "x", origin_x=0, origin_y=10, size=10),
        _glyph(1, "i", origin_x=1, origin_y=12, size=7),
        _glyph(2, "j", origin_x=2, origin_y=14, size=5),
    ]

    regions, _ = evaluate_regions([_region(r"x_{ij}", 3)], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "x",
        "<sub>",
        "i",
        "<sub>",
        "j",
        "</sub>",
        "</sub>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["candidate_status"] == "contradicting"
    assert regions[0]["verdict"] == "contradicted"


def test_canonicalise_des_indices_dans_deux_exposants_inline() -> None:
    glyphs = [
        _glyph(0, "f", origin_x=0, origin_y=10, size=10),
        _glyph(1, "w", origin_x=1, origin_y=11.5, size=7),
        _glyph(2, ",", origin_x=2, origin_y=11.5, size=7),
        _glyph(3, "b", origin_x=3, origin_y=11.5, size=7),
        _glyph(4, "(", origin_x=4, origin_y=10, size=10),
        _glyph(5, "x", origin_x=5, origin_y=10, size=10),
        _glyph(6, ")", origin_x=6, origin_y=10, size=10),
        _glyph(7, "y", origin_x=7, origin_y=6.5, size=7),
        _glyph(8, "i", origin_x=8, origin_y=7.5, size=5),
        _glyph(9, "(", origin_x=9, origin_y=10, size=10),
        _glyph(10, "1", origin_x=10, origin_y=10, size=10),
        _glyph(11, "−", origin_x=11, origin_y=10, size=10),
        _glyph(12, "f", origin_x=12, origin_y=10, size=10),
        _glyph(13, "w", origin_x=13, origin_y=11.5, size=7),
        _glyph(14, ",", origin_x=14, origin_y=11.5, size=7),
        _glyph(15, "b", origin_x=15, origin_y=11.5, size=7),
        _glyph(16, "(", origin_x=16, origin_y=10, size=10),
        _glyph(17, "x", origin_x=17, origin_y=10, size=10),
        _glyph(18, ")", origin_x=18, origin_y=10, size=10),
        _glyph(19, ")", origin_x=19, origin_y=10, size=10),
        _glyph(20, "(", origin_x=20, origin_y=6.5, size=7),
        _glyph(21, "1", origin_x=21, origin_y=6.5, size=7),
        _glyph(22, "−", origin_x=22, origin_y=6.5, size=7),
        _glyph(23, "y", origin_x=23, origin_y=6.5, size=7),
        _glyph(24, "i", origin_x=24, origin_y=7.5, size=5),
        _glyph(25, ")", origin_x=25, origin_y=6.5, size=7),
    ]
    region = _region(r"f_{w,b}(x)^{y_i}(1-f_{w,b}(x))^{(1-y_i)}", len(glyphs))

    regions, _ = evaluate_regions([region], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "f",
        "<sub>",
        "w",
        ",",
        "b",
        "</sub>",
        "(",
        "x",
        ")",
        "<sup>",
        "y",
        "<sub>",
        "i",
        "</sub>",
        "</sup>",
        "(",
        "1",
        "−",
        "f",
        "<sub>",
        "w",
        ",",
        "b",
        "</sub>",
        "(",
        "x",
        ")",
        ")",
        "<sup>",
        "(",
        "1",
        "−",
        "y",
        "<sub>",
        "i",
        "</sub>",
        ")",
        "</sup>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_refuse_des_fragments_latex_invalides_face_a_une_structure_prouvee() -> None:
    glyphs = [
        _glyph(0, "f", origin_x=0, origin_y=10, size=10),
        _glyph(1, "w", origin_x=1, origin_y=11.5, size=7),
        _glyph(2, ",", origin_x=2, origin_y=11.5, size=7),
        _glyph(3, "b", origin_x=3, origin_y=11.5, size=7),
    ]
    region = _region(r"f$_{w}$$_{,}$$_{b}$", len(glyphs))
    region.update(candidate_format="mixed_text", candidate_link_status="linked")

    regions, _ = evaluate_regions([region], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "f",
        "<sub>",
        "w",
        ",",
        "b",
        "</sub>",
    ]
    assert regions[0]["candidate_failure_stage"] == "latex_parsing"
    assert regions[0]["candidate_status"] == "contradicting"
    assert regions[0]["verdict"] == "contradicted"


def test_refuse_d_aplatir_un_indice_imbrique_de_meme_corps() -> None:
    glyphs = [
        _glyph(0, "x", origin_x=0, origin_y=10, size=10),
        _glyph(1, "i", origin_x=1, origin_y=12, size=7),
        _glyph(2, "j", origin_x=2, origin_y=14, size=7),
    ]

    regions, _ = evaluate_regions([_region(r"x_{ij}", 3)], glyphs)

    assert regions[0]["source_relation_reason"] == "source_baseline_ambiguous"
    assert regions[0]["verdict"] == "non_verifiable"


def test_prouve_un_indice_et_un_exposant_decales_horizontalement() -> None:
    glyphs = [
        _glyph(0, "x", origin_x=0, origin_y=10, size=10),
        _glyph(1, "i", origin_x=1, origin_y=13, size=7),
        _glyph(2, "2", origin_x=2, origin_y=8.5, size=5),
    ]

    regions, _ = evaluate_regions([_region(r"x_i^2", 3)], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "x",
        "<sub>",
        "i",
        "</sub>",
        "<sup>",
        "2",
        "</sup>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_prouve_un_indice_et_un_exposant_decales_de_meme_corps() -> None:
    glyphs = [
        _glyph(0, "x", origin_x=0, origin_y=10, size=10),
        _glyph(1, "i", origin_x=1, origin_y=13, size=7),
        _glyph(2, "2", origin_x=2, origin_y=8.5, size=7),
    ]

    regions, _ = evaluate_regions([_region(r"x_i^2", 3)], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "x",
        "<sub>",
        "i",
        "</sub>",
        "<sup>",
        "2",
        "</sup>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_prouve_une_annotation_textuelle_au_dessus_d_un_operateur() -> None:
    glyphs = [
        _glyph(0, "S", origin_x=0, origin_y=10, size=10),
        _glyph(1, "d", origin_x=8, origin_y=5, size=7),
        _glyph(2, "e", origin_x=10, origin_y=5, size=7),
        _glyph(3, "f", origin_x=12, origin_y=5, size=7),
        _glyph(4, "=", origin_x=10, origin_y=10, size=10),
    ]
    for glyph in glyphs[1:4]:
        glyph["rawdict"]["block"] = 1
        glyph["rawdict"]["char"] -= 1
        glyph["rawdict"]["line"] = 1
    glyphs[4]["rawdict"].update(block=1, line=2, char=0)

    regions, _ = evaluate_regions(
        [_region(r"S\stackrel{\text{def}}{=}", len(glyphs))], glyphs
    )

    assert regions[0]["source_relation_signature"] == [
        "S",
        "=",
        "<over>",
        "d",
        "e",
        "f",
        "</over>",
    ]
    assert regions[0]["source_relation_reason"] is None
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_refuse_une_annotation_trop_eloignee_de_l_operateur() -> None:
    glyphs = [
        _glyph(0, "=", origin_x=10, origin_y=10, size=10),
        _glyph(1, "a", origin_x=11, origin_y=-90, size=5),
    ]
    glyphs[1]["rawdict"]["line"] = 1

    regions, _metrics = evaluate_regions([_region(r"\overset{a}{=}", 2)], glyphs)

    assert regions[0]["semantic_status"] == "not_established"
    assert regions[0]["source_relation_reason"] == "source_script_position_ambiguous"
    assert regions[0]["candidate_status"] == "not_evaluated"


@pytest.mark.parametrize(("source", "candidate"), [("ℝ", "R"), ("²", "2"), ("𝑎", "a")])
def test_ne_confond_pas_les_variantes_unicode_mathematiques(
    source: str, candidate: str
) -> None:
    regions, _ = evaluate_regions([_region(candidate, 1)], [_glyph(0, source)])

    assert regions[0]["candidate_status"] == "contradicting"
    assert regions[0]["verdict"] == "contradicted"


def test_reconnait_deux_glyphes_gras_adjacents_comme_un_meme_style() -> None:
    glyphs = [
        _glyph(0, "1", origin_x=0, rendered_font="Bold", span_flags=16),
        _glyph(1, "2", origin_x=1, rendered_font="Bold", span_flags=16),
    ]

    regions, _ = evaluate_regions([_region(r"\mathbf{12}", 2)], glyphs)

    assert regions[0]["source_relation_signature"] == [
        "<bold>",
        "1",
        "2",
        "</bold>",
    ]
    assert regions[0]["candidate_status"] == "matching"


def test_reconnait_les_formes_unicode_canoniquement_equivalentes() -> None:
    regions, _ = evaluate_regions([_region("e\u0301", 1)], [_glyph(0, "é")])

    assert regions[0]["candidate_status"] == "matching"
    assert regions[0]["verdict"] == "conformant_within_scope"


def test_reconnait_une_variante_unicode_sans_serif_grasse() -> None:
    regions, _ = evaluate_regions([_region(r"\mathbf{A}", 1)], [_glyph(0, "𝗔")])

    assert regions[0]["source_relation_signature"] == ["<bold>", "A", "</bold>"]
    assert regions[0]["candidate_status"] == "matching"


def test_refuse_de_deviner_une_baseline_a_taille_egale() -> None:
    glyphs = [
        _glyph(0, "x", origin_x=0, origin_y=10, size=10),
        _glyph(1, "i", origin_x=1, origin_y=4, size=10),
    ]

    regions, _ = evaluate_regions([_region("xi", 2)], glyphs)

    assert regions[0]["source_canonical_tokens"] is None
    assert regions[0]["source_relation_signature"] is None
    assert regions[0]["source_relation_reason"] == "source_baseline_ambiguous"
    assert regions[0]["semantic_status"] == "not_established"
    assert regions[0]["candidate_status"] == "not_evaluated"
    assert regions[0]["verdict"] == "non_verifiable"


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


def test_refuse_une_relation_candidate_absente_de_la_source() -> None:
    regions, _metrics = evaluate_regions([_region(r"w ^ { * }", 2)], _glyphs("w∗"))

    result = regions[0]
    assert result["semantic_status"] == "established"
    assert result["candidate_status"] == "contradicting"
    assert result["verdict"] == "contradicted"


def test_refuse_une_relation_source_absente_du_candidat() -> None:
    glyphs = [_glyph(0, "x"), _glyph(1, "y", origin_y=7.0, size=7.0)]

    regions, _metrics = evaluate_regions([_region("x y", 2)], glyphs)

    assert regions[0]["semantic_status"] == "established"
    assert regions[0]["candidate_status"] == "contradicting"
    assert regions[0]["verdict"] == "contradicted"


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
