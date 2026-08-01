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
    return [region["source_glyph_text"] for region in source_math_regions(glyphs, FONTS)]


def test_detecte_les_variables_grasses_courtes_et_ignore_un_mot_gras() -> None:
    glyphs = [
        _glyph(1, "w", "/VariableBold", 0, 0),
        _glyph(2, "x", "/VariableBold", 0, 4),
        _glyph(3, "prose", "/Body", 2, 14),
        _glyph(4, "feature", "/EmphasisBold", 4, 40),
        _glyph(5, "is", "/EmphasisBold", 6, 72),
    ]

    assert _texts(glyphs) == ["wx"]


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


def test_ne_fusionne_pas_deux_expressions_de_meme_taille_sur_deux_lignes() -> None:
    glyphs = [
        _glyph(1, "x=1", "/Math", 0, 0, top=10),
        _glyph(2, "y=1", "/Math", 0, 0, line=1, top=19),
    ]

    assert _texts(glyphs) == ["x=1", "y=1"]


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
