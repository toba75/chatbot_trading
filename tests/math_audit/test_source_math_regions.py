from __future__ import annotations

from pdf_math_audit.source_math_regions import source_math_regions


FONTS = {
    1: {
        "/Body": {"base_font": "/LMRoman10-Regular", "trace_font": "LMRoman"},
        "/VariableBold": {
            "base_font": "/LMRoman10-Bold",
            "trace_font": "LMRoman-Bold",
        },
        "/EmphasisBold": {
            "base_font": "/LMRoman10-Bold",
            "trace_font": "LMRoman-Bold",
        },
        "/VariableItalic": {
            "base_font": "/BookmanOldStyle-Italic",
            "trace_font": "BookmanOldStyle-Italic",
        },
        "/EmphasisItalic": {
            "base_font": "/BookmanOldStyle-Italic",
            "trace_font": "BookmanOldStyle-Italic",
        },
        "/Math": {
            "base_font": "/LMMathItalic10-Regular",
            "trace_font": "LMMathItalic",
        },
    }
}


def _glyph(
    sequence: int,
    text: str,
    font: str,
    span: int,
    left: float,
    *,
    line: int = 0,
    top: float = 10.0,
    size: float = 10.0,
) -> dict[str, object]:
    return {
        "page": 1,
        "sequence_index": sequence,
        "glyph_name": text,
        "unicode": text,
        "bbox": [left, top, left + 4.0, top + size],
        "font_resource": font,
        "rendered_size": size,
        "rendered_origin_y": top + size,
        "rawdict": {"block": 0, "line": line, "span": span, "char": sequence},
    }


def _texts(glyphs: list[dict[str, object]]) -> list[str]:
    return [
        region["source_glyph_text"] for region in source_math_regions(glyphs, FONTS)
    ]


def test_detecte_les_variables_grasses_courtes_et_ignore_un_mot_gras() -> None:
    glyphs = [
        _glyph(1, "w", "/VariableBold", 0, 0),
        _glyph(2, "x", "/VariableBold", 0, 4),
        _glyph(3, "prose", "/Body", 2, 14),
        _glyph(4, "feature", "/EmphasisBold", 4, 40),
        _glyph(5, "is", "/EmphasisBold", 6, 72),
    ]

    assert _texts(glyphs) == ["wx"]


def test_detecte_les_variables_italiques_courtes_et_ignore_un_mot_italique() -> None:
    glyphs = [
        _glyph(1, "σ", "/VariableItalic", 0, 0),
        _glyph(2, "j", "/VariableItalic", 1, 4, top=11, size=7),
        _glyph(3, ",", "/VariableItalic", 1, 8, top=11, size=7),
        _glyph(4, "t", "/VariableItalic", 1, 12, top=11, size=7),
        _glyph(5, "where", "/EmphasisItalic", 2, 20),
    ]

    assert _texts(glyphs) == ["σj,t"]


def test_ne_transforme_pas_un_mot_court_italique_en_variable() -> None:
    glyphs = [_glyph(1, "is", "/EmphasisItalic", 0, 0)]

    assert _texts(glyphs) == []


def test_conserve_une_expression_delimitee_avec_du_texte_mathematique() -> None:
    glyphs = [
        _glyph(1, "{", "/Math", 0, 0),
        _glyph(2, "spam,not", "/Math", 1, 4),
        _glyph(3, "_", "/Body", 2, 36),
        _glyph(4, "spam", "/Math", 3, 40),
        _glyph(5, "}", "/Math", 4, 56),
        _glyph(6, ".", "/Body", 5, 60),
    ]

    assert _texts(glyphs) == ["{spam,not_spam}"]


def test_rattache_une_base_romaine_a_son_indice_mathematique() -> None:
    glyphs = [
        _glyph(1, "Γ", "/Body", 0, 0, top=10, size=10),
        _glyph(2, "l", "/Math", 1, 4, top=15, size=7),
        _glyph(3, ",", "/Math", 1, 8, top=15, size=7),
        _glyph(4, "u", "/Math", 1, 12, top=15, size=7),
    ]

    regions = source_math_regions(glyphs, FONTS)

    assert len(regions) == 1
    assert regions[0]["source_glyph_text"] == "Γl,u"
    assert regions[0]["glyph_sequence_indices"] == [1, 2, 3, 4]


def test_ne_rattache_pas_une_lettre_de_prose_a_un_fragment_lointain() -> None:
    glyphs = [
        _glyph(1, "Γ", "/Body", 0, 0, top=10, size=10),
        _glyph(2, "l", "/Math", 1, 8.5, top=15, size=7),
        _glyph(3, ",", "/Math", 1, 12.5, top=15, size=7),
        _glyph(4, "u", "/Math", 1, 16.5, top=15, size=7),
    ]

    assert _texts(glyphs) == ["l,u"]


def test_ne_rattache_pas_un_indice_entierement_a_gauche_de_sa_base() -> None:
    glyphs = [
        _glyph(1, "A", "/Body", 0, 10, top=10, size=10),
        _glyph(2, "i", "/Math", 1, 6, top=15, size=7),
    ]

    assert _texts(glyphs) == ["i"]


def test_ne_rattache_pas_un_appel_de_note_en_exposant_a_une_base_de_prose() -> None:
    glyphs = [
        _glyph(1, "A", "/Body", 0, 0, top=10, size=10),
        _glyph(2, "1", "/Math", 1, 5, top=5, size=7),
    ]
    glyphs[0]["rendered_origin_y"] = 20
    glyphs[1]["rendered_origin_y"] = 12

    assert _texts(glyphs) == ["1"]


def test_reconnait_un_connecteur_conditionnel_sans_fusionner_la_prose() -> None:
    conditional = [
        _glyph(index, text, font, index, index * 5)
        for index, (text, font) in enumerate(
            [
                ("x", "/VariableBold"),
                ("≥", "/Math"),
                ("1", "/Body"),
                ("if", "/Body"),
                ("y", "/Math"),
                ("=1", "/Body"),
            ],
            start=1,
        )
    ]
    explanatory = [
        _glyph(index, text, font, index, index * 5, line=1, top=30)
        for index, (text, font) in enumerate(
            [
                ("x", "/VariableBold"),
                ("≥", "/Math"),
                ("1", "/Body"),
                ("because", "/Body"),
                ("y", "/Math"),
                ("=1", "/Body"),
            ],
            start=10,
        )
    ]

    assert _texts(conditional + explanatory) == ["x≥1ify=1", "x≥1", "y=1"]


def test_fusionne_un_indice_place_sur_une_ligne_pdf_distincte() -> None:
    glyphs = [
        _glyph(1, "x", "/Math", 0, 0, top=10),
        _glyph(2, "(2)", "/Body", 1, 4, top=10, size=7),
        _glyph(3, "i", "/Math", 0, 4, line=1, top=17, size=7),
    ]

    regions = source_math_regions(glyphs, FONTS)

    assert len(regions) == 1
    assert regions[0]["source_glyph_text"] == "x(2)i"
    assert regions[0]["glyph_sequence_indices"] == [1, 2, 3]


def test_fusionne_indices_et_exposants_superposes_meme_si_leurs_departs_different() -> (
    None
):
    glyphs = [
        _glyph(1, "f", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "S", "/Math", 1, 3, line=1, top=5, size=7),
        _glyph(3, "I", "/Math", 2, 2, line=2, top=14, size=7),
        _glyph(4, "D", "/Math", 2, 6, line=2, top=14, size=7),
        _glyph(5, "3", "/Math", 2, 10, line=2, top=14, size=7),
    ]

    regions = source_math_regions(glyphs, FONTS)

    assert len(regions) == 1
    assert regions[0]["glyph_sequence_indices"] == [1, 2, 3, 4, 5]


def test_fusionne_une_annotation_textuelle_avec_son_operateur() -> None:
    glyphs = [
        _glyph(1, "S", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "d", "/Body", 1, 8.5, line=1, top=5, size=7),
        _glyph(3, "e", "/Body", 1, 10, line=1, top=5, size=7),
        _glyph(4, "f", "/Body", 1, 11.5, line=1, top=5, size=7),
        _glyph(5, "=", "/Math", 2, 10, line=2, top=10, size=10),
        _glyph(6, "x", "/Math", 2, 18, line=2, top=10, size=10),
    ]

    regions = source_math_regions(glyphs, FONTS)

    assert len(regions) == 1
    assert regions[0]["glyph_sequence_indices"] == [1, 2, 3, 4, 5, 6]


def test_ne_fusionne_pas_une_annotation_lointaine_avec_un_operateur() -> None:
    glyphs = [
        _glyph(1, "d", "/Body", 0, 8.5, line=1, top=-100, size=5),
        _glyph(2, "e", "/Body", 0, 10, line=1, top=-100, size=5),
        _glyph(3, "f", "/Body", 0, 11.5, line=1, top=-100, size=5),
        _glyph(4, "=", "/Math", 1, 10, line=2, top=10, size=10),
    ]

    regions = source_math_regions(glyphs, FONTS)

    assert [region["glyph_sequence_indices"] for region in regions] == [[4]]


def test_ne_fusionne_pas_deux_expressions_de_meme_taille_sur_deux_lignes() -> None:
    glyphs = [
        _glyph(1, "x=1", "/Math", 0, 0, top=10),
        _glyph(2, "y=1", "/Math", 0, 0, line=1, top=19),
    ]

    assert _texts(glyphs) == ["x=1", "y=1"]


def test_ne_fusionne_pas_deux_expressions_indexees_sur_deux_lignes() -> None:
    glyphs = [
        _glyph(1, "x", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "i", "/Math", 1, 4, top=15, size=8),
        _glyph(3, "y", "/Math", 0, 0, line=1, top=19, size=13),
        _glyph(4, "j", "/Math", 1, 4, line=1, top=24, size=7),
    ]

    assert _texts(glyphs) == ["xi", "yj"]


def test_fusionne_une_petite_borne_portant_son_propre_indice() -> None:
    glyphs = [
        _glyph(1, "f", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "S", "/Math", 1, 3, line=1, top=5, size=7),
        _glyph(3, "i", "/Math", 1, 6, line=1, top=7, size=6),
    ]

    assert _texts(glyphs) == ["fSi"]


def test_ignore_les_hauts_de_boite_differents_sur_une_meme_ligne_de_base() -> None:
    glyphs = [
        _glyph(1, "f", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "x", "/Math", 0, 4, top=12, size=10),
        _glyph(3, "S", "/Math", 1, 3, line=1, top=5, size=7),
        _glyph(4, "i", "/Math", 1, 7, line=1, top=6, size=7),
    ]
    glyphs[1]["rendered_origin_y"] = 20
    glyphs[3]["rendered_origin_y"] = 12

    assert _texts(glyphs) == ["fxSi"]


def test_fusionne_les_bornes_superposees_d_un_operateur_mathématique() -> None:
    glyphs = [
        _glyph(1, "√", "/Math", 0, 0, top=10, size=10),
        _glyph(2, "∑", "/Math", 0, 5, top=10, size=10),
        _glyph(3, "D", "/Math", 1, 10, top=7, size=7),
        _glyph(4, "j=1", "/Math", 0, 10, line=1, top=14, size=7),
        _glyph(5, "(w(j))2", "/Math", 1, 22, line=1, top=11, size=10),
    ]
    glyphs[0]["glyph_name"] = "radicalBig"
    glyphs[1]["glyph_name"] = "summationtext"

    assert _texts(glyphs) == ["√∑Dj=1(w(j))2"]


def test_fusionne_le_numerateur_et_le_denominateur_par_la_barre_de_fraction() -> None:
    glyphs = [
        _glyph(1, "2", "/Body", 0, 5, top=5, size=7),
        _glyph(2, "‖", "/Math", 1, 0, line=1, top=18, size=7),
        _glyph(3, "w", "/VariableBold", 2, 4, line=1, top=18, size=7),
        _glyph(4, "‖", "/Math", 3, 9, line=1, top=18, size=7),
    ]
    rules = {1: [{"x0": 0.0, "y": 14.0, "x1": 13.0, "width": 0.4, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert [region["source_glyph_text"] for region in regions] == ["2‖w‖"]
    assert regions[0]["structural_rules"]["fraction"]["seqno"] == 2


def test_ne_transforme_pas_deux_mots_italiques_en_fraction() -> None:
    glyphs = [
        _glyph(1, "where", "/EmphasisItalic", 0, 5, top=5, size=7),
        _glyph(2, "value", "/EmphasisItalic", 1, 5, line=1, top=18, size=7),
    ]
    rules = {1: [{"x0": 4.0, "y": 14.0, "x1": 10.0, "width": 0.4, "seqno": 2}]}

    assert source_math_regions(glyphs, FONTS, rules) == []


def test_ne_transforme_pas_deux_mots_italiques_courts_en_fraction() -> None:
    glyphs = [
        _glyph(1, "is", "/EmphasisItalic", 0, 5, top=5, size=7),
        _glyph(2, "it", "/EmphasisItalic", 1, 5, line=1, top=18, size=7),
    ]
    rules = {1: [{"x0": 4.0, "y": 14.0, "x1": 10.0, "width": 0.4, "seqno": 2}]}

    assert source_math_regions(glyphs, FONTS, rules) == []


def test_ne_prend_pas_une_virgule_terminale_pour_une_liste_de_variables() -> None:
    glyphs = [
        _glyph(1, "is,", "/EmphasisItalic", 0, 5, top=5, size=7),
        _glyph(2, "it,", "/EmphasisItalic", 1, 5, line=1, top=18, size=7),
    ]
    rules = {1: [{"x0": 4.0, "y": 14.0, "x1": 10.0, "width": 0.4, "seqno": 2}]}

    assert source_math_regions(glyphs, FONTS, rules) == []


def test_conserve_une_fraction_de_variables_italiques_contextuelles() -> None:
    glyphs = [
        _glyph(1, "x", "/VariableItalic", 0, 5, top=5, size=7),
        _glyph(2, "y", "/VariableItalic", 1, 5, line=1, top=18, size=7),
    ]
    rules = {1: [{"x0": 4.0, "y": 14.0, "x1": 10.0, "width": 0.4, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert [region["source_glyph_text"] for region in regions] == ["xy"]
    assert regions[0]["structural_rules"]["fraction"]["seqno"] == 2


def test_fusionne_une_fraction_inseree_et_une_somme_avec_sa_borne() -> None:
    glyphs = [
        _glyph(1, "a", "/Math", 0, 0, top=10),
        _glyph(2, "=", "/Math", 1, 5, top=10),
        _glyph(3, "1", "/Body", 2, 20, top=5, size=7),
        _glyph(4, "2", "/Body", 3, 20, line=1, top=18, size=7),
        _glyph(5, "∑", "/Math", 4, 30, line=2, top=10, size=14),
        _glyph(6, "i", "/Math", 5, 28, line=3, top=25, size=7),
        _glyph(7, "=", "/Math", 6, 31, line=3, top=25, size=7),
        _glyph(8, "1", "/Body", 7, 34, line=3, top=25, size=7),
        _glyph(9, "y", "/Math", 8, 40, line=4, top=14),
    ]
    glyphs[4]["glyph_name"] = "summationdisplay"
    rules = {1: [{"x0": 20.0, "y": 14.0, "x1": 24.0, "width": 0.4, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert len(regions) == 1
    assert regions[0]["glyph_sequence_indices"] == list(range(1, 10))
    assert regions[0]["structural_rules"]["fraction"]["seqno"] == 2


def test_ne_prouve_pas_une_fraction_par_une_barre_trop_courte() -> None:
    glyphs = [
        _glyph(1, "2", "/Body", 0, 0, top=5, size=4),
        _glyph(2, "w", "/VariableBold", 1, 0, line=1, top=11, size=4),
    ]
    rules = {1: [{"x0": 1.9, "y": 10.0, "x1": 2.1, "width": 0.1, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert all("fraction" not in region["structural_rules"] for region in regions)


def test_adapte_la_couverture_de_fraction_aux_glyphes_tres_petits() -> None:
    glyphs = [
        _glyph(1, "x", "/Math", 0, 0.1, top=0, size=1),
        _glyph(2, "y", "/Math", 1, 0.1, line=1, top=2, size=1),
    ]
    for glyph in glyphs:
        glyph["bbox"][2] = 0.9
    rules = {1: [{"x0": 0.45, "y": 1.5, "x1": 0.55, "width": 0.1, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert all("fraction" not in region["structural_rules"] for region in regions)


def test_ne_prouve_pas_une_fraction_par_un_separateur_trop_long() -> None:
    glyphs = [
        _glyph(1, "x", "/Math", 0, 48, top=0, size=4),
        _glyph(2, "y", "/Math", 1, 48, line=1, top=6, size=4),
    ]
    rules = {1: [{"x0": 0.0, "y": 5.0, "x1": 100.0, "width": 0.1, "seqno": 2}]}

    regions = source_math_regions(glyphs, FONTS, rules)

    assert all("fraction" not in region["structural_rules"] for region in regions)


def test_conserve_un_identifiant_de_fonction_entre_operateur_et_parenthese() -> None:
    glyphs = [
        _glyph(1, "y", "/Math", 0, 0),
        _glyph(2, "=", "/Body", 1, 4),
        _glyph(3, "sign", "/Body", 1, 8),
        _glyph(4, "(", "/Body", 1, 24),
        _glyph(5, "w", "/VariableBold", 2, 28),
        _glyph(6, "−", "/Math", 3, 32),
        _glyph(7, "b", "/Math", 4, 36),
        _glyph(8, ")", "/Body", 5, 40),
    ]

    assert _texts(glyphs) == ["y=sign(w−b)"]


def test_elimine_la_ponctuation_narrative_aux_deux_extremites() -> None:
    glyphs = [
        _glyph(1, ",", "/Body", 0, 0),
        _glyph(2, "−", "/Math", 1, 4),
        _glyph(3, "1", "/Body", 2, 8),
        _glyph(4, ".", "/Body", 3, 12),
    ]

    assert _texts(glyphs) == ["−1"]


def test_elimine_une_parenthese_ouvrante_sans_fermeture() -> None:
    glyphs = [
        _glyph(1, "(", "/Body", 0, 0),
        _glyph(2, "+", "/Math", 1, 4),
        _glyph(3, "1", "/Body", 2, 8),
    ]

    assert _texts(glyphs) == ["+1"]


def test_ne_depend_pas_d_un_decoupage_en_spans_pour_separer_la_prose() -> None:
    glyphs = [
        _glyph(index, character, "/Body", 0, index * 4)
        for index, character in enumerate("x≥1becausey=1", start=1)
    ]

    assert _texts(glyphs) == ["x≥1", "y=1"]
